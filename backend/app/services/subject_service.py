from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.audit_log import AuditLog
from app.database.models.subject import Subject
from app.schemas.subject import SubjectCreate, SubjectUpdate


class SubjectService:
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
        subject_type: str | None = None,
        semester: int | None = None,
        department: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Subject], int]:
        query = select(Subject)

        if is_active is not None:
            query = query.where(Subject.is_active == is_active)

        if subject_type:
            query = query.where(Subject.subject_type == subject_type)

        if semester:
            query = query.where(Subject.semester == semester)

        if department:
            query = query.where(Subject.department == department)

        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Subject.code.ilike(search_term),
                    Subject.name.ilike(search_term),
                    Subject.department.ilike(search_term),
                )
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.scalar(count_query)) or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(Subject.code)

        result = await self.db.execute(query)
        subjects = result.scalars().all()

        return list(subjects), total

    async def get_by_id(self, subject_id: UUID) -> Subject | None:
        query = select(Subject).where(Subject.id == subject_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Subject | None:
        result = await self.db.execute(select(Subject).where(Subject.code == code))
        return result.scalar_one_or_none()

    async def create(self, data: SubjectCreate, user_id: UUID | None = None) -> Subject:
        existing = await self.get_by_code(data.code)
        if existing:
            raise ValueError(f"Subject with code {data.code} already exists")

        subject = Subject(**data.model_dump())
        self.db.add(subject)
        await self.db.flush()

        audit = AuditLog(
            user_id=user_id,
            action="CREATE",
            entity_type="SUBJECT",
            entity_id=subject.id,
            new_values=self._serialize_for_audit(data.model_dump()),
        )
        self.db.add(audit)
        await self.db.flush()
        return subject

    async def update(
        self, subject_id: UUID, data: SubjectUpdate, user_id: UUID | None = None
    ) -> Subject | None:
        subject = await self.get_by_id(subject_id)
        if not subject:
            return None

        old_values = {
            "code": subject.code,
            "name": subject.name,
            "subject_type": subject.subject_type,
            "credits": subject.credits,
            "theory_hours": subject.theory_hours,
            "practical_hours": subject.practical_hours,
            "tutorial_hours": subject.tutorial_hours,
            "semester": subject.semester,
            "department": subject.department,
            "is_active": subject.is_active,
        }

        update_data = data.model_dump(exclude_unset=True)

        if "code" in update_data and update_data["code"] != subject.code:
            existing = await self.get_by_code(update_data["code"])
            if existing and existing.id != subject_id:
                raise ValueError(f"Subject with code {update_data['code']} already exists")

        for key, value in update_data.items():
            setattr(subject, key, value)

        new_values = {**old_values, **update_data}

        audit = AuditLog(
            user_id=user_id,
            action="UPDATE",
            entity_type="SUBJECT",
            entity_id=subject.id,
            old_values=self._serialize_for_audit(old_values),
            new_values=self._serialize_for_audit(new_values),
        )
        self.db.add(audit)
        await self.db.flush()
        return subject

    async def delete(self, subject_id: UUID, user_id: UUID | None = None) -> bool:
        subject = await self.get_by_id(subject_id)
        if not subject:
            return False

        old_values = {
            "code": subject.code,
            "name": subject.name,
            "subject_type": subject.subject_type,
        }

        audit = AuditLog(
            user_id=user_id,
            action="DELETE",
            entity_type="SUBJECT",
            entity_id=subject.id,
            old_values=old_values,
        )
        self.db.add(audit)

        await self.db.delete(subject)
        return True
