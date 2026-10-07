from dataclasses import dataclass
from uuid import UUID


@dataclass
class TimetableEntryData:
    assignment_id: UUID
    resource_id: UUID
    time_slot_id: UUID
    faculty_id: UUID
    subject_id: UUID
    section_id: UUID
    batch_id: UUID | None
    day_of_week: int
    session_type: str
    is_pinned: bool = False


class SolutionExtractor:
    def __init__(self, assignments: list[dict], resources: list[dict], time_slots: list[dict]):
        self.assignment_map = {a["id"]: a for a in assignments}
        self.resource_map = {r["id"]: r for r in resources}
        self.time_slot_map = {t["id"]: t for t in time_slots}

    def extract(self, solver_entries: list[dict]) -> list[TimetableEntryData]:
        entries = []
        for entry in solver_entries:
            assignment = self.assignment_map.get(entry["assignment_id"])
            time_slot = self.time_slot_map.get(entry["time_slot_id"])

            if not assignment or not time_slot:
                continue

            entries.append(
                TimetableEntryData(
                    assignment_id=entry["assignment_id"],
                    resource_id=entry["resource_id"],
                    time_slot_id=entry["time_slot_id"],
                    faculty_id=assignment["faculty_id"],
                    subject_id=assignment["subject_id"],
                    section_id=assignment["section_id"],
                    batch_id=assignment.get("batch_id"),
                    day_of_week=time_slot["day_of_week"],
                    session_type=assignment["session_type"],
                )
            )

        return entries


def create_timetable_entries(
    extracted_entries: list[TimetableEntryData], version_id: UUID
) -> list[dict]:
    return [
        {
            "version_id": version_id,
            "faculty_id": e.faculty_id,
            "subject_id": e.subject_id,
            "section_id": e.section_id,
            "batch_id": e.batch_id,
            "resource_id": e.resource_id,
            "time_slot_id": e.time_slot_id,
            "day_of_week": e.day_of_week,
            "session_type": e.session_type,
            "is_pinned": e.is_pinned,
        }
        for e in extracted_entries
    ]
