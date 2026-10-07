import time
from dataclasses import dataclass

from ortools.sat.python import cp_model

from app.scheduler.diagnostics import diagnose
from app.scheduler.model import SchedulingModel, SolverInput, SolverResult
from app.scheduler.objectives import ObjectiveBuilder
from app.scheduler.soft_constraints import SoftConstraints


@dataclass
class SolverConfig:
    time_limit_seconds: int = 300
    num_workers: int = 8
    log_search_progress: bool = True


class TimetableSolver:
    def __init__(self, config: SolverConfig | None = None):
        self.config = config or SolverConfig()

    def solve(self, input_data: SolverInput) -> SolverResult:
        start_time = time.time()

        # Build model with hard constraints
        model_wrapper = SchedulingModel(input_data)
        model = model_wrapper.get_model()
        variables = model_wrapper.get_variables()

        # Add soft constraints
        soft_constraints = SoftConstraints(model, variables)
        soft_constraints.set_data(
            input_data.assignments, input_data.resources, input_data.time_slots
        )
        soft_constraints.apply_all()

        # Build objective
        objective_builder = ObjectiveBuilder(model)
        objective_builder.add_term(soft_constraints.get_objective())
        objective_builder.build()

        # Configure solver
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.config.time_limit_seconds
        solver.parameters.num_search_workers = self.config.num_workers
        solver.parameters.log_search_progress = self.config.log_search_progress

        # Solve
        status = solver.Solve(model)
        solve_time = time.time() - start_time

        # Extract solution
        entries = []
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for (a_id, r_id, t_id), var in variables.items():
                if solver.Value(var) == 1:
                    entries.append(
                        {
                            "assignment_id": a_id,
                            "resource_id": r_id,
                            "time_slot_id": t_id,
                        }
                    )

        solved = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        return SolverResult(
            status=status,
            objective_value=(
                solver.ObjectiveValue() if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
            ),
            entries=entries,
            solve_time_seconds=solve_time,
            status_name=solver.StatusName(status),
            diagnostics=[] if solved else diagnose(input_data),
        )
