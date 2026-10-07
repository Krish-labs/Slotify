from uuid import UUID


class ExcelWorker:
    def __init__(self):
        pass

    async def process_import(self, file_path: str, import_type: str) -> dict:
        # TODO: Implement Excel import worker
        return {
            "status": "not_implemented",
            "message": "Excel import worker not yet implemented",
        }

    async def process_export(self, timetable_id: UUID, export_type: str) -> dict:
        # TODO: Implement Excel export worker
        return {
            "status": "not_implemented",
            "message": "Excel export worker not yet implemented",
        }
