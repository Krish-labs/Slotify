from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.timetable_entry import TimetableEntry
from app.database.models.timetable_version import TimetableVersion

ENTRY_FIELDS = (
    "assignment_id",
    "faculty_id",
    "subject_id",
    "section_id",
    "batch_id",
    "resource_id",
    "time_slot_id",
    "day_of_week",
    "period_number",
    "session_type",
    # Scheduling metadata so approval/publish-time validation equals
    # generation-time validation (see TimetableEntry columns).
    "session_duration",
    "section_strength",
    "batch_strength",
)


class VersionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_version(
        self, timetable_id: UUID, change_data: dict, created_by: UUID
    ) -> TimetableVersion:
        """Persist a new version and its entries in the caller's transaction.

        This service MUST NOT commit: transaction ownership belongs to the use
        case (see app/database/transactions.py). The caller wraps the whole use
        case (version + entries + audit + notification) in one
        ``transaction(db)`` and allocates the version number under the
        per-timetable advisory lock.

        ``change_data`` keys: ``entries`` (dicts with ``ENTRY_FIELDS``), and
        optionally ``change_type``, ``change_summary``, ``status``.
        """
        latest = (
            await self.db.execute(
                select(TimetableVersion)
                .where(TimetableVersion.timetable_id == timetable_id)
                .order_by(TimetableVersion.version_number.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        version = TimetableVersion(
            timetable_id=timetable_id,
            version_number=latest.version_number + 1 if latest else 1,
            parent_version_id=latest.id if latest else None,
            change_type=change_data.get("change_type"),
            change_summary=change_data.get("change_summary"),
            status=change_data.get("status", "PENDING"),
            created_by=created_by,
        )
        self.db.add(version)
        await self.db.flush()

        for entry in change_data.get("entries", []):
            self.db.add(
                TimetableEntry(
                    version_id=version.id,
                    **{field: entry.get(field) for field in ENTRY_FIELDS},
                )
            )

        return version

    async def get_versions(self, timetable_id: UUID) -> list[dict]:
        """Return a list of version summaries for the given timetable."""
        versions = (
            (
                await self.db.execute(
                    select(TimetableVersion)
                    .where(TimetableVersion.timetable_id == timetable_id)
                    .order_by(TimetableVersion.version_number.desc())
                )
            )
            .scalars()
            .all()
        )

        return [
            {
                "id": str(v.id),
                "version_number": v.version_number,
                "parent_version_id": str(v.parent_version_id) if v.parent_version_id else None,
                "change_type": v.change_type,
                "status": v.status,
                "created_by": str(v.created_by) if v.created_by else None,
                "change_summary": v.change_summary,
            }
            for v in versions
        ]

    async def get_version(self, timetable_id: UUID, version_id: UUID) -> dict | None:
        """Return a version detail dict, or None if not found."""
        version = (
            await self.db.execute(
                select(TimetableVersion).where(
                    TimetableVersion.timetable_id == timetable_id,
                    TimetableVersion.id == version_id,
                )
            )
        ).scalar_one_or_none()

        if not version:
            return None

        # Fetch entries for this version
        entries = (
            (
                await self.db.execute(
                    select(TimetableEntry).where(TimetableEntry.version_id == version.id)
                )
            )
            .scalars()
            .all()
        )

        return {
            "id": str(version.id),
            "timetable_id": str(version.timetable_id),
            "version_number": version.version_number,
            "parent_version_id": (
                str(version.parent_version_id) if version.parent_version_id else None
            ),
            "change_type": version.change_type,
            "status": version.status,
            "change_summary": version.change_summary,
            "created_by": str(version.created_by) if version.created_by else None,
            "entries": [
                {
                    "id": e.id,
                    "faculty_id": str(e.faculty_id) if e.faculty_id else None,
                    "subject_id": str(e.subject_id) if e.subject_id else None,
                    "section_id": str(e.section_id) if e.section_id else None,
                    "batch_id": str(e.batch_id) if e.batch_id else None,
                    "resource_id": str(e.resource_id) if e.resource_id else None,
                    "time_slot_id": str(e.time_slot_id) if e.time_slot_id else None,
                    "day_of_week": e.day_of_week,
                    "session_type": e.session_type,
                }
                for e in entries
            ],
        }
