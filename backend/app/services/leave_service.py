from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models.audit_log import AuditLog
from app.database.models.faculty import Faculty
from app.database.models.leave import Leave
from app.database.models.substitution import Substitution
from app.database.models.timetable_entry import TimetableEntry
from app.database.models.timetable_version import TimetableVersion
from app.services.notification_service import NotificationService
from app.services.version_service import VersionService


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _serialize_for_audit(data: dict) -> dict:
    """Serialize UUID/date/datetime objects for JSON audit storage."""
    from datetime import date, datetime

    result: dict = {}
    for k, v in data.items():
        if isinstance(v, (date, datetime)):
            result[k] = v.isoformat()
        elif isinstance(v, UUID):
            result[k] = str(v)
        elif v is None:
            result[k] = None
        else:
            result[k] = v
    return result


# Fields a client is allowed to supply. Status/approval columns and ids are
# lifecycle-owned: clients must reach them only through approve/reject/cancel.
_LEAVE_CREATE_FIELDS = (
    "faculty_id",
    "leave_type",
    "start_date",
    "end_date",
    "start_time",
    "end_time",
    "reason",
)
_LEAVE_UPDATE_FIELDS = (
    "leave_type",
    "start_date",
    "end_date",
    "start_time",
    "end_time",
    "reason",
)
_SUBSTITUTION_CREATE_FIELDS = (
    "leave_id",
    "timetable_id",
    "original_faculty_id",
    "substitute_faculty_id",
    "subject_id",
    "section_id",
    "batch_id",
    "date",
    "time_slot_id",
)
_SUBSTITUTION_UPDATE_FIELDS = (
    "leave_id",
    "timetable_id",
    "substitute_faculty_id",
    "subject_id",
    "section_id",
    "batch_id",
    "date",
    "time_slot_id",
)


def _payload(data: dict, allowed: tuple[str, ...]) -> dict:
    return {key: data[key] for key in allowed if key in data}


def _snapshot(model, fields: tuple[str, ...]) -> dict:
    return _serialize_for_audit({key: getattr(model, key) for key in fields})


class LeaveService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, status: str | None = None, faculty_id: UUID | None = None):
        query = select(Leave).options(selectinload(Leave.substitutions))
        conditions = []
        if status:
            conditions.append(Leave.status == status)
        if faculty_id:
            conditions.append(Leave.faculty_id == faculty_id)
        if conditions:
            query = query.where(and_(*conditions))
        query = query.order_by(Leave.start_date.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_by_id(self, leave_id: UUID) -> Leave | None:
        result = await self.db.execute(
            select(Leave).options(selectinload(Leave.substitutions)).where(Leave.id == leave_id)
        )
        return result.scalar_one_or_none()

    async def create(self, data: dict, actor_id: UUID | None = None) -> Leave:
        payload = _payload(data, _LEAVE_CREATE_FIELDS)
        leave = Leave(**payload, status="PENDING")
        self.db.add(leave)
        await self.db.flush()
        self.db.add(
            AuditLog(
                user_id=actor_id,
                action="CREATE",
                entity_type="LEAVE",
                entity_id=leave.id,
                old_values={},
                new_values=_serialize_for_audit(payload | {"status": "PENDING"}),
            )
        )
        return leave

    async def update(
        self, leave_id: UUID, data: dict, actor_id: UUID | None = None
    ) -> Leave | None:
        leave = await self.get_by_id(leave_id)
        if not leave:
            return None
        if leave.status != "PENDING":
            raise ValueError(f"Cannot edit leave in status: {leave.status}")
        payload = _payload(data, _LEAVE_UPDATE_FIELDS)
        if not payload:
            return leave
        old_values = _snapshot(leave, tuple(payload))
        for key, value in payload.items():
            setattr(leave, key, value)
        await self.db.flush()
        self.db.add(
            AuditLog(
                user_id=actor_id,
                action="UPDATE",
                entity_type="LEAVE",
                entity_id=leave.id,
                old_values=old_values,
                new_values=_snapshot(leave, tuple(payload)),
            )
        )
        return leave

    async def delete(self, leave_id: UUID, actor_id: UUID | None = None) -> bool:
        leave = await self.get_by_id(leave_id)
        if not leave:
            return False
        snapshot = _serialize_for_audit(
            {key: getattr(leave, key) for key in _LEAVE_CREATE_FIELDS}
        ) | {"status": leave.status}
        await self.db.delete(leave)
        await self.db.flush()
        self.db.add(
            AuditLog(
                user_id=actor_id,
                action="DELETE",
                entity_type="LEAVE",
                entity_id=leave_id,
                old_values=snapshot,
                new_values={},
            )
        )
        return True

    async def approve(self, leave_id: UUID, approver_id: UUID) -> Leave | None:
        leave = await self.get_by_id(leave_id)
        if not leave:
            return None
        if leave.status != "PENDING":
            raise ValueError(f"Cannot approve leave in status: {leave.status}")

        old_values = {
            "status": leave.status,
            "approved_by": str(leave.approved_by) if leave.approved_by else None,
            "approved_at": leave.approved_at.isoformat() if leave.approved_at else None,
        }
        leave.status = "APPROVED"
        leave.approved_by = approver_id
        leave.approved_at = _now_utc()
        await self.db.flush()

        new_values = {
            "status": leave.status,
            "approved_by": str(leave.approved_by),
            "approved_at": leave.approved_at.isoformat(),
        }
        self.db.add(
            AuditLog(
                user_id=approver_id,
                action="APPROVE",
                entity_type="LEAVE",
                entity_id=leave.id,
                old_values=old_values,
                new_values=new_values,
            )
        )

        await self._create_substitutions_for_leave(leave)
        await self._notify_affected_users(leave, "APPROVED")

        return leave

    async def reject(self, leave_id: UUID, approver_id: UUID) -> Leave | None:
        leave = await self.get_by_id(leave_id)
        if not leave:
            return None
        if leave.status != "PENDING":
            raise ValueError(f"Cannot reject leave in status: {leave.status}")

        old_values = {
            "status": leave.status,
            "approved_by": str(leave.approved_by) if leave.approved_by else None,
            "approved_at": leave.approved_at.isoformat() if leave.approved_at else None,
        }
        leave.status = "REJECTED"
        leave.approved_by = approver_id
        leave.approved_at = _now_utc()
        await self.db.flush()

        new_values = {
            "status": leave.status,
            "approved_by": str(leave.approved_by),
            "approved_at": leave.approved_at.isoformat(),
        }
        self.db.add(
            AuditLog(
                user_id=approver_id,
                action="REJECT",
                entity_type="LEAVE",
                entity_id=leave.id,
                old_values=old_values,
                new_values=new_values,
            )
        )

        await self._notify_affected_users(leave, "REJECTED")
        return leave

    async def cancel(self, leave_id: UUID, cancelled_by: UUID | None = None) -> Leave | None:
        leave = await self.get_by_id(leave_id)
        if not leave:
            return None
        if leave.status not in ("PENDING", "APPROVED"):
            raise ValueError(f"Cannot cancel leave in status: {leave.status}")

        old_values = {
            "status": leave.status,
            "approved_by": str(leave.approved_by) if leave.approved_by else None,
            "approved_at": leave.approved_at.isoformat() if leave.approved_at else None,
        }
        leave.status = "CANCELLED"
        await self.db.flush()

        new_values = {
            "status": leave.status,
        }
        if cancelled_by is not None:
            self.db.add(
                AuditLog(
                    user_id=cancelled_by,
                    action="CANCEL",
                    entity_type="LEAVE",
                    entity_id=leave.id,
                    old_values=old_values,
                    new_values=new_values,
                )
            )

        await self._cancel_substitutions(leave)
        await self._notify_affected_users(leave, "CANCELLED")
        return leave

    async def _create_substitutions_for_leave(self, leave: Leave):
        """Find affected timetable entries and create substitution records."""
        if leave.start_time and leave.end_time:
            date_filter = and_(
                TimetableEntry.day_of_week.in_(
                    self._get_days_in_range(leave.start_date, leave.end_date)
                )
            )
        else:
            date_filter = TimetableEntry.day_of_week.in_(
                self._get_days_in_range(leave.start_date, leave.end_date)
            )

        result = await self.db.execute(
            select(TimetableEntry)
            .join(TimetableVersion, TimetableEntry.version_id == TimetableVersion.id)
            .where(
                TimetableVersion.status.in_(("VALIDATED", "APPROVED", "PUBLISHED")),
                TimetableEntry.faculty_id == leave.faculty_id,
                date_filter,
            )
            .options(
                selectinload(TimetableEntry.version),
                selectinload(TimetableEntry.faculty),
            )
        )
        affected_entries = result.scalars().all()

        # Keep only the newest live version of each timetable: several live
        # versions may coexist (generate, reoptimize, substitution), and a
        # superseded one must never decide who covers a class.
        newest: dict[UUID, TimetableVersion] = {}
        for entry in affected_entries:
            version = entry.version
            if version is None or version.timetable_id is None:
                continue
            current = newest.get(version.timetable_id)
            if current is None or version.version_number > current.version_number:
                newest[version.timetable_id] = version

        seen: set[tuple[UUID, UUID, date]] = set()
        for entry in affected_entries:
            version = entry.version
            if version is None or version.timetable_id is None:
                continue
            if newest[version.timetable_id].id != version.id:
                continue
            substitute = await self._find_eligible_substitute(entry, leave)
            if not substitute:
                continue
            for day in self._days_in_range(leave.start_date, leave.end_date):
                if day.weekday() != entry.day_of_week:
                    continue
                key = (version.timetable_id, entry.time_slot_id, day)
                if key in seen:
                    continue
                seen.add(key)
                self.db.add(
                    Substitution(
                        leave_id=leave.id,
                        timetable_id=version.timetable_id,
                        original_faculty_id=leave.faculty_id,
                        substitute_faculty_id=substitute.id,
                        subject_id=entry.subject_id,
                        section_id=entry.section_id,
                        batch_id=entry.batch_id,
                        date=day,
                        time_slot_id=entry.time_slot_id,
                        status="PENDING",
                    )
                )

        await self.db.flush()

    def _days_in_range(self, start: date, end: date) -> list[date]:
        """Every calendar date from start to end inclusive."""
        return [start + timedelta(days=i) for i in range((end - start).days + 1)]

    def _get_days_in_range(self, start: date, end: date) -> list[int]:
        """Return list of day_of_week integers (0=Monday) for date range."""
        return [d.weekday() for d in self._days_in_range(start, end)]

    async def _find_eligible_substitute(
        self, entry: TimetableEntry, leave: Leave
    ) -> Faculty | None:
        result = await self.db.execute(
            select(Faculty)
            .where(
                Faculty.id != leave.faculty_id,
                Faculty.is_active.is_(True),
                Faculty.is_archived.is_(False),
                Faculty.department == entry.faculty.department,
            )
            .options(selectinload(Faculty.assignments))
        )
        candidates = result.scalars().all()

        for candidate in candidates:
            if await self._is_faculty_available(
                candidate, leave.start_date, leave.end_date, entry.time_slot_id
            ):
                has_assignment = any(
                    a.subject_id == entry.subject_id and a.is_active for a in candidate.assignments
                )
                if has_assignment:
                    return candidate
        return None

    async def _is_faculty_available(
        self, faculty, start_date: date, end_date: date, time_slot_id: UUID
    ) -> bool:
        from app.database.models.leave import Leave as LeaveModel
        from app.database.models.substitution import Substitution as SubModel

        leave_conflict = await self.db.execute(
            select(LeaveModel).where(
                LeaveModel.faculty_id == faculty.id,
                LeaveModel.status.in_(("PENDING", "APPROVED")),
                LeaveModel.start_date <= end_date,
                LeaveModel.end_date >= start_date,
            )
        )
        if leave_conflict.scalar_one_or_none():
            return False

        sub_conflict = await self.db.execute(
            select(SubModel).where(
                SubModel.substitute_faculty_id == faculty.id,
                SubModel.status.in_(("PENDING", "APPROVED")),
                SubModel.date >= start_date,
                SubModel.date <= end_date,
                SubModel.time_slot_id == time_slot_id,
            )
        )
        return not sub_conflict.scalar_one_or_none()

    async def _cancel_substitutions(self, leave: Leave):
        result = await self.db.execute(
            select(Substitution).where(
                Substitution.leave_id == leave.id, Substitution.status.in_(("PENDING", "APPROVED"))
            )
        )
        for sub in result.scalars().all():
            sub.status = "CANCELLED"
        await self.db.flush()

    async def _notify_affected_users(self, leave: Leave, action: str):
        from app.database.models.faculty import Faculty
        from app.database.models.substitution import Substitution as SubModel

        faculty = await self.db.get(Faculty, leave.faculty_id)
        if faculty and faculty.user_id:
            await NotificationService(self.db).send_notification(
                user_id=str(faculty.user_id),
                title=f"Leave {action}",
                message=f"Your leave request from {leave.start_date} to {leave.end_date} has been {action.lower()}.",
                type="SUCCESS" if action == "APPROVED" else "INFO",
                reference_type="LEAVE",
                reference_id=leave.id,
            )

        if not faculty:
            return

        # Re-query: substitutions created during this same request are not yet
        # in leave.substitutions, and the relationship is lazily loaded
        # (illegal in an async session).
        substitutes = (
            (
                await self.db.execute(
                    select(SubModel)
                    .options(selectinload(SubModel.substitute_faculty))
                    .where(SubModel.leave_id == leave.id)
                )
            )
            .scalars()
            .all()
        )
        for sub in substitutes:
            sub_faculty = sub.substitute_faculty
            if sub_faculty and sub_faculty.user_id:
                await NotificationService(self.db).send_notification(
                    user_id=str(sub_faculty.user_id),
                    title="Substitution Assigned",
                    message=f"You have been assigned as substitute for {faculty.first_name} {faculty.last_name} on {sub.date}.",
                    type="INFO",
                    reference_type="SUBSTITUTION",
                    reference_id=sub.id,
                )


class SubstitutionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, status: str | None = None, faculty_id: UUID | None = None):
        from app.database.models.substitution import Substitution as SubModel

        query = select(SubModel).options(
            selectinload(SubModel.original_faculty),
            selectinload(SubModel.substitute_faculty),
            selectinload(SubModel.subject),
            selectinload(SubModel.section),
        )
        conditions = []
        if status:
            conditions.append(SubModel.status == status)
        if faculty_id:
            conditions.append(SubModel.original_faculty_id == faculty_id)
        if conditions:
            query = query.where(and_(*conditions))
        query = query.order_by(SubModel.date.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_by_id(self, substitution_id: UUID) -> Substitution | None:
        from app.database.models.substitution import Substitution as SubModel

        result = await self.db.execute(
            select(SubModel)
            .options(
                selectinload(SubModel.original_faculty),
                selectinload(SubModel.substitute_faculty),
                selectinload(SubModel.subject),
                selectinload(SubModel.section),
                selectinload(SubModel.time_slot),
            )
            .where(SubModel.id == substitution_id)
        )
        return result.scalar_one_or_none()

    async def _resolve_timetable_id(self, payload: dict) -> UUID | None:
        """Find the single live timetable containing the entry being covered.

        Returns None when zero or several timetables match: guessing would
        apply the substitution to the wrong schedule.
        """
        from app.database.models.timetable_entry import TimetableEntry
        from app.database.models.timetable_version import TimetableVersion

        result = await self.db.execute(
            select(TimetableVersion.timetable_id)
            .join(TimetableEntry, TimetableEntry.version_id == TimetableVersion.id)
            .where(
                TimetableVersion.status.in_(("VALIDATED", "APPROVED", "PUBLISHED")),
                TimetableEntry.faculty_id == payload["original_faculty_id"],
                TimetableEntry.subject_id == payload["subject_id"],
                TimetableEntry.section_id == payload["section_id"],
                TimetableEntry.time_slot_id == payload["time_slot_id"],
                TimetableEntry.day_of_week == payload["date"].weekday(),
            )
            .distinct()
        )
        matches = list(result.scalars().all())
        return matches[0] if len(matches) == 1 else None

    async def create(self, data: dict, actor_id: UUID | None = None) -> "Substitution":
        from app.database.models.substitution import Substitution as SubModel

        payload = _payload(data, _SUBSTITUTION_CREATE_FIELDS)
        if data.get("class_id") is not None:
            # class_id is not persisted (class is implied by section); it is
            # checked here so a client cannot pair a class with another class's
            # section and label the substitution wrongly.
            from app.database.models.section import Section as SectionModel

            section = await self.db.get(SectionModel, payload["section_id"])
            if section is None:
                raise ValueError(f"Section with id {payload['section_id']} not found")
            if section.class_id != data["class_id"]:
                raise ValueError(
                    f"Section {payload['section_id']} does not belong to class {data['class_id']}"
                )
        if not payload.get("timetable_id"):
            payload["timetable_id"] = await self._resolve_timetable_id(payload)
        if not payload.get("timetable_id"):
            raise ValueError(
                "timetable_id could not be determined for this substitution; "
                "pass timetable_id explicitly"
            )
        sub = SubModel(**payload, status="PENDING")
        self.db.add(sub)
        await self.db.flush()
        self.db.add(
            AuditLog(
                user_id=actor_id,
                action="CREATE",
                entity_type="SUBSTITUTION",
                entity_id=sub.id,
                old_values={},
                new_values=_serialize_for_audit(payload | {"status": "PENDING"}),
            )
        )
        return sub

    async def update(
        self, substitution_id: UUID, data: dict, actor_id: UUID | None = None
    ) -> "Substitution | None":
        sub = await self.get_by_id(substitution_id)
        if not sub:
            return None
        if sub.status != "PENDING":
            raise ValueError(f"Cannot edit substitution in status: {sub.status}")
        payload = _payload(data, _SUBSTITUTION_UPDATE_FIELDS)
        if not payload:
            return sub
        old_values = _snapshot(sub, tuple(payload))
        for key, value in payload.items():
            setattr(sub, key, value)
        await self.db.flush()
        self.db.add(
            AuditLog(
                user_id=actor_id,
                action="UPDATE",
                entity_type="SUBSTITUTION",
                entity_id=sub.id,
                old_values=old_values,
                new_values=_snapshot(sub, tuple(payload)),
            )
        )
        return sub

    async def delete(self, substitution_id: UUID, actor_id: UUID | None = None) -> bool:

        sub = await self.get_by_id(substitution_id)
        if not sub:
            return False
        snapshot = _serialize_for_audit(
            {key: getattr(sub, key) for key in _SUBSTITUTION_CREATE_FIELDS}
        ) | {"status": sub.status}
        await self.db.delete(sub)
        await self.db.flush()
        self.db.add(
            AuditLog(
                user_id=actor_id,
                action="DELETE",
                entity_type="SUBSTITUTION",
                entity_id=substitution_id,
                old_values=snapshot,
                new_values={},
            )
        )
        return True

    async def approve(self, substitution_id: UUID, approver_id: UUID) -> "Substitution | None":
        sub = await self.get_by_id(substitution_id)
        if not sub:
            return None
        if sub.status != "PENDING":
            raise ValueError(f"Cannot approve substitution in status: {sub.status}")
        if sub.timetable_id is None:
            raise ValueError("Substitution has no timetable_id; cannot apply to a timetable")

        old_values = {
            "status": sub.status,
            "approved_by": str(sub.approved_by) if sub.approved_by else None,
            "approved_at": sub.approved_at.isoformat() if sub.approved_at else None,
        }
        sub.status = "APPROVED"
        sub.approved_by = approver_id
        sub.approved_at = _now_utc()
        await self.db.flush()

        new_values = {
            "status": sub.status,
            "approved_by": str(sub.approved_by),
            "approved_at": sub.approved_at.isoformat(),
        }
        self.db.add(
            AuditLog(
                user_id=approver_id,
                action="APPROVE",
                entity_type="SUBSTITUTION",
                entity_id=sub.id,
                old_values=old_values,
                new_values=new_values,
            )
        )

        await self._apply_substitution_to_timetable(sub)
        await self._notify_substitution_approval(sub, "APPROVED")
        return sub

    async def reject(self, substitution_id: UUID, approver_id: UUID) -> "Substitution | None":
        sub = await self.get_by_id(substitution_id)
        if not sub:
            return None
        if sub.status != "PENDING":
            raise ValueError(f"Cannot reject substitution in status: {sub.status}")

        old_values = {
            "status": sub.status,
            "approved_by": str(sub.approved_by) if sub.approved_by else None,
            "approved_at": sub.approved_at.isoformat() if sub.approved_at else None,
        }
        sub.status = "REJECTED"
        sub.approved_by = approver_id
        sub.approved_at = _now_utc()
        await self.db.flush()

        new_values = {
            "status": sub.status,
            "approved_by": str(sub.approved_by),
            "approved_at": sub.approved_at.isoformat(),
        }
        self.db.add(
            AuditLog(
                user_id=approver_id,
                action="REJECT",
                entity_type="SUBSTITUTION",
                entity_id=sub.id,
                old_values=old_values,
                new_values=new_values,
            )
        )

        await self._notify_substitution_approval(sub, "REJECTED")
        return sub

    async def _apply_substitution_to_timetable(self, substitution):
        """Create a new timetable version for the substitution's own timetable.

        The substitution must carry ``timetable_id`` (set at creation time) so
        approval can never fall back to a globally-latest version, which could
        target the wrong timetable on a multi-timetable database.

        Runs inside the caller's transaction; MUST NOT commit.
        """
        from app.database.models.timetable import Timetable
        from app.database.models.timetable_entry import TimetableEntry
        from app.database.models.timetable_version import TimetableVersion

        timetable = await self.db.get(Timetable, substitution.timetable_id)
        if not timetable:
            return

        from app.workers.timetable_worker import lock_timetable

        await lock_timetable(self.db, timetable.id)

        latest_version = (
            await self.db.execute(
                select(TimetableVersion)
                .where(
                    TimetableVersion.timetable_id == timetable.id,
                    TimetableVersion.status.in_(("VALIDATED", "APPROVED", "PUBLISHED")),
                )
                .order_by(TimetableVersion.version_number.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if not latest_version:
            return

        entries = (
            (
                await self.db.execute(
                    select(TimetableEntry).where(TimetableEntry.version_id == latest_version.id)
                )
            )
            .scalars()
            .all()
        )

        new_entries = []
        changed = False
        for entry in entries:
            new_entry = {
                "assignment_id": str(entry.assignment_id) if entry.assignment_id else None,
                "faculty_id": str(entry.faculty_id),
                "subject_id": str(entry.subject_id),
                "section_id": str(entry.section_id),
                "batch_id": str(entry.batch_id) if entry.batch_id else None,
                "resource_id": str(entry.resource_id),
                "time_slot_id": str(entry.time_slot_id),
                "day_of_week": entry.day_of_week,
                "period_number": entry.period_number,
                "session_type": entry.session_type,
                "is_pinned": entry.is_pinned,
            }
            if (
                entry.faculty_id == substitution.original_faculty_id
                and entry.time_slot_id == substitution.time_slot_id
                and entry.day_of_week == substitution.date.weekday()
            ):
                new_entry["faculty_id"] = str(substitution.substitute_faculty_id)
                changed = True
            new_entries.append(new_entry)

        if not changed:
            return

        await VersionService(self.db).create_version(
            timetable.id,
            {
                "change_type": "SUBSTITUTION",
                "status": "VALIDATED",
                "entries": new_entries,
                "change_summary": f"Substitution for {substitution.original_faculty_id} -> {substitution.substitute_faculty_id}",
            },
            created_by=substitution.approved_by,
        )

    async def _notify_substitution_approval(self, substitution, action: str):

        orig_faculty = substitution.original_faculty
        sub_faculty = substitution.substitute_faculty

        if orig_faculty and orig_faculty.user_id:
            await NotificationService(self.db).send_notification(
                user_id=str(orig_faculty.user_id),
                title=f"Substitution {action}",
                message=f"Your substitution on {substitution.date} has been {action.lower()}.",
                type="SUCCESS" if action == "APPROVED" else "INFO",
                reference_type="SUBSTITUTION",
                reference_id=substitution.id,
            )

        if sub_faculty and sub_faculty.user_id:
            await NotificationService(self.db).send_notification(
                user_id=str(sub_faculty.user_id),
                title=f"Substitution {action}",
                message=f"Your substitution assignment on {substitution.date} has been {action.lower()}.",
                type="SUCCESS" if action == "APPROVED" else "INFO",
                reference_type="SUBSTITUTION",
                reference_id=substitution.id,
            )
