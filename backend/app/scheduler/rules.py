"""Scheduling rules shared by the model, the hard constraints and the diagnostics.

Keeping these predicates in one place means variable creation, constraints and failure
explanations can never disagree about what a "suitable" room or a "section-level"
session is.
"""

LECTURE = "LECTURE"
CLASSROOM = "CLASSROOM"


def is_section_level(assignment) -> bool:
    """True if the session occupies the whole section.

    Lectures always do. Any other session without a batch (e.g. a section-wide tutorial)
    does too. Batch-level sessions (labs, batch tutorials/projects) occupy one batch.
    """
    return assignment.session_type == LECTURE or not getattr(assignment, "batch_id", None)


def required_strength(assignment) -> int:
    """Number of students that must fit in the room."""
    if is_section_level(assignment):
        return getattr(assignment, "section_strength", 0) or 0
    return getattr(assignment, "batch_strength", 0) or 0


def session_duration(assignment) -> int:
    """Consecutive periods per session (1 for ordinary sessions, e.g. 2 for a 2-period lab)."""
    return max(1, getattr(assignment, "session_duration", 1) or 1)


def consecutive_windows(time_slots, duration: int) -> list[tuple]:
    """All runs of ``duration`` adjacent teaching periods on one day, as tuples of slot ids.

    Adjacency is by ``period_number``, so a break or lunch period (which has its own period
    number and is not TEACHING) correctly splits a day into separate runs.
    """
    by_day: dict[int, dict[int, object]] = {}
    for slot in time_slots:
        if slot.slot_type == "TEACHING":
            by_day.setdefault(slot.day_of_week, {})[slot.period_number] = slot.id

    windows = []
    for day in sorted(by_day):
        periods = by_day[day]
        for start in sorted(periods):
            run = [periods.get(start + i) for i in range(duration)]
            if all(slot_id is not None for slot_id in run):
                windows.append(tuple(run))
    return windows


def parallel_batch_groups(assignments) -> list[list]:
    """Groups of practical assignments whose batches must run at the same time (spec C10).

    A group is the practicals of one subject in one section for different batches. It is
    only enforced when it is well-formed: at least two batches, one assignment per batch,
    and identical weekly hours and session duration. Anything else (e.g. unequal hours) is
    left unconstrained rather than made infeasible. Assignments without a subject are never
    grouped, since nothing says they belong together.
    """
    grouped: dict[tuple, list] = {}
    for a in assignments:
        if a.session_type == "PRACTICAL" and a.batch_id and a.subject_id is not None:
            grouped.setdefault((a.section_id, a.subject_id), []).append(a)

    groups = []
    for members in grouped.values():
        if len(members) < 2 or len({a.batch_id for a in members}) != len(members):
            continue
        if len({(a.hours_per_week, session_duration(a)) for a in members}) != 1:
            continue
        groups.append(members)
    return groups


def resource_fits(assignment, resource) -> bool:
    """Whether ``resource`` can host ``assignment`` (type and capacity)."""
    if assignment.session_type == LECTURE and resource.resource_type != CLASSROOM:
        return False
    if assignment.session_type == "PRACTICAL":
        required_type = getattr(assignment, "required_lab_type", None)
        if required_type and resource.resource_type != required_type:
            return False
    return bool(required_strength(assignment) <= resource.capacity)
