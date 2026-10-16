"""Resolve Load Distribution demand into authoritative domain records.

Resolution is deliberately conservative.  A name that cannot be matched to a
persisted faculty, subject, class, section, batch, or lab type is returned as
an unscheduled explanation.  This service never creates master data and never
uses a reference timetable cell as a schedule.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.batch import Batch
from app.database.models.class_model import Class
from app.database.models.faculty import Faculty
from app.database.models.faculty_load import FacultyLoad
from app.database.models.section import Section
from app.database.models.subject import Subject
from app.scheduler.model import SolverAssignment, SolverInput, SolverResource, SolverTimeSlot
from app.scheduler.time_slots import ALLOWED_RESOURCE_NAMES
from app.scheduler.workbook_demand import DemandParseResult, parse_workbook_demand

# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _norm(value: str | None) -> str:
    """Lowercase, strip non-alphanumeric, collapse whitespace."""
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _strip_titles(name: str) -> str:
    """Remove academic/Professional titles for cleaner matching."""
    return re.sub(r"^(mr|mrs|ms|dr|prof)\.?\s*", "", name.strip(), flags=re.I)


def _initials_set(name: str) -> set[str]:
    """Extract initials from a name string."""
    parts = _strip_titles(name).split()
    return {_norm(part)[0] for part in parts if _norm(part)}


def _faculty_norm(faculty: Faculty) -> str:
    """Normalized full name: 'firstname lastname' -> 'firstnamefirstname lastname'."""
    return _norm(f"{faculty.first_name}{faculty.last_name}")


def _resource_type(value: object | None) -> str | None:
    """Map an approved load's resource type to the solver lab type.

    Workbook scheduling reads persisted ``FacultyLoad`` rows directly, while
    the normal derivation workflow maps the same values onto
    ``TeachingAssignment.required_lab_type``. Keep the mapping identical and
    fail closed for unknown values so an unmapped practical cannot be solved
    into an arbitrary room.
    """
    raw_value = getattr(value, "value", value)
    if not isinstance(raw_value, str):
        return None
    return {
        "LAB": "HARDWARE_LAB",
        "COMPUTER_LAB": "SOFTWARE_LAB",
        "WORKSHOP": "HARDWARE_LAB",
    }.get(raw_value)


# ---------------------------------------------------------------------------
# Faculty matching
# ---------------------------------------------------------------------------


def _faculty_match(name: str, faculties: list[Faculty]) -> Faculty | None:
    """Match a source-faculty name against persisted faculty records.

    Strategy (ordered, conservative):
      1. Exact normalized full-name match (e.g. "Dr. Anjali S. Bhatlawande" -> Faculty("Anjali","Bhatlawande"))
      2. Title-stripped normalized match (e.g. "Ms.Shubhangi Gosavi" -> Faculty("Shubhangi","Gosavi"))
      3. Surname + initials disambiguation when surnames are unique
      4. Surname + initials when initials are ambiguous -> returns None (safe fallback)
      5. Unknown name -> None (safe fallback)
    """
    key = _norm(name)

    # Strategy 1: Exact normalized full-name match
    exact = [f for f in faculties if _faculty_norm(f) == key]
    if len(exact) == 1:
        return exact[0]

    # Strategy 2: Title-stripped normalized match
    stripped = _norm(_strip_titles(name))
    stripped_exact = [f for f in faculties if _faculty_norm(f) == stripped]
    if len(stripped_exact) == 1:
        return stripped_exact[0]

    # Strategy 3 & 4: Surname + initials disambiguation
    parts = _strip_titles(name).split()
    if not parts:
        return None
    surname = _norm(parts[-1])
    initials = _initials_set(name)

    candidates: list[Faculty] = []
    for faculty in faculties:
        if _norm(faculty.last_name) != surname:
            continue
        first = _norm(faculty.first_name)
        # When initials are provided, require matching initial(s)
        if initials and first[:1] not in initials:
            continue
        # When no initials are provided (just surname), accept any faculty with this surname
        # but only if there's exactly one candidate (already filtered above by surname)
        candidates.append(faculty)

    # Deduplicate candidates (same faculty may appear via different initials combos).
    # Use the faculty's database id if available, otherwise fall back to a
    # hashable representation (for test compatibility with SimpleNamespace).
    seen: set = set()
    unique_candidates: list[Faculty] = []
    for c in candidates:
        key = getattr(c, "id", str(c))  # Faculty.id or str representation
        if key not in seen:
            seen.add(key)
            unique_candidates.append(c)

    # If exactly one unique candidate -> accept it
    if len(unique_candidates) == 1:
        return unique_candidates[0]

    # If multiple candidates -> ambiguous, return None (safe fallback)
    # This prevents wrong auto-accept when multiple faculty share a surname
    return None if len(unique_candidates) > 1 else None


# ---------------------------------------------------------------------------
# Class matching – considers name + year + branch for unambiguous resolution
# ---------------------------------------------------------------------------


def _class_match(class_name: str, classes: list[Class]) -> Class | None:
    """Match a source-class name against persisted class records.

    Strategy:
      1. Exact normalized name match (case/whitespace insensitive)
      2. When multiple classes share the normalized name, require year+branch
         disambiguation from the source row if available, otherwise return None
    """
    key = _norm(class_name)
    exact_by_name: list[Class] = [c for c in classes if _norm(c.name) == key]

    if not exact_by_name:
        return None

    if len(exact_by_name) == 1:
        return exact_by_name[0]

    # Multiple classes with same name but different year/branch -> need disambiguation
    # Try to use the academic term context from the demand if available
    # For now, return None when not unambiguous (safe conservative fallback)
    # TODO: When source rows carry year/branch info, use it for disambiguation
    return None


# ---------------------------------------------------------------------------


@dataclass
class WorkbookSchedulePlan:
    parsed: DemandParseResult
    solver_input: SolverInput
    assignment_rows: list[dict] = field(default_factory=list)
    unscheduled: list[str] = field(default_factory=list)

    @property
    def source_demands(self) -> int:
        return len(self.parsed.demands)

    @property
    def required_sessions(self) -> int:
        return self.parsed.required_slots

    @property
    def scheduled_sessions(self) -> int:
        return sum(a.hours_per_week for a in self.solver_input.assignments)

    @property
    def unscheduled_sessions(self) -> int:
        return max(0, self.required_sessions - self.scheduled_sessions)

    @property
    def complete(self) -> bool:
        return (
            not self.unscheduled
            and not self.parsed.has_unreviewed_zero_load
            and self.parsed.unrepresented_hours == 0
        )


class WorkbookScheduleService:
    def __init__(self, db: AsyncSession, source_path: str | Path, reference_path: str | Path):
        self.db = db
        self.source_path = Path(source_path)
        self.reference_path = Path(reference_path)

    async def build_plan(
        self,
        academic_year: str,
        semester: int,
        time_slots: list,
        resources: list,
        *,
        slot_hours: int = 2,
        two_hour_grid: bool = True,
        blocked_faculty_slots: set | None = None,
        blocked_resource_slots: set | None = None,
    ) -> WorkbookSchedulePlan:
        parsed = parse_workbook_demand(
            self.source_path,
            academic_year,
            semester,
            self.reference_path,
            slot_hours=slot_hours,
        )
        faculties = list(
            (await self.db.execute(select(Faculty).where(Faculty.is_active.is_(True))))
            .scalars()
            .all()
        )
        classes = list(
            (await self.db.execute(select(Class).where(Class.is_active.is_(True)))).scalars().all()
        )
        subjects = list(
            (await self.db.execute(select(Subject).where(Subject.is_active.is_(True))))
            .scalars()
            .all()
        )
        sections = list(
            (await self.db.execute(select(Section).where(Section.is_active.is_(True))))
            .scalars()
            .all()
        )
        batches = list(
            (await self.db.execute(select(Batch).where(Batch.is_active.is_(True)))).scalars().all()
        )
        loads = list(
            (await self.db.execute(select(FacultyLoad).where(FacultyLoad.is_active.is_(True))))
            .scalars()
            .all()
        )

        section_by_class: dict[UUID, list[Section]] = defaultdict(list)
        for section in sections:
            section_by_class[section.class_id].append(section)
        batches_by_section: dict[UUID, list[Batch]] = defaultdict(list)
        for batch in batches:
            batches_by_section[batch.section_id].append(batch)

        assignments: list[SolverAssignment] = []
        assignment_rows: list[dict] = []
        unscheduled = list(parsed.invalid_rows)
        unscheduled.extend(
            f"Source row {disposition.source_row_number}: {disposition.reason}"
            for disposition in parsed.row_dispositions
            if disposition.disposition == "zero_load_review_required"
        )
        handled_practicals: set[tuple[str, str, int]] = set()
        for demand in parsed.demands:
            if demand.unrepresented_hours:
                unscheduled.append(
                    f"Source row {demand.source_row_number} {demand.session_type} {demand.subject_name}: "
                    f"{demand.unrepresented_hours} one-hour remainder cannot fit a two-hour slot"
                )
            faculty = _faculty_match(demand.faculty_name, faculties)
            class_candidates = [c for c in classes if _norm(c.name) == _norm(demand.class_name)]
            # Use improved class matching that considers year+branch
            subject_candidates = [
                s for s in subjects if _norm(s.name) == _norm(demand.subject_name)
            ]
            if not faculty:
                unscheduled.append(
                    f"Source row {demand.source_row_number}: faculty not mapped: {demand.faculty_name}"
                )
                continue
            # Use improved class matching
            if len(class_candidates) != 1:
                # Try year+branch disambiguation
                class_row = _class_match(demand.class_name, classes)
                if not class_row:
                    unscheduled.append(
                        f"Source row {demand.source_row_number}: class mapping is not unique: {demand.class_name}"
                    )
                    continue
                class_candidates = [class_row]
            else:
                class_row = class_candidates[0]

            subject_candidates = [
                s for s in subjects if _norm(s.name) == _norm(demand.subject_name)
            ]
            if len(subject_candidates) != 1:
                unscheduled.append(
                    f"Source row {demand.source_row_number}: subject mapping is not unique: {demand.subject_name}"
                )
                continue
            subject = subject_candidates[0]
            class_sections = section_by_class[class_row.id]
            if len(class_sections) != 1:
                unscheduled.append(
                    f"Source row {demand.source_row_number}: class needs exactly one mapped section: {demand.class_name}"
                )
                continue
            section = class_sections[0]
            if demand.required_slots <= 0:
                continue

            resource_type = None
            if demand.session_type == "PRACTICAL":
                types = {
                    _resource_type(load.required_resource_type)
                    for load in loads
                    if load.faculty_id == faculty.id
                    and load.subject_id == subject.id
                    and load.section_id == section.id
                    and load.practical_hours > 0
                }
                types.discard(None)
                if len(types) != 1:
                    unscheduled.append(
                        f"Source row {demand.source_row_number}: practical lab type is not uniquely mapped "
                        f"for {demand.subject_name} (configure SOFTWARE_LAB or HARDWARE_LAB)"
                    )
                    continue
                resource_type = next(iter(types))

            if demand.session_type == "PRACTICAL":
                practical_key = (
                    _norm(demand.class_name),
                    _norm(demand.subject_name),
                    demand.source_hours,
                )
                if practical_key in handled_practicals:
                    continue
                handled_practicals.add(practical_key)
                group_demands = [
                    candidate
                    for candidate in parsed.demands
                    if candidate.session_type == "PRACTICAL"
                    and _norm(candidate.subject_name) == _norm(demand.subject_name)
                    and _norm(candidate.class_name) == _norm(demand.class_name)
                    and candidate.source_hours == demand.source_hours
                ]
                group_faculties = [
                    _faculty_match(candidate.faculty_name, faculties) for candidate in group_demands
                ]
                batches_for_section = sorted(
                    batches_by_section[section.id],
                    key=lambda batch: (batch.batch_number, batch.name),
                )
                if (
                    len(group_demands) != len(batches_for_section)
                    or not batches_for_section
                    or any(item is None for item in group_faculties)
                    or len({item.id for item in group_faculties if item}) != len(group_faculties)
                ):
                    unscheduled.append(
                        f"Source row {demand.source_row_number}: {len(batches_for_section)} persisted batch(es) "
                        "and one distinct mapped faculty row per batch are required for parallel practicals"
                    )
                    continue
                group_types = []
                for group_faculty in group_faculties:
                    group_types.append(
                        {
                            _resource_type(load.required_resource_type)
                            for load in loads
                            if group_faculty
                            and load.faculty_id == group_faculty.id
                            and load.subject_id == subject.id
                            and load.section_id == section.id
                            and load.practical_hours > 0
                        }
                        - {None}
                    )
                if any(
                    len(kinds) != 1 or next(iter(kinds)) != resource_type for kinds in group_types
                ):
                    unscheduled.append(
                        f"Source row {demand.source_row_number}: all practical faculty rows need the same mapped lab type"
                    )
                    continue
                for batch, group_faculty in zip(batches_for_section, group_faculties, strict=True):
                    self._append_assignment(
                        assignments,
                        assignment_rows,
                        demand,
                        group_faculty,
                        subject,
                        section,
                        batch,
                        resource_type,
                    )
            else:
                self._append_assignment(
                    assignments, assignment_rows, demand, faculty, subject, section, None, None
                )

        solver_resources = [
            SolverResource(r.id, r.resource_type, r.capacity or 0, bool(r.is_emergency), r.name)
            for r in resources
            if not two_hour_grid or r.name in ALLOWED_RESOURCE_NAMES
        ]
        solver_slots = [
            SolverTimeSlot(
                t.id,
                t.day_of_week,
                t.period_number,
                t.slot_type,
                t.shift,
                getattr(t, "start_time", None),
                getattr(t, "end_time", None),
            )
            for t in time_slots
        ]
        return WorkbookSchedulePlan(
            parsed=parsed,
            solver_input=SolverInput(
                assignments,
                solver_resources,
                solver_slots,
                two_hour_grid=two_hour_grid,
                blocked_faculty_slots=blocked_faculty_slots or set(),
                blocked_resource_slots=blocked_resource_slots or set(),
            ),
            assignment_rows=assignment_rows,
            unscheduled=unscheduled,
        )

    @staticmethod
    def _append_assignment(
        assignments, rows, demand, faculty, subject, section, batch, resource_type
    ):
        assignment_id = uuid5(
            NAMESPACE_URL,
            f"schedulai:{demand.source_semester}:{demand.session_type}:{subject.id}:"
            f"{section.id}:{batch.id if batch else 'section'}:{faculty.id}",
        )
        solver_assignment = SolverAssignment(
            id=assignment_id,
            faculty_id=faculty.id,
            subject_id=subject.id,
            section_id=section.id,
            batch_id=batch.id if batch else None,
            session_type=demand.session_type,
            hours_per_week=demand.required_slots,
            session_duration=1,
            required_lab_type=resource_type,
            section_strength=section.strength or 0,
            batch_strength=(batch.strength or 0) if batch else 0,
        )
        assignments.append(solver_assignment)
        rows.append(
            {
                "id": assignment_id,
                "faculty_id": faculty.id,
                "subject_id": subject.id,
                "section_id": section.id,
                "batch_id": batch.id if batch else None,
                "session_type": demand.session_type,
                "hours_per_week": demand.required_slots,
                "session_duration": 1,
                "required_lab_type": resource_type,
                "preferred_days": [],
                "preferred_shifts": [],
                "is_active": True,
            }
        )
