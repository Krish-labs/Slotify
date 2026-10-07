from uuid import UUID

from ortools.sat.python import cp_model


class SoftConstraints:
    def __init__(
        self, model: cp_model.CpModel, variables: dict[tuple[UUID, UUID, UUID], cp_model.IntVar]
    ):
        self.model = model
        self.variables = variables
        self.assignment_map: dict[UUID, dict] = {}
        self.resource_map: dict[UUID, dict] = {}
        self.time_slot_map: dict[UUID, dict] = {}
        self.penalty_vars: list[cp_model.IntVar] = []
        self.penalty_weights: dict[str, int] = {
            "faculty_day_distribution": 10,
            "faculty_gap_minimization": 5,
            "student_gap_minimization": 5,
            "room_continuity": 3,
            "morning_preference": 2,
            "emergency_resource_usage": 20,
            "preferred_days_shifts": 5,
        }

    def set_data(self, assignments: list, resources: list, time_slots: list):
        self.assignment_map = {a.id: a for a in assignments}
        self.resource_map = {r.id: r for r in resources}
        self.time_slot_map = {t.id: t for t in time_slots}

    def apply_all(self):
        self._faculty_day_distribution()
        self._faculty_gap_minimization()
        self._room_continuity()
        self._morning_preference()
        self._emergency_resource_usage()
        self._preferred_days_shifts()

    def _faculty_day_distribution(self):
        # Penalize multiple sessions same day for same faculty
        for assignment in self.assignment_map.values():
            faculty_id = assignment.faculty_id
            for day in range(6):  # Mon-Sat
                day_vars = []
                for (a_id, _r_id, t_id), var in self.variables.items():
                    if a_id == assignment.id:
                        time_slot = self.time_slot_map.get(t_id)
                        if time_slot and time_slot.day_of_week == day:
                            day_vars.append(var)
                if len(day_vars) > 1:
                    # Create penalty variable for excess sessions
                    penalty = self.model.NewIntVar(
                        0, len(day_vars), f"penalty_faculty_day_{faculty_id}_{day}"
                    )
                    self.model.Add(penalty >= sum(day_vars) - 1)
                    self.penalty_vars.append(
                        penalty * self.penalty_weights["faculty_day_distribution"]
                    )

    def _faculty_gap_minimization(self):
        # Penalize gaps in faculty schedule — operate at FACULTY level, not assignment level,
        # so that inter-subject gaps within the same day are also captured.

        # Build per-faculty, per-day map: period_number -> list[var]
        faculty_day_period_vars: dict[tuple, dict[int, list]] = {}
        for (a_id, _r_id, t_id), var in self.variables.items():
            assignment = self.assignment_map.get(a_id)
            time_slot = self.time_slot_map.get(t_id)
            if not assignment or not time_slot:
                continue
            key = (assignment.faculty_id, time_slot.day_of_week)
            if key not in faculty_day_period_vars:
                faculty_day_period_vars[key] = {}
            period = time_slot.period_number
            if period not in faculty_day_period_vars[key]:
                faculty_day_period_vars[key][period] = []
            faculty_day_period_vars[key][period].append(var)

        for (faculty_id, day), period_map in faculty_day_period_vars.items():
            if len(period_map) < 2:
                continue
            sorted_periods = sorted(period_map.keys())
            for i in range(len(sorted_periods) - 1):
                p_i = sorted_periods[i]
                p_j = sorted_periods[i + 1]
                gap = p_j - p_i - 1
                if gap <= 0:
                    continue

                # Indicators: is_i = 1 iff at least one variable at period p_i is 1
                is_i = self.model.NewBoolVar(f"gap_indicator_{faculty_id}_{day}_{p_i}")
                is_j = self.model.NewBoolVar(f"gap_indicator_{faculty_id}_{day}_{p_j}")
                vars_i = period_map[p_i]
                vars_j = period_map[p_j]
                self.model.AddMaxEquality(is_i, vars_i)
                self.model.AddMaxEquality(is_j, vars_j)

                # both_scheduled = is_i AND is_j
                both = self.model.NewBoolVar(f"gap_both_{faculty_id}_{day}_{p_i}_{p_j}")
                self.model.AddBoolAnd([is_i, is_j]).OnlyEnforceIf(both)
                self.model.AddBoolOr([is_i.Not(), is_j.Not()]).OnlyEnforceIf(both.Not())

                # penalty = gap * both  (gap is a constant, so this is linear)
                penalty = self.model.NewIntVar(
                    0, gap, f"penalty_faculty_gap_{faculty_id}_{day}_{p_i}_{p_j}"
                )
                self.model.Add(penalty == gap * both)
                self.penalty_vars.append(penalty * self.penalty_weights["faculty_gap_minimization"])

    def _room_continuity(self):
        # Prefer same room for same assignment
        for assignment in self.assignment_map.values():
            resources_used = {}
            for (a_id, r_id, _t_id), var in self.variables.items():
                if a_id == assignment.id:
                    if r_id not in resources_used:
                        resources_used[r_id] = []
                    resources_used[r_id].append(var)

            if len(resources_used) > 1:
                # Penalty for using multiple rooms
                penalty = self.model.NewIntVar(
                    0, len(resources_used) - 1, f"penalty_room_continuity_{assignment.id}"
                )
                # Simplified: count of rooms used minus 1
                room_indicators = []
                for r_id, vars_list in resources_used.items():
                    indicator = self.model.NewBoolVar(f"room_used_{assignment.id}_{r_id}")
                    self.model.AddMaxEquality(indicator, vars_list)
                    room_indicators.append(indicator)
                self.model.Add(penalty == sum(room_indicators) - 1)
                self.penalty_vars.append(penalty * self.penalty_weights["room_continuity"])

    def _morning_preference(self):
        # Penalize theory sessions in late shift
        for (a_id, _r_id, t_id), var in self.variables.items():
            assignment = self.assignment_map.get(a_id)
            time_slot = self.time_slot_map.get(t_id)
            if (
                assignment
                and assignment.session_type == "LECTURE"
                and time_slot
                and time_slot.shift == "LATE"
            ):
                penalty = self.model.NewIntVar(0, 1, f"penalty_morning_{a_id}_{t_id}")
                self.model.Add(penalty == var)
                self.penalty_vars.append(penalty * self.penalty_weights["morning_preference"])

    def _emergency_resource_usage(self):
        # Penalize emergency resource usage
        for (a_id, r_id, t_id), var in self.variables.items():
            resource = self.resource_map.get(r_id)
            if resource and resource.is_emergency:
                penalty = self.model.NewIntVar(0, 1, f"penalty_emergency_{a_id}_{r_id}_{t_id}")
                self.model.Add(penalty == var)
                self.penalty_vars.append(penalty * self.penalty_weights["emergency_resource_usage"])

    def _preferred_days_shifts(self):
        # Penalize assignments outside preferred days/shifts
        for (a_id, _r_id, t_id), var in self.variables.items():
            assignment = self.assignment_map.get(a_id)
            time_slot = self.time_slot_map.get(t_id)
            if assignment and time_slot:
                penalty = 0
                if (
                    assignment.preferred_days
                    and time_slot.day_of_week not in assignment.preferred_days
                ):
                    penalty += 1
                if (
                    assignment.preferred_shifts
                    and time_slot.shift not in assignment.preferred_shifts
                ):
                    penalty += 1
                if penalty > 0:
                    penalty_var = self.model.NewIntVar(
                        0, penalty, f"penalty_preference_{a_id}_{t_id}"
                    )
                    self.model.Add(penalty_var == penalty * var)
                    self.penalty_vars.append(
                        penalty_var * self.penalty_weights["preferred_days_shifts"]
                    )

    def get_objective(self):
        return sum(self.penalty_vars)
