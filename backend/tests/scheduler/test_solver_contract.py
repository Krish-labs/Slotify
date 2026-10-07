"""Solver input contract: dict inputs (worker/reoptimizer) and attribute inputs both work.

Pure unit tests, no database.
"""

import uuid

from app.scheduler.model import (
    SchedulingModel,
    SolverAssignment,
    SolverInput,
    SolverResource,
    SolverTimeSlot,
)
from app.scheduler.solver import SolverConfig, TimetableSolver
from app.validators.timetable_validator import TimetableValidator


def _id():
    return uuid.uuid4()


def _dict_input(hours=2, session_type="LECTURE", batch_id=None, **assignment_extra):
    assignment = {
        "id": _id(),
        "faculty_id": _id(),
        "section_id": _id(),
        "session_type": session_type,
        "hours_per_week": hours,
        "batch_id": batch_id,
        **assignment_extra,
    }
    resource = {"id": _id(), "resource_type": "CLASSROOM", "capacity": 60}
    slots = [
        {
            "id": _id(),
            "day_of_week": 0,
            "period_number": p,
            "slot_type": "TEACHING",
            "shift": "MORNING",
        }
        for p in (1, 2, 3)
    ]
    return SolverInput(assignments=[assignment], resources=[resource], time_slots=slots)


def _solver():
    return TimetableSolver(
        SolverConfig(time_limit_seconds=10, num_workers=1, log_search_progress=False)
    )


def test_dict_inputs_are_coerced_to_typed_objects():
    inp = _dict_input()
    assert isinstance(inp.assignments[0], SolverAssignment)
    assert isinstance(inp.resources[0], SolverResource)
    assert isinstance(inp.time_slots[0], SolverTimeSlot)


def test_unknown_dict_keys_are_ignored():
    inp = _dict_input(some_orm_only_field="x")
    assert not hasattr(inp.assignments[0], "some_orm_only_field")


def test_solver_solves_dict_input_end_to_end():
    inp = _dict_input(hours=2)
    result = _solver().solve(inp)

    assert result.is_solved
    assert len(result.entries) == 2
    assert {e["assignment_id"] for e in result.entries} == {inp.assignments[0].id}
    assert len({e["time_slot_id"] for e in result.entries}) == 2


def test_infeasible_hours_report_status_instead_of_entries():
    result = _solver().solve(_dict_input(hours=5))  # only 3 slots exist

    assert not result.is_solved
    assert result.status_name == "INFEASIBLE"
    assert result.entries == []


def test_practical_is_not_excluded_by_section_strength():
    # 40-student section, 20-student batch, 25-seat lab: a batch practical fits.
    batch_id = _id()
    inp = SolverInput(
        assignments=[
            {
                "id": _id(),
                "faculty_id": _id(),
                "section_id": _id(),
                "batch_id": batch_id,
                "session_type": "PRACTICAL",
                "hours_per_week": 1,
                "section_strength": 40,
                "batch_strength": 20,
            }
        ],
        resources=[{"id": _id(), "resource_type": "HARDWARE_LAB", "capacity": 25}],
        time_slots=[{"id": _id(), "day_of_week": 0, "period_number": 1}],
    )
    assert len(SchedulingModel(inp).get_variables()) == 1


def test_lecture_is_excluded_from_room_smaller_than_section():
    inp = _dict_input(hours=1, section_strength=70)  # classroom seats 60
    assert SchedulingModel(inp).get_variables() == {}


def test_validator_flags_assignment_coverage_mismatch():
    a_id, f_id, s_id, r_id, t_id = _id(), _id(), _id(), _id(), _id()
    entries = [
        {
            "assignment_id": a_id,
            "faculty_id": f_id,
            "section_id": s_id,
            "resource_id": r_id,
            "time_slot_id": t_id,
            "session_type": "LECTURE",
            "day_of_week": 0,
            "period_number": 1,
        }
    ]
    validator = TimetableValidator()

    ok = validator.validate(entries, required_hours={a_id: 1})
    assert ok.is_valid

    short = validator.validate(entries, required_hours={a_id: 3})
    assert not short.is_valid
    assert short.violations["assignment_coverage"] == 1

    missing = validator.validate(entries, required_hours={a_id: 1, _id(): 2})
    assert not missing.is_valid
