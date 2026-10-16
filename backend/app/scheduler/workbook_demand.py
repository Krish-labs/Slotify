"""Read-only normalization of the real Load Distribution workbook.

This module only turns source rows into demand records.  It never reads a
reference timetable cell and never creates a schedule.  The solver receives
the returned records only after the database-backed resolver has matched each
name to an existing domain record.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.load_source_service import parse_source_workbook

COMPONENTS = (
    ("theory", "LECTURE"),
    ("practical", "PRACTICAL"),
    ("tutorial", "TUTORIAL"),
    ("project_stage", "PROJECT"),
)


def _hours(value: Any) -> int:
    if value is None or str(value).strip() in {"", "-", "nan"}:
        return 0
    number = float(value)
    if number < 0 or not number.is_integer():
        raise ValueError(f"Source load must be a non-negative whole number: {value!r}")
    return int(number)


@dataclass(frozen=True)
class WorkbookDemand:
    source_row_number: int
    source_semester: str
    faculty_name: str
    class_name: str
    subject_name: str
    session_type: str
    source_hours: int
    # Slot width is chosen by the caller. A remainder is retained in the
    # report instead of being silently rounded away.
    required_slots: int
    unrepresented_hours: int


@dataclass(frozen=True)
class ZeroLoadRow:
    """A source row with valid class/subject/faculty but zero workload.

    These rows represent either legitimate zero-load bookkeeping or incomplete
    data entry. They must be explicitly reviewed before generation can be
    considered ready.
    """
    source_row_number: int
    source_semester: str
    faculty_name: str
    class_name: str
    subject_name: str
    theory: str | None
    practical: str | None
    tutorial: str | None
    project_stage: str | None
    total_load: str | None


@dataclass(frozen=True)
class SourceRowDisposition:
    source_row_number: int
    disposition: str
    reason: str


@dataclass(frozen=True)
class DemandParseResult:
    source_file: str
    semester: str
    rows_read: int
    demands: tuple[WorkbookDemand, ...]
    invalid_rows: tuple[str, ...]
    excluded_rows: tuple[str, ...] = ()
    zero_load_rows: tuple[ZeroLoadRow, ...] = ()
    row_dispositions: tuple[SourceRowDisposition, ...] = ()

    @property
    def source_hours(self) -> int:
        return sum(d.source_hours for d in self.demands)

    @property
    def required_slots(self) -> int:
        return sum(d.required_slots for d in self.demands)

    @property
    def unrepresented_hours(self) -> int:
        return sum(d.unrepresented_hours for d in self.demands)

    @property
    def has_unreviewed_zero_load(self) -> bool:
        """True if any zero-load row exists that has not been explicitly approved."""
        return any(
            disposition.disposition == "zero_load_review_required"
            for disposition in self.row_dispositions
        ) or bool(self.zero_load_rows)


def semester_label(academic_year: str, semester: int) -> str:
    if semester == 1:
        return f"Semester I • {academic_year}"
    if semester == 2:
        return f"Semester II • {academic_year}"
    raise ValueError("semester must be 1 or 2 for the source workbook")


def parse_workbook_demand(
    source_path: str | Path,
    academic_year: str,
    semester: int,
    reference_path: str | Path | None = None,
    *,
    slot_hours: int = 2,
) -> DemandParseResult:
    """Parse exactly one source semester into atomic demand components.

    ``reference_path`` is retained as an API/documentation boundary, but is
    intentionally not opened here. The source workbook remains authoritative
    for names and hours; the generation path separately reads only timing
    intervals from the reference workbook.
    """
    if slot_hours < 1:
        raise ValueError("slot_hours must be positive")
    selected = semester_label(academic_year, semester)
    rows = parse_source_workbook(source_path)
    source_rows = [row for row in rows if row.get("source_semester") == selected]
    demands: list[WorkbookDemand] = []
    invalid_rows: list[str] = []
    excluded_rows: list[str] = []
    zero_load_rows: list[ZeroLoadRow] = []
    row_dispositions: list[SourceRowDisposition] = []

    for row in source_rows:
        faculty = (row.get("faculty_name") or "").strip()
        class_name = (row.get("class_name") or "").strip()
        subject = (row.get("subject_name") or "").strip()
        if not any((faculty, class_name, subject)):
            continue
        normalized = re.sub(r"\s+", "", class_name.upper())
        if "M.TECH" in normalized or "MTECH" in normalized or normalized == "ITDEPARTMENT":
            reason = f"{class_name} is outside FE/SY/TE/BE ENTC"
            excluded_rows.append(f"Source row {row['source_row_number']}: {reason}")
            row_dispositions.append(SourceRowDisposition(int(row["source_row_number"]), "approved_exclusion", reason))
            continue
        if not normalized.startswith(("FY", "FE", "SY", "TY", "TE", "BE")):
            reason = f"unrecognized ENTC class {class_name!r}"
            invalid_rows.append(f"Source row {row['source_row_number']}: {reason}")
            row_dispositions.append(SourceRowDisposition(int(row["source_row_number"]), "invalid_source_row", reason))
            continue
        if not faculty or not class_name or not subject:
            reason = "faculty, class and subject are required"
            invalid_rows.append(f"Source row {row['source_row_number']}: {reason}")
            row_dispositions.append(SourceRowDisposition(int(row["source_row_number"]), "invalid_source_row", reason))
            continue

        row_demands = 0
        try:
            for component, session_type in COMPONENTS:
                hours = _hours(row.get(component))
                if not hours:
                    continue
                row_demands += 1
                demands.append(
                    WorkbookDemand(
                        source_row_number=int(row["source_row_number"]),
                        source_semester=selected,
                        faculty_name=faculty,
                        class_name=class_name,
                        subject_name=subject,
                        session_type=session_type,
                        source_hours=hours,
                        required_slots=hours // slot_hours,
                        unrepresented_hours=hours % slot_hours,
                    )
                )
        except ValueError as exc:
            # Roll back any components already appended for this malformed row.
            demands = [d for d in demands if d.source_row_number != int(row["source_row_number"])]
            reason = str(exc)
            invalid_rows.append(f"Source row {row['source_row_number']}: {reason}")
            row_dispositions.append(SourceRowDisposition(int(row["source_row_number"]), "invalid_source_row", reason))
            continue

        if row_demands:
            row_dispositions.append(
                SourceRowDisposition(
                    int(row["source_row_number"]),
                    "scheduled_demand",
                    "Teaching workload represented as demand",
                )
            )

        # Track rows with valid class/subject/faculty but zero workload.
        # These represent either legitimate zero-load bookkeeping or incomplete
        # data entry and must be explicitly reviewed.
        if row_demands == 0:
            zero_load_rows.append(
                ZeroLoadRow(
                    source_row_number=int(row["source_row_number"]),
                    source_semester=selected,
                    faculty_name=faculty,
                    class_name=class_name,
                    subject_name=subject,
                    theory=row.get("theory"),
                    practical=row.get("practical"),
                    tutorial=row.get("tutorial"),
                    project_stage=row.get("project_stage"),
                    total_load=row.get("total_load"),
                )
            )
            row_dispositions.append(
                SourceRowDisposition(
                    int(row["source_row_number"]),
                    "zero_load_review_required",
                    "No positive teaching hours; review whether this is approved zero-load bookkeeping or incomplete workload data",
                )
            )

    return DemandParseResult(
        source_file=Path(source_path).name,
        semester=selected,
        rows_read=len(source_rows),
        demands=tuple(demands),
        invalid_rows=tuple(invalid_rows),
        excluded_rows=tuple(excluded_rows),
        zero_load_rows=tuple(zero_load_rows),
        row_dispositions=tuple(row_dispositions),
    )
