"""Solve-side helpers for the bounded repair workflow.

These functions operate on plain snapshots (solver dataclasses and dicts),
never on ORM objects: repair attempts run after the read transaction has
ended, so any ORM access would trigger an implicit refresh outside a
transaction. The orchestrating :class:`RepairService` owns sessions,
transactions, and audit; this module owns CP-SAT input derivation, scoping,
enrichment, and persistence payloads.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.database.models.audit_log import AuditLog
from app.database.models.timetable import Timetable
from app.database.models.timetable_entry import TimetableEntry
from app.database.transactions import transaction
from app.scheduler.model import SolverInput, SolverResource
from app.scheduler.reoptimizer import ImpactReport, Reoptimizer
from app.scheduler.time_slots import ALLOWED_RESOURCE_NAMES
from app.schemas.repair import RepairAdjustment
from app.services.version_service import VersionService

# NOTE: timetable_worker helpers are imported lazily inside functions. The
# worker depends on app.services modules, so a module-level import here would
# create a services <-> workers cycle.


def entry_to_dict(row: TimetableEntry) -> dict:
    """Copy a persisted row to a plain dict before the transaction ends."""
    return {
        "id": row.id,
        "assignment_id": row.assignment_id,
        "faculty_id": row.faculty_id,
        "subject_id": row.subject_id,
        "section_id": row.section_id,
        "batch_id": row.batch_id,
        "resource_id": row.resource_id,
        "time_slot_id": row.time_slot_id,
        "day_of_week": row.day_of_week,
        "period_number": row.period_number,
        "session_type": row.session_type,
    }


def enrich_entries(rows: list[dict], solver_input: SolverInput) -> list[dict]:
    """Add the validator's context (durations, capacities, room types)."""
    assignments = {a.id: a for a in solver_input.assignments}
    resources = {r.id: r for r in solver_input.resources}
    slots = {t.id: t for t in solver_input.time_slots}
    enriched = []
    for row in rows:
        assignment = assignments.get(row.get("assignment_id"))
        resource = resources.get(row.get("resource_id"))
        slot = slots.get(row.get("time_slot_id"))
        enriched.append(
            {
                **row,
                "session_duration": (assignment.session_duration if assignment else 1),
                "section_strength": 0,
                "batch_strength": 0,
                "resource_capacity": resource.capacity if resource else 0,
                "resource_type": resource.resource_type if resource else None,
                "required_lab_type": (assignment.required_lab_type if assignment else None),
                "resource_is_emergency": bool(resource and resource.is_emergency),
                "day_of_week": (slot.day_of_week if slot else row.get("day_of_week")),
                "period_number": (slot.period_number if slot else row.get("period_number")),
                "two_hour_grid": solver_input.two_hour_grid,
            }
        )
    return enriched


def deterministic_suggestions(diagnostics: list[str]) -> list[RepairAdjustment]:
    """Safe fallback candidates derived from diagnostic keywords only."""
    lowered = " ".join(diagnostics).lower()
    if "time" in lowered and ("limit" in lowered or "unknown" in lowered):
        return [
            RepairAdjustment(
                kind="extend_time_limit",
                time_limit_seconds=120,
                reason="solver reported an inconclusive status; retry with a larger budget",
            )
        ]
    return [
        RepairAdjustment(
            kind="full_regeneration",
            reason="re-solve the full scope instead of a pinned subproblem",
        )
    ]


def apply_adjustment(
    base: SolverInput,
    inactive_pool: list[SolverResource],
    adjustment: RepairAdjustment,
) -> tuple[SolverInput | None, str | None]:
    """Derive one attempt's solver input from plain snapshots (no ORM).

    Returns ``(input, None)`` on success or ``(None, error)`` when the
    adjustment is incomplete or names unknown resources; the caller records
    the error as the attempt's diagnostics without touching the solver.
    """
    faculty_blocks = set(base.blocked_faculty_slots)
    resource_blocks = set(base.blocked_resource_slots)
    pool = list(base.resources)
    if adjustment.kind == "full_regeneration":
        pass
    elif adjustment.kind == "extend_time_limit":
        if not adjustment.time_limit_seconds:
            return None, "extend_time_limit requires time_limit_seconds"
    elif adjustment.kind == "include_resources":
        if not adjustment.resource_ids:
            return None, "include_resources requires resource_ids"
        known = {str(r.id) for r in pool} | {str(r.id) for r in inactive_pool}
        unknown = sorted(set(adjustment.resource_ids) - known)
        if unknown:
            return None, f"Unknown resource(s), nothing applied: {', '.join(unknown)}"
        have = {str(r.id) for r in pool}
        by_id = {str(r.id): r for r in inactive_pool}
        for resource_id in adjustment.resource_ids:
            match = by_id.get(resource_id)
            if match is not None and resource_id not in have:
                if base.two_hour_grid and (
                    match.name not in ALLOWED_RESOURCE_NAMES
                    or match.resource_type != ALLOWED_RESOURCE_NAMES[match.name][0]
                ):
                    return (
                        None,
                        f"Resource {match.name} is not part of the canonical "
                        "two-hour room grid; register a compatible room instead",
                    )
                pool.append(match)
                have.add(resource_id)
    elif adjustment.kind == "lift_availability_block":
        if not adjustment.faculty_slot_ids and not adjustment.resource_slot_ids:
            return None, "lift_availability_block requires faculty_slot_ids or resource_slot_ids"
        lifted_faculty = set(adjustment.faculty_slot_ids)
        lifted_resource = set(adjustment.resource_slot_ids)
        faculty_blocks = {
            pair
            for pair in faculty_blocks
            if str(pair[0]) not in lifted_faculty and str(pair[1]) not in lifted_faculty
        }
        resource_blocks = {
            pair
            for pair in resource_blocks
            if str(pair[0]) not in lifted_resource and str(pair[1]) not in lifted_resource
        }
    return (
        SolverInput(
            assignments=list(base.assignments),
            resources=pool,
            time_slots=list(base.time_slots),
            two_hour_grid=base.two_hour_grid,
            blocked_faculty_slots=faculty_blocks,
            blocked_resource_slots=resource_blocks,
        ),
        None,
    )


def scoped_subproblem(
    reoptimizer: Reoptimizer,
    solver_input: SolverInput,
    prev_entries: list[dict],
    shortfall: list,
) -> tuple[SolverInput, list[dict]]:
    """Re-solve only the failed scope, pinning unaffected entries.

    ``analyze_impact`` matches change requests against *existing* entries,
    so a brand-new (never scheduled) assignment would match nothing and
    produce an empty, vacuously optimal subproblem. The shortfall set is
    therefore unioned in explicitly, and entries without ids (unpinnable)
    have their assignments pulled into the re-solved scope instead of
    being silently dropped.
    """
    impact = reoptimizer.analyze_impact(
        "LOAD_CHANGE",
        {"assignment_ids": shortfall},
        [{**e, "id": e.get("id") or e.get("assignment_id")} for e in prev_entries],
    )
    affected_ids = set(impact.affected_assignment_ids) | set(shortfall)
    for entry in prev_entries:
        if entry.get("id") is None and entry.get("assignment_id") is not None:
            affected_ids.add(entry["assignment_id"])
    pinned = [
        e
        for e in prev_entries
        if e.get("id") is not None and e.get("assignment_id") not in affected_ids
    ]
    scoped_impact = ImpactReport(
        affected_entry_ids=[
            e["id"]
            for e in prev_entries
            if e.get("id") is not None and e.get("assignment_id") in affected_ids
        ],
        pinned_entry_ids=[e["id"] for e in pinned],
        affected_assignment_ids=list(affected_ids),
        affected_resource_ids=[],
        affected_time_slot_ids=[],
    )
    scoped_input = reoptimizer.build_subproblem(
        scoped_impact,
        solver_input.assignments,
        solver_input.resources,
        solver_input.time_slots,
        prev_entries,
        two_hour_grid=solver_input.two_hour_grid,
        blocked_faculty_slots=solver_input.blocked_faculty_slots,
        blocked_resource_slots=solver_input.blocked_resource_slots,
    )
    return scoped_input, pinned


async def persist_repaired_version(
    db,
    timetable_id: UUID,
    requested_by,
    prev_number: int,
    prev_entries: list[dict],
    entries: list[dict],
    record,
    original_diagnostics: list[str],
    unscheduled: list[dict[str, Any]],
    attempt_count: int,
) -> dict[str, Any]:
    """Persist a validated candidate as a new REPAIR version, atomically.

    Version + entries + audit commit once. Must only be called after the
    independent validator has passed on ``entries``.
    """
    from app.workers.timetable_worker import (
        compute_entry_diff,
        lock_timetable,
        v2_diff_suffix,
    )

    diff = compute_entry_diff(prev_entries, entries)
    async with transaction(db):
        current = await db.get(Timetable, timetable_id)
        if current is None:
            raise ValueError("Timetable disappeared during repair")
        await lock_timetable(db, timetable_id)
        current.status = "VALIDATED"
        current.generated_by = requested_by
        version = await VersionService(db).create_version(
            timetable_id,
            {
                "change_type": "REPAIR",
                "status": "VALIDATED",
                "entries": entries,
                "change_summary": (
                    "Bounded repair"
                    f" (attempt {record.attempt}: "
                    f"{record.adjustment.kind if record.adjustment else 'none'})"
                    f"{v2_diff_suffix(diff)}"
                ),
            },
            created_by=requested_by,
        )
        db.add(
            AuditLog(
                user_id=requested_by,
                action="REPAIR",
                entity_type="TIMETABLE",
                entity_id=timetable_id,
                old_values={"version_number": prev_number} if prev_number else None,
                new_values={
                    "version_number": version.version_number,
                    "solver_status": record.solver_status,
                    "validation_status": "PASS",
                    "applied_adjustment": (
                        record.adjustment.model_dump() if record.adjustment else None
                    ),
                    "original_diagnostics": original_diagnostics[:50],
                    "unscheduled_before": unscheduled,
                    "unscheduled_after": [],
                    "repair_attempts": attempt_count,
                    "entries_count": len(entries),
                    "diff": {
                        "added": len(diff["added"]),
                        "removed": len(diff["removed"]),
                        "changed": len(diff["changed"]),
                        "kept": len(diff["kept"]),
                    },
                },
            )
        )
    return {
        "solver_status": record.solver_status,
        "validation_status": "PASS",
        "version_id": str(version.id),
        "version_number": version.version_number,
        "entries_count": len(entries),
        "unscheduled": [],
        "diff": {
            "added": len(diff["added"]),
            "removed": len(diff["removed"]),
            "changed": len(diff["changed"]),
            "kept": len(diff["kept"]),
        },
    }
