from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.audit_log import AuditLog
from app.database.models.class_model import Class
from app.schemas.class_schema import ClassCreate, ClassUpdate


class ClassService:
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
        academic_year: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Class], int]:
        query = select(Class)

        if is_active is not None:
            query = query.where(Class.is_active == is_active)

        if academic_year:
            query = query.where(Class.academic_year == academic_year)

        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Class.name.ilike(search_term),
                    Class.branch.ilike(search_term),
                    Class.academic_year.ilike(search_term),
                )
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.scalar(count_query)) or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(Class.academic_year.desc(), Class.year, Class.name)

        result = await self.db.execute(query)
        classes = result.scalars().all()

        return list(classes), total

    async def get_by_id(self, class_id: UUID) -> Class | None:
        query = select(Class).where(Class.id == class_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_name_year(self, name: str, academic_year: str) -> Class | None:
        result = await self.db.execute(
            select(Class).where(Class.name == name, Class.academic_year == academic_year)
        )
        return result.scalar_one_or_none()

    async def create(self, data: ClassCreate, user_id: UUID | None = None) -> Class:
        existing = await self.get_by_name_year(data.name, data.academic_year)
        if existing:
            raise ValueError(
                f"Class {data.name} for academic year {data.academic_year} already exists"
            )

        class_obj = Class(**data.model_dump())
        self.db.add(class_obj)
        await self.db.flush()

        audit = AuditLog(
            user_id=user_id,
            action="CREATE",
            entity_type="CLASS",
            entity_id=class_obj.id,
            new_values=self._serialize_for_audit(data.model_dump()),
        )
        self.db.add(audit)
        await self.db.flush()
        return class_obj

    async def update(
        self, class_id: UUID, data: ClassUpdate, user_id: UUID | None = None
    ) -> Class | None:
        class_obj = await self.get_by_id(class_id)
        if not class_obj:
            return None

        old_values = {
            "name": class_obj.name,
            "year": class_obj.year,
            "branch": class_obj.branch,
            "academic_year": class_obj.academic_year,
            "strength": class_obj.strength,
            "is_active": class_obj.is_active,
        }

        update_data = data.model_dump(exclude_unset=True)

        if "name" in update_data or "academic_year" in update_data:
            new_name = update_data.get("name", class_obj.name)
            new_year = update_data.get("academic_year", class_obj.academic_year)
            if new_name != class_obj.name or new_year != class_obj.academic_year:
                existing = await self.get_by_name_year(new_name, new_year)
                if existing and existing.id != class_id:
                    raise ValueError(
                        f"Class {new_name} for academic year {new_year} already exists"
                    )

        for key, value in update_data.items():
            setattr(class_obj, key, value)

        new_values = {**old_values, **update_data}

        audit = AuditLog(
            user_id=user_id,
            action="UPDATE",
            entity_type="CLASS",
            entity_id=class_obj.id,
            old_values=self._serialize_for_audit(old_values),
            new_values=self._serialize_for_audit(new_values),
        )
        self.db.add(audit)
        await self.db.flush()
        return class_obj

    async def delete(self, class_id: UUID, user_id: UUID | None = None) -> bool:
        class_obj = await self.get_by_id(class_id)
        if not class_obj:
            return False

        old_values = {
            "name": class_obj.name,
            "year": class_obj.year,
            "branch": class_obj.branch,
            "academic_year": class_obj.academic_year,
        }

        audit = AuditLog(
            user_id=user_id,
            action="DELETE",
            entity_type="CLASS",
            entity_id=class_obj.id,
            old_values=old_values,
        )
        self.db.add(audit)

        await self.db.delete(class_obj)
        return True
