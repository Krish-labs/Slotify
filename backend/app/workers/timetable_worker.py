import asyncio
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text, update

from app.core.config import settings
from app.core.workbook_paths import source_workbook_path, timing_reference_path
from app.database.connection import AsyncSessionLocal
from app.database.models.academic_term import AcademicTerm
from app.database.models.audit_log import AuditLog
from app.database.models.batch import Batch
from app.database.models.faculty_load import FacultyLoad
from app.database.models.leave import Leave
from app.database.models.resource import Resource
from app.database.models.resource_availability import ResourceAvailability
from app.database.models.section import Section
from app.database.models.teaching_assignment import TeachingAssignment
from app.database.models.time_slot import TimeSlot
from app.database.models.timetable import Timetable
from app.database.models.timetable_entry import TimetableEntry
from app.database.models.timetable_job import TimetableJob
from app.database.models.timetable_template import TimetableTemplate
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
from app.scheduler.time_slots import ALLOWED_RESOURCE_NAMES, CANONICAL_SLOTS, WORKING_DAYS
from app.scheduler.workbook_demand import parse_workbook_demand
from app.services.load_source_service import WorkbookParseError
from app.services.notification_service import NotificationService
from app.services.timetable_state import latest_version_for_timetable
from app.services.timing_reference import reference_teaching_times, reference_time_slots
from app.services.version_service import VersionService
from app.services.workbook_schedule_service import WorkbookScheduleService
from app.validators.timetable_validator import TimetableValidator

logger = logging.getLogger(__name__)

# A RUNNING job older than this is considered dead (worker crashed mid-run).
STALE_JOB_SECONDS = max(600, settings.SOLVER_TIME_LIMIT_SECONDS * 2)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _value(v: Any) -> Any:
    """Unwrap enums (e.g. SessionType) to their plain value."""
    return getattr(v, "value", v)


def _time_overlaps(
    slot_start: time | None,
    slot_end: time | None,
    blocked_start: time | None,
    blocked_end: time | None,
) -> bool:
    if not blocked_start or not blocked_end or not slot_start or not slot_end:
        return True
    return slot_start < blocked_end and blocked_start < slot_end


async def load_availability_blocks(
    db, time_slots: list, resources: list, academic_year: str | None = None
) -> tuple[set, set]:
    """Resolve persisted leave and resource blackouts to solver slot IDs.

    Missing availability rows preserve the existing default of available. A
    leave with no time window blocks the whole matching weekday; explicit
    resource rows block only unavailable overlapping slots.
    """
    faculty_blocks: set[tuple[UUID, UUID]] = set()
    resource_blocks: set[tuple[UUID, UUID]] = set()
    leaves = list(
        (await db.execute(select(Leave).where(Leave.status.in_(("PENDING", "APPROVED")))))
        .scalars()
        .all()
    )
    for leave in leaves:
        current = leave.start_date
        while current <= leave.end_date:
            for slot in time_slots:
                if slot.day_of_week == current.weekday() and _time_overlaps(
                    slot.start_time, slot.end_time, leave.start_time, leave.end_time
                ):
                    faculty_blocks.add((leave.faculty_id, slot.id))
            current += timedelta(days=1)

    resource_ids = [resource.id for resource in resources]
    if resource_ids:
        rows = list(
            (
                await db.execute(
                    select(ResourceAvailability).where(
                        ResourceAvailability.resource_id.in_(resource_ids),
                        ResourceAvailability.is_available.is_(False),
                        *(
                            [ResourceAvailability.academic_year == academic_year]
                            if academic_year
                            else []
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            for slot in time_slots:
                if slot.day_of_week == row.day_of_week and _time_overlaps(
                    slot.start_time, slot.end_time, row.start_time, row.end_time
                ):
                    resource_blocks.add((row.resource_id, slot.id))
    return faculty_blocks, resource_blocks


def build_solver_input(
    assignments: list,
    resources: list,
    time_slots: list,
    sections: dict[UUID, Any],
    batches: dict[UUID, Any],
    blocked_faculty_slots: set[tuple[UUID, UUID]] | None = None,
    blocked_resource_slots: set[tuple[UUID, UUID]] | None = None,
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

    canonical = {
        (day, slot.period_number, slot.start_time, slot.end_time)
        for day in WORKING_DAYS
        for slot in CANONICAL_SLOTS
    }
    actual = {
        (t.day_of_week, t.period_number, t.start_time, t.end_time)
        for t in time_slots
        if t.slot_type == "TEACHING"
    }
    two_hour_grid = actual == canonical
    if two_hour_grid:
        resources = [
            r
            for r in resources
            if r.name in ALLOWED_RESOURCE_NAMES
            and r.resource_type == ALLOWED_RESOURCE_NAMES[r.name][0]
        ]

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
                start_time=getattr(t, "start_time", None),
                end_time=getattr(t, "end_time", None),
            )
            for t in time_slots
        ],
        two_hour_grid=two_hour_grid,
        blocked_faculty_slots=blocked_faculty_slots or set(),
        blocked_resource_slots=blocked_resource_slots or set(),
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
                "resource_type": r.resource_type,
                "required_lab_type": a.required_lab_type,
                "resource_is_emergency": r.is_emergency,
                "time_slot_id": t.id,
                "day_of_week": t.day_of_week,
                "period_number": t.period_number,
                "start_time": t.start_time,
                "end_time": t.end_time,
                "duration_minutes": (
                    int(
                        (t.end_time.hour * 60 + t.end_time.minute)
                        - (t.start_time.hour * 60 + t.start_time.minute)
                    )
                    if t.start_time and t.end_time
                    else 60
                ),
                "two_hour_grid": solver_input.two_hour_grid,
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
    if isinstance(value, list | tuple):
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
            except WorkbookParseError as exc:
                await db.rollback()
                return {
                    "error": "Unable to parse the source workbook",
                    "stage": "source_workbook",
                    "details": [str(exc)],
                    "sheet": exc.sheet,
                    "row": exc.row,
                    "field": exc.field,
                }
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

        if not assignments:
            approved_loads = int(
                await db.scalar(
                    select(func.count())
                    .select_from(FacultyLoad)
                    .where(
                        FacultyLoad.academic_term_id == term.id,
                        FacultyLoad.is_active.is_(True),
                        FacultyLoad.is_approved.is_(True),
                    )
                )
                or 0
            )
            return {
                "error": "No active teaching assignments found for this timetable",
                "stage": "approved_load_to_assignment",
                "details": [
                    f"Approved FacultyLoad records for this term: {approved_loads}",
                    "Approve FacultyLoad records to derive TeachingAssignment records before generation.",
                ],
            }

        for label, rows in (("resources", resources), ("time slots", time_slots)):
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

        blocked_faculty_slots, blocked_resource_slots = await load_availability_blocks(
            db, time_slots, resources, timetable.academic_year
        )
        solver_input = build_solver_input(
            assignments,
            resources,
            time_slots,
            sections,
            batches,
            blocked_faculty_slots,
            blocked_resource_slots,
        )
        if solver_input.two_hour_grid and not solver_input.resources:
            return {
                "error": "No compatible department rooms are registered",
                "details": [
                    "Register classrooms 309, 311, 314; software labs 307A, 307B, 308A, 308B; hardware labs 303, 304, 305, 306."
                ],
            }
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
            outcome = "infeasible" if result.is_infeasible else "unknown"
            return {
                "error": f"Solver did not produce a timetable (status: {result.status_name}; outcome: {outcome})",
                "details": result.diagnostics,
                "solve_time": result.solve_time_seconds,
                "solver_status": result.status_name,
                "optimality_proven": result.optimality_proven,
            }

        entries = build_entries(result.entries, solver_input)
        validation = TimetableValidator().validate(
            entries,
            required_hours=required_hours,
            check_resource_compatibility=True,
            blocked_faculty_slots=solver_input.blocked_faculty_slots,
            blocked_resource_slots=solver_input.blocked_resource_slots,
        )
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
                        "solver_status": result.status_name,
                        "optimality_proven": result.optimality_proven,
                        "validation_status": "PASS",
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
            "solver_status": result.status_name,
            "validation_status": "PASS",
            "conflicts": {k: v for k, v in validation.violations.items() if "conflict" in k},
            "required_sessions": sum(required_hours.values()),
            "unscheduled_sessions": 0,
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

    async def generate_from_workbook(
        self,
        timetable_id: UUID,
        requested_by: UUID,
        source_path: str | Path | None = None,
        reference_path: str | Path | None = None,
    ) -> dict:
        """Generate from the real source workbook through CP-SAT.

        The source workbook is normalized into authoritative assignments, then
        CP-SAT chooses placements. The independent validator gates persistence.
        LLM assistance is limited to the separate constraint/explanation API.
        """
        source = Path(source_path) if source_path else source_workbook_path()
        reference = Path(reference_path) if reference_path else timing_reference_path()
        async with self.session_factory() as db:
            try:
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
                        "error": f"No academic term for {timetable.academic_year} semester {timetable.semester}"
                    }
                term_id = term.id
                if not source.exists():
                    return {"error": f"Source workbook not found: {source}"}
                parsed = parse_workbook_demand(
                    source, timetable.academic_year, timetable.semester, reference, slot_hours=1
                )
                if not parsed.demands or parsed.invalid_rows:
                    return {
                        "error": "Source workbook has no valid teaching demand for the selected semester",
                        "stage": "source_workbook",
                        "details": list(parsed.invalid_rows),
                    }
                if not reference.exists():
                    return {
                        "error": f"Timing reference workbook not found: {reference}",
                        "stage": "timing_reference",
                    }

                resources = list(
                    (await db.execute(select(Resource).where(Resource.is_active.is_(True))))
                    .scalars()
                    .all()
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
                if not resources:
                    return {
                        "error": "No configured timetable resources are available",
                        "stage": "source_configuration",
                        "details": [
                            "Use existing classroom and laboratory records; source generation does not create rooms."
                        ],
                    }
                if not time_slots:
                    return {
                        "error": "No active time slots are configured for this timetable template",
                        "stage": "source_configuration",
                        "details": [
                            "Configure the template time slots before requesting generation."
                        ],
                    }
                reference_times = reference_teaching_times(reference)
                expected_timing = {
                    (day, period, start, end)
                    for day in WORKING_DAYS
                    for period, (start, end) in enumerate(reference_times, start=1)
                }
                current_timing = {
                    (slot.day_of_week, slot.period_number, slot.start_time, slot.end_time)
                    for slot in time_slots
                    if slot.slot_type == "TEACHING"
                }
                staged_template = None
                if current_timing != expected_timing:
                    staged_template_id = uuid.uuid4()
                    staged_template = TimetableTemplate(
                        id=staged_template_id,
                        name=f"{timetable.name} source timing",
                        description=f"Teaching intervals read from {reference.name}",
                        academic_year=timetable.academic_year,
                        is_default=False,
                        is_active=True,
                    )
                    time_slots = reference_time_slots(reference, staged_template_id)
                blocked_faculty_slots, blocked_resource_slots = await load_availability_blocks(
                    db, time_slots, resources, timetable.academic_year
                )
                plan = await WorkbookScheduleService(db, source, reference).build_plan(
                    timetable.academic_year,
                    timetable.semester,
                    time_slots,
                    resources,
                    slot_hours=1,
                    two_hour_grid=False,
                    blocked_faculty_slots=blocked_faculty_slots,
                    blocked_resource_slots=blocked_resource_slots,
                )
                if not plan.solver_input.assignments or not plan.complete:
                    return {
                        "error": "Source workbook is parsed, but its demands are not fully mapped",
                        "stage": "source_mapping",
                        "source_file": source.name,
                        "reference_file": reference.name,
                        "semester": plan.parsed.semester,
                        "source_demands": plan.source_demands,
                        "required_sessions": plan.required_sessions,
                        "scheduled_sessions": 0,
                        "unscheduled_sessions": plan.required_sessions,
                        "unscheduled": plan.unscheduled,
                        "invalid_rows": list(plan.parsed.invalid_rows),
                        "unrepresented_hours": plan.parsed.unrepresented_hours,
                        "excluded_rows": list(plan.parsed.excluded_rows),
                    }

                required_hours = {a.id: a.hours_per_week for a in plan.solver_input.assignments}
                previous_version = await latest_version_for_timetable(db, timetable_id)
                previous_entries: list[dict] = []
                previous_number = previous_version.version_number if previous_version else 0
                if previous_version:
                    previous_rows = (
                        (
                            await db.execute(
                                select(TimetableEntry).where(
                                    TimetableEntry.version_id == previous_version.id
                                )
                            )
                        )
                        .scalars()
                        .all()
                    )
                    previous_entries = [
                        {
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
                        for row in previous_rows
                    ]
                await end_read_transaction(db)
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(None, self.solver.solve, plan.solver_input)
                if not result.has_feasible_solution:
                    return {
                        "error": f"Solver did not produce a complete timetable (status: {result.status_name})",
                        "stage": "cp_sat",
                        "solver_status": result.status_name,
                        "optimality_proven": result.optimality_proven,
                        "source_file": source.name,
                        "reference_file": reference.name,
                        "source_demands": plan.source_demands,
                        "required_sessions": plan.required_sessions,
                        "scheduled_sessions": 0,
                        "unscheduled_sessions": plan.required_sessions,
                        "unscheduled": plan.unscheduled + result.diagnostics,
                        "excluded_rows": list(plan.parsed.excluded_rows),
                        "details": result.diagnostics,
                    }

                entries = build_entries(result.entries, plan.solver_input)
                validation = TimetableValidator().validate(
                    entries,
                    required_hours=required_hours,
                    check_resource_compatibility=True,
                    blocked_faculty_slots=plan.solver_input.blocked_faculty_slots,
                    blocked_resource_slots=plan.solver_input.blocked_resource_slots,
                )
                if not validation.is_valid:
                    return {
                        "error": "Independent validation failed",
                        "stage": "independent_validation",
                        "solver_status": result.status_name,
                        "details": validation.errors,
                        "source_file": source.name,
                        "reference_file": reference.name,
                    }
                diff = compute_entry_diff(previous_entries, entries)

                async with transaction(db):
                    current = await db.get(Timetable, timetable_id)
                    if current is None:
                        raise ValueError("Timetable disappeared during generation")
                    await lock_timetable(db, timetable_id)
                    if staged_template is not None:
                        db.add(staged_template)
                        for slot in time_slots:
                            db.add(
                                TimeSlot(
                                    id=slot.id,
                                    template_id=staged_template.id,
                                    day_of_week=slot.day_of_week,
                                    period_number=slot.period_number,
                                    start_time=slot.start_time,
                                    end_time=slot.end_time,
                                    slot_type=slot.slot_type,
                                    shift=slot.shift,
                                    is_active=True,
                                )
                            )
                        current.template_id = staged_template.id
                    for row in plan.assignment_rows:
                        if await db.get(TeachingAssignment, row["id"]) is None:
                            db.add(TeachingAssignment(**row, academic_term_id=term_id))
                    await db.flush()
                    status = "VALIDATED"
                    current.status = status
                    current.generated_by = requested_by
                    version = await VersionService(db).create_version(
                        timetable_id,
                        {
                            "change_type": "SOURCE_WORKBOOK_CP_SAT",
                            "status": status,
                            "entries": entries,
                            "change_summary": (
                                f"{source.name}, {plan.parsed.semester}; CP-SAT candidate validated"
                                f"{v2_diff_suffix(diff)}"
                            ),
                        },
                        created_by=requested_by,
                    )
                    db.add(
                        AuditLog(
                            user_id=requested_by,
                            action="GENERATE",
                            entity_type="TIMETABLE",
                            entity_id=timetable_id,
                            old_values=(
                                {"version_number": previous_number} if previous_number else None
                            ),
                            new_values={
                                "version_id": str(version.id),
                                "source_file": source.name,
                                "semester": plan.parsed.semester,
                                "source_demands": plan.source_demands,
                                "required_sessions": plan.required_sessions,
                                "scheduled_sessions": len(entries),
                                "unscheduled": len(plan.unscheduled),
                                "solver_status": result.status_name,
                                "optimality_proven": result.optimality_proven,
                                "validation": "PASS",
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
                    "success": True,
                    "complete": True,
                    "status": status,
                    "version_id": str(version.id),
                    "version_number": version.version_number,
                    "entries_count": len(entries),
                    "source_file": source.name,
                    "semester": plan.parsed.semester,
                    "source_demands": plan.source_demands,
                    "required_sessions": plan.required_sessions,
                    "scheduled_sessions": len(entries),
                    "unscheduled_sessions": max(0, plan.required_sessions - len(entries)),
                    "unscheduled": plan.unscheduled,
                    "excluded_rows": list(plan.parsed.excluded_rows),
                    "solver_status": result.status_name,
                    "optimality_proven": result.optimality_proven,
                    "validation_status": "PASS",
                    "conflicts": {
                        k: v for k, v in validation.violations.items() if "conflict" in k
                    },
                    "batch_practical_sessions": sum(
                        1 for e in entries if e["session_type"] == "PRACTICAL"
                    ),
                    "repair_attempts": 0,
                    "diff": {
                        "added": len(diff["added"]),
                        "removed": len(diff["removed"]),
                        "changed": len(diff["changed"]),
                        "kept": len(diff["kept"]),
                    },
                }
            except Exception as exc:
                logger.exception("Workbook timetable generation failed for %s", timetable_id)
                await db.rollback()
                return {"error": f"Unexpected failure: {exc}"}

    async def _ensure_workbook_configuration(
        self, db, timetable, requested_by: UUID
    ) -> dict | None:
        """Register only the exact rooms and four canonical slots when absent."""
        existing_resources = {
            r.name: r
            for r in (
                await db.execute(
                    select(Resource).where(Resource.name.in_(list(ALLOWED_RESOURCE_NAMES)))
                )
            )
            .scalars()
            .all()
        }
        for name, (kind, capacity) in ALLOWED_RESOURCE_NAMES.items():
            current = existing_resources.get(name)
            if current and (current.resource_type != kind or (current.capacity or 0) < capacity):
                return {
                    "error": f"Resource {name} is registered with incompatible type or capacity"
                }

        slots = list(
            (
                await db.execute(
                    select(TimeSlot).where(TimeSlot.template_id == timetable.template_id)
                )
            )
            .scalars()
            .all()
        )
        by_coordinate = {(s.day_of_week, s.period_number): s for s in slots}
        if any(
            current
            and (
                current.start_time != canonical.start_time
                or current.end_time != canonical.end_time
                or current.slot_type != "TEACHING"
            )
            for day in WORKING_DAYS
            for canonical in CANONICAL_SLOTS
            for current in [by_coordinate.get((day, canonical.period_number))]
        ):
            template = TimetableTemplate(
                id=uuid.uuid4(),
                name=f"{timetable.name} two-hour source grid",
                description="Canonical two-hour Load Distribution generation grid",
                academic_year=timetable.academic_year,
                is_default=False,
                is_active=True,
            )
            db.add(template)
            db.add(
                AuditLog(
                    user_id=requested_by,
                    action="CREATE",
                    entity_type="TIMETABLE_TEMPLATE",
                    entity_id=template.id,
                    new_values={"name": template.name, "academic_year": template.academic_year},
                )
            )
            timetable.template_id = template.id
            by_coordinate = {}

        for name, (kind, capacity) in ALLOWED_RESOURCE_NAMES.items():
            if not existing_resources.get(name):
                resource = Resource(
                    id=uuid.uuid4(),
                    name=name,
                    resource_type=kind,
                    capacity=capacity,
                    room_number=name,
                    is_active=True,
                    is_emergency=False,
                )
                db.add(resource)
                db.add(
                    AuditLog(
                        user_id=requested_by,
                        action="CREATE",
                        entity_type="RESOURCE",
                        entity_id=resource.id,
                        new_values={"name": name, "resource_type": kind, "capacity": capacity},
                    )
                )

        for day in WORKING_DAYS:
            for canonical in CANONICAL_SLOTS:
                current = by_coordinate.get((day, canonical.period_number))
                if not current:
                    db.add(
                        TimeSlot(
                            template_id=timetable.template_id,
                            day_of_week=day,
                            period_number=canonical.period_number,
                            start_time=canonical.start_time,
                            end_time=canonical.end_time,
                            slot_type="TEACHING",
                            shift=canonical.shift,
                            is_active=True,
                        )
                    )
        await db.flush()
        return None

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

        blocked_faculty_slots, blocked_resource_slots = await load_availability_blocks(
            db, time_slots, resources, timetable.academic_year
        )
        solver_input = build_solver_input(
            assignments,
            resources,
            time_slots,
            sections,
            batches,
            blocked_faculty_slots,
            blocked_resource_slots,
        )
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
            assignment = next(
                (a for a in solver_input.assignments if a.id == entry["assignment_id"]), None
            )
            resource = next(
                (r for r in solver_input.resources if r.id == entry["resource_id"]), None
            )
            entry["two_hour_grid"] = solver_input.two_hour_grid
            entry["required_lab_type"] = assignment.required_lab_type if assignment else None
            entry["resource_type"] = resource.resource_type if resource else None

        # Step 1: impact analysis - determine affected vs pinned entries
        reoptimizer = Reoptimizer()
        impact = reoptimizer.analyze_impact(change_type, change_data, current_entries)

        if not impact.affected_entry_ids:
            message = (
                "Solver found no feasible re-timetable (status: INFEASIBLE): "
                f"no entries fall in the requested {change_type} scope"
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
            two_hour_grid=solver_input.two_hour_grid,
            blocked_faculty_slots=solver_input.blocked_faculty_slots,
            blocked_resource_slots=solver_input.blocked_resource_slots,
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
        validation = validator.validate(
            combined_entries,
            required_hours=required_hours,
            check_resource_compatibility=True,
            blocked_faculty_slots=solver_input.blocked_faculty_slots,
            blocked_resource_slots=solver_input.blocked_resource_slots,
        )
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
