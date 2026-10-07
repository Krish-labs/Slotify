from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.audit_log import AuditLog
from app.database.models.resource import Resource
from app.schemas.resource import ResourceCreate, ResourceUpdate


class ResourceService:
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
        resource_type: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Resource], int]:
        query = select(Resource)

        if is_active is not None:
            query = query.where(Resource.is_active == is_active)

        if resource_type:
            query = query.where(Resource.resource_type == resource_type)

        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Resource.name.ilike(search_term),
                    Resource.building.ilike(search_term),
                    Resource.room_number.ilike(search_term),
                )
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.scalar(count_query)) or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(Resource.name)

        result = await self.db.execute(query)
        resources = result.scalars().all()

        return list(resources), total

    async def get_by_id(self, resource_id: UUID) -> Resource | None:
        query = select(Resource).where(Resource.id == resource_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Resource | None:
        result = await self.db.execute(select(Resource).where(Resource.name == name))
        return result.scalar_one_or_none()

    async def create(self, data: ResourceCreate, user_id: UUID | None = None) -> Resource:
        existing = await self.get_by_name(data.name)
        if existing:
            raise ValueError(f"Resource with name {data.name} already exists")

        resource = Resource(**data.model_dump())
        self.db.add(resource)
        await self.db.flush()

        audit = AuditLog(
            user_id=user_id,
            action="CREATE",
            entity_type="RESOURCE",
            entity_id=resource.id,
            new_values=self._serialize_for_audit(data.model_dump()),
        )
        self.db.add(audit)
        await self.db.flush()
        return resource

    async def update(
        self, resource_id: UUID, data: ResourceUpdate, user_id: UUID | None = None
    ) -> Resource | None:
        resource = await self.get_by_id(resource_id)
        if not resource:
            return None

        old_values = {
            "name": resource.name,
            "resource_type": resource.resource_type,
            "capacity": resource.capacity,
            "building": resource.building,
            "floor": resource.floor,
            "room_number": resource.room_number,
            "features": resource.features,
            "is_emergency": resource.is_emergency,
            "is_active": resource.is_active,
        }

        update_data = data.model_dump(exclude_unset=True)

        if "name" in update_data and update_data["name"] != resource.name:
            existing = await self.get_by_name(update_data["name"])
            if existing and existing.id != resource_id:
                raise ValueError(f"Resource with name {update_data['name']} already exists")

        for key, value in update_data.items():
            setattr(resource, key, value)

        new_values = {**old_values, **update_data}

        audit = AuditLog(
            user_id=user_id,
            action="UPDATE",
            entity_type="RESOURCE",
            entity_id=resource.id,
            old_values=self._serialize_for_audit(old_values),
            new_values=self._serialize_for_audit(new_values),
        )
        self.db.add(audit)
        await self.db.flush()
        return resource

    async def delete(self, resource_id: UUID, user_id: UUID | None = None) -> bool:
        resource = await self.get_by_id(resource_id)
        if not resource:
            return False

        old_values = {
            "name": resource.name,
            "resource_type": resource.resource_type,
            "capacity": resource.capacity,
        }

        audit = AuditLog(
            user_id=user_id,
            action="DELETE",
            entity_type="RESOURCE",
            entity_id=resource.id,
            old_values=old_values,
        )
        self.db.add(audit)

        await self.db.delete(resource)
        return True
