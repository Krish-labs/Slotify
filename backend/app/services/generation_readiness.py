"""Pre-generation readiness checks for the full generation workflow.

The TimetableWorker already refuses to generate when inputs are missing, but
the user only learns that *after* pressing Generate. This module runs the same
checks up front (read-only, no solving) so the UI can show mapping/validation
errors BEFORE generation:

  1. A valid academic term must exist for the timetable's (year, semester).
  2. Approved FacultyLoad records must exist for that term.
  3. TeachingAssignments must have been derived from those approved loads.
  4. Every mapping the solver needs must resolve: sections (and batches for
     batch-level loads), active resources, and active teaching time slots for
     the timetable's template.
"""

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.academic_term import AcademicTerm
from app.database.models.batch import Batch
from app.database.models.faculty_load import FacultyLoad
from app.database.models.resource import Resource
from app.database.models.section import Section
from app.database.models.teaching_assignment import TeachingAssignment
from app.database.models.time_slot import TimeSlot
from app.database.models.timetable import Timetable


@dataclass
class ReadinessReport:
    checks: list[dict] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return all(check["status"] != "FAIL" for check in self.checks)

    @property
    def errors(self) -> list[str]:
        return [c["message"] for c in self.checks if c["status"] == "FAIL"]

    @property
    def warnings(self) -> list[str]:
        return [c["message"] for c in self.checks if c["status"] == "WARNING"]

    def fail(self, check: str, message: str) -> None:
        self.checks.append({"check": check, "status": "FAIL", "message": message})

    def warn(self, check: str, message: str) -> None:
        self.checks.append({"check": check, "status": "WARNING", "message": message})

    def ok(self, check: str, message: str) -> None:
        self.checks.append({"check": check, "status": "OK", "message": message})


async def build_readiness_report(
    db: AsyncSession, timetable_id: UUID
) -> tuple[ReadinessReport | None, Timetable | None]:
    """Run every pre-generation check for one timetable.

    Returns (None, None) only when the timetable itself does not exist; in
    every other case a full report is returned (checks that cannot run because
    an earlier check failed are recorded as FAIL, not skipped silently).
    """
    report = ReadinessReport()

    timetable = await db.get(Timetable, timetable_id)
    if not timetable:
        return None, None

    term = (
        await db.execute(
            select(AcademicTerm).where(
                AcademicTerm.academic_year == timetable.academic_year,
                AcademicTerm.semester == timetable.semester,
            )
        )
    ).scalar_one_or_none()
    if not term:
        report.fail(
            "academic_term",
            f"No academic term for {timetable.academic_year} semester {timetable.semester}; "
            "create the term in Load Distribution before generating",
        )
        return report, timetable
    report.ok(
        "academic_term",
        f"Academic term: {term.name} ({term.academic_year} semester {term.semester})",
    )

    approved_loads = int(
        await db.scalar(
            select(func.count())
            .select_from(FacultyLoad)
            .where(
                FacultyLoad.academic_term_id == term.id,
                FacultyLoad.is_active.is_(True),
                FacultyLoad.is_approved.is_(True),
            )
        )
        or 0
    )
    if approved_loads == 0:
        report.fail(
            "approved_loads",
            "No approved FacultyLoad records for this term; approve mapped Load "
            "Distribution rows first",
        )
    else:
        report.ok("approved_loads", f"{approved_loads} approved FacultyLoad record(s)")

    assignments = list(
        (
            await db.execute(
                select(TeachingAssignment).where(
                    TeachingAssignment.academic_term_id == term.id,
                    TeachingAssignment.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    if not assignments:
        report.fail(
            "teaching_assignments",
            "No active TeachingAssignments derived for this term; approving Load "
            "Distribution rows derives them automatically",
        )
        return report, timetable
    report.ok("teaching_assignments", f"{len(assignments)} active TeachingAssignment(s)")

    section_ids = {a.section_id for a in assignments}
    sections = (
        (await db.execute(select(Section).where(Section.id.in_(section_ids)))).scalars().all()
    )
    missing_sections = section_ids - {s.id for s in sections}
    if missing_sections:
        report.fail(
            "section_mapping",
            f"{len(missing_sections)} assignment(s) reference missing sections",
        )
    else:
        report.ok("section_mapping", f"All {len(sections)} sections resolve")

    batch_ids = {a.batch_id for a in assignments if a.batch_id}
    if batch_ids:
        batches = (await db.execute(select(Batch).where(Batch.id.in_(batch_ids)))).scalars().all()
        missing_batches = batch_ids - {b.id for b in batches}
        if missing_batches:
            report.fail(
                "batch_mapping",
                f"{len(missing_batches)} assignment(s) reference missing batches",
            )
        else:
            report.ok("batch_mapping", f"All {len(batches)} batches resolve")

    resources = (
        (await db.execute(select(Resource).where(Resource.is_active.is_(True)))).scalars().all()
    )
    if not resources:
        report.fail("resources", "No active resources (rooms/labs); add them in Resources")
    else:
        report.ok("resources", f"{len(resources)} active resource(s)")

    time_slots = list(
        (
            await db.execute(
                select(TimeSlot).where(
                    TimeSlot.template_id == timetable.template_id,
                    TimeSlot.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    teaching_slots = [t for t in time_slots if t.slot_type == "TEACHING"]
    if not teaching_slots:
        report.fail(
            "time_slots",
            "No active TEACHING time slots for this timetable's template; add "
            "them under the template before generating",
        )
    else:
        report.ok("time_slots", f"{len(teaching_slots)} teaching time slot(s)")

    return report, timetable
