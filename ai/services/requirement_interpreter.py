from typing import Dict, List, Optional


class RequirementInterpreter:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    async def interpret(self, requirement: str, context: Dict = None) -> Dict:
        """Interpret a scheduling requirement into structured actions."""
        if not self.llm_client:
            return self._mock_interpret(requirement)

        # Real implementation would call LLM
        return self._mock_interpret(requirement)

    def _mock_interpret(self, requirement: str) -> Dict:
        req_lower = requirement.lower()

        actions = []
        constraints = []

        if "move" in req_lower or "reschedule" in req_lower:
            actions.append("Identify affected sessions")
            actions.append("Check alternative time slots")
            actions.append("Validate constraints for new slot")
            actions.append("Run reoptimization")

        if "add" in req_lower or "new" in req_lower:
            actions.append("Check faculty availability")
            actions.append("Check resource availability")
            actions.append("Create new teaching assignment")
            actions.append("Run incremental optimization")

        if "remove" in req_lower or "cancel" in req_lower:
            actions.append("Identify sessions to remove")
            actions.append("Release resources and time slots")
            actions.append("Run reoptimization to fill gaps")

        if "faculty" in req_lower:
            constraints.append("Faculty availability must be checked")
        if "room" in req_lower or "lab" in req_lower:
            constraints.append("Resource capacity and type must match")
        if "batch" in req_lower:
            constraints.append("Batch scheduling must be parallel")

        return {
            "original_requirement": requirement,
            "action_items": actions,
            "constraints": constraints,
            "estimated_complexity": "low" if len(actions) <= 2 else "medium",
            "requires_reoptimization": len(actions) > 1
        }

    async def suggest_alternatives(self, failed_scenario: Dict) -> List[Dict]:
        """Suggest alternative approaches when a requirement fails."""
        return [
            {
                "approach": "Relax soft constraints",
                "description": "Allow more gap periods or emergency room usage",
                "trade_off": "Lower timetable quality score"
            },
            {
                "approach": "Use emergency resources",
                "description": "Schedule in emergency classrooms/labs",
                "trade_off": "May not have ideal equipment"
            },
            {
                "approach": "Split sessions",
                "description": "Divide large sessions into smaller groups",
                "trade_off": "Requires more faculty hours"
            },
            {
                "approach": "Adjust batch sizes",
                "description": "Rebalance batch assignments",
                "trade_off": "May affect lab group dynamics"
            }
        ]