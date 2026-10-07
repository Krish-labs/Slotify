from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.batch import Batch


class BatchProcessor:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_batches_for_section(
        self, section_id: UUID, section_strength: int, batch_size: int = 22
    ) -> list[dict]:
        # Calculate number of batches needed
        num_batches = (section_strength + batch_size - 1) // batch_size  # ceiling division
        batches = []
        for i in range(1, num_batches + 1):
            batch_name = f"B{i}"
            start_idx = (i - 1) * batch_size
            end_idx = min(i * batch_size, section_strength)
            strength = end_idx - start_idx

            batches.append(
                {
                    "section_id": section_id,
                    "name": batch_name,
                    "batch_number": i,
                    "strength": strength,
                }
            )
        return batches

    async def save_batches(self, batches: list[dict]) -> int:
        saved = 0
        for batch_data in batches:
            batch = Batch(**batch_data)
            self.db.add(batch)
            saved += 1
        return saved

    async def get_batches_for_section(self, section_id: UUID) -> list[Batch]:
        result = await self.db.execute(select(Batch).where(Batch.section_id == section_id))
        return list(result.scalars().all())
