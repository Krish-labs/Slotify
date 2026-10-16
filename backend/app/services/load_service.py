from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models.academic_term import AcademicTerm
from app.database.models.audit_log import AuditLog
from app.database.models.batch import Batch
from app.database.models.class_model import Class
from app.database.models.faculty import Faculty
from app.database.models.faculty_load import FacultyLoad, SessionType
from app.database.models.section import Section
from app.database.models.subject import Subject
from app.schemas.load import FacultyLoadCreate, FacultyLoadImportPreview, FacultyLoadUpdate


class LoadService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _serialize_for_audit(self, data: dict) -> dict[str, Any]:
        """Serialize UUID, date/datetime objects for JSON storage"""
        from datetime import date, datetime

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
        faculty_id: UUID | None = None,
        academic_term_id: UUID | None = None,
        subject_id: UUID | None = None,
        class_id: UUID | None = None,
        section_id: UUID | None = None,
        session_type: SessionType | None = None,
        is_active: bool | None = None,
        is_approved: bool | None = None,
    ) -> tuple[list[FacultyLoad], int]:
        query = select(FacultyLoad).options(
            selectinload(FacultyLoad.faculty),
            selectinload(FacultyLoad.academic_term),
            selectinload(FacultyLoad.subject),
            selectinload(FacultyLoad.class_),
            selectinload(FacultyLoad.section),
            selectinload(FacultyLoad.batch),
        )

        if faculty_id:
            query = query.where(FacultyLoad.faculty_id == faculty_id)
        if academic_term_id:
            query = query.where(FacultyLoad.academic_term_id == academic_term_id)
        if subject_id:
            query = query.where(FacultyLoad.subject_id == subject_id)
        if class_id:
            query = query.where(FacultyLoad.class_id == class_id)
        if section_id:
            query = query.where(FacultyLoad.section_id == section_id)
        if session_type:
            query = query.where(FacultyLoad.session_type == session_type)
        if is_active is not None:
            query = query.where(FacultyLoad.is_active == is_active)
        if is_approved is not None:
            query = query.where(FacultyLoad.is_approved == is_approved)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = int(await self.db.scalar(count_query) or 0)

        # Apply pagination
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(FacultyLoad.created_at.desc())

        result = await self.db.execute(query)
        loads = result.scalars().all()

        return list(loads), total

    async def get_by_id(self, load_id: UUID) -> FacultyLoad | None:
        query = (
            select(FacultyLoad)
            .options(
                selectinload(FacultyLoad.faculty),
                selectinload(FacultyLoad.academic_term),
                selectinload(FacultyLoad.subject),
                selectinload(FacultyLoad.class_),
                selectinload(FacultyLoad.section),
                selectinload(FacultyLoad.batch),
            )
            .where(FacultyLoad.id == load_id)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(self, data: FacultyLoadCreate, user_id: UUID | None = None) -> FacultyLoad:
        # Validate references
        await self._validate_references(data)

        # Check for duplicate
        existing = await self._check_duplicate(data)
        if existing:
            raise ValueError(
                "Duplicate load record exists for this faculty, subject, class, section, batch, and session type"
            )

        load = FacultyLoad(**data.model_dump())
        self.db.add(load)
        await self.db.flush()

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="CREATE",
            entity_type="FACULTY_LOAD",
            entity_id=load.id,
            new_values=self._serialize_for_audit(data.model_dump()),
        )
        self.db.add(audit)
        await self.db.flush()
        return load

    async def update(
        self, load_id: UUID, data: FacultyLoadUpdate, user_id: UUID | None = None
    ) -> FacultyLoad | None:
        load = await self.get_by_id(load_id)
        if not load:
            return None

        old_values = {
            "theory_hours": load.theory_hours,
            "practical_hours": load.practical_hours,
            "tutorial_hours": load.tutorial_hours,
            "project_hours": load.project_hours,
            "session_duration": load.session_duration,
            "required_resource_type": (
                load.required_resource_type.value if load.required_resource_type else None
            ),
            "notes": load.notes,
            "is_active": load.is_active,
            "is_approved": load.is_approved,
        }

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key in ("required_resource_type", "session_type") and value is not None:
                setattr(load, key, value)
            else:
                setattr(load, key, value)

        new_values = {**old_values, **update_data}

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="UPDATE",
            entity_type="FACULTY_LOAD",
            entity_id=load.id,
            old_values=old_values,
            new_values=new_values,
        )
        self.db.add(audit)
        await self.db.flush()
        return load

    async def approve(self, load_id: UUID, approved_by: UUID) -> FacultyLoad | None:
        load = await self.get_by_id(load_id)
        if not load:
            return None

        old_values = {
            "is_approved": load.is_approved,
            "approved_by": str(load.approved_by) if load.approved_by else None,
            "approved_at": load.approved_at.isoformat() if load.approved_at else None,
        }

        load.is_approved = True
        load.approved_by = approved_by
        load.approved_at = datetime.now(UTC)

        new_values = {
            "is_approved": load.is_approved,
            "approved_by": str(load.approved_by),
            "approved_at": load.approved_at.isoformat(),
        }

        # Audit log
        audit = AuditLog(
            user_id=approved_by,
            action="APPROVE",
            entity_type="FACULTY_LOAD",
            entity_id=load.id,
            old_values=old_values,
            new_values=new_values,
        )
        self.db.add(audit)
        await self.db.flush()
        return load

    async def delete(self, load_id: UUID, user_id: UUID | None = None) -> bool:
        load = await self.get_by_id(load_id)
        if not load:
            return False

        old_values = {
            "faculty_id": str(load.faculty_id),
            "academic_term_id": str(load.academic_term_id),
            "subject_id": str(load.subject_id),
            "class_id": str(load.class_id),
            "section_id": str(load.section_id),
            "batch_id": str(load.batch_id) if load.batch_id else None,
            "session_type": load.session_type.value,
        }

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="DELETE",
            entity_type="FACULTY_LOAD",
            entity_id=load.id,
            old_values=old_values,
        )
        self.db.add(audit)

        await self.db.delete(load)
        return True

    async def _validate_references(self, data: FacultyLoadCreate) -> None:
        # Check faculty exists
        faculty = await self.db.get(Faculty, data.faculty_id)
        if not faculty:
            raise ValueError(f"Faculty with id {data.faculty_id} not found")

        # Check academic term exists
        term = await self.db.get(AcademicTerm, data.academic_term_id)
        if not term:
            raise ValueError(f"Academic term with id {data.academic_term_id} not found")

        # Check subject exists
        subject = await self.db.get(Subject, data.subject_id)
        if not subject:
            raise ValueError(f"Subject with id {data.subject_id} not found")

        # Check class exists
        class_ = await self.db.get(Class, data.class_id)
        if not class_:
            raise ValueError(f"Class with id {data.class_id} not found")

        # Check section exists and belongs to class
        section = await self.db.get(Section, data.section_id)
        if not section:
            raise ValueError(f"Section with id {data.section_id} not found")
        if section.class_id != data.class_id:
            raise ValueError(f"Section {data.section_id} does not belong to class {data.class_id}")

        # Check batch if provided
        if data.batch_id:
            batch = await self.db.get(Batch, data.batch_id)
            if not batch:
                raise ValueError(f"Batch with id {data.batch_id} not found")
            if batch.section_id != data.section_id:
                raise ValueError(
                    f"Batch {data.batch_id} does not belong to section {data.section_id}"
                )

        # Practical sessions must have a batch
        if data.session_type == SessionType.PRACTICAL and not data.batch_id:
            raise ValueError("Practical sessions require a batch assignment")

    async def _check_duplicate(self, data: FacultyLoadCreate) -> FacultyLoad | None:
        query = select(FacultyLoad).where(
            FacultyLoad.faculty_id == data.faculty_id,
            FacultyLoad.academic_term_id == data.academic_term_id,
            FacultyLoad.subject_id == data.subject_id,
            FacultyLoad.class_id == data.class_id,
            FacultyLoad.section_id == data.section_id,
            FacultyLoad.batch_id == data.batch_id,
            FacultyLoad.session_type == data.session_type,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def preview_import(self, df) -> list[FacultyLoadImportPreview]:
        """Preview Excel import with validation"""
        from app.processors.load_normalizer import LoadNormalizer
        from app.validators.load_validator import LoadValidator

        validator = LoadValidator()
        validator.validate_dataframe(df)

        normalizer = LoadNormalizer(self.db)
        previews = []

        for idx, row in df.iterrows():
            row_data = row.to_dict()
            row_errors = []
            row_warnings = []

            # Validate individual row
            row_validation = validator.validate_load_records([row_data])
            row_errors.extend(row_validation.errors)
            row_warnings.extend(row_validation.warnings)

            # Try to normalize
            try:
                normalized = await normalizer.normalize(df.iloc[[idx]])
                if not normalized:
                    row_errors.append("Could not normalize row - missing reference data")
            except Exception as e:
                row_errors.append(f"Normalization error: {str(e)}")

            previews.append(
                FacultyLoadImportPreview(
                    row_index=idx,
                    data=row_data,
                    errors=row_errors,
                    warnings=row_warnings,
                )
            )

        return previews

    async def import_from_excel(self, file_path: str, user_id: UUID | None = None) -> dict:
        from app.importers.excel_loader import ExcelLoader

        loader = ExcelLoader()
        df = loader.load_load_distribution(file_path)

        previews = await self.preview_import(df)

        valid_previews = [p for p in previews if not p.errors]
        invalid_count = len(previews) - len(valid_previews)

        if invalid_count > 0:
            raise ValueError(f"Import validation failed: {invalid_count} rows have errors")

        # Normalize and save
        from app.processors.load_normalizer import LoadNormalizer

        normalizer = LoadNormalizer(self.db)
        normalized_records = await normalizer.normalize(df)

        saved_count = 0
        for record in normalized_records:
            load = FacultyLoad(**record)
            self.db.add(load)
            saved_count += 1
        return {
            "imported": saved_count,
            "warnings": [],
            "previews": previews,
        }

    async def get_faculty_load_summary(self, academic_term_id: UUID) -> list[dict[str, Any]]:
        """Get faculty-wise load summary for an academic term"""
        query = (
            select(
                FacultyLoad.faculty_id,
                Faculty.first_name,
                Faculty.last_name,
                Faculty.employee_id,
                func.sum(
                    FacultyLoad.theory_hours
                    + FacultyLoad.practical_hours
                    + FacultyLoad.tutorial_hours
                    + FacultyLoad.project_hours
                ).label("total_hours"),
                func.sum(FacultyLoad.theory_hours).label("theory_hours"),
                func.sum(FacultyLoad.practical_hours).label("practical_hours"),
                func.sum(FacultyLoad.tutorial_hours).label("tutorial_hours"),
                func.sum(FacultyLoad.project_hours).label("project_hours"),
            )
            .join(Faculty)
            .where(
                FacultyLoad.academic_term_id == academic_term_id,
                FacultyLoad.is_active == True,
            )
            .group_by(
                FacultyLoad.faculty_id,
                Faculty.first_name,
                Faculty.last_name,
                Faculty.employee_id,
            )
        )

        result = await self.db.execute(query)
        return [
            {
                "faculty_id": row.faculty_id,
                "employee_id": row.employee_id,
                "name": f"{row.first_name} {row.last_name}",
                "total_hours": row.total_hours or 0,
                "theory_hours": row.theory_hours or 0,
                "practical_hours": row.practical_hours or 0,
                "tutorial_hours": row.tutorial_hours or 0,
                "project_hours": row.project_hours or 0,
            }
            for row in result
        ]

    async def get_class_load_summary(self, academic_term_id: UUID) -> list[dict[str, Any]]:
        """Get class-wise load summary for an academic term"""
        query = (
            select(
                FacultyLoad.class_id,
                Class.name,
                Class.year,
                Class.branch,
                func.sum(
                    FacultyLoad.theory_hours
                    + FacultyLoad.practical_hours
                    + FacultyLoad.tutorial_hours
                    + FacultyLoad.project_hours
                ).label("total_hours"),
            )
            .join(Class)
            .where(
                FacultyLoad.academic_term_id == academic_term_id,
                FacultyLoad.is_active == True,
            )
            .group_by(
                FacultyLoad.class_id,
                Class.name,
                Class.year,
                Class.branch,
            )
        )

        result = await self.db.execute(query)
        return [
            {
                "class_id": row.class_id,
                "name": row.name,
                "year": row.year,
                "branch": row.branch,
                "total_hours": row.total_hours or 0,
            }
            for row in result
        ]

    async def get_subject_load_summary(self, academic_term_id: UUID) -> list[dict[str, Any]]:
        """Get subject-wise load summary for an academic term"""
        query = (
            select(
                FacultyLoad.subject_id,
                Subject.code,
                Subject.name,
                func.sum(
                    FacultyLoad.theory_hours
                    + FacultyLoad.practical_hours
                    + FacultyLoad.tutorial_hours
                    + FacultyLoad.project_hours
                ).label("total_hours"),
            )
            .join(Subject)
            .where(
                FacultyLoad.academic_term_id == academic_term_id,
                FacultyLoad.is_active == True,
            )
            .group_by(
                FacultyLoad.subject_id,
                Subject.code,
                Subject.name,
            )
        )

        result = await self.db.execute(query)
        return [
            {
                "subject_id": row.subject_id,
                "code": row.code,
                "name": row.name,
                "total_hours": row.total_hours or 0,
            }
            for row in result
        ]
