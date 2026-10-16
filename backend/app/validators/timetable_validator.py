from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from app.scheduler.rules import is_section_level


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    violations: dict[str, int]


class TimetableValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.violations = defaultdict(int)

    def validate(
        self,
        entries: list[dict],
        required_hours: dict | None = None,
        *,
        check_resource_compatibility: bool = False,
        blocked_faculty_slots: set[tuple[Any, Any]] | None = None,
        blocked_resource_slots: set[tuple[Any, Any]] | None = None,
    ) -> ValidationResult:
        """Validate entries independently of the solver.

        ``required_hours`` maps assignment_id -> hours_per_week. When given, every
        assignment must be scheduled for exactly that many slots.
        """
        self.errors = []
        self.warnings = []
        self.violations = defaultdict(int)

        self._check_faculty_conflicts(entries)
        self._check_student_group_conflicts(entries)
        self._check_resource_conflicts(entries)
        self._check_capacity(entries)
        self._check_session_blocks(entries)
        self._check_parallel_batches(entries)
        self._check_assignment_coverage(entries, required_hours)
        self._check_two_hour_grid(entries)
        self._check_slot_availability(
            entries, blocked_faculty_slots or set(), blocked_resource_slots or set()
        )
        if check_resource_compatibility:
            self._check_resource_compatibility(entries)
        self._check_soft_constraints(entries)

        return ValidationResult(
            is_valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
            violations=dict(self.violations),
        )

    def _check_slot_availability(
        self,
        entries: list[dict],
        blocked_faculty_slots: set[tuple[Any, Any]],
        blocked_resource_slots: set[tuple[Any, Any]],
    ) -> None:
        for entry in entries:
            if (entry["faculty_id"], entry["time_slot_id"]) in blocked_faculty_slots:
                self.errors.append(
                    f"Faculty {entry['faculty_id']} is unavailable at time slot "
                    f"{entry['time_slot_id']}"
                )
                self.violations["faculty_unavailable"] += 1
            if (entry["resource_id"], entry["time_slot_id"]) in blocked_resource_slots:
                self.errors.append(
                    f"Resource {entry['resource_id']} is unavailable at time slot "
                    f"{entry['time_slot_id']}"
                )
                self.violations["resource_unavailable"] += 1

    def _check_session_blocks(self, entries: list[dict]):
        """Multi-period sessions must be whole blocks of adjacent periods in one room.

        Entries are one row per period. For an assignment with ``session_duration`` d > 1,
        the periods it uses on a given day in a given room must form runs of adjacent
        periods whose lengths are multiples of d. A period alone in its room/day, or a run
        of the wrong length, means a block was split across rooms, days or a gap.
        """
        groups = defaultdict(list)
        durations = {}
        for entry in entries:
            duration = entry.get("session_duration") or 1
            if duration <= 1 or entry.get("period_number") is None:
                continue
            assignment = entry["assignment_id"]
            durations[assignment] = duration
            groups[(assignment, entry["day_of_week"], entry["resource_id"])].append(
                entry["period_number"]
            )

        for (assignment, day, resource), periods in groups.items():
            duration = durations[assignment]
            periods.sort()
            runs, run = [], 1
            for previous, current in zip(periods, periods[1:], strict=False):
                if current == previous + 1:
                    run += 1
                else:
                    runs.append(run)
                    run = 1
            runs.append(run)
            if any(length % duration != 0 for length in runs):
                self.errors.append(
                    f"Broken session block: assignment {assignment} needs {duration} consecutive "
                    f"periods in one room, but day {day} / resource {resource} has periods {periods}"
                )
                self.violations["session_block_broken"] += 1

    def _check_parallel_batches(self, entries: list[dict]):
        """Batches of a section practising the same subject run in the same slots (C10).

        Only checked for well-formed groups: two or more batches, one assignment per batch,
        and the same number of scheduled periods each. Anything else is left to the coverage
        check rather than reported twice.
        """
        # (section, subject) -> batch -> {assignments, slots, periods}
        groups: defaultdict[Any, defaultdict[Any, dict[str, Any]]] = defaultdict(
            lambda: defaultdict(lambda: {"assignments": set(), "slots": []})
        )
        for entry in entries:
            if (
                entry["session_type"] != "PRACTICAL"
                or not entry.get("batch_id")
                or entry.get("subject_id") is None
            ):
                continue
            batch = groups[(entry["section_id"], entry["subject_id"])][entry["batch_id"]]
            batch["assignments"].add(entry["assignment_id"])
            batch["slots"].append(entry["time_slot_id"])

        for (section_id, subject_id), batches in groups.items():
            if len(batches) < 2:
                continue
            if any(len(b["assignments"]) != 1 for b in batches.values()):
                continue
            if len({len(b["slots"]) for b in batches.values()}) != 1:
                continue
            if len({frozenset(b["slots"]) for b in batches.values()}) > 1:
                self.errors.append(
                    f"Parallel batches: batches of section {section_id} practising subject "
                    f"{subject_id} are not scheduled in the same time slots"
                )
                self.violations["parallel_batches"] += 1

    def _check_faculty_conflicts(self, entries: list[dict]):
        faculty_slot = defaultdict(list)
        for entry in entries:
            key = (entry["faculty_id"], entry["time_slot_id"])
            faculty_slot[key].append(entry)

        for key, entries_list in faculty_slot.items():
            if len(entries_list) > 1:
                faculty_id, time_slot_id = key
                self.errors.append(
                    f"Faculty conflict: faculty {faculty_id} has {len(entries_list)} entries at time slot {time_slot_id}"
                )
                self.violations["faculty_conflict"] += 1

    def _check_student_group_conflicts(self, entries: list[dict]):
        """Students cannot be in two places at once.

        A session is section-wide if it is a lecture or has no batch; otherwise it belongs
        to one batch. Per (section, slot): one section-wide session at most, one session
        per batch at most, and no batch session alongside a section-wide one. Different
        batches of a section may legitimately run in parallel.
        """
        section_wide = defaultdict(list)
        per_batch = defaultdict(list)
        batch_occupancy = defaultdict(list)
        for entry in entries:
            slot = entry["time_slot_id"]
            if entry["session_type"] == "PRACTICAL" and not entry.get("batch_id"):
                self.errors.append(f"Practical assignment {entry['assignment_id']} has no batch")
                self.violations["practical_batch_missing"] += 1
            if entry.get("batch_id"):
                batch_occupancy[(entry["section_id"], slot, entry["batch_id"])].append(entry)
            if is_section_level(entry):
                section_wide[(entry["section_id"], slot)].append(entry)
            else:
                per_batch[(entry["section_id"], slot, entry["batch_id"])].append(entry)

        for (section_id, slot), items in section_wide.items():
            if len(items) > 1:
                self.errors.append(
                    f"Section conflict: section {section_id} has {len(items)} section-wide "
                    f"sessions at time slot {slot}"
                )
                self.violations["section_conflict"] += 1

        for (_section_id, slot, batch_id), items in per_batch.items():
            if len(items) > 1:
                self.errors.append(
                    f"Batch conflict: batch {batch_id} has {len(items)} entries at time slot {slot}"
                )
                self.violations["batch_conflict"] += 1

        for section_id, slot, batch_id in per_batch:
            if section_wide.get((section_id, slot)):
                self.errors.append(
                    f"Section/batch conflict: batch {batch_id} has a session at time slot {slot} "
                    f"while section {section_id} has a section-wide session"
                )
                self.violations["section_batch_conflict"] += 1

        # A project is section-wide even if stale data still carries a batch ID.
        # Preserve the direct same-batch diagnostic while applying the stronger
        # section-wide conflict rule above.
        for (section_id, slot, batch_id), items in batch_occupancy.items():
            if len(items) > 1 and any(item["session_type"] == "PROJECT" for item in items):
                self.errors.append(
                    f"Batch conflict: batch {batch_id} has {len(items)} entries at time slot {slot}"
                )
                self.violations["batch_conflict"] += 1

    def _check_resource_conflicts(self, entries: list[dict]):
        resource_slot = defaultdict(list)
        for entry in entries:
            key = (entry["resource_id"], entry["time_slot_id"])
            resource_slot[key].append(entry)

        for key, entries_list in resource_slot.items():
            if len(entries_list) > 1:
                resource_id, time_slot_id = key
                self.errors.append(
                    f"Resource conflict: resource {resource_id} has {len(entries_list)} entries at time slot {time_slot_id}"
                )
                self.violations["resource_conflict"] += 1

    def _check_capacity(self, entries: list[dict]):
        for entry in entries:
            if entry.get("section_strength") and entry.get("resource_capacity"):
                if entry["section_strength"] > entry["resource_capacity"]:
                    self.errors.append(
                        f"Capacity exceeded: section {entry['section_id']} ({entry['section_strength']}) > resource {entry['resource_id']} ({entry['resource_capacity']})"
                    )
                    self.violations["capacity_exceeded"] += 1
            if entry.get("batch_strength") and entry.get("resource_capacity"):
                if entry["batch_strength"] > entry["resource_capacity"]:
                    self.errors.append(
                        f"Capacity exceeded: batch {entry['batch_id']} ({entry['batch_strength']}) > resource {entry['resource_id']} ({entry['resource_capacity']})"
                    )
                    self.violations["capacity_exceeded"] += 1

    def _check_assignment_coverage(self, entries: list[dict], required_hours: dict | None = None):
        if required_hours is None:
            return

        scheduled: defaultdict[Any, int] = defaultdict(int)
        for entry in entries:
            scheduled[entry["assignment_id"]] += 1

        for assignment_id, required in required_hours.items():
            actual = scheduled.get(assignment_id, 0)
            if actual != required:
                self.errors.append(
                    f"Coverage mismatch: assignment {assignment_id} "
                    f"scheduled {actual}h, required {required}h"
                )
                self.violations["assignment_coverage"] += 1

    def _check_two_hour_grid(self, entries: list[dict]):
        """Recheck institutional attendance and room compatibility after solving."""
        if not any(e.get("two_hour_grid") for e in entries):
            return
        by_day = defaultdict(set)
        for entry in entries:
            if not entry.get("two_hour_grid"):
                self.errors.append("Mixed time-slot grids in a single timetable version")
                self.violations["time_grid"] += 1
                continue
            period = entry.get("period_number")
            if entry.get("day_of_week") not in range(6) or period not in range(1, 5):
                self.errors.append(f"Invalid two-hour slot for assignment {entry['assignment_id']}")
                self.violations["time_grid"] += 1
            by_day[(entry["section_id"], entry["day_of_week"])].add(period)
            room_type = entry.get("resource_type")
            session_type = entry["session_type"]
            expected = (
                entry.get("required_lab_type") if session_type == "PRACTICAL" else "CLASSROOM"
            )
            if session_type == "PRACTICAL":
                if room_type not in ("SOFTWARE_LAB", "HARDWARE_LAB") or not expected:
                    self.errors.append(
                        f"Unclassified practical lab for assignment {entry['assignment_id']}"
                    )
                    self.violations["lab_type"] += 1
                elif expected != room_type:
                    self.errors.append(
                        f"Incompatible practical lab for assignment {entry['assignment_id']}"
                    )
                    self.violations["lab_type"] += 1
            elif room_type != expected:
                self.errors.append(
                    f"Non-classroom theory/tutorial/project room for assignment {entry['assignment_id']}"
                )
                self.violations["room_type"] += 1

        for (section, day), periods in by_day.items():
            if len(periods) > 3 or {1, 4} <= periods:
                self.errors.append(
                    f"Class attendance exceeds six hours or spans slots 1 and 4: section {section}, day {day}"
                )
                self.violations["class_daily_limit"] += 1

    def _check_resource_compatibility(self, entries: list[dict]):
        """Validate room type even when a timetable uses reference-hour slots."""
        if any(entry.get("two_hour_grid") for entry in entries) or not any(
            "resource_type" in entry for entry in entries
        ):
            return
        for entry in entries:
            resource_type = entry.get("resource_type")
            expected = (
                entry.get("required_lab_type")
                if entry["session_type"] == "PRACTICAL"
                else "CLASSROOM"
            )
            if entry["session_type"] == "PRACTICAL" and not expected:
                continue
            if not resource_type or not expected:
                self.errors.append(
                    f"Resource type is missing for assignment {entry['assignment_id']}"
                )
                self.violations["resource_type"] += 1
            elif resource_type != expected:
                self.errors.append(
                    f"Incompatible resource for assignment {entry['assignment_id']}: "
                    f"expected {expected}, got {resource_type}"
                )
                self.violations["resource_type"] += 1

    def _check_soft_constraints(self, entries: list[dict]):
        # Faculty day distribution
        faculty_day_sessions: defaultdict[Any, defaultdict[Any, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        for entry in entries:
            faculty_day_sessions[entry["faculty_id"]][entry["day_of_week"]] += 1

        for faculty_id, days in faculty_day_sessions.items():
            for day, count in days.items():
                if count > 2:
                    self.warnings.append(f"Faculty {faculty_id} has {count} sessions on day {day}")
                    self.violations["faculty_day_distribution"] += 1

        # Faculty gaps
        faculty_day_periods: defaultdict[Any, defaultdict[Any, list[Any]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for entry in entries:
            if entry.get("period_number") is None:
                continue
            faculty_day_periods[entry["faculty_id"]][entry["day_of_week"]].append(
                entry["period_number"]
            )

        for faculty_id, day_period_map in faculty_day_periods.items():
            for day, periods in day_period_map.items():
                periods.sort()
                for i in range(len(periods) - 1):
                    gap = periods[i + 1] - periods[i] - 1
                    if gap > 0:
                        self.warnings.append(
                            f"Faculty {faculty_id} has {gap} gap period(s) on day {day}"
                        )
                        self.violations["faculty_gap"] += 1

        # Emergency resource usage
        for entry in entries:
            if entry.get("resource_is_emergency"):
                self.warnings.append(
                    f"Emergency resource {entry['resource_id']} used for assignment {entry['assignment_id']}"
                )
                self.violations["emergency_resource_usage"] += 1
