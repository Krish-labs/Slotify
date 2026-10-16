from dataclasses import dataclass, field, fields
from datetime import time
from typing import Any
from uuid import UUID

from ortools.sat.python import cp_model

from app.scheduler.hard_constraints import HardConstraints
from app.scheduler.rules import is_section_level, resource_fits


@dataclass
class SolverAssignment:
    id: UUID
    faculty_id: UUID
    section_id: UUID
    session_type: str
    hours_per_week: int
    # Consecutive periods per session; hours_per_week / session_duration sessions are placed.
    session_duration: int = 1
    batch_id: UUID | None = None
    subject_id: UUID | None = None
    preferred_days: list[int] = field(default_factory=list)
    preferred_shifts: list[str] = field(default_factory=list)
    required_lab_type: str | None = None
    section_strength: int = 0
    batch_strength: int = 0


@dataclass
class SolverResource:
    id: UUID
    resource_type: str
    capacity: int
    is_emergency: bool = False
    name: str = ""


@dataclass
class SolverTimeSlot:
    id: UUID
    day_of_week: int
    period_number: int
    slot_type: str = "TEACHING"
    shift: str = "MORNING"
    start_time: time | None = None
    end_time: time | None = None


def _coerce(cls: type, item: Any) -> Any:
    """Turn a dict into ``cls``; leave attribute-style objects untouched.

    The solver reads inputs by attribute. Callers (the worker, the reoptimizer)
    naturally produce dicts, so ``SolverInput`` normalises them here instead of
    each caller having to know the solver's internal representation.
    """
    if not isinstance(item, dict):
        return item
    known = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in item.items() if k in known})


@dataclass
class SolverInput:
    assignments: list
    resources: list
    time_slots: list
    # Legacy: force specific (assignment, resource, time_slot) variables to 1 when
    # those keys exist in the variable space.
    pinned_constraints: list = field(default_factory=list)
    # Reoptimization: dicts describing entries that must be preserved as-is
    # (faculty_id, section_id, batch_id, resource_id, time_slot_id, session_type).
    # New placements may never clash with them.
    pinned_entries: list = field(default_factory=list)
    # Reoptimization: dicts {"faculty_id", "day_of_week"} the affected faculty
    # cannot teach (leave / explicit unavailability windows).
    unavailable: list = field(default_factory=list)
    # This policy applies only to the four two-hour institutional slots. Older
    # templates use one-hour periods and retain their existing semantics.
    two_hour_grid: bool = False
    # Slot-level hard availability blocks resolved by the worker.
    blocked_faculty_slots: set[tuple[UUID, UUID]] = field(default_factory=set)
    blocked_resource_slots: set[tuple[UUID, UUID]] = field(default_factory=set)

    def __post_init__(self):
        self.assignments = [_coerce(SolverAssignment, a) for a in self.assignments]
        self.resources = [_coerce(SolverResource, r) for r in self.resources]
        self.time_slots = [_coerce(SolverTimeSlot, t) for t in self.time_slots]
        self.blocked_faculty_slots = {
            (UUID(str(faculty_id)), UUID(str(slot_id)))
            for faculty_id, slot_id in self.blocked_faculty_slots
        }
        self.blocked_resource_slots = {
            (UUID(str(resource_id)), UUID(str(slot_id)))
            for resource_id, slot_id in self.blocked_resource_slots
        }


@dataclass
class SolverResult:
    status: int
    objective_value: int | float | None
    entries: list
    solve_time_seconds: float
    status_name: str = ""
    # Human-readable reasons a problem is unsolvable (only filled when it wasn't solved).
    diagnostics: list[str] = field(default_factory=list)

    @property
    def is_solved(self) -> bool:
        return self.status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    @property
    def has_feasible_solution(self) -> bool:
        return self.status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    @property
    def optimality_proven(self) -> bool:
        return self.status == cp_model.OPTIMAL

    @property
    def is_infeasible(self) -> bool:
        return self.status == cp_model.INFEASIBLE

    @property
    def is_unknown(self) -> bool:
        return self.status in (cp_model.UNKNOWN, cp_model.MODEL_INVALID)


class SchedulingModel:
    def __init__(self, input_data: SolverInput):
        self.model = cp_model.CpModel()
        self.input = input_data
        self.variables: dict[tuple[Any, Any, Any], Any] = {}
        self.block_starts: dict[Any, Any] = {}
        self._build_variables()
        self._assignment_by_id = {a.id: a for a in self.input.assignments}
        self._add_hard_constraints()

    def _build_variables(self):
        # Create decision variables for valid (assignment, resource, time_slot) combinations
        for assignment in self.input.assignments:
            for resource in self.input.resources:
                if self._is_valid_resource(assignment, resource):
                    for time_slot in self.input.time_slots:
                        if self._is_valid_time_slot(assignment, time_slot):
                            var_name = f"x_{assignment.id}_{resource.id}_{time_slot.id}"
                            self.variables[(assignment.id, resource.id, time_slot.id)] = (
                                self.model.NewBoolVar(var_name)
                            )

    def _is_valid_resource(self, assignment, resource) -> bool:
        if self.input.two_hour_grid:
            if assignment.session_type == "PRACTICAL":
                if (
                    not assignment.required_lab_type
                    or resource.resource_type != assignment.required_lab_type
                ):
                    return False
            elif resource.resource_type != "CLASSROOM":
                return False
        return resource_fits(assignment, resource)

    def _is_valid_time_slot(self, assignment, time_slot) -> bool:
        # Only teaching slots
        return bool(time_slot.slot_type == "TEACHING")

    def _add_hard_constraints(self):
        # Delegate entirely to the canonical HardConstraints implementation.
        hard = HardConstraints(self.model, self.variables)
        hard.set_data(self.input.assignments, self.input.resources, self.input.time_slots)
        hard.two_hour_grid = self.input.two_hour_grid
        hard.apply_all()
        self.block_starts = hard.block_starts

        # Pinned constraints: force specific (assignment, resource, time_slot) combos to 1.
        # pinned_constraints is a list of dicts with keys assignment_id, resource_id, time_slot_id.
        for entry in self.input.pinned_constraints or []:
            key = (entry["assignment_id"], entry["resource_id"], entry["time_slot_id"])
            if key in self.variables:
                self.model.Add(self.variables[key] == 1)

        # Reoptimization context: preserved entries occupy faculty/rooms/student
        # groups, and unavailable windows block the affected faculty's days.
        self._apply_pinned_occupancy()
        self._apply_unavailability()
        self._apply_slot_availability()

    def _apply_pinned_occupancy(self):
        """New placements must not clash with preserved (pinned) entries.

        Mirrors the canonical conflict rules for entries outside the re-solved
        scope: one session per faculty per slot, one session per room per slot,
        and students never in two places (section-wide vs per-batch, with
        different batches of a section allowed to run in parallel).
        """
        if not self.input.pinned_entries:
            return

        pinned_faculty: set = set()
        pinned_resource: set = set()
        pinned_any_section: set = set()  # (section, slot): any pinned entry
        pinned_section_wide: set = set()  # (section, slot): section-wide pinned
        pinned_batch: set = set()  # (section, batch, slot)

        for entry in self.input.pinned_entries:
            slot = entry["time_slot_id"]
            pinned_faculty.add((entry["faculty_id"], slot))
            pinned_resource.add((entry["resource_id"], slot))
            key = (entry["section_id"], slot)
            pinned_any_section.add(key)
            if entry["session_type"] == "LECTURE" or not entry.get("batch_id"):
                pinned_section_wide.add(key)
            else:
                pinned_batch.add((entry["section_id"], entry["batch_id"], slot))

        for (a_id, r_id, t_id), var in self.variables.items():
            assignment = self._assignment_by_id.get(a_id)
            if assignment is None:
                continue
            blocked = (assignment.faculty_id, t_id) in pinned_faculty or (
                r_id,
                t_id,
            ) in pinned_resource
            if not blocked:
                if is_section_level(assignment):
                    blocked = (assignment.section_id, t_id) in pinned_any_section
                else:
                    blocked = (assignment.section_id, t_id) in pinned_section_wide or (
                        assignment.section_id,
                        assignment.batch_id,
                        t_id,
                    ) in pinned_batch
            if blocked:
                self.model.Add(var == 0)

    def _apply_unavailability(self):
        """A faculty member on leave / unavailable cannot teach on those days."""
        if not self.input.unavailable:
            return
        blocked = {
            (UUID(str(item["faculty_id"])), int(item["day_of_week"]))
            for item in self.input.unavailable
        }
        slot_day = {t.id: t.day_of_week for t in self.input.time_slots}
        for (a_id, _r_id, t_id), var in self.variables.items():
            assignment = self._assignment_by_id.get(a_id)
            if assignment and (assignment.faculty_id, slot_day.get(t_id)) in blocked:
                self.model.Add(var == 0)

    def _apply_slot_availability(self):
        for (a_id, resource_id, slot_id), var in self.variables.items():
            assignment = self._assignment_by_id.get(a_id)
            if assignment and (
                (assignment.faculty_id, slot_id) in self.input.blocked_faculty_slots
                or (resource_id, slot_id) in self.input.blocked_resource_slots
            ):
                self.model.Add(var == 0)

    def get_model(self) -> cp_model.CpModel:
        return self.model

    def get_variables(self) -> dict:
        return self.variables
