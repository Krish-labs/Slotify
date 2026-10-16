from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from uuid import UUID, uuid4

import openpyxl


@dataclass(frozen=True)
class ReferenceTimeSlot:
    id: UUID
    template_id: UUID
    day_of_week: int
    period_number: int
    start_time: time
    end_time: time
    slot_type: str = "TEACHING"
    shift: str = "MORNING"
    is_active: bool = True


_TIME_RANGE = re.compile(r"^\s*(\d{1,3})(?::(\d{2}))?\s*[-–]\s*(\d{1,2})(?::(\d{2}))?\s*$")


def _parse_time_range(value: object) -> tuple[time, time] | None:
    match = _TIME_RANGE.match(str(value or ""))
    if not match:
        return None
    start_hour, start_minute, end_hour, end_minute = match.groups()
    if start_minute is None and len(start_hour) == 3:
        start_hour, start_minute = start_hour[0], start_hour[1:]
    if end_minute is None and len(end_hour) == 3:
        end_hour, end_minute = end_hour[0], end_hour[1:]
    try:
        start_value = int(start_hour)
        end_value = int(end_hour)
        # The reference workbook writes afternoon hours as 1:00, 2:00, etc.
        # Convert those labels to 24-hour values without changing the source.
        if start_value < 8:
            start_value += 12
        if end_value < 8:
            end_value += 12
        start = datetime.strptime(f"{start_value}:{int(start_minute or 0):02d}", "%H:%M").time()
        end = datetime.strptime(f"{end_value}:{int(end_minute or 0):02d}", "%H:%M").time()
    except ValueError:
        return None
    if (
        datetime.combine(datetime.min, end) - datetime.combine(datetime.min, start)
    ).seconds != 3600:
        return None
    return start, end


def reference_teaching_times(path: str | Path) -> tuple[tuple[time, time], ...]:
    """Read only one-hour teaching intervals from the timing reference.

    No faculty, subject, class, room, or timetable cell is consumed from this
    workbook.  The first class sheet with a ``Day Time`` column supplies the
    institution's clock, including its breaks.
    """
    workbook = Path(path)
    if not workbook.exists():
        raise FileNotFoundError(f"Timing reference workbook not found: {workbook}")
    book = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
    for sheet in book.worksheets:
        values = [row[0] for row in sheet.iter_rows(min_col=1, max_col=1, values_only=True)]
        if not any(str(value or "").strip().lower() == "day  time" for value in values):
            continue
        teaching = tuple(
            parsed for value in values if (parsed := _parse_time_range(value)) is not None
        )
        if teaching:
            return teaching
    raise ValueError("Timing reference has no one-hour teaching intervals in a class sheet")


def reference_time_slots(path: str | Path, template_id: UUID) -> list[ReferenceTimeSlot]:
    teaching_times = reference_teaching_times(path)
    return [
        ReferenceTimeSlot(
            id=uuid4(),
            template_id=template_id,
            day_of_week=day,
            period_number=period,
            start_time=start,
            end_time=end,
            shift="LATE" if start.hour >= 15 else "MORNING",
        )
        for day in range(6)
        for period, (start, end) in enumerate(teaching_times, start=1)
    ]
