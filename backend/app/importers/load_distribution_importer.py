import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.faculty_load import FacultyLoad
from app.importers.excel_loader import ExcelLoader
from app.processors.load_normalizer import LoadNormalizer
from app.validators.load_validator import LoadValidator


class LoadDistributionImporter:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.loader = ExcelLoader()
        self.validator = LoadValidator()
        self.normalizer = LoadNormalizer(db)

    async def import_from_excel(self, file_path: str) -> dict:
        # Load raw data
        df = self.loader.load_load_distribution(file_path)

        # Validate
        validation = self.validator.validate_dataframe(df)
        if not validation.is_valid:
            raise ValueError(f"Validation failed: {validation.errors}")

        # Normalize
        normalized_records = await self.normalizer.normalize(df)

        # Save to database
        saved_count = 0
        for record in normalized_records:
            load = FacultyLoad(**record)
            self.db.add(load)
            saved_count += 1
        return {
            "imported": saved_count,
            "warnings": validation.warnings,
        }

    async def import_from_dataframe(self, df: pd.DataFrame) -> dict:
        validation = self.validator.validate_dataframe(df)
        if not validation.is_valid:
            raise ValueError(f"Validation failed: {validation.errors}")

        normalized_records = await self.normalizer.normalize(df)

        saved_count = 0
        for record in normalized_records:
            load = FacultyLoad(**record)
            self.db.add(load)
            saved_count += 1
        return {
            "imported": saved_count,
            "warnings": validation.warnings,
        }
