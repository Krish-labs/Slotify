"""Closed repair-adjustment schemas for the bounded repair workflow.

Only the kinds listed here can reach the solver. Anything else — in
particular any "ignore this hard rule" request — fails validation with a
useful error instead of reaching CP-SAT. The LLM may suggest these
candidates, but every one is re-validated here before use.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_MAX_REPAIR_ATTEMPTS = 2
ABSOLUTE_MAX_REPAIR_ATTEMPTS = 5

RepairAdjustmentKind = Literal[
    "full_regeneration",
    "extend_time_limit",
    "include_resources",
    "lift_availability_block",
]

#: Kinds that override persisted availability data for one solve. They never
#: weaken a conflict rule, but they do set aside leave/blackout records, so
#: they require explicit human approval per repair request.
APPROVAL_GATED_KINDS: frozenset[str] = frozenset({"include_resources", "lift_availability_block"})


class RepairAdjustment(BaseModel):
    """One candidate constraint adjustment for a single re-solve."""

    model_config = ConfigDict(extra="forbid")

    kind: RepairAdjustmentKind
    reason: str = Field(default="", max_length=500)
    # extend_time_limit: replacement CP-SAT budget in seconds.
    time_limit_seconds: int | None = Field(default=None, ge=1, le=600)
    # include_resources: inactive room ids to admit to this solve's pool.
    resource_ids: list[str] = Field(default_factory=list, max_length=20)
    # lift_availability_block: faculty or slot ids whose availability blocks
    # to ignore for this solve (a faculty id lifts all of its blocks; a slot
    # id lifts every block on that slot).
    faculty_slot_ids: list[str] = Field(default_factory=list, max_length=20)
    resource_slot_ids: list[str] = Field(default_factory=list, max_length=20)

    def needs_approval(self) -> bool:
        return self.kind in APPROVAL_GATED_KINDS


class RepairAttemptRecord(BaseModel):
    """Structured diagnostics for one re-solve attempt."""

    model_config = ConfigDict(extra="forbid")

    attempt: int
    adjustment: RepairAdjustment | None = None
    solver_status: str = ""
    validation_errors: list[str] = Field(default_factory=list)
    solver_diagnostics: list[str] = Field(default_factory=list)
    applied: bool = False
    # Validated candidate entries (solver + pinned scope). Excluded from dumps
    # so attempt logs stay small structured diagnostics, not timetable data.
    entries: list[dict[str, Any]] = Field(default_factory=list, exclude=True)


def shortfall_assignments(entries: list[dict], required_hours: dict[Any, int]) -> list[Any]:
    """Assignment ids whose scheduled hours differ from required hours."""
    scheduled: dict[Any, int] = {}
    for entry in entries:
        key = entry.get("assignment_id")
        scheduled[key] = scheduled.get(key, 0) + 1
    return [
        assignment_id
        for assignment_id, required in required_hours.items()
        if scheduled.get(assignment_id, 0) != required
    ]


def unscheduled_demand(entries: list[dict], required_hours: dict[Any, int]) -> list[dict[str, Any]]:
    """Explicit per-assignment unscheduled hours (never silent)."""
    scheduled: dict[Any, int] = {}
    for entry in entries:
        key = entry.get("assignment_id")
        scheduled[key] = scheduled.get(key, 0) + 1
    return [
        {
            "assignment_id": str(assignment_id),
            "required_hours": required,
            "scheduled_hours": scheduled.get(assignment_id, 0),
        }
        for assignment_id, required in required_hours.items()
        if scheduled.get(assignment_id, 0) < required
    ]
