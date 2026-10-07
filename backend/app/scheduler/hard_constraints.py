from collections import defaultdict
from uuid import UUID

from ortools.sat.python import cp_model

from app.scheduler.rules import (
    consecutive_windows,
    is_section_level,
    parallel_batch_groups,
    resource_fits,
    session_duration,
)


class HardConstraints:
    def __init__(
        self, model: cp_model.CpModel, variables: dict[tuple[UUID, UUID, UUID], cp_model.IntVar]
    ):
        self.model = model
        self.variables = variables
        self.assignment_map: dict[UUID, dict] = {}
        self.resource_map: dict[UUID, dict] = {}
        self.time_slot_map: dict[UUID, dict] = {}
        # (assignment_id, resource_id, first_time_slot_id) -> 1 iff a multi-period session
        # starts there. Only populated for assignments with session_duration > 1.
        self.block_starts: dict[tuple[UUID, UUID, UUID], cp_model.IntVar] = {}

    def set_data(self, assignments: list, resources: list, time_slots: list):
        self.assignment_map = {a.id: a for a in assignments}
        self.resource_map = {r.id: r for r in resources}
        self.time_slot_map = {t.id: t for t in time_slots}

    def apply_all(self):
        self._session_blocks()
        self._assignment_coverage()
        self._faculty_conflict()
        self._student_group_conflict()
        self._resource_conflict()
        self._resource_suitability()
        self._template_compliance()
        self._parallel_batches()

    def _session_blocks(self):
        """Multi-period sessions: ``session_duration`` adjacent periods, same day, same room.

        The per-period occupancy variables ``x[a, r, t]`` stay the single source of truth for
        every other constraint (faculty, student group, room conflicts). Here each is tied to
        block-start variables, so a period is occupied exactly when some block covering it
        starts: ``x == sum(covering starts)``. Two overlapping blocks of one assignment would
        make that sum 2, which a Boolean ``x`` cannot equal, so overlap is excluded for free.
        """
        multi = [a for a in self.assignment_map.values() if session_duration(a) > 1]
        if not multi:
            return

        vars_by_assignment: dict[UUID, dict[tuple, cp_model.IntVar]] = defaultdict(dict)
        for (a_id, r_id, t_id), var in self.variables.items():
            vars_by_assignment[a_id][(r_id, t_id)] = var

        windows_by_duration: dict[int, list[tuple]] = {}
        for assignment in multi:
            duration = session_duration(assignment)
            if duration not in windows_by_duration:
                windows_by_duration[duration] = consecutive_windows(
                    self.time_slot_map.values(), duration
                )
            own = vars_by_assignment.get(assignment.id, {})
            rooms = {r_id for (r_id, _t) in own}

            covering: dict[tuple, list] = defaultdict(list)
            for room in rooms:
                for window in windows_by_duration[duration]:
                    if all((room, t) in own for t in window):
                        start = self.model.NewBoolVar(f"blk_{assignment.id}_{room}_{window[0]}")
                        self.block_starts[(assignment.id, room, window[0])] = start
                        for t in window:
                            covering[(room, t)].append(start)

            for (room, t), var in own.items():
                self.model.Add(var == sum(covering.get((room, t), [])))

    def _assignment_coverage(self):
        """Every assignment gets exactly its weekly hours (as whole sessions)."""
        by_assignment: dict[UUID, list] = defaultdict(list)
        for (a_id, _r_id, _t_id), var in self.variables.items():
            by_assignment[a_id].append(var)

        starts_by_assignment: dict[UUID, list] = defaultdict(list)
        for (a_id, _r_id, _t_id), start in self.block_starts.items():
            starts_by_assignment[a_id].append(start)

        for assignment in self.assignment_map.values():
            hours = assignment.hours_per_week
            duration = session_duration(assignment)

            if duration > 1:
                if hours % duration != 0:
                    # Cannot be split into whole sessions; surfaced by diagnostics.
                    self.model.AddBoolOr([])
                    continue
                starts = starts_by_assignment.get(assignment.id, [])
                if starts:
                    self.model.Add(sum(starts) == hours // duration)
                elif hours > 0:
                    self.model.AddBoolOr([])
                continue

            candidates = by_assignment.get(assignment.id, [])
            if candidates:
                self.model.Add(sum(candidates) == hours)
            elif hours > 0:
                # No suitable (room, slot) exists. Dropping the assignment silently would
                # return a "solved" timetable that is missing classes; make it infeasible.
                self.model.AddBoolOr([])

    def _faculty_conflict(self):
        """A faculty member teaches at most one session per slot."""
        faculty_slot_vars = defaultdict(list)
        for (a_id, _r_id, t_id), var in self.variables.items():
            assignment = self.assignment_map.get(a_id)
            if assignment:
                faculty_slot_vars[(assignment.faculty_id, t_id)].append(var)

        for vars_list in faculty_slot_vars.values():
            if len(vars_list) > 1:
                self.model.Add(sum(vars_list) <= 1)

    def _student_group_conflict(self):
        """Students are never in two places at once.

        Per (section, slot):
          * at most one section-wide session (lectures, batch-less tutorials/projects),
          * at most one session per batch (any type: practical, tutorial, project),
          * a section-wide session excludes every batch session (the batches are part of
            the section). Different batches may run in parallel.
        """
        section_vars = defaultdict(list)
        batch_vars = defaultdict(lambda: defaultdict(list))

        for (a_id, _r_id, t_id), var in self.variables.items():
            assignment = self.assignment_map.get(a_id)
            if not assignment:
                continue
            key = (assignment.section_id, t_id)
            if is_section_level(assignment):
                section_vars[key].append(var)
            else:
                batch_vars[key][assignment.batch_id].append(var)

        for key, vars_list in section_vars.items():
            if len(vars_list) > 1:
                self.model.Add(sum(vars_list) <= 1)

        for key, per_batch in batch_vars.items():
            all_batch_vars = []
            for vars_list in per_batch.values():
                if len(vars_list) > 1:
                    self.model.Add(sum(vars_list) <= 1)
                all_batch_vars.extend(vars_list)

            section_level = section_vars.get(key)
            if section_level:
                # busy >= every batch var; busy + section-wide sessions <= 1
                busy = self.model.NewBoolVar(f"batch_busy_{key[0]}_{key[1]}")
                for var in all_batch_vars:
                    self.model.AddImplication(var, busy)
                self.model.Add(busy + sum(section_level) <= 1)

    def _resource_conflict(self):
        """A room hosts at most one session per slot."""
        resource_slot_vars = defaultdict(list)
        for (_a_id, r_id, t_id), var in self.variables.items():
            resource_slot_vars[(r_id, t_id)].append(var)

        for vars_list in resource_slot_vars.values():
            if len(vars_list) > 1:
                self.model.Add(sum(vars_list) <= 1)

    def _resource_suitability(self):
        """Room type and capacity must fit the session."""
        for (a_id, r_id, _t_id), var in self.variables.items():
            assignment = self.assignment_map.get(a_id)
            resource = self.resource_map.get(r_id)
            if assignment and resource and not resource_fits(assignment, resource):
                self.model.Add(var == 0)

    def _template_compliance(self):
        """Only teaching slots (not breaks/lunch) can be used."""
        for (_a_id, _r_id, t_id), var in self.variables.items():
            time_slot = self.time_slot_map.get(t_id)
            if time_slot and time_slot.slot_type != "TEACHING":
                self.model.Add(var == 0)

    def _parallel_batches(self):
        """All batches of a section practising the same subject run at the same time (C10).

        Per period the batches must agree on whether they are in session, so single-period
        labs line up slot for slot and multi-period labs line up block for block. Each batch
        still needs its own room at that time, via the ordinary room-conflict constraint.
        """
        groups = parallel_batch_groups(self.assignment_map.values())
        if not groups:
            return

        wanted = {a.id for group in groups for a in group}
        occupancy: dict[UUID, dict[UUID, list]] = defaultdict(lambda: defaultdict(list))
        for (a_id, _r_id, t_id), var in self.variables.items():
            if a_id in wanted:
                occupancy[a_id][t_id].append(var)

        for group in groups:
            reference = group[0]
            all_slots = set()
            for member in group:
                all_slots.update(occupancy[member.id])
            for member in group[1:]:
                for t_id in all_slots:
                    self.model.Add(
                        sum(occupancy[member.id].get(t_id, []))
                        == sum(occupancy[reference.id].get(t_id, []))
                    )
