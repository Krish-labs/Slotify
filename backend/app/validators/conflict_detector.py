from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID


@dataclass
class Conflict:
    conflict_type: str  # FACULTY, SECTION, BATCH, RESOURCE
    entity_id: UUID
    time_slot_id: UUID
    entries: list[dict]
    severity: str = "ERROR"  # ERROR, WARNING


class ConflictDetector:
    def __init__(self):
        self.conflicts: list[Conflict] = []

    def detect(self, entries: list[dict]) -> list[Conflict]:
        self.conflicts = []

        self._detect_faculty_conflicts(entries)
        self._detect_section_conflicts(entries)
        self._detect_batch_conflicts(entries)
        self._detect_resource_conflicts(entries)

        return self.conflicts

    def _detect_faculty_conflicts(self, entries: list[dict]):
        faculty_slot = defaultdict(list)
        for entry in entries:
            key = (entry["faculty_id"], entry["time_slot_id"])
            faculty_slot[key].append(entry)

        for (faculty_id, time_slot_id), entries_list in faculty_slot.items():
            if len(entries_list) > 1:
                self.conflicts.append(
                    Conflict(
                        conflict_type="FACULTY",
                        entity_id=faculty_id,
                        time_slot_id=time_slot_id,
                        entries=entries_list,
                    )
                )

    def _detect_section_conflicts(self, entries: list[dict]):
        section_slot = defaultdict(list)
        for entry in entries:
            if entry["session_type"] == "LECTURE":
                key = (entry["section_id"], entry["time_slot_id"])
                section_slot[key].append(entry)

        for (section_id, time_slot_id), entries_list in section_slot.items():
            if len(entries_list) > 1:
                self.conflicts.append(
                    Conflict(
                        conflict_type="SECTION",
                        entity_id=section_id,
                        time_slot_id=time_slot_id,
                        entries=entries_list,
                    )
                )

    def _detect_batch_conflicts(self, entries: list[dict]):
        batch_slot = defaultdict(list)
        for entry in entries:
            if entry["session_type"] in ("PRACTICAL", "TUTORIAL") and entry.get("batch_id"):
                key = (entry["batch_id"], entry["time_slot_id"])
                batch_slot[key].append(entry)

        for (batch_id, time_slot_id), entries_list in batch_slot.items():
            if len(entries_list) > 1:
                self.conflicts.append(
                    Conflict(
                        conflict_type="BATCH",
                        entity_id=batch_id,
                        time_slot_id=time_slot_id,
                        entries=entries_list,
                    )
                )

    def _detect_resource_conflicts(self, entries: list[dict]):
        resource_slot = defaultdict(list)
        for entry in entries:
            key = (entry["resource_id"], entry["time_slot_id"])
            resource_slot[key].append(entry)

        for (resource_id, time_slot_id), entries_list in resource_slot.items():
            if len(entries_list) > 1:
                self.conflicts.append(
                    Conflict(
                        conflict_type="RESOURCE",
                        entity_id=resource_id,
                        time_slot_id=time_slot_id,
                        entries=entries_list,
                    )
                )

    def get_conflict_summary(self) -> dict[str, int]:
        summary: defaultdict[str, int] = defaultdict(int)
        for conflict in self.conflicts:
            summary[conflict.conflict_type] += 1
        return dict(summary)

    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0
