from typing import Any
from uuid import UUID

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.academic_term import AcademicTerm
from app.database.models.batch import Batch
from app.database.models.class_model import Class
from app.database.models.faculty import Faculty
from app.database.models.faculty_load import ResourceType, SessionType
from app.database.models.section import Section
from app.database.models.subject import Subject


class LoadNormalizer:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def normalize(self, df: pd.DataFrame) -> list[dict]:
        # Get existing entities from database
        faculty_map = await self._get_faculty_map()
        academic_term_map = await self._get_academic_term_map()
        subject_map = await self._get_subject_map()
        class_map = await self._get_class_map()
        section_map = await self._get_section_map()
        batch_map = await self._get_batch_map()

        normalized = []
        for _, row in df.iterrows():
            record = await self._normalize_row(
                row, faculty_map, academic_term_map, subject_map, class_map, section_map, batch_map
            )
            if record:
                normalized.append(record)

        return normalized

    async def _get_faculty_map(self) -> dict[str, UUID]:
        result = await self.db.execute(select(Faculty.employee_id, Faculty.id))
        return {row.employee_id: row.id for row in result}

    async def _get_academic_term_map(self) -> dict[str, UUID]:
        result = await self.db.execute(
            select(AcademicTerm.academic_year, AcademicTerm.semester, AcademicTerm.id)
        )
        return {f"{row.academic_year}-{row.semester}": row.id for row in result}

    async def _get_subject_map(self) -> dict[str, UUID]:
        result = await self.db.execute(select(Subject.code, Subject.id))
        return {row.code: row.id for row in result}

    async def _get_class_map(self) -> dict[str, UUID]:
        result = await self.db.execute(select(Class.name, Class.id))
        return {row.name: row.id for row in result}

    async def _get_section_map(self) -> dict[tuple[Any, Any], UUID]:
        result = await self.db.execute(select(Section.id, Section.class_id, Section.name))
        section_map: dict[tuple[Any, Any], UUID] = {}
        for row in result:
            class_result = await self.db.execute(select(Class.name).where(Class.id == row.class_id))
            class_name = class_result.scalar_one_or_none()
            if class_name:
                section_map[(class_name, row.name)] = row.id
        return section_map

    async def _get_batch_map(self) -> dict[tuple[Any, Any], UUID]:
        result = await self.db.execute(select(Batch.id, Batch.section_id, Batch.name))
        batch_map: dict[tuple[Any, Any], UUID] = {}
        for row in result:
            batch_map[(row.section_id, row.name)] = row.id
        return batch_map

    async def _normalize_row(
        self,
        row: pd.Series,
        faculty_map: dict,
        academic_term_map: dict,
        subject_map: dict,
        class_map: dict,
        section_map: dict,
        batch_map: dict,
    ) -> dict | None:
        # Map faculty by employee_id
        faculty_key = str(row.get("faculty_employee_id", "")).strip()
        if faculty_key not in faculty_map:
            return None

        # Map academic term
        academic_year = str(row.get("academic_year", "")).strip()
        semester = int(row.get("semester", 0))
        term_key = f"{academic_year}-{semester}"
        if term_key not in academic_term_map:
            return None

        # Map subject
        subject_code = str(row.get("subject_code", "")).strip()
        if subject_code not in subject_map:
            return None

        # Map class
        class_name = str(row.get("class_name", "")).strip()
        if class_name not in class_map:
            return None
        class_id = class_map[class_name]

        # Map section
        section_name = str(row.get("section", "")).strip()
        section_key = (class_name, section_name)
        if section_key not in section_map:
            return None
        section_id = section_map[section_key]

        # Map batch if provided
        batch_id = None
        batch_name = str(row.get("batch", "")).strip()
        if batch_name:
            batch_key = (section_id, batch_name)
            if batch_key in batch_map:
                batch_id = batch_map[batch_key]

        # Map session_type
        session_type_str = str(row.get("session_type", "THEORY")).strip().upper()
        try:
            session_type = SessionType(session_type_str)
        except ValueError:
            session_type = SessionType.THEORY

        # Map required_resource_type
        resource_type_str = str(row.get("required_resource_type", "NONE")).strip().upper()
        try:
            required_resource_type = ResourceType(resource_type_str)
        except ValueError:
            required_resource_type = ResourceType.NONE

        # Parse hours
        theory_hours = int(pd.to_numeric(row.get("theory_hours", 0), errors="coerce") or 0)
        practical_hours = int(pd.to_numeric(row.get("practical_hours", 0), errors="coerce") or 0)
        tutorial_hours = int(pd.to_numeric(row.get("tutorial_hours", 0), errors="coerce") or 0)
        project_hours = int(pd.to_numeric(row.get("project_hours", 0), errors="coerce") or 0)
        session_duration = int(pd.to_numeric(row.get("session_duration", 1), errors="coerce") or 1)

        notes = str(row.get("notes", "")).strip() if pd.notna(row.get("notes")) else None

        return {
            "faculty_id": faculty_map[faculty_key],
            "academic_term_id": academic_term_map[term_key],
            "subject_id": subject_map[subject_code],
            "class_id": class_id,
            "section_id": section_id,
            "batch_id": batch_id,
            "session_type": session_type,
            "theory_hours": theory_hours,
            "practical_hours": practical_hours,
            "tutorial_hours": tutorial_hours,
            "project_hours": project_hours,
            "session_duration": session_duration,
            "required_resource_type": required_resource_type,
            "notes": notes,
        }
