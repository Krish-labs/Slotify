from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.audit_log import AuditLog
from app.database.models.batch import Batch
from app.schemas.batch import BatchCreate, BatchUpdate


class BatchService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _serialize_for_audit(self, data: dict) -> dict[str, Any]:
        """Serialize date/datetime objects for JSON storage"""
        result: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, date | datetime):
                result[k] = v.isoformat()
            elif isinstance(v, UUID):
                result[k] = str(v)
            elif v is None:
                result[k] = None
            else:
                result[k] = v
        return result

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        section_id: UUID | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Batch], int]:
        query = select(Batch)

        if is_active is not None:
            query = query.where(Batch.is_active == is_active)

        if section_id:
            query = query.where(Batch.section_id == section_id)

        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Batch.name.ilike(search_term),
                )
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.scalar(count_query)) or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(Batch.batch_number, Batch.name)

        result = await self.db.execute(query)
        batches = result.scalars().all()

        return list(batches), total

    async def get_by_id(self, batch_id: UUID) -> Batch | None:
        query = select(Batch).where(Batch.id == batch_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_section_and_name(self, section_id: UUID, name: str) -> Batch | None:
        result = await self.db.execute(
            select(Batch).where(Batch.section_id == section_id, Batch.name == name)
        )
        return result.scalar_one_or_none()

    async def create(self, data: BatchCreate, user_id: UUID | None = None) -> Batch:
        existing = await self.get_by_section_and_name(data.section_id, data.name)
        if existing:
            raise ValueError(f"Batch {data.name} for section {data.section_id} already exists")

        batch = Batch(**data.model_dump())
        self.db.add(batch)
        await self.db.flush()

        audit = AuditLog(
            user_id=user_id,
            action="CREATE",
            entity_type="BATCH",
            entity_id=batch.id,
            new_values=self._serialize_for_audit(data.model_dump()),
        )
        self.db.add(audit)
        await self.db.flush()
        return batch

    async def update(
        self, batch_id: UUID, data: BatchUpdate, user_id: UUID | None = None
    ) -> Batch | None:
        batch = await self.get_by_id(batch_id)
        if not batch:
            return None

        old_values = {
            "section_id": str(batch.section_id),
            "name": batch.name,
            "batch_number": batch.batch_number,
            "strength": batch.strength,
            "is_active": batch.is_active,
        }

        update_data = data.model_dump(exclude_unset=True)

        if "name" in update_data and update_data["name"] != batch.name:
            existing = await self.get_by_section_and_name(batch.section_id, update_data["name"])
            if existing and existing.id != batch_id:
                raise ValueError(f"Batch {update_data['name']} for this section already exists")

        for key, value in update_data.items():
            setattr(batch, key, value)

        new_values = {**old_values, **update_data}

        audit = AuditLog(
            user_id=user_id,
            action="UPDATE",
            entity_type="BATCH",
            entity_id=batch.id,
            old_values=self._serialize_for_audit(old_values),
            new_values=self._serialize_for_audit(new_values),
        )
        self.db.add(audit)
        await self.db.flush()
        return batch

    async def delete(self, batch_id: UUID, user_id: UUID | None = None) -> bool:
        batch = await self.get_by_id(batch_id)
        if not batch:
            return False

        old_values = {
            "section_id": str(batch.section_id),
            "name": batch.name,
            "batch_number": batch.batch_number,
            "strength": batch.strength,
        }

        audit = AuditLog(
            user_id=user_id,
            action="DELETE",
            entity_type="BATCH",
            entity_id=batch.id,
            old_values=old_values,
        )
        self.db.add(audit)

        await self.db.delete(batch)
        return True
