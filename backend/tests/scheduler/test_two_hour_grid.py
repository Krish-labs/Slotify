from uuid import uuid4

from app.scheduler.model import SolverAssignment, SolverInput, SolverResource, SolverTimeSlot
from app.scheduler.solver import SolverConfig, TimetableSolver
from app.scheduler.time_slots import CANONICAL_SLOTS, WORKING_DAYS
from app.validators.timetable_validator import TimetableValidator


def test_two_hour_grid_schedules_three_parallel_batches_and_validates():
    section = uuid4()
    subject = uuid4()
    batch_ids = [uuid4() for _ in range(3)]
    faculty_ids = [uuid4() for _ in range(4)]
    assignments = [
        SolverAssignment(
            id=uuid4(),
            faculty_id=faculty_ids[0],
            section_id=section,
            subject_id=subject,
            session_type="LECTURE",
            hours_per_week=1,
            section_strength=60,
        )
    ]
    assignments.extend(
        SolverAssignment(
            id=uuid4(),
            faculty_id=faculty_ids[index + 1],
            section_id=section,
            subject_id=subject,
            batch_id=batch,
            session_type="PRACTICAL",
            hours_per_week=1,
            required_lab_type="SOFTWARE_LAB",
            section_strength=60,
            batch_strength=20,
        )
        for index, batch in enumerate(batch_ids)
    )
    resources = [
        SolverResource(uuid4(), "CLASSROOM", 60, name="309"),
        SolverResource(uuid4(), "CLASSROOM", 60, name="311"),
        SolverResource(uuid4(), "CLASSROOM", 60, name="314"),
        SolverResource(uuid4(), "SOFTWARE_LAB", 20, name="307A"),
        SolverResource(uuid4(), "SOFTWARE_LAB", 20, name="307B"),
        SolverResource(uuid4(), "SOFTWARE_LAB", 20, name="308A"),
    ]
    slots = [
        SolverTimeSlot(uuid4(), day, slot.period_number, "TEACHING", slot.shift)
        for day in WORKING_DAYS
        for slot in CANONICAL_SLOTS
    ]
    solver_input = SolverInput(assignments, resources, slots, two_hour_grid=True)
    result = TimetableSolver(
        SolverConfig(time_limit_seconds=10, num_workers=1, log_search_progress=False)
    ).solve(solver_input)

    assert result.is_solved, result.diagnostics
    assignment_map = {assignment.id: assignment for assignment in assignments}
    resource_map = {resource.id: resource for resource in resources}
    slot_map = {slot.id: slot for slot in slots}
    entries = [
        {
            "assignment_id": entry["assignment_id"],
            "faculty_id": assignment_map[entry["assignment_id"]].faculty_id,
            "subject_id": subject,
            "section_id": section,
            "batch_id": assignment_map[entry["assignment_id"]].batch_id,
            "resource_id": entry["resource_id"],
            "resource_type": resource_map[entry["resource_id"]].resource_type,
            "required_lab_type": assignment_map[entry["assignment_id"]].required_lab_type,
            "time_slot_id": entry["time_slot_id"],
            "day_of_week": slot_map[entry["time_slot_id"]].day_of_week,
            "period_number": slot_map[entry["time_slot_id"]].period_number,
            "session_type": assignment_map[entry["assignment_id"]].session_type,
            "two_hour_grid": True,
        }
        for entry in result.entries
    ]
    validation = TimetableValidator().validate(
        entries,
        required_hours={assignment.id: assignment.hours_per_week for assignment in assignments},
    )

    assert validation.is_valid, validation.errors
    practical_slots = {
        entry["time_slot_id"] for entry in entries if entry["session_type"] == "PRACTICAL"
    }
    assert len(practical_slots) == 1
    assert validation.violations.get("class_daily_limit", 0) == 0


def test_two_hour_grid_uses_the_actual_two_batch_set():
    section = uuid4()
    subject = uuid4()
    faculty_ids = [uuid4() for _ in range(2)]
    batch_ids = [uuid4() for _ in range(2)]
    assignments = [
        SolverAssignment(
            id=uuid4(),
            faculty_id=faculty_ids[index],
            section_id=section,
            subject_id=subject,
            batch_id=batch_ids[index],
            session_type="PRACTICAL",
            hours_per_week=1,
            required_lab_type="SOFTWARE_LAB",
            section_strength=40,
            batch_strength=20,
        )
        for index in range(2)
    ]
    resources = [
        SolverResource(uuid4(), "SOFTWARE_LAB", 20, name="307A"),
        SolverResource(uuid4(), "SOFTWARE_LAB", 20, name="307B"),
    ]
    slots = [
        SolverTimeSlot(uuid4(), day, slot.period_number, "TEACHING", slot.shift)
        for day in WORKING_DAYS
        for slot in CANONICAL_SLOTS
    ]

    result = TimetableSolver(
        SolverConfig(time_limit_seconds=10, num_workers=1, log_search_progress=False)
    ).solve(SolverInput(assignments, resources, slots, two_hour_grid=True))

    assert result.is_solved, result.diagnostics
    assert len({entry["time_slot_id"] for entry in result.entries}) == 1
