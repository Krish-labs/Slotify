#!/usr/bin/env python3
"""
Import load distribution from Excel file.
Usage: python scripts/import_data.py --file data/raw/Load Distribution.xlsx
"""

import asyncio
import argparse
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.database.connection import AsyncSessionLocal, engine, Base  # noqa: E402
from app.importers.load_distribution_importer import LoadDistributionImporter  # noqa: E402
import app.database.models  # noqa: E402, F401 – ensure all models are registered


async def main():
    parser = argparse.ArgumentParser(description="Import load distribution from Excel")
    parser.add_argument("--file", required=True, help="Path to Excel file")
    args = parser.parse_args()

    # Ensure tables exist (idempotent)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Import
    async with AsyncSessionLocal() as db:
        importer = LoadDistributionImporter(db)
        result = await importer.import_from_excel(args.file)
        print(f"Imported: {result['imported']} records")
        if result.get("warnings"):
            for w in result["warnings"]:
                print(f"Warning: {w}")


if __name__ == "__main__":
    asyncio.run(main())
