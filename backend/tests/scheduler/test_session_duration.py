"""Multi-period sessions (session_duration) and parallel batches. No database."""

import uuid

from app.scheduler.diagnostics import diagnose
from app.scheduler.model import SchedulingModel, SolverInput
from app.scheduler.rules import consecutive_windows
from app.scheduler.solver import SolverConfig, TimetableSolver
from app.validators.timetable_validator import TimetableValidator


def _id():
    return uuid.uuid4()


def _solver():
    return TimetableSolver(
        SolverConfig(time_limit_seconds=20, num_workers=1, log_search_progress=False)
    )


def _lab(section, batch, hours=2, duration=2, subject=None, faculty=None, **extra):
    return {
        "id": _id(),
        "faculty_id": faculty or _id(),
        "section_id": section,
        "batch_id": batch,
        "subject_id": subject,
        "session_type": "PRACTICAL",
        "hours_per_week": hours,
        "session_duration": duration,
        **extra,
    }


def _lecture(section, hours=1, **extra):
    return {
        "id": _id(),
        "faculty_id": _id(),
        "section_id": section,
        "session_type": "LECTURE",
        "hours_per_week": hours,
        **extra,
    }


def _labs(n=2, capacity=30):
    return [{"id": _id(), "resource_type": "HARDWARE_LAB", "capacity": capacity} for _ in range(n)]


def _slots(per_day, days=1, break_after=None):
    """`per_day` periods per day; an optional non-teaching period number splits the day."""
    slots = []
    for day in range(days):
        for p in range(1, per_day + 1):
            slot_type = "BREAK" if p == break_after else "TEACHING"
            slots.append(
                {"id": _id(), "day_of_week": day, "period_number": p, "slot_type": slot_type}
            )
    return slots


def _placement(result, assignment, inp):
    """[(day, period, resource_id)] for one assignment, sorted."""
    slot = {t.id: t for t in inp.time_slots}
    return sorted(
        (
            slot[e["time_slot_id"]].day_of_week,
            slot[e["time_slot_id"]].period_number,
            e["resource_id"],
        )
        for e in result.entries
        if e["assignment_id"] == assignment["id"]
    )


# ------------------------------------------------------------------ consecutive_windows


def test_windows_require_adjacent_teaching_periods_on_one_day():
    inp = SolverInput([], [], _slots(per_day=4, days=2, break_after=3))
    windows = consecutive_windows(inp.time_slots, 2)
    slot = {t.id: (t.day_of_week, t.period_number) for t in inp.time_slots}
    got = {tuple(slot[s] for s in w) for w in windows}
    # periods 1-2 only (3 is a break, 4 is isolated), on each of the two days
    assert got == {((0, 1), (0, 2)), ((1, 1), (1, 2))}


def test_windows_of_duration_one_are_every_teaching_slot():
    inp = SolverInput([], [], _slots(per_day=3, days=2))
    assert len(consecutive_windows(inp.time_slots, 1)) == 6


# ------------------------------------------------------------------ solver behaviour


def test_two_period_lab_is_placed_in_adjacent_periods_in_one_room():
    lab = _lab(_id(), _id(), hours=2, duration=2)
    inp = SolverInput([lab], _labs(), _slots(per_day=4, days=2))

    result = _solver().solve(inp)

    assert result.is_solved
    placed = _placement(result, lab, inp)
    assert len(placed) == 2
    (d1, p1, r1), (d2, p2, r2) = placed
    assert d1 == d2 and p2 == p1 + 1 and r1 == r2


def test_four_hours_of_two_period_labs_form_two_blocks():
    lab = _lab(_id(), _id(), hours=4, duration=2)
    inp = SolverInput([lab], _labs(), _slots(per_day=4, days=2))

    result = _solver().solve(inp)

    assert result.is_solved
    placed = _placement(result, lab, inp)
    assert len(placed) == 4
    by_day = {}
    for d, p, r in placed:
        by_day.setdefault((d, r), []).append(p)
    for periods in by_day.values():  # every same-day/same-room run splits into whole blocks
        run = 1
        runs = []
        for a, b in zip(periods, periods[1:], strict=False):
            if b == a + 1:
                run += 1
            else:
                runs.append(run)
                run = 1
        runs.append(run if periods else 0)
        assert all(r % 2 == 0 for r in runs), periods


def test_three_period_block_is_contiguous():
    lab = _lab(_id(), _id(), hours=3, duration=3)
    inp = SolverInput([lab], _labs(), _slots(per_day=5, days=2))
    result = _solver().solve(inp)
    assert result.is_solved
    periods = [p for _, p, _ in _placement(result, lab, inp)]
    assert periods == list(range(periods[0], periods[0] + 3))


def test_block_cannot_straddle_a_break():
    # 4 periods/day with period 2 a break: no two adjacent teaching periods exist except 3-4.
    lab = _lab(_id(), _id(), hours=2, duration=2)
    inp = SolverInput([lab], _labs(), _slots(per_day=4, days=1, break_after=2))
    result = _solver().solve(inp)
    assert result.is_solved
    assert [p for _, p, _ in _placement(result, lab, inp)] == [3, 4]


def test_block_cannot_span_days():
    # one teaching period per day => a 2-period block can never fit
    lab = _lab(_id(), _id(), hours=2, duration=2)
    inp = SolverInput([lab], _labs(), _slots(per_day=1, days=5))
    result = _solver().solve(inp)
    assert result.status_name == "INFEASIBLE"
    assert any("consecutive" in d for d in result.diagnostics)


def test_duration_one_behaves_like_before():
    lab = _lab(_id(), _id(), hours=3, duration=1)
    inp = SolverInput([lab], _labs(1), _slots(per_day=5))
    result = _solver().solve(inp)
    assert result.is_solved and len(result.entries) == 3


def test_hours_not_divisible_by_duration_is_infeasible_with_a_reason():
    lab = _lab(_id(), _id(), hours=3, duration=2)
    inp = SolverInput([lab], _labs(), _slots(per_day=6))

    result = _solver().solve(inp)

    assert result.status_name == "INFEASIBLE"
    assert any("multiple of" in d for d in result.diagnostics)


def test_block_occupies_the_batch_for_every_period_of_the_block():
    section, batch = _id(), _id()
    lab = _lab(section, batch, hours=2, duration=2)
    other = _lab(section, batch, hours=1, duration=1)  # same batch, must avoid the block
    # 3 periods: block takes 2, leaving exactly 1 for the other session.
    inp = SolverInput([lab, other], _labs(), _slots(per_day=3))
    result = _solver().solve(inp)
    assert result.is_solved
    a = {p for _, p, _ in _placement(result, lab, inp)}
    b = {p for _, p, _ in _placement(result, other, inp)}
    assert a.isdisjoint(b)

    tight = SolverInput([lab, other], _labs(), _slots(per_day=2))
    assert _solver().solve(tight).status_name == "INFEASIBLE"


def test_block_occupies_the_room_for_every_period():
    # Two single-room labs both wanting a 2-block, only 3 periods: second one cannot fit.
    a = _lab(_id(), _id(), hours=2, duration=2)
    b = _lab(_id(), _id(), hours=2, duration=2)
    one_room = SolverInput([a, b], _labs(1), _slots(per_day=3))
    assert _solver().solve(one_room).status_name == "INFEASIBLE"
    two_rooms = SolverInput([a, b], _labs(2), _slots(per_day=3))
    assert _solver().solve(two_rooms).is_solved


def test_pinned_block_is_respected():
    lab = _lab(_id(), _id(), hours=2, duration=2)
    resources = _labs(1)
    slots = _slots(per_day=4)
    inp = SolverInput(
        [lab],
        resources,
        slots,
        pinned_constraints=[
            {
                "assignment_id": lab["id"],
                "resource_id": resources[0]["id"],
                "time_slot_id": slots[2]["id"],
            }
        ],
    )
    result = _solver().solve(inp)
    assert result.is_solved
    assert [p for _, p, _ in _placement(result, lab, inp)] == [3, 4]


# ------------------------------------------------------------------ parallel batches


def test_same_subject_batches_of_a_section_run_in_the_same_slots():
    section, subject = _id(), _id()
    labs = [_lab(section, _id(), hours=2, duration=2, subject=subject) for _ in range(3)]
    # 6 periods, 3 labs: without parallelism the three 2-blocks could be staggered.
    inp = SolverInput(labs, _labs(3), _slots(per_day=6))

    result = _solver().solve(inp)

    assert result.is_solved
    slot_sets = [{p for _, p, _ in _placement(result, lab, inp)} for lab in labs]
    assert slot_sets[0] == slot_sets[1] == slot_sets[2]


def test_parallel_batches_need_enough_rooms_at_once():
    section, subject = _id(), _id()
    labs = [_lab(section, _id(), hours=2, duration=2, subject=subject) for _ in range(3)]
    # 3 batches must run simultaneously but only 2 labs exist => infeasible,
    # even though 6 periods would let them run one after another.
    result = _solver().solve(SolverInput(labs, _labs(2), _slots(per_day=6)))
    assert result.status_name == "INFEASIBLE"


def test_different_subjects_are_not_forced_parallel():
    section = _id()
    labs = [_lab(section, _id(), hours=2, duration=2, subject=_id()) for _ in range(3)]
    result = _solver().solve(SolverInput(labs, _labs(2), _slots(per_day=6)))
    assert result.is_solved  # 2 labs, staggered blocks


def test_unknown_subject_is_not_grouped():
    section = _id()
    labs = [_lab(section, _id(), hours=2, duration=2, subject=None) for _ in range(3)]
    assert _solver().solve(SolverInput(labs, _labs(2), _slots(per_day=6))).is_solved


def test_different_sections_are_not_forced_parallel():
    subject = _id()
    labs = [_lab(_id(), _id(), hours=2, duration=2, subject=subject) for _ in range(2)]
    result = _solver().solve(SolverInput(labs, _labs(1), _slots(per_day=4)))
    assert result.is_solved  # one room, so they must be staggered


def test_groups_with_unequal_hours_are_left_alone_instead_of_made_infeasible():
    section, subject = _id(), _id()
    a = _lab(section, _id(), hours=2, duration=2, subject=subject)
    b = _lab(section, _id(), hours=4, duration=2, subject=subject)
    result = _solver().solve(SolverInput([a, b], _labs(2), _slots(per_day=6)))
    assert result.is_solved


def test_parallel_batches_coexist_with_the_sections_lecture():
    section, subject = _id(), _id()
    lecture = _lecture(section, hours=3)
    labs = [_lab(section, _id(), hours=2, duration=2, subject=subject) for _ in range(2)]
    classrooms = [{"id": _id(), "resource_type": "CLASSROOM", "capacity": 60}]
    inp = SolverInput([lecture, *labs], classrooms + _labs(2), _slots(per_day=5))

    result = _solver().solve(inp)

    assert result.is_solved
    lecture_periods = {p for _, p, _ in _placement(result, lecture, inp)}
    lab_periods = {p for _, p, _ in _placement(result, labs[0], inp)}
    assert lecture_periods.isdisjoint(lab_periods)
    assert lab_periods == {p for _, p, _ in _placement(result, labs[1], inp)}


# ------------------------------------------------------------------ diagnostics


def test_diagnostics_flag_indivisible_hours_and_missing_runs():
    section = _id()
    indivisible = _lab(section, _id(), hours=3, duration=2)
    inp = SolverInput([indivisible], _labs(), _slots(per_day=1, days=5))
    messages = " | ".join(diagnose(inp))
    assert "multiple of" in messages
    assert "consecutive" in messages


def test_diagnostics_flag_parallel_group_with_too_few_rooms():
    section, subject = _id(), _id()
    labs = [_lab(section, _id(), hours=2, duration=2, subject=subject) for _ in range(3)]
    messages = " | ".join(diagnose(SolverInput(labs, _labs(2), _slots(per_day=6))))
    assert "parallel" in messages.lower() and "3" in messages


# ------------------------------------------------------------------ validator


def _entry(assignment, section, batch, subject, slot, resource, day, period, duration, hours=None):
    return {
        "assignment_id": assignment,
        "faculty_id": assignment,  # unique per assignment, so no faculty clash
        "subject_id": subject,
        "section_id": section,
        "batch_id": batch,
        "session_type": "PRACTICAL",
        "session_duration": duration,
        "resource_id": resource,
        "time_slot_id": slot,
        "day_of_week": day,
        "period_number": period,
    }


def test_validator_accepts_contiguous_blocks():
    a, s, b, sub, room = _id(), _id(), _id(), _id(), _id()
    entries = [
        _entry(a, s, b, sub, _id(), room, 0, 2, 2),
        _entry(a, s, b, sub, _id(), room, 0, 3, 2),
    ]
    assert TimetableValidator().validate(entries).is_valid


def test_validator_rejects_split_block():
    a, s, b, sub, room = _id(), _id(), _id(), _id(), _id()
    entries = [
        _entry(a, s, b, sub, _id(), room, 0, 1, 2),
        _entry(a, s, b, sub, _id(), room, 0, 3, 2),  # gap: periods 1 and 3
    ]
    result = TimetableValidator().validate(entries)
    assert not result.is_valid
    assert result.violations["session_block_broken"] == 1


def test_validator_rejects_block_split_across_rooms_or_days():
    a, s, b, sub = _id(), _id(), _id(), _id()
    across_rooms = [
        _entry(a, s, b, sub, _id(), _id(), 0, 1, 2),
        _entry(a, s, b, sub, _id(), _id(), 0, 2, 2),
    ]
    assert TimetableValidator().validate(across_rooms).violations["session_block_broken"] >= 1

    across_days = [
        _entry(a, s, b, sub, _id(), _id(), 0, 4, 2),
        _entry(a, s, b, sub, _id(), _id(), 1, 1, 2),
    ]
    assert TimetableValidator().validate(across_days).violations["session_block_broken"] >= 1


def test_validator_ignores_blocks_for_single_period_sessions():
    a, s, b, sub, room = _id(), _id(), _id(), _id(), _id()
    entries = [
        _entry(a, s, b, sub, _id(), room, 0, 1, 1),
        _entry(a, s, b, sub, _id(), room, 0, 5, 1),
    ]
    assert TimetableValidator().validate(entries).is_valid


def test_validator_flags_batches_that_should_run_in_parallel_but_do_not():
    s, sub = _id(), _id()
    s1, s2, s3 = _id(), _id(), _id()
    b1, b2 = _id(), _id()
    a1, a2 = _id(), _id()
    room1, room2 = _id(), _id()
    staggered = [
        _entry(a1, s, b1, sub, s1, room1, 0, 1, 1),
        _entry(a2, s, b2, sub, s2, room2, 0, 2, 1),
    ]
    result = TimetableValidator().validate(staggered)
    assert not result.is_valid
    assert result.violations["parallel_batches"] == 1

    together = [
        _entry(a1, s, b1, sub, s3, room1, 0, 1, 1),
        _entry(a2, s, b2, sub, s3, room2, 0, 1, 1),
    ]
    assert TimetableValidator().validate(together).is_valid


def test_validator_does_not_enforce_parallelism_for_unequal_groups():
    s, sub = _id(), _id()
    a1, a2 = _id(), _id()
    b1, b2 = _id(), _id()
    room1, room2 = _id(), _id()
    entries = [
        _entry(a1, s, b1, sub, _id(), room1, 0, 1, 1),
        _entry(a2, s, b2, sub, _id(), room2, 0, 2, 1),
        _entry(a2, s, b2, sub, _id(), room2, 0, 3, 1),
    ]
    assert "parallel_batches" not in TimetableValidator().validate(entries).violations


def test_solver_output_always_passes_the_validator():
    section, subject = _id(), _id()
    labs = [_lab(section, _id(), hours=4, duration=2, subject=subject) for _ in range(2)]
    lecture = _lecture(section, hours=3)
    classrooms = [{"id": _id(), "resource_type": "CLASSROOM", "capacity": 60}]
    inp = SolverInput([lecture, *labs], classrooms + _labs(2), _slots(per_day=6, days=2))
    result = _solver().solve(inp)
    assert result.is_solved

    by_id = {a.id: a for a in inp.assignments}
    slot = {t.id: t for t in inp.time_slots}
    entries = [
        {
            "assignment_id": e["assignment_id"],
            "faculty_id": by_id[e["assignment_id"]].faculty_id,
            "subject_id": by_id[e["assignment_id"]].subject_id,
            "section_id": by_id[e["assignment_id"]].section_id,
            "batch_id": by_id[e["assignment_id"]].batch_id,
            "session_type": by_id[e["assignment_id"]].session_type,
            "session_duration": by_id[e["assignment_id"]].session_duration,
            "resource_id": e["resource_id"],
            "time_slot_id": e["time_slot_id"],
            "day_of_week": slot[e["time_slot_id"]].day_of_week,
            "period_number": slot[e["time_slot_id"]].period_number,
        }
        for e in result.entries
    ]
    validation = TimetableValidator().validate(
        entries, required_hours={a.id: a.hours_per_week for a in inp.assignments}
    )
    assert validation.is_valid, validation.errors


def test_model_exposes_block_starts_only_for_multi_period_assignments():
    lab = _lab(_id(), _id(), hours=2, duration=2)
    single = _lab(_id(), _id(), hours=2, duration=1)
    model = SchedulingModel(SolverInput([lab, single], _labs(1), _slots(per_day=4)))
    assert {a for (a, _, _) in model.block_starts} == {lab["id"]}
