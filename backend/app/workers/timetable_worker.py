import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, text, update

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
from app.database.models.timetable_job import TimetableJob
from app.database.transactions import end_read_transaction, transaction
from app.scheduler.model import (
    SolverAssignment,
    SolverInput,
    SolverResource,
    SolverTimeSlot,
)
from app.scheduler.reoptimizer import Reoptimizer
from app.scheduler.rules import is_section_level
from app.scheduler.solver import SolverConfig, TimetableSolver
from app.services.notification_service import NotificationService
from app.services.timetable_state import latest_version_for_timetable
from app.services.version_service import VersionService
from app.validators.timetable_validator import TimetableValidator

logger = logging.getLogger(__name__)

# A RUNNING job older than this is considered dead (worker crashed mid-run).
STALE_JOB_SECONDS = max(600, settings.SOLVER_TIME_LIMIT_SECONDS * 2)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _value(v: Any) -> Any:
    """Unwrap enums (e.g. SessionType) to their plain value."""
    return getattr(v, "value", v)


def build_solver_input(
    assignments: list,
    resources: list,
    time_slots: list,
    sections: dict[UUID, Any],
    batches: dict[UUID, Any],
) -> SolverInput:
    """Map ORM rows to the solver's typed input, resolving strengths from sections/batches."""
    solver_assignments = []
    for a in assignments:
        section = sections.get(a.section_id)
        batch = batches.get(a.batch_id) if a.batch_id else None
        solver_assignments.append(
            SolverAssignment(
                id=a.id,
                faculty_id=a.faculty_id,
                subject_id=a.subject_id,
                section_id=a.section_id,
                batch_id=a.batch_id,
                session_type=_value(a.session_type),
                hours_per_week=a.hours_per_week,
                session_duration=a.session_duration or 1,
                preferred_days=list(a.preferred_days or []),
                preferred_shifts=list(a.preferred_shifts or []),
                required_lab_type=getattr(a, "required_lab_type", None),
                section_strength=(section.strength or 0) if section else 0,
                batch_strength=(batch.strength or 0) if batch else 0,
            )
        )

    return SolverInput(
        assignments=solver_assignments,
        resources=[
            SolverResource(
                id=r.id,
                name=r.name,
                resource_type=r.resource_type,
                capacity=r.capacity,
                is_emergency=bool(r.is_emergency),
            )
            for r in resources
        ],
        time_slots=[
            SolverTimeSlot(
                id=t.id,
                day_of_week=t.day_of_week,
                period_number=t.period_number,
                slot_type=t.slot_type,
                shift=t.shift,
            )
            for t in time_slots
        ],
    )


def build_entries(solver_entries: list[dict], solver_input: SolverInput) -> list[dict]:
    """Expand solver output (ids only) into full entries for validation and persistence."""
    assignments = {a.id: a for a in solver_input.assignments}
    resources = {r.id: r for r in solver_input.resources}
    slots = {t.id: t for t in solver_input.time_slots}

    entries = []
    for e in solver_entries:
        a = assignments[e["assignment_id"]]
        r = resources[e["resource_id"]]
        t = slots[e["time_slot_id"]]
        entries.append(
            {
                "assignment_id": a.id,
                "faculty_id": a.faculty_id,
                "subject_id": a.subject_id,
                "session_duration": a.session_duration,
                "section_id": a.section_id,
                "batch_id": a.batch_id,
                "session_type": a.session_type,
                "resource_id": r.id,
                "resource_capacity": r.capacity,
                "resource_is_emergency": r.is_emergency,
                "time_slot_id": t.id,
                "day_of_week": t.day_of_week,
                "period_number": t.period_number,
                "section_strength": a.section_strength if is_section_level(a) else 0,
                "batch_strength": a.batch_strength if not is_section_level(a) else 0,
            }
        )
    return entries


def _entry_key(entry: dict):
    """Identity for diffing: the natural key (assignment, resource, time slot).

    Persisted rows also carry an ``id``, but fresh solver rows don't, so the
    natural key is used on both sides. Database unique constraints guarantee no
    two entries of one version share it, and it lets a re-placed-but-identical
    entry diff as "kept" instead of removed+added.
    """
    return (
        "natural",
        entry.get("assignment_id"),
        entry.get("resource_id"),
        entry.get("time_slot_id"),
    )


def compute_entry_diff(previous_entries: list[dict], current_entries: list[dict]) -> dict:
    """Compute added, changed, and removed entries between two versions.

    Returns a dict with:
    - added: list of entry dicts present in current but not in previous
    - removed: list of entry dicts present in previous but not in current
    - changed: list of entry dicts present in both but with differences
    - kept: list of entry dicts unchanged between versions
    """
    prev_by_key = {_entry_key(e): e for e in previous_entries}
    curr_by_key = {_entry_key(e): e for e in current_entries}

    added = []
    removed = []
    changed = []
    kept = []

    # Added entries (in current but not previous)
    for key, entry in curr_by_key.items():
        if key not in prev_by_key:
            added.append(entry)

    # Removed entries (in previous but not current)
    for key, entry in prev_by_key.items():
        if key not in curr_by_key:
            removed.append(entry)

    # Common entries - check for changes
    for key in set(prev_by_key.keys()) & set(curr_by_key.keys()):
        prev = prev_by_key[key]
        curr = curr_by_key[key]
        # Compare key fields
        diff_fields = {
            "faculty_id",
            "subject_id",
            "section_id",
            "batch_id",
            "resource_id",
            "time_slot_id",
            "day_of_week",
            "session_type",
        }
        changes = {}
        for field in diff_fields:
            if prev.get(field) != curr.get(field):
                changes[field] = {"previous": prev.get(field), "current": curr.get(field)}
        if changes:
            # Entry is changed - include current state
            changed.append({**curr, "changes": changes})
        else:
            kept.append(curr)

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "kept": kept,
    }


def v2_diff_suffix(diff: dict | None) -> str:
    """Return a human-readable suffix describing the diff for change summaries."""
    if not diff:
        return ""
    parts = []
    if diff["added"]:
        parts.append(f"{len(diff['added'])} added")
    if diff["removed"]:
        parts.append(f"{len(diff['removed'])} removed")
    if diff["changed"]:
        parts.append(f"{len(diff['changed'])} changed")
    return f" ({', '.join(parts)})"


# ---------------------------------------------------------------------------
# Durable job helpers (timetable_jobs is the source of truth; Redis only
# transports work). All of these run inside the caller's transaction.
# ---------------------------------------------------------------------------


async def lock_timetable(db, timetable_id: UUID) -> None:
    """Serialize mutations for one timetable (PostgreSQL advisory xact lock).

    The lock is transaction-scoped: it is held until the use case's transaction
    commits/rolls back. On non-PostgreSQL test databases this is a no-op; the
    (timetable_id, version_number) unique constraint remains the safety net.
    """
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"timetable:{timetable_id}"},
        )


async def claim_job(db, job_id: str | None) -> bool:
    """Atomically claim a QUEUED job (prevents double execution by 2 workers).

    Commits its own small transaction so the claim is durable before any solve
    work starts. Returns False when the job does not exist or is no longer
    QUEUED (already claimed / finished).
    """
    if not job_id:
        return True  # legacy payloads without a durable job record
    async with transaction(db):
        result = await db.execute(
            update(TimetableJob)
            .where(TimetableJob.id == UUID(job_id), TimetableJob.status == "QUEUED")
            .values(
                status="RUNNING", started_at=_now_utc(), retry_count=TimetableJob.retry_count + 1
            )
        )
    return bool(result.rowcount)


async def set_job_outcome(
    db,
    job_id: str | None,
    status: str,
    error: str | None = None,
    result: dict | None = None,
) -> None:
    """Record the outcome of a job. Runs inside the caller's transaction so a
    SUCCEEDED status is atomic with the timetable version it produced."""
    if not job_id:
        return
    values: dict = {"status": status, "error": error}
    if result is not None:
        values["result"] = _json_safe(result)
    if status in ("SUCCEEDED", "FAILED", "CANCELLED"):
        values["completed_at"] = _now_utc()
    await db.execute(update(TimetableJob).where(TimetableJob.id == UUID(job_id)).values(**values))


async def fail_job(session_factory, job_id: str | None, error: str) -> None:
    """Mark a job FAILED in its own transaction (used on unexpected errors)."""
    if not job_id:
        return
    try:
        async with session_factory() as db, transaction(db):
            await set_job_outcome(db, job_id, "FAILED", error=error)
    except Exception:
        logger.exception("Failed to mark job %s as FAILED", job_id)


def _json_safe(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


async def reconcile_stale_jobs(session_factory) -> int:
    """Mark RUNNING jobs older than STALE_JOB_SECONDS as FAILED.

    Runs at worker startup: a worker that died mid-solve leaves a RUNNING row
    behind, and without this reconciliation the job would be lost forever.
    Returns the number of jobs reaped.
    """
    cutoff = _now_utc() - timedelta(seconds=STALE_JOB_SECONDS)
    try:
        async with session_factory() as db, transaction(db):
            result = await db.execute(
                update(TimetableJob)
                .where(TimetableJob.status == "RUNNING", TimetableJob.started_at < cutoff)
                .values(
                    status="FAILED",
                    error="stale job: worker did not report completion",
                    completed_at=_now_utc(),
                )
            )
        return int(result.rowcount or 0)
    except Exception:
        logger.exception("Stale-job reconciliation failed")
        return 0


class TimetableWorker:
    def __init__(
        self,
        session_factory: Callable = AsyncSessionLocal,
        solver: TimetableSolver | None = None,
    ):
        self.session_factory = session_factory
        self.solver = solver or TimetableSolver(
            SolverConfig(
                time_limit_seconds=settings.SOLVER_TIME_LIMIT_SECONDS,
                num_workers=settings.SOLVER_NUM_WORKERS,
                log_search_progress=settings.DEBUG,
            )
        )

    # ------------------------------------------------------------------
    # Full generation
    # ------------------------------------------------------------------

    async def generate_timetable(self, timetable_id: UUID, requested_by: UUID | None = None):
        """Generate, validate and persist a new timetable version.

        Transaction model (single owner = this use case):
          1. short read transaction  -> snapshot inputs, then END it
          2. CP-SAT solve             -> no DB transaction is held
          3. one write transaction    -> version + entries + audit + notification
                                         + timetable status, committed once
        Nothing is persisted unless the solution passes independent validation.
        """
        async with self.session_factory() as db:
            try:
                return await self._generate(db, timetable_id, requested_by)
            except Exception as exc:
                logger.exception("Timetable generation failed for %s", timetable_id)
                await db.rollback()
                return {"error": f"Unexpected failure: {exc}"}

    async def _generate(self, db, timetable_id: UUID, requested_by: UUID | None):
        # ---------- Phase A: read inputs (short read transaction) ----------
        timetable = await db.get(Timetable, timetable_id)
        if not timetable:
            return {"error": "Timetable not found"}

        term = (
            await db.execute(
                select(AcademicTerm).where(
                    AcademicTerm.academic_year == timetable.academic_year,
                    AcademicTerm.semester == timetable.semester,
                )
            )
        ).scalar_one_or_none()
        if not term:
            return {
                "error": (
                    f"No academic term for {timetable.academic_year} semester {timetable.semester}"
                )
            }

        created_by = requested_by or timetable.generated_by
        if created_by is None:
            return {"error": "No user to attribute the new version to (pass requested_by)"}

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
        resources = list(
            (await db.execute(select(Resource).where(Resource.is_active.is_(True)))).scalars().all()
        )
        time_slots = list(
            (
                await db.execute(
                    select(TimeSlot).where(
                        TimeSlot.template_id == timetable.template_id,
                        TimeSlot.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )

        for label, rows in (
            ("teaching assignments", assignments),
            ("resources", resources),
            ("time slots", time_slots),
        ):
            if not rows:
                return {"error": f"No active {label} found for this timetable"}

        section_ids = {a.section_id for a in assignments}
        batch_ids = {a.batch_id for a in assignments if a.batch_id}
        sections = {
            s.id: s
            for s in (await db.execute(select(Section).where(Section.id.in_(section_ids))))
            .scalars()
            .all()
        }
        batches = {}
        if batch_ids:
            batches = {
                b.id: b
                for b in (await db.execute(select(Batch).where(Batch.id.in_(batch_ids))))
                .scalars()
                .all()
            }

        solver_input = build_solver_input(assignments, resources, time_slots, sections, batches)
        required_hours = {a.id: a.hours_per_week for a in solver_input.assignments}

        # Diff baseline + version number allocation baseline, captured as plain
        # data so nothing ORM-backed is needed after the read transaction ends.
        prev_version = await latest_version_for_timetable(db, timetable_id)
        prev_number = prev_version.version_number if prev_version else 0
        prev_entries_dict: list[dict] = []
        if prev_version:
            prev_rows = (
                (
                    await db.execute(
                        select(TimetableEntry).where(TimetableEntry.version_id == prev_version.id)
                    )
                )
                .scalars()
                .all()
            )
            prev_entries_dict = [
                {
                    "assignment_id": e.assignment_id,
                    "faculty_id": e.faculty_id,
                    "subject_id": e.subject_id,
                    "section_id": e.section_id,
                    "batch_id": e.batch_id,
                    "resource_id": e.resource_id,
                    "time_slot_id": e.time_slot_id,
                    "day_of_week": e.day_of_week,
                    "period_number": e.period_number,
                    "session_type": e.session_type,
                }
                for e in prev_rows
            ]

        # End the read transaction: CP-SAT may run for minutes and must not
        # hold a PostgreSQL transaction (or connection locks) open.
        await end_read_transaction(db)

        # ---------- Phase B: solve (no DB transaction held) ----------
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, self.solver.solve, solver_input)
        if not result.is_solved:
            return {
                "error": f"Solver found no timetable (status: {result.status_name})",
                "details": result.diagnostics,
                "solve_time": result.solve_time_seconds,
            }

        entries = build_entries(result.entries, solver_input)
        validation = TimetableValidator().validate(entries, required_hours=required_hours)
        if not validation.is_valid:
            return {"error": "Validation failed", "details": validation.errors}

        diff = compute_entry_diff(prev_entries_dict, entries)

        # ---------- Phase C: one write transaction (use case owns it) ----------
        async with transaction(db):
            current = await db.get(Timetable, timetable_id)
            if current is None:
                raise ValueError("Timetable disappeared during generation")
            # Serialize concurrent mutations for this timetable; the unique
            # constraint on (timetable_id, version_number) stays as safety net.
            await lock_timetable(db, timetable_id)

            current.status = "VALIDATED"
            current.generated_by = created_by

            version = await VersionService(db).create_version(
                timetable_id,
                {
                    "change_type": "FULL_REGENERATION",
                    "status": "VALIDATED",
                    "entries": entries,
                    "change_summary": f"Full generation{v2_diff_suffix(diff)}",
                },
                created_by=created_by,
            )

            # Atomic with the version: audit + notification.
            db.add(
                AuditLog(
                    user_id=created_by,
                    action="GENERATE",
                    entity_type="TIMETABLE",
                    entity_id=timetable_id,
                    old_values={"version_number": prev_number} if prev_number else None,
                    new_values={
                        "version_number": version.version_number,
                        "change_type": "FULL_REGENERATION",
                        "entries_count": len(entries),
                    },
                )
            )
            await NotificationService(db).send_notification(
                str(created_by),
                "Timetable Generated",
                f"Timetable {current.name} has been generated successfully.",
                "SUCCESS",
            )

        # Committed. Safe to build the response from durable state.
        return {
            "success": True,
            "version_id": str(version.id),
            "version_number": version.version_number,
            "entries_count": len(entries),
            "warnings": validation.warnings,
            "solve_time": result.solve_time_seconds,
            "diff": {
                "added": len(diff["added"]),
                "removed": len(diff["removed"]),
                "changed": len(diff["changed"]),
                "kept": len(diff["kept"]),
            },
        }

    # ------------------------------------------------------------------
    # Reoptimization (durable job workflow)
    # ------------------------------------------------------------------

    async def reoptimize_timetable(
        self, timetable_id: UUID, change_data: dict, job_id: str | None = None
    ):
        async with self.session_factory() as db:
            try:
                return await self._reoptimize(db, timetable_id, change_data, job_id)
            except Exception as exc:
                logger.exception("Reoptimization failed for %s", timetable_id)
                await db.rollback()
                await fail_job(self.session_factory, job_id, str(exc))
                return {"error": f"Unexpected failure: {exc}"}

    async def _reoptimize(self, db, timetable_id: UUID, change_data: dict, job_id: str | None):
        # Step 0: claim the durable job (prevents double execution by two workers).
        if job_id:
            claimed = await claim_job(db, job_id)
            if not claimed:
                return {
                    "error": "Job is not claimable (already running/finished)",
                    "job_id": job_id,
                }

        # ---------- Phase A: read inputs (short read transaction) ----------
        timetable = await db.get(Timetable, timetable_id)
        if not timetable:
            await self._fail_current(db, job_id, "Timetable not found")
            return {"error": "Timetable not found"}
        # Plain copy: end_read_transaction() rolls back and expires every ORM
        # object, so the name must not be read off ``timetable`` afterwards.
        timetable_name = timetable.name
        change_type = self._detect_change_type(change_data)

        latest_version = await latest_version_for_timetable(db, timetable_id)
        if not latest_version:
            await self._fail_current(db, job_id, "No versions found for this timetable")
            return {"error": "No versions found for this timetable"}
        parent_version_id = latest_version.id
        parent_number = latest_version.version_number

        entries = (
            (
                await db.execute(
                    select(TimetableEntry).where(TimetableEntry.version_id == latest_version.id)
                )
            )
            .scalars()
            .all()
        )
        current_entries = [
            {
                "id": e.id,
                "assignment_id": e.assignment_id,
                "faculty_id": e.faculty_id,
                "subject_id": e.subject_id,
                "section_id": e.section_id,
                "batch_id": e.batch_id,
                "resource_id": e.resource_id,
                "time_slot_id": e.time_slot_id,
                "day_of_week": e.day_of_week,
                "period_number": e.period_number,
                "session_type": e.session_type,
            }
            for e in entries
        ]

        # NOTE: a template change lists the slots RETAINED by the new template
        # (same semantics as Reoptimizer.analyze_impact / build_subproblem).
        # Entries on non-retained slots are affected and re-solve within the
        # retained slots; feasibility is decided by the solver, not by a
        # pre-check (a disjoint retained set can still be feasible when
        # capacity allows the affected sessions to move).

        term = (
            await db.execute(
                select(AcademicTerm).where(
                    AcademicTerm.academic_year == timetable.academic_year,
                    AcademicTerm.semester == timetable.semester,
                )
            )
        ).scalar_one_or_none()
        if not term:
            await self._fail_current(db, job_id, "No academic term for this timetable")
            return {"error": "No academic term for this timetable"}

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
        resources = list(
            (await db.execute(select(Resource).where(Resource.is_active.is_(True)))).scalars().all()
        )
        time_slots = list(
            (
                await db.execute(
                    select(TimeSlot).where(
                        TimeSlot.template_id == timetable.template_id,
                        TimeSlot.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )

        section_ids = {a.section_id for a in assignments}
        sections = {
            s.id: s
            for s in (await db.execute(select(Section).where(Section.id.in_(section_ids))))
            .scalars()
            .all()
        }
        batch_ids = {a.batch_id for a in assignments if a.batch_id}
        batches = {}
        if batch_ids:
            batches = {
                b.id: b
                for b in (await db.execute(select(Batch).where(Batch.id.in_(batch_ids))))
                .scalars()
                .all()
            }

        solver_input = build_solver_input(assignments, resources, time_slots, sections, batches)
        required_hours = {a.id: a.hours_per_week for a in solver_input.assignments}

        # Pinned entries keep their session duration / strengths so the merged
        # timetable can be validated with exactly the same information a fresh
        # solve would have.
        duration_by_assignment = {a.id: a.session_duration for a in solver_input.assignments}
        strength_by_assignment = {
            a.id: (a.section_strength, a.batch_strength) for a in solver_input.assignments
        }
        for entry in current_entries:
            entry["session_duration"] = duration_by_assignment.get(entry["assignment_id"], 1) or 1
            sec, bat = strength_by_assignment.get(entry["assignment_id"], (0, 0))
            entry["section_strength"] = sec
            entry["batch_strength"] = bat

        # Step 1: impact analysis - determine affected vs pinned entries
        reoptimizer = Reoptimizer()
        impact = reoptimizer.analyze_impact(change_type, change_data, current_entries)

        if not impact.affected_entry_ids:
            message = (
                f"Reoptimization has no affected entries for change type "
                f"{change_type}; nothing to re-optimize"
            )
            await self._fail_current(db, job_id, message)
            return {"error": message}

        # Step 2: build subproblem - affected assignments re-solve within the
        # full active space; pinned entries constrain placements and are merged
        # back into the persisted version untouched.
        subproblem = reoptimizer.build_subproblem(
            impact,
            solver_input.assignments,
            solver_input.resources,
            solver_input.time_slots,
            current_entries,
            change_type=change_type,
            change_data=change_data,
        )

        # End the read transaction before solving (see _generate).
        await end_read_transaction(db)

        # ---------- Phase B: solve (no DB transaction held) ----------
        solver_config = SolverConfig(
            time_limit_seconds=60,
            num_workers=settings.SOLVER_NUM_WORKERS,
            log_search_progress=settings.DEBUG,
        )
        solver = TimetableSolver(solver_config)
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, solver.solve, subproblem)

        if not result.is_solved:
            message = f"Solver found no feasible re-timetable (status: {result.status_name})"
            await self._fail_current(db, job_id, message, details=result.diagnostics)
            return {
                "error": message,
                "diagnostics": result.diagnostics,
                "solve_time": result.solve_time_seconds,
            }

        # Step 4: build entries, merge pinned entries back, validate the
        # combined timetable independently. Validating only the re-solved scope
        # would be vacuous - the persisted version is pinned + new.
        new_entries = build_entries(result.entries, subproblem)
        pinned_ids = set(impact.pinned_entry_ids)
        pinned_entries = [e for e in current_entries if e["id"] in pinned_ids]

        # Merge safety: a re-solved entry that lands on exactly a pinned
        # entry's (assignment, resource, slot) is a duplicate; the pinned row
        # wins so the unique constraints can never be violated.
        pinned_keys = {_entry_key(e) for e in pinned_entries}
        new_entries = [e for e in new_entries if _entry_key(e) not in pinned_keys]

        combined_entries = pinned_entries + new_entries

        if not combined_entries:
            message = (
                "Reoptimization produced zero entries; parent version has valid "
                "entries but combined result is empty"
            )
            await self._fail_current(db, job_id, message)
            return {"error": message}

        validator = TimetableValidator()
        validation = validator.validate(combined_entries, required_hours=required_hours)
        if not validation.is_valid:
            message = "Validation failed"
            await self._fail_current(db, job_id, message, details=validation.errors)
            return {"error": message, "details": validation.errors}

        diff = compute_entry_diff(current_entries, combined_entries)

        # ---------- Phase C: one write transaction (use case owns it) ----------
        async with transaction(db):
            await lock_timetable(db, timetable_id)

            # Optimistic concurrency: if another use case moved the latest
            # version while we were solving, our snapshot is stale. Fail
            # cleanly (the client retries); never merge onto the wrong parent.
            latest_now = await latest_version_for_timetable(db, timetable_id)
            if latest_now is None or latest_now.id != parent_version_id:
                raise StaleParentError(
                    f"Timetable changed during reoptimization "
                    f"(parent version {parent_number} is no longer latest); retry"
                )

            created_by = latest_now.created_by
            version = await VersionService(db).create_version(
                timetable_id,
                {
                    "change_type": change_type,
                    "status": "VALIDATED",
                    "entries": combined_entries,
                    "change_summary": f"{change_type} reoptimization{v2_diff_suffix(diff)}",
                },
                created_by=created_by,
            )

            # Atomic with the version: audit + notification + job outcome.
            db.add(
                AuditLog(
                    user_id=created_by,
                    action="REOPTIMIZE",
                    entity_type="TIMETABLE",
                    entity_id=timetable_id,
                    old_values={"version_number": parent_number},
                    new_values={
                        "version_number": version.version_number,
                        "change_type": change_type,
                        "affected_entries": len(impact.affected_entry_ids),
                        "pinned_entries": len(impact.pinned_entry_ids),
                        "diff": {k: len(v) for k, v in diff.items()},
                    },
                )
            )
            await NotificationService(db).send_notification(
                str(created_by),
                "Timetable Reoptimized",
                f"Timetable {timetable_name} has been reoptimized successfully.",
                "SUCCESS",
            )
            outcome = {
                "success": True,
                "version_id": str(version.id),
                "version_number": version.version_number,
                "entries_count": len(combined_entries),
                "affected_entries": len(impact.affected_entry_ids),
                "pinned_entries": len(impact.pinned_entry_ids),
                "warnings": validation.warnings,
                "solve_time": result.solve_time_seconds,
                "change_type": change_type,
                "diff": {k: len(v) for k, v in diff.items()},
            }
            await set_job_outcome(db, job_id, "SUCCEEDED", result=outcome)

        return outcome

    async def _fail_current(
        self, db, job_id: str | None, message: str, details: list | None = None
    ) -> None:
        """Record a FAILED job outcome when a use case fails before its write
        transaction (own transaction; the caller then returns an error)."""
        try:
            async with transaction(db):
                await set_job_outcome(
                    db, job_id, "FAILED", error=message, result={"details": details or []}
                )
        except Exception:
            await db.rollback()
            logger.exception("Failed to record job failure: %s", message)

    _KNOWN_CHANGE_TYPES = (
        "LOAD_CHANGE",
        "RESOURCE_CHANGE",
        "FACULTY_AVAILABILITY",
        "TEMPLATE_CHANGE",
        "LEAVE",
    )

    def _detect_change_type(self, change_data: dict) -> str:
        """Resolve the change type: explicit value first, then key inference.

        The LEAVE check must come before the bare faculty_id check, otherwise a
        leave payload (faculty_id + date_range) is misread as a plain
        availability change.
        """
        if not change_data:
            return "LOAD_CHANGE"
        explicit = change_data.get("change_type")
        if explicit in self._KNOWN_CHANGE_TYPES:
            return str(explicit)
        keys = set(change_data.keys())
        if "faculty_id" in keys and "date_range" in keys:
            return "LEAVE"
        if "assignment_ids" in keys:
            return "LOAD_CHANGE"
        if "resource_id" in keys:
            return "RESOURCE_CHANGE"
        if "time_slot_ids" in keys:
            return "TEMPLATE_CHANGE"
        if "faculty_id" in keys:
            return "FACULTY_AVAILABILITY"
        return "LOAD_CHANGE"


class StaleParentError(RuntimeError):
    """Raised when the timetable changed between the read phase and the write
    phase of a reoptimization (optimistic-concurrency failure)."""
