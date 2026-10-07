from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from app.scheduler.model import SolverAssignment, SolverInput, SolverResource, SolverTimeSlot
from app.scheduler.solver import SolverResult, TimetableSolver


@dataclass
class ImpactReport:
    affected_entry_ids: list[UUID]
    pinned_entry_ids: list[UUID]
    affected_assignment_ids: list[UUID]
    affected_resource_ids: list[UUID]
    affected_time_slot_ids: list[UUID]


def _ids(value) -> str:
    """Normalize ids that may arrive as UUIDs or strings (JSON payloads)."""
    return str(value) if value is not None else ""


def leave_weekdays(date_range: dict | None) -> set[int] | None:
    """Weekdays (0=Mon) covered by a leave/availability date range.

    Accepts ``date`` objects or ISO strings under ``start``/``end`` (or
    ``start_date``/``end_date``). Returns ``None`` when the range is missing or
    unparsable, meaning "no day information" (affect everything, block nothing).
    """
    if not date_range:
        return None
    raw_start = date_range.get("start", date_range.get("start_date"))
    raw_end = date_range.get("end", date_range.get("end_date"))
    if raw_start is None or raw_end is None:
        return None
    try:
        start = raw_start if isinstance(raw_start, date) else date.fromisoformat(str(raw_start))
        end = raw_end if isinstance(raw_end, date) else date.fromisoformat(str(raw_end))
    except ValueError:
        return None
    if end < start:
        return None
    days: set[int] = set()
    current = start
    while current <= end:
        days.add(current.weekday())
        current += timedelta(days=1)
    return days


class Reoptimizer:
    def __init__(self, solver: TimetableSolver | None = None):
        self.solver = solver or TimetableSolver()

    def analyze_impact(
        self, change_type: str, change_data: dict, current_entries: list[dict]
    ) -> ImpactReport:
        """Split current entries into an affected scope and a pinned remainder.

        change_data often arrives with stringified ids (JSON API/tests) while
        entries carry native UUIDs, so all comparisons normalize via ``str()``.
        """
        change_data = change_data or {}
        affected_entries: set[UUID] = set()
        affected_assignments: set[UUID] = set()
        affected_resources: set[UUID] = set()
        affected_time_slots: set[UUID] = set()

        def mark(entry: dict) -> None:
            affected_entries.add(entry["id"])
            affected_assignments.add(entry["assignment_id"])
            affected_resources.add(entry["resource_id"])
            affected_time_slots.add(entry["time_slot_id"])

        if change_type == "LOAD_CHANGE":
            wanted = {_ids(x) for x in change_data.get("assignment_ids", [])}
            for entry in current_entries:
                if _ids(entry["assignment_id"]) in wanted:
                    mark(entry)
        elif change_type == "RESOURCE_CHANGE":
            resource_id = _ids(change_data.get("resource_id"))
            for entry in current_entries:
                if _ids(entry["resource_id"]) == resource_id:
                    mark(entry)
        elif change_type == "FACULTY_AVAILABILITY":
            faculty_id = _ids(change_data.get("faculty_id"))
            days = change_data.get("time_range", {}).get("days")
            days = {int(d) for d in days} if days is not None else None
            for entry in current_entries:
                if _ids(entry["faculty_id"]) == faculty_id and (
                    days is None or int(entry["day_of_week"]) in days
                ):
                    mark(entry)
        elif change_type == "LEAVE":
            faculty_id = _ids(change_data.get("faculty_id"))
            days = leave_weekdays(change_data.get("date_range"))
            for entry in current_entries:
                if _ids(entry["faculty_id"]) == faculty_id and (
                    days is None or int(entry["day_of_week"]) in days
                ):
                    mark(entry)
        elif change_type == "TEMPLATE_CHANGE":
            # change_data["time_slot_ids"] lists the slots RETAINED by the new
            # template (same semantics as build_subproblem and the worker's
            # pre-check). Entries on non-retained slots must move; entries on
            # retained slots stay pinned.
            wanted = {_ids(x) for x in change_data.get("time_slot_ids", [])}
            for entry in current_entries:
                if _ids(entry["time_slot_id"]) not in wanted:
                    mark(entry)

        # Parallel-batch ripple (spec C10): sibling batches practising the same
        # subject in the same section must stay aligned, so they re-solve
        # together. Leaving them pinned would produce a combined timetable that
        # violates the hard parallel-batch rule.
        affected_list = [e for e in current_entries if e["id"] in affected_entries]
        group_keys = {
            (_ids(e["section_id"]), _ids(e.get("subject_id")))
            for e in affected_list
            if e["session_type"] == "PRACTICAL" and e.get("batch_id")
        }
        if group_keys:
            for entry in current_entries:
                if entry["id"] in affected_entries:
                    continue
                if entry["session_type"] != "PRACTICAL" or not entry.get("batch_id"):
                    continue
                if (
                    _ids(entry["section_id"]),
                    _ids(entry.get("subject_id")),
                ) in group_keys and entry["assignment_id"] not in affected_assignments:
                    mark(entry)

        all_entry_ids = {e["id"] for e in current_entries}
        return ImpactReport(
            affected_entry_ids=list(affected_entries),
            pinned_entry_ids=list(all_entry_ids - affected_entries),
            affected_assignment_ids=list(affected_assignments),
            affected_resource_ids=list(affected_resources),
            affected_time_slot_ids=list(affected_time_slots),
        )

    def build_subproblem(
        self,
        impact: ImpactReport,
        all_assignments: list[SolverAssignment],
        all_resources: list[SolverResource],
        all_time_slots: list[SolverTimeSlot],
        current_entries: list[dict],
        change_type: str | None = None,
        change_data: dict | None = None,
    ) -> SolverInput:
        """Build the solver input for one reoptimization step.

        The subproblem re-solves only the affected assignments, but gives them
        the full space of active rooms and time slots (except for template
        changes, which restrict placement to the retained slots). Pinned
        entries are passed through as both occupancy constraints (so newly
        placed sessions never clash) AND as pinned_constraints (forcing the
        exact assignment/resource/slot variables to 1 when those combinations
        exist in the subproblem's variable space).
        """
        affected_assignment_ids = set(impact.affected_assignment_ids)
        affected_assignments = [a for a in all_assignments if a.id in affected_assignment_ids]

        if change_type == "TEMPLATE_CHANGE":
            retained = {_ids(x) for x in (change_data or {}).get("time_slot_ids", [])}
            time_slots = [t for t in all_time_slots if _ids(t.id) in retained]
        else:
            time_slots = list(all_time_slots)
        resources = list(all_resources)

        pinned_entries = [
            entry for entry in current_entries if entry["id"] in set(impact.pinned_entry_ids)
        ]

        # Build pinned_constraints from pinned_entries to force exact
        # (assignment, resource, time_slot) combinations when those variables
        # exist in the subproblem's variable space.
        pinned_constraints = [
            {
                "assignment_id": e["assignment_id"],
                "resource_id": e["resource_id"],
                "time_slot_id": e["time_slot_id"],
            }
            for e in pinned_entries
        ]

        unavailable: list[dict] = []
        if change_type in ("LEAVE", "FACULTY_AVAILABILITY"):
            faculty_id = _ids((change_data or {}).get("faculty_id"))
            if change_type == "LEAVE":
                days = leave_weekdays((change_data or {}).get("date_range"))
            else:
                raw_days = (change_data or {}).get("time_range", {}).get("days")
                days = {int(d) for d in raw_days} if raw_days is not None else None
            if faculty_id and days:
                unavailable = [
                    {"faculty_id": faculty_id, "day_of_week": day} for day in sorted(days)
                ]

        return SolverInput(
            assignments=affected_assignments,
            resources=resources,
            time_slots=time_slots,
            pinned_constraints=pinned_constraints,
            pinned_entries=pinned_entries,
            unavailable=unavailable,
        )

    def reoptimize(
        self,
        impact: ImpactReport,
        all_assignments: list[SolverAssignment],
        all_resources: list[SolverResource],
        all_time_slots: list[SolverTimeSlot],
        current_entries: list[dict],
    ) -> SolverResult:
        subproblem = self.build_subproblem(
            impact, all_assignments, all_resources, all_time_slots, current_entries
        )
        return self.solver.solve(subproblem)
