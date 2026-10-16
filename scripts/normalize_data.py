#!/usr/bin/env python3
"""
Normalize imported data and build teaching assignments.
Usage: python scripts/normalize_data.py --academic-year 2025-26 --semester 3
"""

import asyncio
import argparse


import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.database.connection import AsyncSessionLocal
from app.processors.assignment_builder import AssignmentBuilder
from app.processors.batch_processor import BatchProcessor
from app.processors.resource_processor import ResourceProcessor
from app.database.models.section import Section
from sqlalchemy import select


async def main():
    parser = argparse.ArgumentParser(description="Normalize data and build assignments")
    parser.add_argument("--academic-year", default="2025-26", help="Academic year")
    parser.add_argument("--semester", type=int, default=3, help="Semester number")
    args = parser.parse_args()


    async with AsyncSessionLocal() as db:
        # Build assignments from loads
        print("Building teaching assignments...")
        assignment_builder = AssignmentBuilder(db)
        assignments = await assignment_builder.build_from_load(args.academic_year, args.semester)
        saved = await assignment_builder.save_assignments(assignments)
        print(f"Created {saved} teaching assignments")

        # Create batches for sections
        print("Creating batches...")
        batch_processor = BatchProcessor(db)
        result = await db.execute(select(Section).where(Section.is_active == True))
        sections = list(result.scalars().all())

        for section in sections:
            batches = await batch_processor.create_batches_for_section(
                section.id, int(section.strength or 60)
            )
            if batches:
                saved_batches = await batch_processor.save_batches(batches)
                print(f"  Section {section.name}: {saved_batches} batches created")

        # Initialize E&TC resources
        print("Initializing resources...")
        resource_processor = ResourceProcessor(db)
        saved_resources = await resource_processor.initialize_entc_resources(args.academic_year)
        print(f"Initialized {saved_resources} E&TC resources")

        print("Data normalization complete!")


if __name__ == "__main__":
    asyncio.run(main())
