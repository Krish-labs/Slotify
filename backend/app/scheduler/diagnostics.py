"""Explain *why* a scheduling problem has no solution.

CP-SAT only reports INFEASIBLE. These cheap necessary-condition checks name the likely
culprits so a human can fix the input (add a room, move load, add slots). They never
prove feasibility: an empty result means "no obvious cause", not "solvable".
"""

from collections import defaultdict

from app.scheduler.model import SolverInput
from app.scheduler.rules import (
    consecutive_windows,
    is_section_level,
    parallel_batch_groups,
    required_strength,
    resource_fits,
    session_duration,
)


def diagnose(input_data: SolverInput) -> list[str]:
    assignments = input_data.assignments
    teaching_slots = [t for t in input_data.time_slots if t.slot_type == "TEACHING"]
    n_slots = len(teaching_slots)
    messages: list[str] = []

    def label(a) -> str:
        return f"assignment {a.id} ({a.session_type}, section {a.section_id})"

    # 1. Assignments that cannot be placed anywhere / need more hours than slots exist.
    for a in assignments:
        if a.hours_per_week <= 0:
            continue
        fitting = [r for r in input_data.resources if resource_fits(a, r)]
        if not fitting:
            largest = max((r.capacity for r in input_data.resources), default=0)
            messages.append(
                f"No room fits {label(a)}: needs capacity {required_strength(a)} "
                f"(and a suitable room type); largest room seats {largest}"
            )
        if a.hours_per_week > n_slots:
            messages.append(
                f"{label(a).capitalize()} needs {a.hours_per_week}h but only "
                f"{n_slots} teaching slots exist"
            )

    # 1b. Multi-period sessions: whole blocks only, and a long enough run must exist.
    windows_by_duration: dict[int, list] = {}
    for a in assignments:
        duration = session_duration(a)
        if duration <= 1 or a.hours_per_week <= 0:
            continue
        if a.hours_per_week % duration != 0:
            messages.append(
                f"{label(a).capitalize()} has {a.hours_per_week}h, which is not a multiple of "
                f"its session duration ({duration} periods)"
            )
        if duration not in windows_by_duration:
            windows_by_duration[duration] = consecutive_windows(input_data.time_slots, duration)
        if not windows_by_duration[duration]:
            messages.append(
                f"{label(a).capitalize()} needs {duration} consecutive teaching periods in a "
                f"day, but no day has such a run (breaks and day boundaries split runs)"
            )

    # 1c. Parallel batches each need their own room at the same time.
    for group in parallel_batch_groups(assignments):
        usable = {r.id for a in group for r in input_data.resources if resource_fits(a, r)}
        if len(usable) < len(group):
            messages.append(
                f"Parallel batches of section {group[0].section_id}: {len(group)} batches of the "
                f"same subject must run at the same time but only {len(usable)} suitable "
                f"room(s) exist"
            )

    # 2. A faculty member cannot teach more hours than there are slots.
    faculty_hours: dict = defaultdict(int)
    for a in assignments:
        faculty_hours[a.faculty_id] += a.hours_per_week
    for faculty_id, hours in faculty_hours.items():
        if hours > n_slots:
            messages.append(
                f"Faculty {faculty_id} is assigned {hours}h but only {n_slots} teaching slots exist"
            )

    # 3. A section's students cannot be in two places: section-wide sessions plus the
    #    busiest batch must fit in the available slots.
    section_hours: dict = defaultdict(int)
    batch_hours: dict = defaultdict(lambda: defaultdict(int))
    for a in assignments:
        if is_section_level(a):
            section_hours[a.section_id] += a.hours_per_week
        else:
            batch_hours[a.section_id][a.batch_id] += a.hours_per_week
    for section_id in set(section_hours) | set(batch_hours):
        busiest_batch = max(batch_hours[section_id].values(), default=0)
        needed = section_hours[section_id] + busiest_batch
        if needed > n_slots:
            messages.append(
                f"Section {section_id} needs at least {needed} slots "
                f"({section_hours[section_id]}h section-wide + {busiest_batch}h for its busiest "
                f"batch) but only {n_slots} teaching slots exist"
            )

    # 4. Total room-hours versus total room-slots.
    total_hours = sum(a.hours_per_week for a in assignments)
    capacity = n_slots * len(input_data.resources)
    if total_hours > capacity:
        messages.append(
            f"{total_hours} teaching hours requested but only {capacity} room-slots "
            f"({len(input_data.resources)} rooms x {n_slots} slots) exist"
        )

    return messages
