from uuid import UUID

from ortools.sat.python import cp_model


class VariableManager:
    def __init__(self, model: cp_model.CpModel):
        self.model = model
        self.variables: dict[tuple[UUID, UUID, UUID], cp_model.IntVar] = {}

    def create_variable(
        self, assignment_id: UUID, resource_id: UUID, time_slot_id: UUID
    ) -> cp_model.IntVar:
        key = (assignment_id, resource_id, time_slot_id)
        if key not in self.variables:
            var_name = f"x_{assignment_id}_{resource_id}_{time_slot_id}"
            # ortools' py.typed stubs only expose the snake_case names, but the
            # camelCase aliases are still present and supported at runtime.
            self.variables[key] = self.model.NewBoolVar(var_name)  # type: ignore[attr-defined]
        return self.variables[key]

    def get_variable(
        self, assignment_id: UUID, resource_id: UUID, time_slot_id: UUID
    ) -> cp_model.IntVar | None:
        return self.variables.get((assignment_id, resource_id, time_slot_id))

    def get_all_variables(self) -> dict[tuple[UUID, UUID, UUID], cp_model.IntVar]:
        return self.variables

    def get_variables_for_assignment(self, assignment_id: UUID) -> list:
        return [v for (a_id, r_id, t_id), v in self.variables.items() if a_id == assignment_id]

    def get_variables_for_faculty_at_slot(self, faculty_id: UUID, time_slot_id: UUID) -> list:
        return []

    def get_variables_for_section_at_slot(self, section_id: UUID, time_slot_id: UUID) -> list:
        return []

    def get_variables_for_batch_at_slot(self, batch_id: UUID, time_slot_id: UUID) -> list:
        return []

    def get_variables_for_resource_at_slot(self, resource_id: UUID, time_slot_id: UUID) -> list:
        return [
            v
            for (a_id, r_id, t_id), v in self.variables.items()
            if r_id == resource_id and t_id == time_slot_id
        ]
