"""Hard-constraint semantics. Pure unit tests, no database."""

import uuid

from app.scheduler.diagnostics import diagnose
from app.scheduler.model import SolverInput
from app.scheduler.solver import SolverConfig, TimetableSolver
from app.validators.timetable_validator import TimetableValidator


def _id():
    return uuid.uuid4()


def _solver():
    return TimetableSolver(
        SolverConfig(time_limit_seconds=10, num_workers=1, log_search_progress=False)
    )


def _assignment(section_id, session_type="LECTURE", hours=1, batch_id=None, faculty_id=None, **kw):
    return {
        "id": _id(),
        "faculty_id": faculty_id or _id(),
        "section_id": section_id,
        "batch_id": batch_id,
        "session_type": session_type,
        "hours_per_week": hours,
        **kw,
    }


def _rooms(n=3, capacity=60):
    return [{"id": _id(), "resource_type": "CLASSROOM", "capacity": capacity} for _ in range(n)]


def _slots(n):
    return [{"id": _id(), "day_of_week": 0, "period_number": p + 1} for p in range(n)]


def _slot_sets(result, assignments):
    by_a = {a["id"]: set() for a in assignments}
    for e in result.entries:
        by_a[e["assignment_id"]].add(e["time_slot_id"])
    return by_a


def test_batch_session_never_overlaps_its_sections_lecture():
    section, batch = _id(), _id()
    lecture = _assignment(section, "LECTURE", hours=2)
    lab = _assignment(section, "PRACTICAL", hours=2, batch_id=batch)
    # 4 slots, exactly enough for 2 + 2 only if they do not overlap.
    inp = SolverInput([lecture, lab], _rooms(), _slots(4))

    result = _solver().solve(inp)

    assert result.is_solved
    slots = _slot_sets(result, [lecture, lab])
    assert slots[lecture["id"]].isdisjoint(slots[lab["id"]])


def test_batch_and_lecture_overlap_makes_tight_problem_infeasible():
    section, batch = _id(), _id()
    lecture = _assignment(section, "LECTURE", hours=3)
    lab = _assignment(section, "PRACTICAL", hours=2, batch_id=batch)
    # 3 + 2 hours of one student group's time in 4 slots cannot fit.
    result = _solver().solve(SolverInput([lecture, lab], _rooms(), _slots(4)))
    assert result.status_name == "INFEASIBLE"


def test_different_batches_of_a_section_may_run_in_parallel():
    section = _id()
    b1, b2 = _id(), _id()
    lab1 = _assignment(section, "PRACTICAL", hours=2, batch_id=b1)
    lab2 = _assignment(section, "PRACTICAL", hours=2, batch_id=b2)
    # 2 slots: both batches must use both slots.
    result = _solver().solve(SolverInput([lab1, lab2], _rooms(), _slots(2)))
    assert result.is_solved


def test_same_batch_cannot_have_two_sessions_at_once_including_projects():
    section, batch = _id(), _id()
    lab = _assignment(section, "PRACTICAL", hours=2, batch_id=batch)
    project = _assignment(section, "PROJECT", hours=1, batch_id=batch)
    # 3 hours of one batch's time in 2 slots.
    result = _solver().solve(SolverInput([lab, project], _rooms(), _slots(2)))
    assert result.status_name == "INFEASIBLE"


def test_section_level_tutorial_without_batch_conflicts_like_a_lecture():
    section = _id()
    lecture = _assignment(section, "LECTURE", hours=1)
    tutorial = _assignment(section, "TUTORIAL", hours=1, batch_id=None)
    # Both involve the whole section: they need two distinct slots.
    inp = SolverInput([lecture, tutorial], _rooms(), _slots(2))
    result = _solver().solve(inp)
    slots = _slot_sets(result, [lecture, tutorial])
    assert slots[lecture["id"]].isdisjoint(slots[tutorial["id"]])

    # And with a single slot there is no solution.
    one_slot = _solver().solve(SolverInput([lecture, tutorial], _rooms(), _slots(1)))
    assert one_slot.status_name == "INFEASIBLE"


def test_assignment_with_no_feasible_room_is_infeasible_not_silently_dropped():
    section = _id()
    big = _assignment(section, "LECTURE", hours=2, section_strength=200)
    ok = _assignment(_id(), "LECTURE", hours=1)
    result = _solver().solve(SolverInput([big, ok], _rooms(capacity=60), _slots(3)))

    assert not result.is_solved
    assert result.status_name == "INFEASIBLE"


def test_diagnostics_explain_why_an_assignment_cannot_be_placed():
    section = _id()
    big = _assignment(section, "LECTURE", hours=2, section_strength=200)
    result = _solver().solve(SolverInput([big], _rooms(capacity=60), _slots(3)))

    assert any("no room" in d.lower() and "200" in d for d in result.diagnostics)


def test_diagnostics_flag_faculty_overload_and_too_many_hours():
    faculty = _id()
    a1 = _assignment(_id(), hours=3, faculty_id=faculty)
    a2 = _assignment(_id(), hours=3, faculty_id=faculty)
    inp = SolverInput([a1, a2], _rooms(), _slots(4))

    messages = " | ".join(diagnose(inp))
    assert "6" in messages and "4" in messages  # 6h of teaching in 4 slots


def test_diagnostics_empty_for_a_healthy_problem():
    inp = SolverInput([_assignment(_id(), hours=2)], _rooms(), _slots(4))
    assert diagnose(inp) == []


def test_validator_flags_batch_session_overlapping_section_lecture():
    section, batch = _id(), _id()
    slot = _id()

    def entry(session_type, batch_id, faculty):
        return {
            "assignment_id": _id(),
            "faculty_id": faculty,
            "section_id": section,
            "batch_id": batch_id,
            "resource_id": _id(),
            "time_slot_id": slot,
            "session_type": session_type,
            "day_of_week": 0,
            "period_number": 1,
        }

    result = TimetableValidator().validate(
        [entry("LECTURE", None, _id()), entry("PRACTICAL", batch, _id())]
    )

    assert not result.is_valid
    assert result.violations["section_batch_conflict"] == 1


def test_validator_flags_project_sessions_double_booking_a_batch():
    section, batch, slot = _id(), _id(), _id()

    def entry(session_type):
        return {
            "assignment_id": _id(),
            "faculty_id": _id(),
            "section_id": section,
            "batch_id": batch,
            "resource_id": _id(),
            "time_slot_id": slot,
            "session_type": session_type,
            "day_of_week": 0,
            "period_number": 1,
        }

    result = TimetableValidator().validate([entry("PRACTICAL"), entry("PROJECT")])
    assert result.violations["batch_conflict"] == 1


def test_validator_allows_parallel_batches():
    section, slot = _id(), _id()

    def entry(batch):
        return {
            "assignment_id": _id(),
            "faculty_id": _id(),
            "section_id": section,
            "batch_id": batch,
            "resource_id": _id(),
            "time_slot_id": slot,
            "session_type": "PRACTICAL",
            "day_of_week": 0,
            "period_number": 1,
        }

    assert TimetableValidator().validate([entry(_id()), entry(_id())]).is_valid


def test_solver_and_validator_agree_on_a_larger_problem():
    # 3 sections x (2 lectures + 2 batches x 1 lab) in 12 slots; whatever the solver
    # produces must pass the independent validator.
    assignments = []
    for _ in range(3):
        section = _id()
        assignments.append(_assignment(section, "LECTURE", hours=2))
        for _ in range(2):
            assignments.append(_assignment(section, "PRACTICAL", hours=1, batch_id=_id()))
    inp = SolverInput(assignments, _rooms(4), _slots(12))
    result = _solver().solve(inp)
    assert result.is_solved

    by_id = {a.id: a for a in inp.assignments}
    slot_day = {t.id: t for t in inp.time_slots}
    entries = [
        {
            "assignment_id": e["assignment_id"],
            "faculty_id": by_id[e["assignment_id"]].faculty_id,
            "section_id": by_id[e["assignment_id"]].section_id,
            "batch_id": by_id[e["assignment_id"]].batch_id,
            "session_type": by_id[e["assignment_id"]].session_type,
            "resource_id": e["resource_id"],
            "time_slot_id": e["time_slot_id"],
            "day_of_week": slot_day[e["time_slot_id"]].day_of_week,
            "period_number": slot_day[e["time_slot_id"]].period_number,
        }
        for e in result.entries
    ]
    validation = TimetableValidator().validate(
        entries, required_hours={a.id: a.hours_per_week for a in inp.assignments}
    )
    assert validation.is_valid, validation.errors
