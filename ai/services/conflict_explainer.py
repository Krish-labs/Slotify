from typing import Dict, List


class ConflictExplainer:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def explain(self, conflict_data: Dict) -> str:
        """Generate natural language explanation for a conflict."""
        if not self.llm_client:
            return self._generate_explanation(conflict_data)

        # Real implementation would call LLM with prompt template
        return self._generate_explanation(conflict_data)

    def _generate_explanation(self, conflict: Dict) -> str:
        conflict_type = conflict.get("type", "UNKNOWN")

        if conflict_type == "FACULTY":
            return self._explain_faculty_conflict(conflict)
        elif conflict_type == "SECTION":
            return self._explain_section_conflict(conflict)
        elif conflict_type == "BATCH":
            return self._explain_batch_conflict(conflict)
        elif conflict_type == "RESOURCE":
            return self._explain_resource_conflict(conflict)
        else:
            return f"Unknown conflict type: {conflict_type}. Please review manually."

    def _explain_faculty_conflict(self, conflict: Dict) -> str:
        faculty = conflict.get("faculty_name", "A faculty member")
        time_slot = conflict.get("time_slot", "a time slot")
        entries = conflict.get("entries", [])

        if len(entries) >= 2:
            subjects = [e.get("subject", "a subject") for e in entries]
            sections = [e.get("section", "a section") for e in entries]
            rooms = [e.get("room", "a room") for e in entries]

            return (
                f"{faculty} is scheduled to teach {subjects[0]} to {sections[0]} in {rooms[0]} "
                f"AND {subjects[1]} to {sections[1]} in {rooms[1]} at {time_slot}. "
                f"A faculty member cannot be in two places at once. "
                f"Resolution: Move one session to a different time slot, or assign a different faculty."
            )

        return f"{faculty} has a scheduling conflict at {time_slot}. Please review."

    def _explain_section_conflict(self, conflict: Dict) -> str:
        section = conflict.get("section_name", "A section")
        time_slot = conflict.get("time_slot", "a time slot")
        entries = conflict.get("entries", [])

        if len(entries) >= 2:
            subjects = [e.get("subject", "a subject") for e in entries]
            faculties = [e.get("faculty", "a faculty") for e in entries]

            return (
                f"{section} has two lectures scheduled simultaneously at {time_slot}: "
                f"{subjects[0]} (by {faculties[0]}) and {subjects[1]} (by {faculties[1]}). "
                f"Students cannot attend two classes at the same time. "
                f"Resolution: Reschedule one subject to a different period."
            )

        return f"{section} has a scheduling conflict at {time_slot}. Please review."

    def _explain_batch_conflict(self, conflict: Dict) -> str:
        batch = conflict.get("batch_name", "A batch")
        time_slot = conflict.get("time_slot", "a time slot")
        entries = conflict.get("entries", [])

        if len(entries) >= 2:
            subjects = [e.get("subject", "a subject") for e in entries]
            faculties = [e.get("faculty", "a faculty") for e in entries]
            rooms = [e.get("room", "a room") for e in entries]

            return (
                f"{batch} has two practical sessions at {time_slot}: "
                f"{subjects[0]} (by {faculties[0]} in {rooms[0]}) and "
                f"{subjects[1]} (by {faculties[1]} in {rooms[1]}). "
                f"Students in this batch cannot be in two labs simultaneously. "
                f"Resolution: Schedule practicals on different days or consecutive periods."
            )

        return f"{batch} has a scheduling conflict at {time_slot}. Please review."

    def _explain_resource_conflict(self, conflict: Dict) -> str:
        resource = conflict.get("resource_name", "A resource")
        time_slot = conflict.get("time_slot", "a time slot")
        entries = conflict.get("entries", [])

        if len(entries) >= 2:
            subjects = [e.get("subject", "a subject") for e in entries]
            sections = [e.get("section", "a section") for e in entries]

            return (
                f"{resource} is double-booked at {time_slot} for {subjects[0]} ({sections[0]}) "
                f"and {subjects[1]} ({sections[1]}). "
                f"A room/lab cannot host two classes simultaneously. "
                f"Resolution: Move one class to another available room (LH-102, LH-103, or emergency rooms LH-201/LH-202)."
            )

        return f"{resource} has a scheduling conflict at {time_slot}. Please review."

    async def explain_all(self, conflicts: List[Dict]) -> List[Dict]:
        """Explain multiple conflicts."""
        explained = []
        for conflict in conflicts:
            explanation = await self.explain(conflict)
            explained.append({
                "conflict": conflict,
                "explanation": explanation,
                "severity": "high" if conflict.get("type") in ["FACULTY", "SECTION"] else "medium"
            })
        return explained

    def get_summary(self, conflicts: List[Dict]) -> str:
        """Get a summary of all conflicts."""
        if not conflicts:
            return "No conflicts detected."

        type_counts = {}
        for c in conflicts:
            t = c.get("type", "UNKNOWN")
            type_counts[t] = type_counts.get(t, 0) + 1

        parts = [f"{count} {type}" for type, count in type_counts.items()]
        return f"Found {len(conflicts)} conflict(s): {', '.join(parts)}."