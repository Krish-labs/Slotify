from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.resource import Resource
from app.database.models.section import Section
from app.database.models.time_slot import TimeSlot
from app.database.models.timetable import Timetable
from app.database.models.timetable_entry import TimetableEntry
from app.database.models.timetable_version import TimetableVersion
from app.exporters.change_history_exporter import ChangeHistoryExporter
from app.exporters.class_timetable_exporter import ClassTimetableExporter
from app.exporters.faculty_timetable_exporter import FacultyTimetableExporter
from app.exporters.master_timetable_exporter import MasterTimetableExporter
from app.exporters.resource_allocation_exporter import ResourceAllocationExporter
from app.validators.timetable_validator import TimetableValidator


class TimetableService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self):
        result = await self.db.execute(select(Timetable).where(Timetable.status != "ARCHIVED"))
        timetables = result.scalars().all()
        return [
            {
                "id": str(t.id),
                "name": t.name,
                "academic_year": t.academic_year,
                "semester": t.semester,
                "status": t.status,
            }
            for t in timetables
        ]

    async def get_by_id(self, timetable_id: UUID):
        timetable = await self.db.get(Timetable, timetable_id)
        if not timetable:
            return None
        return {
            "id": str(timetable.id),
            "name": timetable.name,
            "template_id": str(timetable.template_id),
            "academic_year": timetable.academic_year,
            "semester": timetable.semester,
            "status": timetable.status,
            "generated_by": str(timetable.generated_by) if timetable.generated_by else None,
            "approved_by": str(timetable.approved_by) if timetable.approved_by else None,
        }

    async def create(self, data: dict):
        timetable = Timetable(**data)
        self.db.add(timetable)
        await self.db.flush()
        return timetable

    async def generate(self, timetable_id: UUID, requested_by: UUID | None = None):
        # Local import: workers depend on services, so importing the worker at
        # module level would create a cycle (runner -> timetable_worker ->
        # services.__init__ -> timetable_service -> timetable_worker).
        from app.workers.timetable_worker import TimetableWorker

        worker = TimetableWorker()
        return await worker.generate_timetable(timetable_id, requested_by)

    async def validate(self, timetable_id: UUID):
        timetable = await self.db.get(Timetable, timetable_id)
        if not timetable:
            return {"error": "Timetable not found"}

        latest_version = (
            await self.db.execute(
                select(TimetableVersion)
                .where(TimetableVersion.timetable_id == timetable.id)
                .order_by(TimetableVersion.version_number.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if not latest_version:
            return {
                "status": "FAIL",
                "errors": ["No version found for this timetable"],
                "warnings": [],
                "violations": {},
            }

        entries = (
            (
                await self.db.execute(
                    select(TimetableEntry).where(TimetableEntry.version_id == latest_version.id)
                )
            )
            .scalars()
            .all()
        )

        entries_dict = [
            {
                "id": e.id,
                "assignment_id": str(e.assignment_id) if e.assignment_id else None,
                "faculty_id": str(e.faculty_id) if e.faculty_id else None,
                "subject_id": str(e.subject_id) if e.subject_id else None,
                "section_id": str(e.section_id) if e.section_id else None,
                "batch_id": str(e.batch_id) if e.batch_id else None,
                "resource_id": str(e.resource_id) if e.resource_id else None,
                "time_slot_id": str(e.time_slot_id) if e.time_slot_id else None,
                "day_of_week": e.day_of_week,
                "period_number": e.period_number,
                "session_type": e.session_type,
            }
            for e in entries
        ]

        validator = TimetableValidator()
        validation = validator.validate(entries_dict, required_hours={})

        status = "PASS" if validation.is_valid else "FAIL" if validation.errors else "WARNING"
        return {
            "status": status,
            "errors": validation.errors,
            "warnings": validation.warnings,
            "violations": dict(validation.violations),
        }

    async def reoptimize(self, timetable_id: UUID, change_data: dict):
        # Local import for the same cycle reason as generate() above.
        from app.workers.timetable_worker import TimetableWorker

        worker = TimetableWorker()
        return await worker.reoptimize_timetable(timetable_id, change_data)

    async def export_class(self, timetable_id: UUID) -> str:
        timetable = await self.db.get(Timetable, timetable_id)
        if not timetable:
            raise ValueError("Timetable not found")

        latest_version = (
            await self.db.execute(
                select(TimetableVersion)
                .where(TimetableVersion.timetable_id == timetable.id)
                .filter(TimetableVersion.status == "VALIDATED")
                .order_by(TimetableVersion.version_number.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if not latest_version:
            raise ValueError("No validated version found for this timetable")

        entries = await self._get_version_entries(latest_version.id)
        sections = await self._get_sections_dict(entries)
        time_slots = await self._get_time_slots_dict(entries)
        resources = await self._get_resources_dict(entries)

        exporter = ClassTimetableExporter()
        output_path = f"/tmp/export_class_{timetable_id}.xlsx"
        exporter.export(entries, sections, time_slots, resources, output_path)
        return output_path

    async def export_faculty(self, timetable_id: UUID) -> str:
        timetable = await self.db.get(Timetable, timetable_id)
        if not timetable:
            raise ValueError("Timetable not found")

        latest_version = (
            await self.db.execute(
                select(TimetableVersion)
                .where(TimetableVersion.timetable_id == timetable.id)
                .filter(TimetableVersion.status == "VALIDATED")
                .order_by(TimetableVersion.version_number.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if not latest_version:
            raise ValueError("No validated version found for this timetable")

        entries = await self._get_version_entries(latest_version.id)
        faculty = await self._get_faculty_dict(entries)
        time_slots = await self._get_time_slots_dict(entries)
        resources = await self._get_resources_dict(entries)

        exporter = FacultyTimetableExporter()
        output_path = f"/tmp/export_faculty_{timetable_id}.xlsx"
        exporter.export(entries, faculty, time_slots, resources, output_path)
        return output_path

    async def export_master(self, timetable_id: UUID) -> str:
        timetable = await self.db.get(Timetable, timetable_id)
        if not timetable:
            raise ValueError("Timetable not found")

        latest_version = (
            await self.db.execute(
                select(TimetableVersion)
                .where(TimetableVersion.timetable_id == timetable.id)
                .filter(TimetableVersion.status == "VALIDATED")
                .order_by(TimetableVersion.version_number.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if not latest_version:
            raise ValueError("No validated version found for this timetable")

        entries = await self._get_version_entries(latest_version.id)
        resources = await self._get_resources_dict(entries)
        time_slots = await self._get_time_slots_dict(entries)
        sections = await self._get_sections_dict(entries)
        faculty = await self._get_faculty_dict(entries)

        exporter = MasterTimetableExporter()
        output_path = f"/tmp/export_master_{timetable_id}.xlsx"
        exporter.export(entries, resources, time_slots, sections, faculty, output_path)
        return output_path

    async def export_resource_allocation(self, timetable_id: UUID) -> str:
        timetable = await self.db.get(Timetable, timetable_id)
        if not timetable:
            raise ValueError("Timetable not found")

        latest_version = (
            await self.db.execute(
                select(TimetableVersion)
                .where(TimetableVersion.timetable_id == timetable.id)
                .filter(TimetableVersion.status == "VALIDATED")
                .order_by(TimetableVersion.version_number.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if not latest_version:
            raise ValueError("No validated version found for this timetable")

        entries = await self._get_version_entries(latest_version.id)
        resources = await self._get_resources_dict(entries)
        time_slots = await self._get_time_slots_dict(entries)

        exporter = ResourceAllocationExporter()
        output_path = f"/tmp/export_resource_allocation_{timetable_id}.xlsx"
        exporter.export(entries, resources, time_slots, output_path)
        return output_path

    async def export_change_history(self, timetable_id: UUID) -> str:
        timetable = await self.db.get(Timetable, timetable_id)
        if not timetable:
            raise ValueError("Timetable not found")

        versions = (
            (
                await self.db.execute(
                    select(TimetableVersion)
                    .where(TimetableVersion.timetable_id == timetable.id)
                    .order_by(TimetableVersion.version_number.desc())
                )
            )
            .scalars()
            .all()
        )

        exporter = ChangeHistoryExporter()
        output_path = f"/tmp/export_change_history_{timetable_id}.xlsx"
        exporter.export(versions, output_path)
        return output_path

    async def export_validation_report(self, timetable_id: UUID) -> str:
        validation = await self.validate(timetable_id)
        from app.exporters.validation_report_exporter import ValidationReportExporter

        exporter = ValidationReportExporter()
        output_path = f"/tmp/export_validation_{timetable_id}.xlsx"
        exporter.export(validation, output_path)
        return output_path

    async def _get_version_entries(self, version_id: UUID) -> list[dict]:
        result = await self.db.execute(
            select(TimetableEntry).where(TimetableEntry.version_id == version_id)
        )
        entries = result.scalars().all()
        return [
            {
                "id": e.id,
                "assignment_id": str(e.assignment_id) if e.assignment_id else None,
                "faculty_id": str(e.faculty_id),
                "subject_id": str(e.subject_id),
                "section_id": str(e.section_id),
                "batch_id": str(e.batch_id) if e.batch_id else None,
                "resource_id": str(e.resource_id),
                "time_slot_id": str(e.time_slot_id),
                "day_of_week": e.day_of_week,
                "period_number": e.period_number,
                "session_type": e.session_type,
                "subject_name": e.subject.name if e.subject else "",
                "faculty_name": (
                    f"{e.faculty.first_name} {e.faculty.last_name}" if e.faculty else ""
                ),
                "section_name": e.section.name if e.section else "",
            }
            for e in entries
        ]

    async def _get_sections_dict(self, entries: list[dict]) -> dict:
        section_ids = {e["section_id"] for e in entries}
        result = await self.db.execute(select(Section).where(Section.id.in_(section_ids)))
        return {s.id: {"name": s.name} for s in result.scalars().all()}

    async def _get_time_slots_dict(self, entries: list[dict]) -> dict:
        time_slot_ids = {e["time_slot_id"] for e in entries}
        result = await self.db.execute(select(TimeSlot).where(TimeSlot.id.in_(time_slot_ids)))
        return {
            t.id: {
                "day_of_week": t.day_of_week,
                "period_number": t.period_number,
                "start_time": t.start_time,
                "end_time": t.end_time,
            }
            for t in result.scalars().all()
        }

    async def _get_resources_dict(self, entries: list[dict]) -> dict:
        resource_ids = {e["resource_id"] for e in entries}
        result = await self.db.execute(select(Resource).where(Resource.id.in_(resource_ids)))
        return {
            r.id: {"name": r.name, "resource_type": r.resource_type} for r in result.scalars().all()
        }

    async def _get_faculty_dict(self, entries: list[dict]) -> dict:
        faculty_ids = {e["faculty_id"] for e in entries}
        from app.database.models.faculty import Faculty

        result = await self.db.execute(select(Faculty).where(Faculty.id.in_(faculty_ids)))
        return {
            f.id: {"first_name": f.first_name, "last_name": f.last_name}
            for f in result.scalars().all()
        }
