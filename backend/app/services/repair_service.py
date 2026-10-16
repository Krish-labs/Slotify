"""Bounded repair workflow for failed or incomplete timetable generation.

Repair runs only after the baseline solver and the independent validator have
spoken: it takes structured validation/solver diagnostics, applies a small
queue of caller-approved constraint adjustments, re-runs CP-SAT, and validates
the result independently before persisting anything.

Safety properties:

- Retry limit: at most ``max_retries`` re-solves (default 2, hard cap 5).
- The LLM may *suggest* candidate adjustments (see
  ``ai_constraint_service.suggest_repair_adjustments``), but suggestions are
  re-validated here and approval-gated kinds still need explicit approval.
- Availability overrides (lifting a leave/resource block, pulling an inactive
  room into one solve) require ``approve_hard_relaxation=True``; without it
  they are rejected with a useful error instead of being applied silently.
- Hard-conflict relaxations (ignore a faculty/room/student clash, exceed the
  daily limit, seat a session in an unsuitable room) are not representable:
  unknown ``kind`` values are rejected as unsupported.
- A repaired candidate is persisted only after independent validation passes,
  in a single transaction (version + entries + audit). Failed repair persists
  nothing except a ``REPAIR_FAILED`` audit row, and returns the original
  diagnostics with an honest incomplete/infeasible outcome.
- Unaffected entries are preserved via the :class:`Reoptimizer` pinned scope
  whenever the failure scope is a strict subset of the demand.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.core.config import settings
from app.database.connection import AsyncSessionLocal
from app.database.models.academic_term import AcademicTerm
from app.database.models.audit_log import AuditLog
from app.database.models.batch import Batch
from app.database.models.resource import Resource
from app.database.models.section import Section
from app.database.models.teaching_assignment import TeachingAssignment
from app.database.models.time_slot import TimeSlot
from app.database.models.timetable import Timetable
from app.database.models.timetable_entry import TimetableEntry
from app.database.transactions import end_read_transaction, transaction
from app.scheduler.model import SolverInput, SolverResource
from app.scheduler.reoptimizer import Reoptimizer
from app.scheduler.solver import SolverConfig, TimetableSolver
from app.schemas.repair import (
    ABSOLUTE_MAX_REPAIR_ATTEMPTS,
    APPROVAL_GATED_KINDS,
    DEFAULT_MAX_REPAIR_ATTEMPTS,
    RepairAdjustment,
    RepairAttemptRecord,
    shortfall_assignments,
    unscheduled_demand,
)
from app.services.repair_solver import (
    apply_adjustment,
    deterministic_suggestions,
    enrich_entries,
    entry_to_dict,
    persist_repaired_version,
    scoped_subproblem,
)
from app.services.timetable_state import latest_version_for_timetable
from app.validators.timetable_validator import TimetableValidator

# NOTE: build_solver_input / load_availability_blocks / build_entries from
# app.workers.timetable_worker are imported lazily inside methods. The worker
# depends on app.services modules, so a module-level import here would create
# a services <-> workers cycle
# (services/__init__ -> repair_service -> timetable_worker -> services.*).

logger = logging.getLogger(__name__)


class RepairService:
    def __init__(
        self,
        session_factory: Callable = AsyncSessionLocal,
        solver: TimetableSolver | None = None,
    ):
        self.session_factory = session_factory
        self.solver = solver
        self.reoptimizer = Reoptimizer(solver or TimetableSolver())

    def _solver_for(self, adjustment: RepairAdjustment | None) -> TimetableSolver:
        if self.solver is not None and (
            adjustment is None or adjustment.kind != "extend_time_limit"
        ):
            return self.solver
        limit = settings.SOLVER_TIME_LIMIT_SECONDS
        if adjustment is not None and adjustment.time_limit_seconds:
            limit = adjustment.time_limit_seconds
        return TimetableSolver(
            SolverConfig(
                time_limit_seconds=limit,
                num_workers=settings.SOLVER_NUM_WORKERS,
                log_search_progress=False,
            )
        )

    async def repair_timetable(
        self,
        timetable_id: UUID,
        requested_by: UUID,
        *,
        adjustments: list[dict[str, Any]] | None = None,
        max_retries: int = DEFAULT_MAX_REPAIR_ATTEMPTS,
        approve_hard_relaxation: bool = False,
        suggest: bool = False,
    ) -> dict[str, Any]:
        """Attempt a bounded repair of a timetable's scheduling problem."""
        if not 1 <= max_retries <= ABSOLUTE_MAX_REPAIR_ATTEMPTS:
            return {
                "error": (f"max_retries must be between 1 and {ABSOLUTE_MAX_REPAIR_ATTEMPTS}"),
                "repair_attempts": 0,
            }
        parsed: list[RepairAdjustment] = []
        for raw in adjustments or []:
            try:
                parsed.append(RepairAdjustment.model_validate(raw))
            except Exception as exc:  # noqa: BLE001 - boundary: report, don't crash
                return {
                    "error": f"Unsupported repair adjustment {raw!r}: {exc}",
                    "stage": "adjustment_validation",
                    "repair_attempts": 0,
                    "supported_kinds": sorted(
                        ["full_regeneration", "extend_time_limit"] + sorted(APPROVAL_GATED_KINDS)
                    ),
                }
        gated = [a for a in parsed if a.needs_approval()]
        if gated and not approve_hard_relaxation:
            return {
                "error": (
                    "Explicit approval is required before overriding availability: "
                    + ", ".join(sorted({a.kind for a in gated}))
                    + ". Resubmit with approve_hard_relaxation=true."
                ),
                "stage": "approval_required",
                "repair_attempts": 0,
                "gated_adjustments": [a.model_dump() for a in gated],
            }

        async with self.session_factory() as db:
            try:
                return await self._repair(
                    db,
                    timetable_id,
                    requested_by,
                    parsed,
                    max_retries,
                    suggest,
                )
            except Exception as exc:  # noqa: BLE001 - boundary: honest failure
                logger.exception("Repair failed for %s", timetable_id)
                await db.rollback()
                return {"error": f"Unexpected failure: {exc}", "repair_attempts": 0}

    async def _repair(
        self,
        db,
        timetable_id: UUID,
        requested_by: UUID,
        parsed: list[RepairAdjustment],
        max_retries: int,
        suggest: bool,
    ) -> dict[str, Any]:
        timetable = await db.get(Timetable, timetable_id)
        if not timetable:
            return {"error": "Timetable not found", "repair_attempts": 0}
        # Snapshot plain IDs up front: end_read_transaction() expires every ORM
        # object, so nothing ORM-backed may be touched after the solve.
        tt_id = timetable.id
        template_id = timetable.template_id
        academic_year = timetable.academic_year
        semester = timetable.semester
        term = (
            await db.execute(
                select(AcademicTerm).where(
                    AcademicTerm.academic_year == academic_year,
                    AcademicTerm.semester == semester,
                )
            )
        ).scalar_one_or_none()
        if not term:
            return {
                "error": (f"No academic term for {academic_year} semester {semester}"),
                "repair_attempts": 0,
            }

        assignments = list(
            (
                await db.execute(
                    select(TeachingAssignment).where(
                        TeachingAssignment.academic_term_id == term.id,
                        TeachingAssignment.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not assignments:
            return {"error": "No active teaching assignments to repair", "repair_attempts": 0}
        resources = list(
            (await db.execute(select(Resource).where(Resource.is_active.is_(True)))).scalars().all()
        )
        inactive_resources = list(
            (await db.execute(select(Resource).where(Resource.is_active.is_(False))))
            .scalars()
            .all()
        )
        # Snapshot everything the post-solve rebuild needs as plain dataclasses
        # BEFORE end_read_transaction(): after the rollback every ORM attribute
        # access would trigger an implicit refresh outside a transaction.
        inactive_pool = [
            SolverResource(
                id=r.id,
                name=r.name,
                resource_type=r.resource_type,
                capacity=r.capacity,
                is_emergency=bool(r.is_emergency),
            )
            for r in inactive_resources
        ]
        time_slots = list(
            (
                await db.execute(
                    select(TimeSlot).where(
                        TimeSlot.template_id == template_id,
                        TimeSlot.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not resources or not time_slots:
            return {
                "error": "No active resources or time slots to repair with",
                "repair_attempts": 0,
            }

        section_ids = {a.section_id for a in assignments}
        sections = {
            s.id: s
            for s in (await db.execute(select(Section).where(Section.id.in_(section_ids))))
            .scalars()
            .all()
        }
        batch_ids = {a.batch_id for a in assignments if a.batch_id}
        batches: dict = {}
        if batch_ids:
            batches = {
                b.id: b
                for b in (await db.execute(select(Batch).where(Batch.id.in_(batch_ids))))
                .scalars()
                .all()
            }

        from app.workers.timetable_worker import build_solver_input, load_availability_blocks

        blocked_faculty, blocked_resources = await load_availability_blocks(
            db, time_slots, resources, academic_year
        )
        base_input = build_solver_input(
            assignments,
            resources,
            time_slots,
            sections,
            batches,
            blocked_faculty,
            blocked_resources,
        )
        required_hours = {a.id: a.hours_per_week for a in base_input.assignments}

        prev_version = await latest_version_for_timetable(db, timetable_id)
        prev_version_id = prev_version.id if prev_version else None
        prev_number = prev_version.version_number if prev_version else 0
        prev_rows: list = []
        if prev_version_id is not None:
            prev_rows = list(
                (
                    await db.execute(
                        select(TimetableEntry).where(TimetableEntry.version_id == prev_version_id)
                    )
                )
                .scalars()
                .all()
            )
        prev_entries = [entry_to_dict(row) for row in prev_rows]
        validation = TimetableValidator().validate(
            enrich_entries(prev_entries, base_input),
            required_hours=required_hours,
            check_resource_compatibility=True,
            blocked_faculty_slots=base_input.blocked_faculty_slots,
            blocked_resource_slots=base_input.blocked_resource_slots,
        )
        original_diagnostics = list(validation.errors)
        unscheduled = unscheduled_demand(prev_entries, required_hours)
        if validation.is_valid and not unscheduled:
            await end_read_transaction(db)
            return {
                "repaired": False,
                "reason": "latest version already validates with complete coverage",
                "repair_attempts": 0,
                "validation_status": "PASS",
            }

        queue = list(parsed)
        not_attempted: list[dict[str, Any]] = []
        if suggest and not queue:
            queue = deterministic_suggestions(original_diagnostics)
        if len(queue) > max_retries:
            not_attempted = [a.model_dump() for a in queue[max_retries:]]
            queue = queue[:max_retries]
        # A fallback full-scope re-solve guarantees the retry budget is spent
        # on a genuinely different CP-SAT problem instead of idling.
        if len(queue) < max_retries and not any(a.kind == "full_regeneration" for a in queue):
            queue.append(RepairAdjustment(kind="full_regeneration", reason="fallback"))
        queue = queue[:max_retries]

        await end_read_transaction(db)

        attempts: list[RepairAttemptRecord] = []
        for index, adjustment in enumerate(queue, start=1):
            record = await self._attempt(
                base_input=base_input,
                inactive_pool=inactive_pool,
                prev_entries=prev_entries,
                required_hours=required_hours,
                adjustment=adjustment,
                attempt=index,
            )
            attempts.append(record)
            if record.applied:
                persisted = await persist_repaired_version(
                    db,
                    tt_id,
                    requested_by,
                    prev_number,
                    prev_entries,
                    list(record.entries),
                    record,
                    original_diagnostics,
                    unscheduled,
                    len(attempts),
                )
                return {
                    "success": True,
                    "repaired": True,
                    "status": "VALIDATED",
                    **persisted,
                    "repair_attempts": len(attempts),
                    "attempts": [a.model_dump() for a in attempts],
                    "not_attempted": not_attempted,
                    "original_diagnostics": original_diagnostics,
                }

        async with transaction(db):
            db.add(
                AuditLog(
                    user_id=requested_by,
                    action="REPAIR_FAILED",
                    entity_type="TIMETABLE",
                    entity_id=tt_id,
                    new_values={
                        "original_diagnostics": original_diagnostics[:50],
                        "unscheduled": unscheduled,
                        "repair_attempts": len(attempts),
                        "attempts": [a.model_dump() for a in attempts],
                    },
                )
            )
        outcome = (
            "infeasible"
            if any("INFEASIBLE" in (a.solver_status or "") for a in attempts)
            else "incomplete"
        )
        return {
            "error": (
                f"Repair failed after {len(attempts)} attempt(s); "
                f"the timetable remains {outcome} and nothing was published"
            ),
            "stage": "repair_exhausted",
            "outcome": outcome,
            "repair_attempts": len(attempts),
            "attempts": [a.model_dump() for a in attempts],
            "not_attempted": not_attempted,
            "original_diagnostics": original_diagnostics,
            "unscheduled": unscheduled,
        }

    async def _attempt(
        self,
        *,
        base_input: SolverInput,
        inactive_pool: list[SolverResource],
        prev_entries: list[dict],
        required_hours: dict,
        adjustment: RepairAdjustment,
        attempt: int,
    ) -> RepairAttemptRecord:
        record = RepairAttemptRecord(attempt=attempt, adjustment=adjustment)
        solver_input, adjustment_error = apply_adjustment(
            base_input,
            inactive_pool,
            adjustment,
        )
        if solver_input is None:
            record.validation_errors = [adjustment_error or "invalid adjustment"]
            return record
        shortfall = shortfall_assignments(prev_entries, required_hours)
        # Full scope unless a strict, pinnable subset failed: with no previous
        # entries there is nothing to preserve, and an empty current_entries
        # list would make analyze_impact return an empty (vacuously optimal)
        # subproblem instead of a real repair.
        if (
            adjustment.kind == "full_regeneration"
            or not prev_entries
            or not shortfall
            or len(shortfall) >= len(required_hours)
        ):
            scoped_input = solver_input
            pinned: list[dict] = []
        else:
            scoped_input, pinned = scoped_subproblem(
                self.reoptimizer, solver_input, prev_entries, shortfall
            )

        solver = self._solver_for(adjustment)
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, solver.solve, scoped_input)
        record.solver_status = result.status_name
        record.solver_diagnostics = list(result.diagnostics)
        if not result.has_feasible_solution:
            record.validation_errors = list(result.diagnostics) or [
                f"Solver produced no candidate (status: {result.status_name})"
            ]
            return record
        from app.workers.timetable_worker import build_entries

        candidate = build_entries(result.entries, scoped_input)
        combined = candidate + enrich_entries(pinned, solver_input)
        validation = TimetableValidator().validate(
            combined,
            required_hours=required_hours,
            check_resource_compatibility=True,
            blocked_faculty_slots=solver_input.blocked_faculty_slots,
            blocked_resource_slots=solver_input.blocked_resource_slots,
        )
        record.validation_errors = list(validation.errors)
        if validation.is_valid:
            record.applied = True
            record.entries = combined
        return record
