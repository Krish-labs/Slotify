from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.timetable_entry import TimetableEntry
from app.database.models.timetable_version import TimetableVersion
from app.scheduler.reoptimizer import ImpactReport, Reoptimizer


class ImpactAnalysisService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.reoptimizer = Reoptimizer()

    async def analyze_load_change(self, load_ids: list[str]) -> ImpactReport:
        """Analyze impact of teaching assignment changes."""
        load_uuids = [UUID(lid) for lid in load_ids]
        return await self._analyze_by_assignments(load_uuids)

    async def analyze_resource_change(self, resource_ids: list[str]) -> ImpactReport:
        """Analyze impact of resource changes."""
        resource_uuids = [UUID(rid) for rid in resource_ids]
        latest_version = await self._get_latest_validated_version()
        if not latest_version:
            return ImpactReport([], [], [], [], [])

        entries = await self._get_version_entries(latest_version.id)
        change_data = {"resource_id": resource_uuids[0]} if resource_uuids else {}
        return self.reoptimizer.analyze_impact("RESOURCE_CHANGE", change_data, entries)

    async def analyze_faculty_availability_change(
        self, faculty_id: str, time_range: dict
    ) -> ImpactReport:
        """Analyze impact of faculty availability changes (leave, etc.)."""
        latest_version = await self._get_latest_validated_version()
        if not latest_version:
            return ImpactReport([], [], [], [], [])

        entries = await self._get_version_entries(latest_version.id)
        change_data = {"faculty_id": UUID(faculty_id), "time_range": time_range}
        return self.reoptimizer.analyze_impact("FACULTY_AVAILABILITY", change_data, entries)

    async def analyze_template_change(self, template_id: str) -> ImpactReport:
        """Analyze impact of timetable template changes."""
        latest_version = await self._get_latest_validated_version()
        if not latest_version:
            return ImpactReport([], [], [], [], [])

        entries = await self._get_version_entries(latest_version.id)
        change_data: dict[str, list[Any]] = {"time_slot_ids": []}
        return self.reoptimizer.analyze_impact("TEMPLATE_CHANGE", change_data, entries)

    async def analyze_leave_impact(self, leave_id: str) -> ImpactReport:
        """Analyze impact of a leave request."""
        from app.database.models.leave import Leave

        leave = await self.db.get(Leave, UUID(leave_id))
        if not leave:
            return ImpactReport([], [], [], [], [])

        latest_version = await self._get_latest_validated_version()
        if not latest_version:
            return ImpactReport([], [], [], [], [])

        entries = await self._get_version_entries(latest_version.id)
        change_data = {
            "faculty_id": leave.faculty_id,
            "date_range": {"start": leave.start_date, "end": leave.end_date},
        }
        return self.reoptimizer.analyze_impact("LEAVE", change_data, entries)

    async def get_affected_entries(self, change_type: str, change_data: dict) -> list[dict]:
        """Get timetable entries affected by a change."""
        latest_version = await self._get_latest_validated_version()
        if not latest_version:
            return []

        entries = await self._get_version_entries(latest_version.id)
        impact = self.reoptimizer.analyze_impact(change_type, change_data, entries)

        affected = [e for e in entries if e["id"] in impact.affected_entry_ids]
        return affected

    async def get_pinned_entries(self, affected_entry_ids: list[str]) -> list[dict]:
        """Get entries that should remain unchanged (pinned)."""
        latest_version = await self._get_latest_validated_version()
        if not latest_version:
            return []

        entries = await self._get_version_entries(latest_version.id)
        affected_uuids = [UUID(eid) for eid in affected_entry_ids]
        pinned = [e for e in entries if e["id"] not in affected_uuids]
        return pinned

    async def analyze_substitution_impact(self, substitution_id: str) -> ImpactReport:
        """Analyze impact of a substitution."""
        from app.database.models.substitution import Substitution

        sub = await self.db.get(Substitution, UUID(substitution_id))
        if not sub:
            return ImpactReport([], [], [], [], [])

        latest_version = await self._get_latest_validated_version()
        if not latest_version:
            return ImpactReport([], [], [], [], [])

        entries = await self._get_version_entries(latest_version.id)
        change_data = {
            "faculty_id": sub.original_faculty_id,
            "time_slot_id": sub.time_slot_id,
            "date": sub.date,
        }
        return self.reoptimizer.analyze_impact("SUBSTITUTION", change_data, entries)

    async def _get_latest_validated_version(self) -> TimetableVersion | None:
        result = await self.db.execute(
            select(TimetableVersion)
            .where(TimetableVersion.status.in_(("VALIDATED", "APPROVED", "PUBLISHED")))
            .order_by(TimetableVersion.version_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_version_entries(self, version_id: UUID) -> list[dict]:
        result = await self.db.execute(
            select(TimetableEntry).where(TimetableEntry.version_id == version_id)
        )
        entries = result.scalars().all()
        return [
            {
                "id": e.id,
                "assignment_id": e.assignment_id,
                "faculty_id": e.faculty_id,
                "subject_id": e.subject_id,
                "section_id": e.section_id,
                "batch_id": e.batch_id,
                "resource_id": e.resource_id,
                "time_slot_id": e.time_slot_id,
                "day_of_week": e.day_of_week,
                "period_number": e.period_number,
                "session_type": e.session_type,
            }
            for e in entries
        ]

    async def _analyze_by_assignments(self, assignment_ids: list[UUID]) -> ImpactReport:
        latest_version = await self._get_latest_validated_version()
        if not latest_version:
            return ImpactReport([], [], [], [], [])

        entries = await self._get_version_entries(latest_version.id)
        change_data = {"assignment_ids": [str(aid) for aid in assignment_ids]}
        return self.reoptimizer.analyze_impact("LOAD_CHANGE", change_data, entries)
