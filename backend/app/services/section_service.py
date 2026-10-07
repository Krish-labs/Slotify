from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.audit_log import AuditLog
from app.database.models.section import Section
from app.schemas.section import SectionCreate, SectionUpdate


class SectionService:
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
        class_id: UUID | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Section], int]:
        query = select(Section)

        if is_active is not None:
            query = query.where(Section.is_active == is_active)

        if class_id:
            query = query.where(Section.class_id == class_id)

        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Section.name.ilike(search_term),
                )
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.scalar(count_query)) or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(Section.name)

        result = await self.db.execute(query)
        sections = result.scalars().all()

        return list(sections), total

    async def get_by_id(self, section_id: UUID) -> Section | None:
        query = select(Section).where(Section.id == section_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_class_and_name(self, class_id: UUID, name: str) -> Section | None:
        result = await self.db.execute(
            select(Section).where(Section.class_id == class_id, Section.name == name)
        )
        return result.scalar_one_or_none()

    async def create(self, data: SectionCreate, user_id: UUID | None = None) -> Section:
        existing = await self.get_by_class_and_name(data.class_id, data.name)
        if existing:
            raise ValueError(f"Section {data.name} for class {data.class_id} already exists")

        section = Section(**data.model_dump())
        self.db.add(section)
        await self.db.flush()

        audit = AuditLog(
            user_id=user_id,
            action="CREATE",
            entity_type="SECTION",
            entity_id=section.id,
            new_values=self._serialize_for_audit(data.model_dump()),
        )
        self.db.add(audit)
        await self.db.flush()
        return section

    async def update(
        self, section_id: UUID, data: SectionUpdate, user_id: UUID | None = None
    ) -> Section | None:
        section = await self.get_by_id(section_id)
        if not section:
            return None

        old_values = {
            "class_id": str(section.class_id),
            "name": section.name,
            "strength": section.strength,
            "is_active": section.is_active,
        }

        update_data = data.model_dump(exclude_unset=True)

        if "name" in update_data and update_data["name"] != section.name:
            existing = await self.get_by_class_and_name(section.class_id, update_data["name"])
            if existing and existing.id != section_id:
                raise ValueError(f"Section {update_data['name']} for this class already exists")

        for key, value in update_data.items():
            setattr(section, key, value)

        new_values = {**old_values, **update_data}

        audit = AuditLog(
            user_id=user_id,
            action="UPDATE",
            entity_type="SECTION",
            entity_id=section.id,
            old_values=self._serialize_for_audit(old_values),
            new_values=self._serialize_for_audit(new_values),
        )
        self.db.add(audit)
        await self.db.flush()
        return section

    async def delete(self, section_id: UUID, user_id: UUID | None = None) -> bool:
        section = await self.get_by_id(section_id)
        if not section:
            return False

        old_values = {
            "class_id": str(section.class_id),
            "name": section.name,
            "strength": section.strength,
        }

        audit = AuditLog(
            user_id=user_id,
            action="DELETE",
            entity_type="SECTION",
            entity_id=section.id,
            old_values=old_values,
        )
        self.db.add(audit)

        await self.db.delete(section)
        return True
