from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.academic_term import AcademicTerm
from app.database.models.audit_log import AuditLog
from app.database.models.batch import Batch
from app.database.models.class_model import Class
from app.database.models.faculty import Faculty
from app.database.models.faculty_load import FacultyLoad, SessionType
from app.database.models.load_distribution_source import LoadDistributionSourceRow
from app.database.models.section import Section
from app.database.models.subject import Subject

SOURCE_COLUMNS = (
    "serial_number",
    "faculty_name",
    "designation",
    "class_name",
    "subject_name",
    "theory",
    "practical",
    "tutorial",
    "project_stage",
    "total_load",
    "sign",
)


class WorkbookParseError(ValueError):
    """A source workbook could not be read or did not match its contract."""

    def __init__(
        self,
        message: str,
        *,
        sheet: str | None = None,
        row: int | None = None,
        field: str | None = None,
    ):
        super().__init__(message)
        self.sheet = sheet
        self.row = row
        self.field = field

    def diagnostics(self) -> dict[str, str | int | None]:
        return {
            "sheet": self.sheet,
            "row": self.row,
            "field": self.field,
            "message": str(self),
        }


MAPPING_COLUMNS = (
    "faculty_id",
    "subject_id",
    "class_id",
    "section_id",
    "batch_id",
    "academic_term_id",
)


def _cell(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).replace("\n", " ").strip()
    if not text:
        return None
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def _calculated_total(values: dict[str, Any]) -> str:
    total = 0.0
    for field in ("theory", "practical", "tutorial", "project_stage"):
        try:
            total += float(values.get(field) or 0)
        except (TypeError, ValueError):
            continue
    return str(int(total)) if total.is_integer() else str(total)


def _semester_label(frame: pd.DataFrame, header_row: int, section_number: int) -> str:
    context = " ".join(
        str(value) for value in frame.iloc[:header_row].astype(str).values.ravel() if value != "nan"
    )
    match = re.search(r"A\.Y\.\s*(\d{4}-\d{2})", context)
    if section_number == 2:
        year_match = re.search(r"SEMESTER\s+II[_ ](\d{2,4}-\d{2})", context, re.I)
        year = year_match.group(1) if year_match else (match.group(1) if match else "")
        if year and len(year.split("-", 1)[0]) == 2:
            year = f"20{year}"
        return f"Semester II • {year}" if year else "Semester II"
    year = match.group(1) if match else ""
    return f"Semester I • {year}" if year else "Semester I"


def parse_source_workbook(
    path: str | Path, faculty_workbook: str | Path | None = None
) -> list[dict[str, Any]]:
    workbook = Path(path)
    if not workbook.exists():
        raise WorkbookParseError(f"Source workbook not found: {workbook}")
    if not workbook.is_file():
        raise WorkbookParseError(f"Source workbook is not a file: {workbook}")
    if not workbook.stat().st_mode & 0o444:
        raise WorkbookParseError(f"Source workbook is not readable: {workbook}")

    try:
        sheets = pd.ExcelFile(workbook).sheet_names
    except Exception as exc:  # noqa: BLE001 - preserve a useful boundary error
        raise WorkbookParseError(f"Unable to open Excel workbook {workbook.name}: {exc}") from exc
    if "Sheet1" not in sheets:
        raise WorkbookParseError(
            f"Expected source sheet 'Sheet1'; found {', '.join(sheets) or 'no sheets'}",
            field="sheet_name",
        )
    try:
        frame = pd.read_excel(workbook, sheet_name="Sheet1", header=None)
    except Exception as exc:  # noqa: BLE001 - preserve a useful boundary error
        raise WorkbookParseError(
            f"Unable to read source sheet 'Sheet1': {exc}", sheet="Sheet1"
        ) from exc
    rows: list[dict[str, Any]] = []
    section_number = 0
    active_faculty: str | None = None
    active_class: str | None = None

    section_headers = 0
    for index, raw in frame.iterrows():
        values = [_cell(value) for value in raw.iloc[:11].tolist()]
        values.extend([None] * (11 - len(values)))
        first, second = values[0], values[1]
        if first and first.lower().startswith("sr.") and second == "Name of Faculty":
            section_number += 1
            section_headers += 1
            active_faculty = None
            active_class = None
            continue
        if not section_number or (first and first.lower() == "total"):
            continue
        if not any(values):
            continue
        if values[5:9] == ["Theory", "Practical", "Tutorial", "Project Stage 1"]:
            continue
        if not any(values[3:5]):
            continue
        if first and first.isdigit():
            active_faculty = second
            active_class = None
        effective_faculty = second or active_faculty
        if values[3]:
            active_class = values[3]
        data: dict[str, Any] = dict(zip(SOURCE_COLUMNS, values, strict=True))
        data["faculty_name"] = effective_faculty
        data["class_name"] = values[3] or active_class
        data.update(
            {
                "source_file": workbook.name,
                "source_sheet": "Sheet1",
                "source_semester": _semester_label(frame, index, section_number),
                "source_row_number": int(index) + 1,
            }
        )
        errors: list[str] = []
        if effective_faculty:
            errors.append("Authoritative faculty employee_id is not present in either workbook")
            errors.append("Authoritative faculty email is not present in either workbook")
        elif data["subject_name"] or data["class_name"]:
            errors.append("Faculty context is missing for this source row")
        if data["subject_name"]:
            errors.append("Authoritative subject_code is not present in either workbook")
        if data["class_name"]:
            errors.append("Authoritative section is not present in either workbook")
        errors.append("Academic-term start_date and end_date are not present in either workbook")
        data["validation_errors"] = errors
        rows.append(data)
    if section_headers == 0:
        raise WorkbookParseError(
            "Source sheet 'Sheet1' does not contain the expected teaching-load header "
            "(Sr. No. / Name of Faculty)",
            sheet="Sheet1",
            field="header",
        )
    return rows


class LoadSourceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _audit_values(row: LoadDistributionSourceRow) -> dict[str, Any]:
        return {
            column: (
                str(getattr(row, column))
                if isinstance(getattr(row, column), UUID)
                else getattr(row, column)
            )
            for column in (*SOURCE_COLUMNS, *MAPPING_COLUMNS)
        }

    async def import_workbook(
        self,
        path: str,
        user_id: UUID,
        faculty_workbook: str | Path | None = None,
        source_file: str | None = None,
    ) -> dict[str, int]:
        parsed = parse_source_workbook(path, faculty_workbook)
        source_file = source_file or Path(path).name
        for record in parsed:
            record["source_file"] = source_file
        existing = await self.db.execute(
            select(LoadDistributionSourceRow).where(
                LoadDistributionSourceRow.source_file == source_file
            )
        )
        for row in existing.scalars().all():
            await self.db.delete(row)
        await self.db.flush()
        for data in parsed:
            row = LoadDistributionSourceRow(**data)
            self.db.add(row)
            await self.db.flush()
            self.db.add(
                AuditLog(
                    user_id=user_id,
                    action="CREATE",
                    entity_type="LOAD_SOURCE_ROW",
                    entity_id=row.id,
                    new_values=self._audit_values(row),
                )
            )
        return {
            "imported": len(parsed),
            "invalid": sum(bool(r["validation_errors"]) for r in parsed),
        }

    async def list_rows(self, semester: str | None = None) -> list[LoadDistributionSourceRow]:
        query = select(LoadDistributionSourceRow).where(
            LoadDistributionSourceRow.is_deleted.is_(False)
        )
        if semester:
            query = query.where(LoadDistributionSourceRow.source_semester == semester)
        query = query.order_by(
            LoadDistributionSourceRow.source_semester,
            LoadDistributionSourceRow.source_row_number,
        )
        return list((await self.db.execute(query)).scalars().all())

    async def update(
        self, row_id: UUID, values: dict[str, Any], user_id: UUID
    ) -> LoadDistributionSourceRow | None:
        row = await self.db.get(LoadDistributionSourceRow, row_id)
        if not row or row.is_deleted:
            return None
        old_values = self._audit_values(row)
        for column in (*SOURCE_COLUMNS, *MAPPING_COLUMNS):
            if column in values:
                setattr(row, column, values[column])
        if (
            any(column in values for column in ("theory", "practical", "tutorial", "project_stage"))
            and "total_load" not in values
        ):
            row.total_load = _calculated_total(
                {column: getattr(row, column) for column in SOURCE_COLUMNS}
            )
        row.validation_errors = await self._validate_row(row)
        await self.db.flush()
        self.db.add(
            AuditLog(
                user_id=user_id,
                action="UPDATE",
                entity_type="LOAD_SOURCE_ROW",
                entity_id=row.id,
                old_values=old_values,
                new_values=self._audit_values(row),
            )
        )
        return row

    async def create(self, values: dict[str, Any], user_id: UUID) -> LoadDistributionSourceRow:
        row = LoadDistributionSourceRow(
            source_file="Load Distribution.xlsx",
            source_sheet="Sheet1",
            source_semester=values["source_semester"],
            source_row_number=values.get("source_row_number", 0),
            **{column: values.get(column) for column in (*SOURCE_COLUMNS, *MAPPING_COLUMNS)},
        )
        if not values.get("total_load"):
            row.total_load = _calculated_total(values)
        row.validation_errors = await self._validate_row(row)
        self.db.add(row)
        await self.db.flush()
        self.db.add(
            AuditLog(
                user_id=user_id,
                action="CREATE",
                entity_type="LOAD_SOURCE_ROW",
                entity_id=row.id,
                new_values=self._audit_values(row),
            )
        )
        return row

    async def delete(self, row_id: UUID, user_id: UUID) -> bool:
        row = await self.db.get(LoadDistributionSourceRow, row_id)
        if not row or row.is_deleted:
            return False
        old_values = self._audit_values(row)
        row.is_deleted = True
        await self.db.flush()
        self.db.add(
            AuditLog(
                user_id=user_id,
                action="DELETE",
                entity_type="LOAD_SOURCE_ROW",
                entity_id=row.id,
                old_values=old_values,
            )
        )
        return True

    @staticmethod
    def _hours(value: str | None, field: str, errors: list[str]) -> int:
        if value is None or value.strip() in {"", "-"}:
            return 0
        try:
            number = float(value)
        except ValueError:
            errors.append(f"{field} must be a number, blank, or '-'")
            return 0
        if number < 0 or not number.is_integer():
            errors.append(f"{field} must be a non-negative whole number")
            return 0
        return int(number)

    async def _validate_row(self, row: LoadDistributionSourceRow) -> list[str]:
        errors: list[str] = []
        faculty = await self.db.get(Faculty, row.faculty_id) if row.faculty_id else None
        subject = await self.db.get(Subject, row.subject_id) if row.subject_id else None
        class_ = await self.db.get(Class, row.class_id) if row.class_id else None
        section = await self.db.get(Section, row.section_id) if row.section_id else None
        batch = await self.db.get(Batch, row.batch_id) if row.batch_id else None
        term = (
            await self.db.get(AcademicTerm, row.academic_term_id) if row.academic_term_id else None
        )

        if not faculty:
            errors.append(
                "Map Faculty to an existing record or create one with employee_id and email"
            )
        if not subject:
            errors.append("Map Subject to an existing record or create one with subject_code")
        if not class_:
            errors.append("Map Class to an existing authoritative class")
        if not section:
            errors.append("Map Section to an existing record or create one")
        elif class_ and section.class_id != class_.id:
            errors.append("Mapped section does not belong to the mapped class")
        if not term:
            errors.append("Map AcademicTerm with authoritative start_date and end_date")
        if batch and section and batch.section_id != section.id:
            errors.append("Mapped batch does not belong to the mapped section")

        theory = self._hours(row.theory, "Theory", errors)
        practical = self._hours(row.practical, "Practical", errors)
        tutorial = self._hours(row.tutorial, "Tutorial", errors)
        project = self._hours(row.project_stage, "Project Stage", errors)
        if not any((theory, practical, tutorial, project)):
            errors.append("At least one load component must be greater than zero")
        if practical and not batch:
            errors.append("Practical load requires an authoritative batch mapping")
        return errors

    async def approve(self, row_id: UUID, user_id: UUID) -> LoadDistributionSourceRow:
        row = await self.db.get(LoadDistributionSourceRow, row_id)
        if not row or row.is_deleted:
            raise ValueError("Source row not found")
        if row.is_approved and row.faculty_load_id:
            return row

        row.validation_errors = await self._validate_row(row)
        if row.validation_errors:
            await self.db.flush()
            raise ValueError("Source row is not valid: " + "; ".join(row.validation_errors))

        errors: list[str] = []
        theory = self._hours(row.theory, "Theory", errors)
        practical = self._hours(row.practical, "Practical", errors)
        tutorial = self._hours(row.tutorial, "Tutorial", errors)
        project = self._hours(row.project_stage, "Project Stage", errors)
        if errors:
            raise ValueError("Source row is not valid: " + "; ".join(errors))

        existing = await self.db.execute(
            select(FacultyLoad).where(
                FacultyLoad.faculty_id == row.faculty_id,
                FacultyLoad.academic_term_id == row.academic_term_id,
                FacultyLoad.subject_id == row.subject_id,
                FacultyLoad.class_id == row.class_id,
                FacultyLoad.section_id == row.section_id,
                FacultyLoad.batch_id == row.batch_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("A matching FacultyLoad already exists for this source row")

        load = FacultyLoad(
            faculty_id=row.faculty_id,
            academic_term_id=row.academic_term_id,
            subject_id=row.subject_id,
            class_id=row.class_id,
            section_id=row.section_id,
            batch_id=row.batch_id,
            session_type=SessionType.THEORY,
            theory_hours=theory,
            practical_hours=practical,
            tutorial_hours=tutorial,
            project_hours=project,
            session_duration=1,
            is_approved=True,
            approved_by=user_id,
            approved_at=datetime.now(UTC),
        )
        self.db.add(load)
        await self.db.flush()
        row.faculty_load_id = load.id
        row.is_approved = True
        row.approved_by = user_id
        row.approved_at = datetime.now(UTC)
        row.validation_errors = []
        await self.db.flush()
        return row
