"""Institutional two-hour timetable slots.

The faculty workbook is deliberately not used as a timetable template.  It is
only used by the source importer for names and semester context.  Generation
always uses this explicit grid, including its breaks and Monday-to-Saturday
boundary.
"""

from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True)
class CanonicalSlot:
    period_number: int
    start_time: time
    end_time: time
    shift: str


CANONICAL_SLOTS: tuple[CanonicalSlot, ...] = (
    CanonicalSlot(1, time(8, 0), time(10, 0), "MORNING"),
    CanonicalSlot(2, time(10, 15), time(12, 15), "MORNING"),
    CanonicalSlot(3, time(13, 0), time(15, 0), "MORNING"),
    CanonicalSlot(4, time(15, 15), time(17, 15), "LATE"),
)

WORKING_DAYS = tuple(range(6))
ALLOWED_RESOURCE_NAMES = {
    "309": ("CLASSROOM", 60),
    "311": ("CLASSROOM", 60),
    "314": ("CLASSROOM", 60),
    "307A": ("SOFTWARE_LAB", 20),
    "307B": ("SOFTWARE_LAB", 20),
    "308A": ("SOFTWARE_LAB", 20),
    "308B": ("SOFTWARE_LAB", 20),
    "303": ("HARDWARE_LAB", 20),
    "304": ("HARDWARE_LAB", 20),
    "305": ("HARDWARE_LAB", 20),
    "306": ("HARDWARE_LAB", 20),
}


def canonical_slot_rows(template_id):
    """Return plain dictionaries suitable for ``TimeSlot`` construction."""
    return [
        {
            "template_id": template_id,
            "day_of_week": day,
            "period_number": slot.period_number,
            "start_time": slot.start_time,
            "end_time": slot.end_time,
            "slot_type": "TEACHING",
            "shift": slot.shift,
            "is_active": True,
        }
        for day in WORKING_DAYS
        for slot in CANONICAL_SLOTS
    ]
