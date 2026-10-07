from uuid import UUID

from app.scheduler.solver import TimetableSolver


class ReoptimizationWorker:
    def __init__(self, solver: TimetableSolver | None = None):
        self.solver = solver or TimetableSolver()

    async def process_reoptimization(
        self, timetable_id: UUID, change_data: dict, session_factory
    ) -> dict:
        from app.workers.timetable_worker import TimetableWorker

        worker = TimetableWorker(session_factory=session_factory, solver=self.solver)
        return dict(await worker.reoptimize_timetable(timetable_id, change_data))
