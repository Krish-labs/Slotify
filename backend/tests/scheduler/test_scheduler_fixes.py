"""
Targeted tests for Phase-2 critical scheduler fixes.
These are pure unit tests — no database required.
"""

import uuid
from types import SimpleNamespace

from ortools.sat.python import cp_model

from app.scheduler.model import SchedulingModel, SolverInput
from app.scheduler.soft_constraints import SoftConstraints

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uuid():
    return uuid.uuid4()


def _ns(**kwargs):
    return SimpleNamespace(**kwargs)


def _make_assignment(
    faculty_id=None,
    section_id=None,
    session_type="LECTURE",
    hours_per_week=3,
    batch_id=None,
    preferred_days=None,
    preferred_shifts=None,
):
    return _ns(
        id=_uuid(),
        faculty_id=faculty_id or _uuid(),
        section_id=section_id or _uuid(),
        session_type=session_type,
        hours_per_week=hours_per_week,
        batch_id=batch_id,
        preferred_days=preferred_days or [],
        preferred_shifts=preferred_shifts or [],
        required_lab_type=None,
        section_strength=30,
        batch_strength=15,
    )


def _make_resource(resource_type="CLASSROOM", capacity=60, is_emergency=False):
    return _ns(
        id=_uuid(),
        resource_type=resource_type,
        capacity=capacity,
        is_emergency=is_emergency,
    )


def _make_time_slot(day_of_week=0, period_number=1, slot_type="TEACHING", shift="MORNING"):
    return _ns(
        id=_uuid(),
        day_of_week=day_of_week,
        period_number=period_number,
        slot_type=slot_type,
        shift=shift,
    )


# ---------------------------------------------------------------------------
# Test: gap constraint — faculty-level (cross-assignment)
# ---------------------------------------------------------------------------


class TestFacultyGapMinimization:
    def test_gap_penalty_created_for_cross_assignment_gap(self):
        model = cp_model.CpModel()
        faculty_id = _uuid()
        a1 = _make_assignment(faculty_id=faculty_id)
        a2 = _make_assignment(faculty_id=faculty_id)
        resource = _make_resource()
        ts_p1 = _make_time_slot(day_of_week=0, period_number=1)
        ts_p3 = _make_time_slot(day_of_week=0, period_number=3)

        variables = {
            (a1.id, resource.id, ts_p1.id): model.NewBoolVar("v1"),
            (a2.id, resource.id, ts_p3.id): model.NewBoolVar("v2"),
        }
        sc = SoftConstraints(model, variables)
        sc.set_data([a1, a2], [resource], [ts_p1, ts_p3])
        sc._faculty_gap_minimization()
        assert len(sc.penalty_vars) > 0

    def test_adjacent_periods_no_gap_penalty(self):
        model = cp_model.CpModel()
        faculty_id = _uuid()
        a1 = _make_assignment(faculty_id=faculty_id)
        a2 = _make_assignment(faculty_id=faculty_id)
        resource = _make_resource()
        ts_p1 = _make_time_slot(day_of_week=0, period_number=1)
        ts_p2 = _make_time_slot(day_of_week=0, period_number=2)

        variables = {
            (a1.id, resource.id, ts_p1.id): model.NewBoolVar("v1"),
            (a2.id, resource.id, ts_p2.id): model.NewBoolVar("v2"),
        }
        sc = SoftConstraints(model, variables)
        sc.set_data([a1, a2], [resource], [ts_p1, ts_p2])
        sc._faculty_gap_minimization()
        assert sc.penalty_vars == []

    def test_gap_model_feasible(self):
        model = cp_model.CpModel()
        faculty_id = _uuid()
        a = _make_assignment(faculty_id=faculty_id)
        resource = _make_resource()
        ts_p1 = _make_time_slot(day_of_week=0, period_number=1)
        ts_p3 = _make_time_slot(day_of_week=0, period_number=3)
        variables = {
            (a.id, resource.id, ts_p1.id): model.NewBoolVar("v1"),
            (a.id, resource.id, ts_p3.id): model.NewBoolVar("v2"),
        }
        sc = SoftConstraints(model, variables)
        sc.set_data([a], [resource], [ts_p1, ts_p3])
        sc._faculty_gap_minimization()
        obj = sc.get_objective()
        if obj is not None:
            model.Minimize(obj)
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


# ---------------------------------------------------------------------------
# Test: SchedulingModel — pinned constraints via dict format
# ---------------------------------------------------------------------------


class TestSchedulingModelPinnedConstraints:
    def test_empty_input_constructs(self):
        inp = SolverInput(assignments=[], resources=[], time_slots=[])
        m = SchedulingModel(inp)
        assert m.get_model() is not None
        assert m.get_variables() == {}

    def test_pinned_constraint_dict_format_valid(self):
        assignment = _make_assignment(hours_per_week=1)
        resource = _make_resource()
        ts = _make_time_slot()
        inp = SolverInput(
            assignments=[assignment],
            resources=[resource],
            time_slots=[ts],
            pinned_constraints=[
                {
                    "assignment_id": assignment.id,
                    "resource_id": resource.id,
                    "time_slot_id": ts.id,
                }
            ],
        )
        m = SchedulingModel(inp)
        solver = cp_model.CpSolver()
        status = solver.Solve(m.get_model())
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


# ---------------------------------------------------------------------------
# Test: import_data.py syntax
# ---------------------------------------------------------------------------


def test_import_data_script_parseable():
    import ast
    from pathlib import Path

    script = Path(__file__).resolve().parents[3] / "scripts" / "import_data.py"
    source = script.read_text()
    tree = ast.parse(source)
    assert tree is not None


# ---------------------------------------------------------------------------
# Test: RBAC dependencies importable
# ---------------------------------------------------------------------------


def test_require_permissions_importable():
    from app.api.dependencies import require_permissions
    from app.core.permissions import Permission

    dep = require_permissions(Permission.TIMETABLE_GENERATE)
    assert callable(dep)


def test_require_roles_importable():
    from app.api.dependencies import require_roles

    dep = require_roles("ADMIN", "HOD")
    assert callable(dep)
