from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.importers.excel_loader import ExcelLoader


class TimetableImporter:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.loader = ExcelLoader()

    async def import_from_excel(self, file_path: str, timetable_id: UUID) -> dict:
        self.loader.load_timetable(file_path)  # fails fast on an unreadable file

        # TODO: Parse timetable format and create entries
        # This would need the specific Excel format

        return {
            "imported": 0,
            "message": "Timetable import not yet implemented",
        }
