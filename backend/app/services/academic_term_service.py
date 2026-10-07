from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.academic_term import AcademicTerm
from app.database.models.audit_log import AuditLog
from app.schemas.academic_term import AcademicTermCreate, AcademicTermUpdate


class AcademicTermService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _serialize_for_audit(self, data: dict) -> dict[str, Any]:
        """Serialize date/datetime objects for JSON storage"""
        result: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, (date, datetime)):
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
        is_active: bool | None = None,
        is_current: bool | None = None,
    ) -> tuple[list[AcademicTerm], int]:
        query = select(AcademicTerm)

        if is_active is not None:
            query = query.where(AcademicTerm.is_active == is_active)
        if is_current is not None:
            query = query.where(AcademicTerm.is_current == is_current)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.scalar(count_query)) or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(AcademicTerm.academic_year.desc(), AcademicTerm.semester.desc())

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_by_id(self, term_id: UUID) -> AcademicTerm | None:
        result = await self.db.execute(select(AcademicTerm).where(AcademicTerm.id == term_id))
        return result.scalar_one_or_none()

    async def get_current(self) -> AcademicTerm | None:
        result = await self.db.execute(select(AcademicTerm).where(AcademicTerm.is_current == True))
        return result.scalar_one_or_none()

    async def get_by_year_semester(self, academic_year: str, semester: int) -> AcademicTerm | None:
        result = await self.db.execute(
            select(AcademicTerm).where(
                AcademicTerm.academic_year == academic_year,
                AcademicTerm.semester == semester,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, data: AcademicTermCreate, user_id: UUID | None = None) -> AcademicTerm:
        # If this is set as current, unset other current terms
        if data.is_current:
            await self._unset_current_term()

        term = AcademicTerm(**data.model_dump())
        self.db.add(term)
        await self.db.flush()

        audit = AuditLog(
            user_id=user_id,
            action="CREATE",
            entity_type="ACADEMIC_TERM",
            entity_id=term.id,
            new_values=self._serialize_for_audit(data.model_dump()),
        )
        self.db.add(audit)
        await self.db.flush()
        return term

    async def update(
        self, term_id: UUID, data: AcademicTermUpdate, user_id: UUID | None = None
    ) -> AcademicTerm | None:
        term = await self.get_by_id(term_id)
        if not term:
            return None

        old_values = {
            "name": term.name,
            "academic_year": term.academic_year,
            "semester": term.semester,
            "start_date": term.start_date.isoformat(),
            "end_date": term.end_date.isoformat(),
            "is_active": term.is_active,
            "is_current": term.is_current,
        }

        update_data = data.model_dump(exclude_unset=True)

        # If setting as current, unset other current terms
        if update_data.get("is_current"):
            await self._unset_current_term(exclude_id=term_id)

        for key, value in update_data.items():
            setattr(term, key, value)

        new_values = {**old_values, **update_data}

        audit = AuditLog(
            user_id=user_id,
            action="UPDATE",
            entity_type="ACADEMIC_TERM",
            entity_id=term.id,
            old_values=self._serialize_for_audit(old_values),
            new_values=self._serialize_for_audit(new_values),
        )
        self.db.add(audit)
        await self.db.flush()
        return term

    async def delete(self, term_id: UUID, user_id: UUID | None = None) -> bool:
        term = await self.get_by_id(term_id)
        if not term:
            return False

        old_values = {
            "name": term.name,
            "academic_year": term.academic_year,
            "semester": term.semester,
        }

        audit = AuditLog(
            user_id=user_id,
            action="DELETE",
            entity_type="ACADEMIC_TERM",
            entity_id=term.id,
            old_values=old_values,
        )
        self.db.add(audit)

        await self.db.delete(term)
        return True

    async def _unset_current_term(self, exclude_id: UUID | None = None) -> None:
        query = select(AcademicTerm).where(AcademicTerm.is_current == True)
        if exclude_id:
            query = query.where(AcademicTerm.id != exclude_id)
        result = await self.db.execute(query)
        for term in result.scalars().all():
            term.is_current = False
