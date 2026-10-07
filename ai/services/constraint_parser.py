import json
from typing import Dict, List, Optional
from pathlib import Path


class ConstraintParser:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.prompt_template = self._load_prompt("constraint_parser.md")

    def _load_prompt(self, filename: str) -> str:
        prompt_path = Path(__file__).parent.parent / "prompts" / filename
        if prompt_path.exists():
            return prompt_path.read_text()
        return ""

    async def parse(self, natural_language: str) -> Dict:
        """Parse natural language into structured constraints."""
        if not self.llm_client:
            return self._mock_parse(natural_language)

        # In real implementation, call LLM with prompt
        # response = await self.llm_client.complete(
        #     prompt=self.prompt_template + f"\n\nInput: {natural_language}\nOutput:"
        # )
        # return json.loads(response)

        return self._mock_parse(natural_language)

    def _mock_parse(self, text: str) -> Dict:
        """Mock parser for development."""
        text_lower = text.lower()

        if "not teach" in text_lower or "unavailable" in text_lower:
            return {
                "type": "faculty_unavailability",
                "faculty_id": "unknown",
                "constraints": [
                    {
                        "day_of_week": 4,
                        "shift": "LATE",
                        "reason": "Parsed from: " + text
                    }
                ]
            }

        if "morning" in text_lower or "prefer" in text_lower:
            return {
                "type": "session_preference",
                "section_id": "unknown",
                "subject_code": "unknown",
                "preferred_shift": "MORNING",
                "priority": "medium"
            }

        if "maintenance" in text_lower or "unavailable" in text_lower:
            return {
                "type": "resource_unavailability",
                "resource_id": "unknown",
                "constraints": [
                    {
                        "day_of_week": 0,
                        "reason": "Parsed from: " + text
                    }
                ]
            }

        return {
            "type": "unknown",
            "raw_text": text,
            "message": "Could not parse constraint"
        }

    async def parse_batch(self, texts: List[str]) -> List[Dict]:
        """Parse multiple natural language inputs."""
        return [await self.parse(text) for text in texts]


class RequirementInterpreter:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def interpret(self, requirement: str, context: Dict = None) -> Dict:
        """Interpret scheduling requirement into actionable items."""
        if not self.llm_client:
            return self._mock_interpret(requirement)

        return self._mock_interpret(requirement)

    def _mock_interpret(self, requirement: str) -> Dict:
        return {
            "requirement": requirement,
            "action_items": [
                "Check faculty availability",
                "Verify resource capacity",
                "Validate against existing timetable"
            ],
            "constraints": []
        }


class ConflictExplainer:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.prompt_template = self._load_prompt("conflict_explainer.md")

    def _load_prompt(self, filename: str) -> str:
        prompt_path = Path(__file__).parent.parent / "prompts" / filename
        if prompt_path.exists():
            return prompt_path.read_text()
        return ""

    async def explain(self, conflict_data: Dict) -> str:
        """Generate natural language explanation for a conflict."""
        if not self.llm_client:
            return self._mock_explain(conflict_data)

        return self._mock_explain(conflict_data)

    def _mock_explain(self, conflict: Dict) -> str:
        conflict_type = conflict.get("type", "UNKNOWN")

        if conflict_type == "FACULTY":
            faculty = conflict.get("faculty_name", "Unknown Faculty")
            time_slot = conflict.get("time_slot", "Unknown Time")
            entries = conflict.get("entries", [])
            subjects = ", ".join([e.get("subject", "") for e in entries])
            return f"{faculty} is double-booked at {time_slot} teaching {subjects}. Please reschedule one session."

        if conflict_type == "SECTION":
            section = conflict.get("section_name", "Unknown Section")
            time_slot = conflict.get("time_slot", "Unknown Time")
            entries = conflict.get("entries", [])
            subjects = ", ".join([e.get("subject", "") for e in entries])
            return f"{section} has conflicting lectures at {time_slot}: {subjects}. Students cannot attend both."

        if conflict_type == "BATCH":
            batch = conflict.get("batch_name", "Unknown Batch")
            time_slot = conflict.get("time_slot", "Unknown Time")
            entries = conflict.get("entries", [])
            subjects = ", ".join([e.get("subject", "") for e in entries])
            return f"{batch} has conflicting practicals at {time_slot}: {subjects}."

        if conflict_type == "RESOURCE":
            resource = conflict.get("resource_name", "Unknown Resource")
            time_slot = conflict.get("time_slot", "Unknown Time")
            entries = conflict.get("entries", [])
            subjects = ", ".join([e.get("subject", "") for e in entries])
            return f"{resource} is double-booked at {time_slot} for {subjects}."

        return f"Conflict detected: {conflict_type}. Please review and resolve."