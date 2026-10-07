from typing import Dict, List
from enum import Enum


class Intent(Enum):
    CONSTRAINT_CREATION = "constraint_creation"
    CONSTRAINT_MODIFICATION = "constraint_modification"
    CONFLICT_RESOLUTION = "conflict_resolution"
    SCHEDULE_QUERY = "schedule_query"
    REPORT_REQUEST = "report_request"
    DATA_IMPORT = "data_import"
    UNKNOWN = "unknown"


class IntentClassifier:
    def __init__(self):
        self.patterns = {
            Intent.CONSTRAINT_CREATION: [
                "should not", "must not", "cannot", "prefer", "preferable",
                "only teach", "available", "unavailable", "avoid"
            ],
            Intent.CONSTRAINT_MODIFICATION: [
                "change", "modify", "update", "adjust", "move", "reschedule"
            ],
            Intent.CONFLICT_RESOLUTION: [
                "conflict", "clash", "double-booked", "overlap", "resolve", "fix"
            ],
            Intent.SCHEDULE_QUERY: [
                "show", "view", "display", "what", "when", "where", "who",
                "timetable for", "schedule for"
            ],
            Intent.REPORT_REQUEST: [
                "report", "export", "download", "generate report", "summary"
            ],
            Intent.DATA_IMPORT: [
                "import", "upload", "load", "excel", "file"
            ],
        }

    def classify(self, text: str) -> Intent:
        text_lower = text.lower()

        for intent, patterns in self.patterns.items():
            for pattern in patterns:
                if pattern in text_lower:
                    return intent

        return Intent.UNKNOWN

    def classify_with_confidence(self, text: str) -> Dict:
        intent = self.classify(text)
        confidence = 0.9 if intent != Intent.UNKNOWN else 0.1

        return {
            "intent": intent.value,
            "confidence": confidence,
            "matched_patterns": self._get_matched_patterns(text, intent)
        }

    def _get_matched_patterns(self, text: str, intent: Intent) -> List[str]:
        text_lower = text.lower()
        patterns = self.patterns.get(intent, [])
        return [p for p in patterns if p in text_lower]


class EntityExtractor:
    def __init__(self):
        self.entity_patterns = {
            "faculty": ["dr.", "prof.", "professor", "faculty", "teacher"],
            "section": ["section", "sec ", "div "],
            "batch": ["batch", "group "],
            "subject": ["subject", "course", "paper"],
            "room": ["room", "lab", "classroom", "lh-", "sl-", "hl-"],
            "day": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "mon", "tue", "wed", "thu", "fri", "sat"],
            "time": ["morning", "afternoon", "evening", ":", "am", "pm"],
        }

    def extract(self, text: str) -> Dict[str, List[str]]:
        text_lower = text.lower()
        entities = {}

        for entity_type, patterns in self.entity_patterns.items():
            found = []
            for pattern in patterns:
                if pattern in text_lower:
                    found.append(pattern)
            if found:
                entities[entity_type] = found

        return entities