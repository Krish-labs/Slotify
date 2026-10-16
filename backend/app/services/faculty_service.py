from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.audit_log import AuditLog
from app.database.models.faculty import Faculty
from app.schemas.faculty import FacultyCreate, FacultyUpdate


class FacultyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        department: str | None = None,
        is_active: bool | None = None,
        include_archived: bool = False,
    ) -> tuple[list[Faculty], int]:
        query = select(Faculty)

        if not include_archived:
            query = query.where(Faculty.is_archived == False)

        if is_active is not None:
            query = query.where(Faculty.is_active == is_active)

        if department:
            query = query.where(Faculty.department == department)

        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Faculty.first_name.ilike(search_term),
                    Faculty.last_name.ilike(search_term),
                    Faculty.email.ilike(search_term),
                    Faculty.employee_id.ilike(search_term),
                )
            )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.scalar(count_query)) or 0

        # Apply pagination
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(Faculty.last_name, Faculty.first_name)

        result = await self.db.execute(query)
        faculty_list = result.scalars().all()

        return list(faculty_list), total

    async def get_by_id(self, faculty_id: UUID, include_archived: bool = False) -> Faculty | None:
        query = select(Faculty).where(Faculty.id == faculty_id)
        if not include_archived:
            query = query.where(Faculty.is_archived == False)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_employee_id(self, employee_id: str) -> Faculty | None:
        result = await self.db.execute(select(Faculty).where(Faculty.employee_id == employee_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Faculty | None:
        result = await self.db.execute(select(Faculty).where(Faculty.email == email))
        return result.scalar_one_or_none()

    def _serialize_for_audit(self, data: dict) -> dict[str, Any]:
        """Serialize date/datetime objects for JSON storage"""
        from datetime import date, datetime

        result: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, date | datetime):
                result[k] = v.isoformat()
            elif v is None:
                result[k] = None
            else:
                result[k] = v
        return result

    async def create(self, data: FacultyCreate, user_id: UUID | None = None) -> Faculty:
        faculty = Faculty(**data.model_dump())
        self.db.add(faculty)
        await self.db.flush()

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="CREATE",
            entity_type="FACULTY",
            entity_id=faculty.id,
            new_values=self._serialize_for_audit(data.model_dump()),
        )
        self.db.add(audit)
        await self.db.flush()
        return faculty

    async def update(
        self, faculty_id: UUID, data: FacultyUpdate, user_id: UUID | None = None
    ) -> Faculty | None:
        faculty = await self.get_by_id(faculty_id)
        if not faculty:
            return None

        old_values = {
            "first_name": faculty.first_name,
            "last_name": faculty.last_name,
            "email": faculty.email,
            "phone": faculty.phone,
            "department": faculty.department,
            "designation": faculty.designation,
            "joining_date": faculty.joining_date.isoformat() if faculty.joining_date else None,
            "is_active": faculty.is_active,
        }

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(faculty, key, value)

        new_values = {**old_values, **update_data}

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="UPDATE",
            entity_type="FACULTY",
            entity_id=faculty.id,
            old_values=old_values,
            new_values=new_values,
        )
        self.db.add(audit)
        await self.db.flush()
        return faculty

    async def archive(self, faculty_id: UUID, archived_by: UUID) -> Faculty | None:
        faculty = await self.get_by_id(faculty_id, include_archived=True)
        if not faculty:
            return None

        old_values = {
            "is_active": faculty.is_active,
            "is_archived": faculty.is_archived,
            "archived_at": faculty.archived_at.isoformat() if faculty.archived_at else None,
            "archived_by": str(faculty.archived_by) if faculty.archived_by else None,
        }

        faculty.is_archived = True
        faculty.is_active = False
        faculty.archived_at = datetime.now(UTC)
        faculty.archived_by = archived_by

        new_values = {
            "is_active": faculty.is_active,
            "is_archived": faculty.is_archived,
            "archived_at": faculty.archived_at.isoformat(),
            "archived_by": str(faculty.archived_by),
        }

        # Audit log
        audit = AuditLog(
            user_id=archived_by,
            action="ARCHIVE",
            entity_type="FACULTY",
            entity_id=faculty.id,
            old_values=old_values,
            new_values=new_values,
        )
        self.db.add(audit)
        await self.db.flush()
        return faculty

    async def restore(self, faculty_id: UUID, user_id: UUID) -> Faculty | None:
        faculty = await self.get_by_id(faculty_id, include_archived=True)
        if not faculty:
            return None

        old_values = {
            "is_active": faculty.is_active,
            "is_archived": faculty.is_archived,
            "archived_at": faculty.archived_at.isoformat() if faculty.archived_at else None,
            "archived_by": str(faculty.archived_by) if faculty.archived_by else None,
        }

        faculty.is_archived = False
        faculty.is_active = True
        faculty.archived_at = None
        faculty.archived_by = None

        new_values = {
            "is_active": faculty.is_active,
            "is_archived": faculty.is_archived,
            "archived_at": None,
            "archived_by": None,
        }

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="RESTORE",
            entity_type="FACULTY",
            entity_id=faculty.id,
            old_values=old_values,
            new_values=new_values,
        )
        self.db.add(audit)
        await self.db.flush()
        return faculty

    async def delete(self, faculty_id: UUID, user_id: UUID | None = None) -> bool:
        faculty = await self.get_by_id(faculty_id, include_archived=True)
        if not faculty:
            return False

        old_values = {
            "employee_id": faculty.employee_id,
            "first_name": faculty.first_name,
            "last_name": faculty.last_name,
            "email": faculty.email,
        }

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="DELETE",
            entity_type="FACULTY",
            entity_id=faculty.id,
            old_values=old_values,
        )
        self.db.add(audit)

        await self.db.delete(faculty)
        return True

    async def get_total_load(self, faculty_id: UUID, academic_term_id: UUID | None = None) -> int:
        from app.database.models.faculty_load import FacultyLoad

        query = select(
            func.sum(
                FacultyLoad.theory_hours
                + FacultyLoad.practical_hours
                + FacultyLoad.tutorial_hours
                + FacultyLoad.project_hours
            )
        ).where(
            FacultyLoad.faculty_id == faculty_id,
            FacultyLoad.is_active == True,
        )

        if academic_term_id:
            query = query.where(FacultyLoad.academic_term_id == academic_term_id)

        result = await self.db.execute(query)
        return result.scalar() or 0
