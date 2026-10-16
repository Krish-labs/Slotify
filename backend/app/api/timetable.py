import contextlib
import json
import os
import tempfile
import uuid as uuid_module
from hashlib import sha256
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_db, require_permissions
from app.core.permissions import Permission
from app.core.workbook_paths import source_workbook_path, timing_reference_path
from app.database.models import (
    AcademicTerm,
    Resource,
    Section,
    TimeSlot,
    Timetable,
    TimetableEntry,
    TimetableJob,
    TimetableTemplate,
    TimetableVersion,
)
from app.database.models.audit_log import AuditLog
from app.database.transactions import transaction
from app.exporters.change_history_exporter import ChangeHistoryExporter
from app.exporters.class_timetable_exporter import ClassTimetableExporter
from app.exporters.faculty_timetable_exporter import FacultyTimetableExporter
from app.exporters.master_timetable_exporter import MasterTimetableExporter
from app.exporters.resource_allocation_exporter import ResourceAllocationExporter
from app.scheduler.workbook_demand import parse_workbook_demand
from app.schemas.repair import DEFAULT_MAX_REPAIR_ATTEMPTS
from app.schemas.timetable import TimetableCreate
from app.services.generation_readiness import build_readiness_report
from app.services.load_source_service import WorkbookParseError
from app.services.repair_service import RepairService
from app.services.timetable_state import (
    InvalidTransition,
    apply_version_transition,
    latest_version_for_timetable,
    mirror_timetable_status,
)
from app.services.timing_reference import reference_teaching_times
from app.services.validation_context import (
    build_version_validation_context,
    validate_version_entries,
)
from app.workers.runner import enqueue_reoptimize, get_redis, get_result
from app.workers.timetable_worker import TimetableWorker

router = APIRouter(prefix="/timetable", tags=["timetable"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_timetable_or_404(db: AsyncSession, timetable_id: UUID) -> Timetable:
    timetable = await db.get(Timetable, timetable_id)
    if not timetable:
        raise HTTPException(status_code=404, detail="Timetable not found")
    return timetable


def _parse_uuid_or_404(raw: str, label: str = "id") -> UUID:
    """Parse user-controlled IDs as 404, not 500.

    ``UUID("not-a-uuid")`` raises ``ValueError``; without this helper every
    timetable/version route answers 500 on malformed input (log noise +
    fingerprinting). Callers pass the already-validated UUID onward.
    """
    try:
        return UUID(raw)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=404, detail=f"{label} not found") from None


def _temp_export_path(prefix: str, timetable_id: UUID | str) -> str:
    """Unique per-request export path (no predictable /tmp collisions).

    Predictable ``/tmp/export_<kind>_<id>.xlsx`` names allow cross-user
    overwrite races and symlink pre-creation on shared /tmp. A random suffix
    keeps the file private to this request; ``_stream_export`` unlinks it.
    """
    fd, path = tempfile.mkstemp(prefix=f"{prefix}_{timetable_id}_", suffix=".xlsx")
    os.close(fd)
    return path


async def _get_version_or_404(
    db: AsyncSession, timetable_id: UUID, version_id: UUID
) -> TimetableVersion:
    version = (
        await db.execute(
            select(TimetableVersion)
            .where(
                TimetableVersion.timetable_id == timetable_id,
                TimetableVersion.id == version_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


EXPORTABLE_VERSION_STATUSES = ("GENERATED", "VALIDATED", "APPROVED", "PUBLISHED")


async def _get_export_version(
    db: AsyncSession, timetable_id: UUID, version_id: str | None
) -> TimetableVersion:
    if version_id:
        version = await _get_version_or_404(db, timetable_id, _parse_uuid_or_404(version_id, "Version"))
        if version.status not in EXPORTABLE_VERSION_STATUSES:
            raise HTTPException(status_code=409, detail="Selected version is not exportable")
        return version

    version = (
        await db.execute(
            select(TimetableVersion)
            .where(TimetableVersion.timetable_id == timetable_id)
            .where(TimetableVersion.status.in_(EXPORTABLE_VERSION_STATUSES))
            .order_by(TimetableVersion.version_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="No validated version found for this timetable")
    return version


def _version_state_response(version: TimetableVersion) -> dict:
    return {
        "success": True,
        "version_id": str(version.id),
        "version_number": version.version_number,
        "status": version.status,
    }


async def _stream_export(path: str, download_name: str) -> Response:
    """Return a workbook as a downloadable response and clean the temp file up."""
    with open(path, "rb") as fh:
        content = fh.read()
    with contextlib.suppress(OSError):
        os.unlink(path)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={download_name}"},
    )


def _idempotency_key(timetable_id: UUID, change_data: dict, client_key: str | None) -> str:
    if client_key:
        return f"reoptimize:{client_key}"[:128]
    canonical = json.dumps(change_data, sort_keys=True, default=str)
    return f"reoptimize:{sha256(f'{timetable_id}|{canonical}'.encode()).hexdigest()}"[:128]


# ---------------------------------------------------------------------------
# Timetable creation (previously missing: the workflow had no entry point)
# ---------------------------------------------------------------------------


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_timetable(
    data: TimetableCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_CREATE)),
):
    """Create a timetable in DRAFT state.

    A timetable must reference an active template and a real academic term for
    its (academic_year, semester); generation resolves assignments through that
    term, so creating an unanchored timetable would produce un-generatable rows.
    """
    async with transaction(db):
        template = await db.get(TimetableTemplate, data.template_id)
        if not template or not template.is_active:
            raise HTTPException(status_code=400, detail="Template not found or inactive")

        term = (
            await db.execute(
                select(AcademicTerm).where(
                    AcademicTerm.academic_year == data.academic_year,
                    AcademicTerm.semester == data.semester,
                )
            )
        ).scalar_one_or_none()
        if not term:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No academic term for {data.academic_year} semester {data.semester}; "
                    "create the term before the timetable"
                ),
            )

        timetable = Timetable(
            name=data.name,
            template_id=data.template_id,
            academic_year=data.academic_year,
            semester=data.semester,
            status="DRAFT",
            generated_by=current_user.id,
        )
        db.add(timetable)
        await db.flush()
        db.add(
            AuditLog(
                user_id=current_user.id,
                action="CREATE",
                entity_type="TIMETABLE",
                entity_id=timetable.id,
                new_values={
                    "name": timetable.name,
                    "academic_year": timetable.academic_year,
                    "semester": timetable.semester,
                    "template_id": str(timetable.template_id),
                    "status": "DRAFT",
                },
            )
        )
    return {
        "id": str(timetable.id),
        "name": timetable.name,
        "academic_year": timetable.academic_year,
        "semester": timetable.semester,
        "status": timetable.status,
    }


# no-slash twin: the SPA calls GET /timetable while POST lives on the same
# path, so without this alias the list request answers 405.
@router.get("")
@router.get("/")
async def list_timetables(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_READ)),
):
    timetables = (
        (await db.execute(select(Timetable).where(Timetable.status != "ARCHIVED"))).scalars().all()
    )
    return {
        "timetables": [
            {
                "id": str(t.id),
                "name": t.name,
                "academic_year": t.academic_year,
                "semester": t.semester,
                "status": t.status,
            }
            for t in timetables
        ]
    }


@router.get("/{timetable_id}")
async def get_timetable(
    timetable_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_READ)),
):
    timetable = await _get_timetable_or_404(db, _parse_uuid_or_404(timetable_id, "Timetable"))
    return {
        "id": str(timetable.id),
        "name": timetable.name,
        "template_id": str(timetable.template_id),
        "academic_year": timetable.academic_year,
        "semester": timetable.semester,
        "status": timetable.status,
        "generated_by": str(timetable.generated_by) if timetable.generated_by else None,
        "approved_by": str(timetable.approved_by) if timetable.approved_by else None,
    }


@router.post("/{timetable_id}/generate")
async def generate_timetable(
    timetable_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_GENERATE)),
):
    """Generate a new timetable version via full regeneration.

    The actor is always the authenticated principal; generation runs inline and
    owns one write transaction (see TimetableWorker._generate).
    """
    timetable = await _get_timetable_or_404(db, _parse_uuid_or_404(timetable_id, "Timetable"))
    worker = TimetableWorker()
    result = await worker.generate_timetable(timetable.id, requested_by=current_user.id)
    if "error" in result:
        # Validation / infeasibility / not-found failures are client-visible
        # outcomes, not 500s: the request itself succeeded.
        raise HTTPException(status_code=422, detail=result)
    return result


@router.get("/{timetable_id}/workbook-readiness")
async def get_workbook_readiness(
    timetable_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_READ)),
):
    """Parse the immutable source workbook without persisting or scheduling."""
    timetable = await _get_timetable_or_404(db, _parse_uuid_or_404(timetable_id, "Timetable"))
    source = source_workbook_path()
    reference = timing_reference_path()
    if not source.exists():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Source workbook not found",
                "stage": "source_workbook",
                "source_file": str(source),
                "details": [
                    "Check that data/raw/Load Distribution.xlsx is mounted at /app/data in Docker."
                ],
            },
        )
    try:
        parsed = parse_workbook_demand(
            source,
            timetable.academic_year,
            timetable.semester,
            reference,
            slot_hours=1,
        )
    except WorkbookParseError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Unable to parse the source workbook",
                "stage": "source_workbook",
                "source_file": source.name,
                "details": [str(exc)],
                "sheet": exc.sheet,
                "row": exc.row,
                "field": exc.field,
            },
        ) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Unable to parse the source workbook",
                "stage": "source_workbook",
                "source_file": source.name,
                "details": [str(exc)],
            },
        ) from exc
    if not reference.exists():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Timing reference workbook not found",
                "stage": "timing_reference",
                "source_file": reference.name,
                "details": ["The timetable workbook is used only for its teaching-time intervals."],
            },
        )
    try:
        timing_intervals = reference_teaching_times(reference)
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "Unable to parse the timing reference workbook",
                "stage": "timing_reference",
                "source_file": reference.name,
                "details": [str(exc)],
            },
        ) from exc
    return {
        "timetable_id": str(timetable.id),
        "source_file": source.name,
        "reference_file": reference.name,
        "timing_reference_available": reference.exists(),
        "timing_intervals": len(timing_intervals),
        "source_sheet": "Sheet1",
        "semester": parsed.semester,
        "rows_read": parsed.rows_read,
        "source_demands": len(parsed.demands),
        "source_hours": parsed.source_hours,
        "required_sessions": parsed.required_slots,
        "unrepresented_hours": parsed.unrepresented_hours,
        "invalid_rows": list(parsed.invalid_rows),
        "excluded_rows": list(parsed.excluded_rows),
        "row_dispositions": [
            {
                "source_file": parsed.source_file,
                "source_sheet": "Sheet1",
                "source_row_number": disposition.source_row_number,
                "disposition": disposition.disposition,
                "reason": disposition.reason,
            }
            for disposition in parsed.row_dispositions
        ],
        "zero_load_rows": [
            {
                "source_row_number": z.source_row_number,
                "faculty_name": z.faculty_name,
                "class_name": z.class_name,
                "subject_name": z.subject_name,
                "theory": z.theory,
                "practical": z.practical,
                "tutorial": z.tutorial,
                "project_stage": z.project_stage,
                "total_load": z.total_load,
            }
            for z in parsed.zero_load_rows
        ],
        "ready": (
            bool(parsed.demands)
            and not parsed.invalid_rows
            and not parsed.has_unreviewed_zero_load
            and reference.exists()
        ),
    }


@router.post("/{timetable_id}/generate-source")
async def generate_from_source_workbook(
    timetable_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_GENERATE)),
):
    """Generate a CP-SAT timetable from Load Distribution.xlsx."""
    timetable = await _get_timetable_or_404(db, _parse_uuid_or_404(timetable_id, "Timetable"))
    result = await TimetableWorker().generate_from_workbook(
        timetable.id,
        requested_by=current_user.id,
    )
    if "error" in result and not result.get("success"):
        raise HTTPException(status_code=422, detail=result)
    return result


@router.get("/{timetable_id}/readiness")
async def get_generation_readiness(
    timetable_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_READ)),
):
    """Pre-generation readiness: the same checks generation enforces, up front.

    Lets the UI show mapping/validation errors BEFORE the solver runs (academic
    term, approved FacultyLoad, derived TeachingAssignments, sections/batches,
    resources, teaching time slots). Read-only.
    """
    timetable = await _get_timetable_or_404(db, _parse_uuid_or_404(timetable_id, "Timetable"))
    report, _ = await build_readiness_report(db, timetable.id)
    if report is None:  # unreachable behind _get_timetable_or_404, kept for safety
        raise HTTPException(status_code=404, detail="Timetable not found")
    return {
        "timetable_id": str(timetable.id),
        "ready": report.ready,
        "errors": report.errors,
        "warnings": report.warnings,
        "checks": report.checks,
    }


@router.post("/{timetable_id}/reoptimize")
async def reoptimize_timetable(
    timetable_id: str,
    change_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_GENERATE)),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Enqueue a reoptimization as a DURABLE job.

    A ``timetable_jobs`` row (QUEUED) is committed before the work is pushed to
    Redis, so the job can never become invisible. Repeating the request with
    the same logical change while the job is QUEUED/RUNNING returns the
    existing job instead of creating a duplicate.
    """
    timetable = await _get_timetable_or_404(db, _parse_uuid_or_404(timetable_id, "Timetable"))
    key = _idempotency_key(timetable.id, change_data, idempotency_key)

    async with transaction(db):
        existing = (
            await db.execute(
                select(TimetableJob).where(
                    TimetableJob.idempotency_key == key,
                    TimetableJob.status.in_(("QUEUED", "RUNNING")),
                )
            )
        ).scalar_one_or_none()
        if existing:
            return {
                "job_id": str(existing.id),
                "status": existing.status,
                "deduplicated": True,
            }

        parent = await latest_version_for_timetable(db, timetable.id)
        job_id = uuid_module.uuid4()
        job = TimetableJob(
            id=job_id,
            timetable_id=timetable.id,
            operation="reoptimize",
            status="QUEUED",
            requested_by=current_user.id,
            change_data=change_data,
            correlation_id=str(job_id),
            parent_version_id=parent.id if parent else None,
            idempotency_key=key,
        )
        db.add(job)

    # Committed: the job now exists even if Redis dies. Enqueue OUTSIDE the
    # transaction, exactly once, using the durable job id so the worker claims
    # this row; a second push would run the same reoptimization twice.
    # On failure the job is marked FAILED and we return 503 so the client can
    # retry (the retry then creates a fresh QUEUED job).
    redis = get_redis()
    try:
        await enqueue_reoptimize(
            redis,
            timetable.id,
            change_data=change_data,
            requested_by=current_user.id,
            job_id=str(job_id),
        )
    except Exception as exc:
        async with transaction(db):
            from app.workers.timetable_worker import set_job_outcome

            await set_job_outcome(db, str(job_id), "FAILED", error=f"enqueue failed: {exc}")
        raise HTTPException(
            status_code=503, detail="Job queued durably but enqueue failed; retry"
        ) from exc
    finally:
        await redis.close()

    return {"job_id": str(job_id), "status": "QUEUED"}


@router.get("/reoptimize/{job_id}")
async def get_reoptimize_result(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_READ)),
):
    """Poll a reoptimization job. Durable state (timetable_jobs) first."""
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        job_uuid = None

    if job_uuid:
        job = await db.get(TimetableJob, job_uuid)
        if job:
            return {
                "job_id": str(job.id),
                "status": job.status,
                "operation": job.operation,
                "timetable_id": str(job.timetable_id),
                "result": job.result,
                "error": job.error,
                "retry_count": job.retry_count,
                "created_at": job.created_at,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
            }

    # Legacy fallback: jobs enqueued before the durable record existed.
    redis = get_redis()
    try:
        result = await get_result(redis, job_id)
        return result or {"status": "not_found", "job_id": job_id}
    finally:
        await redis.close()


class RepairRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adjustments: list[dict[str, Any]] = Field(default_factory=list, max_length=5)
    max_retries: int = Field(default=DEFAULT_MAX_REPAIR_ATTEMPTS, ge=1, le=5)
    approve_hard_relaxation: bool = False
    suggest: bool = False


@router.post("/{timetable_id}/repair")
async def repair_timetable(
    timetable_id: str,
    data: RepairRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_GENERATE)),
):
    """Bounded repair of a failed or incomplete timetable (at most ``max_retries`` re-solves).

    Structured validation/solver diagnostics drive each revised CP-SAT solve;
    unaffected entries stay pinned where feasible. Availability overrides
    require ``approve_hard_relaxation``. A repaired candidate is persisted as
    a new VALIDATED version only after independent validation passes; failed
    repair persists nothing and returns the original diagnostics honestly.
    """
    timetable = await _get_timetable_or_404(db, _parse_uuid_or_404(timetable_id, "Timetable"))
    result = await RepairService().repair_timetable(
        timetable.id,
        requested_by=current_user.id,
        adjustments=data.adjustments,
        max_retries=data.max_retries,
        approve_hard_relaxation=data.approve_hard_relaxation,
        suggest=data.suggest,
    )
    if "error" in result and not result.get("success"):
        raise HTTPException(status_code=422, detail=result)
    return result


@router.post("/{timetable_id}/validate")
async def validate_timetable(
    timetable_id: str,
    version_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_READ)),
):
    """Validate the latest version with the FULL validation context.

    Approval-time and API validation are deliberately identical to
    generation-time validation: per-entry session duration, strengths/capacity
    and required hours are all included, and an empty timetable can never
    validate vacuously.
    """
    timetable = await _get_timetable_or_404(db, _parse_uuid_or_404(timetable_id, "Timetable"))
    version = (
        await _get_version_or_404(db, timetable.id, _parse_uuid_or_404(version_id, "Version"))
        if version_id
        else await latest_version_for_timetable(db, timetable.id)
    )
    if not version:
        return {
            "status": "FAIL",
            "errors": ["No version found for this timetable"],
            "warnings": [],
            "violations": {},
        }

    entries_dict, required_hours = await build_version_validation_context(db, version.id)
    validation = validate_version_entries(entries_dict, required_hours)

    if not entries_dict:
        errors = validation.errors + ["Timetable version has no entries"]
        return {
            "status": "FAIL",
            "errors": errors,
            "warnings": validation.warnings,
            "violations": dict(validation.violations),
        }

    return {
        "status": "PASS" if validation.is_valid else "FAIL",
        "errors": validation.errors,
        "warnings": validation.warnings,
        "violations": dict(validation.violations),
        "version_id": str(version.id),
        "version_number": version.version_number,
        "version_status": version.status,
    }


@router.get("/{timetable_id}/versions")
async def list_timetable_versions(
    timetable_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_READ)),
):
    versions = (
        (
            await db.execute(
                select(TimetableVersion)
                .where(
                    TimetableVersion.timetable_id == _parse_uuid_or_404(timetable_id, "Timetable")
                )
                .order_by(TimetableVersion.version_number.desc())
            )
        )
        .scalars()
        .all()
    )
    return {
        "versions": [
            {
                "id": str(v.id),
                "version_number": v.version_number,
                "parent_version_id": str(v.parent_version_id) if v.parent_version_id else None,
                "change_type": v.change_type,
                "status": v.status,
                "change_summary": v.change_summary,
                "created_by": str(v.created_by) if v.created_by else None,
            }
            for v in versions
        ]
    }


@router.get("/{timetable_id}/versions/{version_id}")
async def get_timetable_version(
    timetable_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_READ)),
):
    version = (
        await db.execute(
            select(TimetableVersion)
            .options(
                selectinload(TimetableVersion.entries).selectinload(TimetableEntry.subject),
                selectinload(TimetableVersion.entries).selectinload(TimetableEntry.faculty),
                selectinload(TimetableVersion.entries).selectinload(TimetableEntry.section),
                selectinload(TimetableVersion.entries).selectinload(TimetableEntry.resource),
                selectinload(TimetableVersion.entries).selectinload(TimetableEntry.batch),
                selectinload(TimetableVersion.entries).selectinload(TimetableEntry.time_slot),
            )
            .where(
                TimetableVersion.timetable_id == _parse_uuid_or_404(timetable_id, "Timetable"),
                TimetableVersion.id == _parse_uuid_or_404(version_id, "Version"),
            )
        )
    ).scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    entries_dict = [
        {
            "id": e.id,
            "assignment_id": str(e.assignment_id) if e.assignment_id else None,
            "faculty_id": str(e.faculty_id) if e.faculty_id else None,
            "subject_id": str(e.subject_id) if e.subject_id else None,
            "section_id": str(e.section_id) if e.section_id else None,
            "batch_id": str(e.batch_id) if e.batch_id else None,
            "resource_id": str(e.resource_id) if e.resource_id else None,
            "time_slot_id": str(e.time_slot_id) if e.time_slot_id else None,
            "day_of_week": e.day_of_week,
            "period_number": e.period_number,
            "start_time": e.time_slot.start_time.isoformat() if e.time_slot else None,
            "end_time": e.time_slot.end_time.isoformat() if e.time_slot else None,
            "session_type": e.session_type,
            "subject_name": e.subject.name if e.subject else None,
            "faculty_name": (
                f"{e.faculty.first_name} {e.faculty.last_name}" if e.faculty else None
            ),
            "section_name": e.section.name if e.section else None,
            "resource_name": e.resource.name if e.resource else None,
            "batch_name": e.batch.name if e.batch else None,
        }
        for e in version.entries
    ]

    return {
        "id": str(version.id),
        "timetable_id": str(version.timetable_id),
        "version_number": version.version_number,
        "parent_version_id": str(version.parent_version_id) if version.parent_version_id else None,
        "change_type": version.change_type,
        "status": version.status,
        "change_summary": version.change_summary,
        "created_by": str(version.created_by) if version.created_by else None,
        "entries": entries_dict,
    }


# ---------------------------------------------------------------------------
# Version state machine transitions (single authority: timetable_state)
# ---------------------------------------------------------------------------


@router.post("/{timetable_id}/versions/{version_id}/approve")
async def approve_timetable_version(
    timetable_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_APPROVE)),
):
    """VALIDATED|UNDER_REVIEW -> APPROVED (validated, audited, notified, durable)."""
    timetable = await _get_timetable_or_404(db, _parse_uuid_or_404(timetable_id, "Timetable"))
    async with transaction(db):
        version = await _get_version_or_404(
            db, timetable.id, _parse_uuid_or_404(version_id, "Version")
        )
        entries_dict, required_hours = await build_version_validation_context(db, version.id)
        if not entries_dict:
            raise InvalidTransition("Version has no entries; generate a timetable first")
        validation = validate_version_entries(entries_dict, required_hours)
        try:
            await apply_version_transition(
                db,
                version,
                "APPROVED",
                current_user.id,
                require_validation=True,
                validation_errors=validation.errors,
            )
            await mirror_timetable_status(db, timetable, "APPROVED", current_user.id)
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
    return _version_state_response(version)


@router.post("/{timetable_id}/versions/{version_id}/reject")
async def reject_timetable_version(
    timetable_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_APPROVE)),
):
    timetable = await _get_timetable_or_404(db, _parse_uuid_or_404(timetable_id, "Timetable"))
    async with transaction(db):
        version = await _get_version_or_404(
            db, timetable.id, _parse_uuid_or_404(version_id, "Version")
        )
        try:
            await apply_version_transition(db, version, "REJECTED", current_user.id)
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
    return _version_state_response(version)


@router.post("/{timetable_id}/versions/{version_id}/submit-review")
async def submit_for_review(
    timetable_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_GENERATE)),
):
    timetable = await _get_timetable_or_404(db, _parse_uuid_or_404(timetable_id, "Timetable"))
    async with transaction(db):
        version = await _get_version_or_404(
            db, timetable.id, _parse_uuid_or_404(version_id, "Version")
        )
        try:
            await apply_version_transition(db, version, "UNDER_REVIEW", current_user.id)
            await mirror_timetable_status(db, timetable, "UNDER_REVIEW", current_user.id)
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
    return _version_state_response(version)


@router.post("/{timetable_id}/versions/{version_id}/publish")
async def publish_timetable_version(
    timetable_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_APPROVE)),
):
    """APPROVED -> PUBLISHED (re-validated with the full context; durable)."""
    timetable = await _get_timetable_or_404(db, _parse_uuid_or_404(timetable_id, "Timetable"))
    async with transaction(db):
        version = await _get_version_or_404(
            db, timetable.id, _parse_uuid_or_404(version_id, "Version")
        )
        entries_dict, required_hours = await build_version_validation_context(db, version.id)
        validation = validate_version_entries(entries_dict, required_hours)
        try:
            await apply_version_transition(
                db,
                version,
                "PUBLISHED",
                current_user.id,
                require_validation=True,
                validation_errors=validation.errors,
            )
            await mirror_timetable_status(db, timetable, "PUBLISHED", current_user.id)
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
    return {
        **_version_state_response(version),
        "timetable_status": timetable.status,
        "approved_by": str(timetable.approved_by) if timetable.approved_by else None,
        "approved_at": timetable.approved_at.isoformat() if timetable.approved_at else None,
    }


@router.post("/{timetable_id}/versions/{version_id}/archive")
async def archive_timetable_version(
    timetable_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_APPROVE)),
):
    timetable = await _get_timetable_or_404(db, _parse_uuid_or_404(timetable_id, "Timetable"))
    async with transaction(db):
        version = await _get_version_or_404(
            db, timetable.id, _parse_uuid_or_404(version_id, "Version")
        )
        try:
            await apply_version_transition(db, version, "ARCHIVED", current_user.id)
            await mirror_timetable_status(db, timetable, "ARCHIVED", current_user.id)
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
    return {
        **_version_state_response(version),
        "timetable_status": timetable.status,
    }


# ---------------------------------------------------------------------------
# Exports (workbook bytes, so the frontend can actually download them)
# ---------------------------------------------------------------------------


@router.get("/{timetable_id}/export/class")
async def export_class_timetable(
    timetable_id: str,
    version_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_EXPORT)),
):
    timetable = await _get_timetable_or_404(db, _parse_uuid_or_404(timetable_id, "Timetable"))
    version = await _get_export_version(db, timetable.id, version_id)

    entries_dict, _required = await build_version_validation_context(db, version.id)
    sections = (
        (
            await db.execute(
                select(Section).where(Section.id.in_({e["section_id"] for e in entries_dict}))
            )
        )
        .scalars()
        .all()
    )
    sections_dict = {s.id: {"name": s.name} for s in sections}
    time_slots = (
        (
            await db.execute(
                select(TimeSlot).where(
                    TimeSlot.id.in_({UUID(e["time_slot_id"]) for e in entries_dict})
                )
            )
        )
        .scalars()
        .all()
    )
    time_slots_dict = {
        t.id: {"day_of_week": t.day_of_week, "period_number": t.period_number} for t in time_slots
    }
    resources = (
        (
            await db.execute(
                select(Resource).where(
                    Resource.id.in_({UUID(e["resource_id"]) for e in entries_dict})
                )
            )
        )
        .scalars()
        .all()
    )
    resources_dict = {r.id: {"name": r.name, "resource_type": r.resource_type} for r in resources}

    output_path = _temp_export_path("export_class", timetable.id)
    ClassTimetableExporter().export(
        entries=entries_dict,
        sections=sections_dict,
        time_slots=time_slots_dict,
        resources=resources_dict,
        output_path=output_path,
    )
    return await _stream_export(output_path, f"class_timetable_{version.version_number}.xlsx")


@router.get("/{timetable_id}/export/faculty")
async def export_faculty_timetable(
    timetable_id: str,
    version_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_EXPORT)),
):
    from app.database.models import Faculty as FacultyModel

    timetable = await _get_timetable_or_404(db, _parse_uuid_or_404(timetable_id, "Timetable"))
    version = await _get_export_version(db, timetable.id, version_id)

    entries_dict, _required = await build_version_validation_context(db, version.id)
    faculties = (
        (
            await db.execute(
                select(FacultyModel).where(
                    FacultyModel.id.in_({UUID(e["faculty_id"]) for e in entries_dict})
                )
            )
        )
        .scalars()
        .all()
    )
    faculties_dict = {
        f.id: {"first_name": f.first_name, "last_name": f.last_name} for f in faculties
    }
    time_slots = (
        (
            await db.execute(
                select(TimeSlot).where(
                    TimeSlot.id.in_({UUID(e["time_slot_id"]) for e in entries_dict})
                )
            )
        )
        .scalars()
        .all()
    )
    time_slots_dict = {
        t.id: {"day_of_week": t.day_of_week, "period_number": t.period_number} for t in time_slots
    }
    resources = (
        (
            await db.execute(
                select(Resource).where(
                    Resource.id.in_({UUID(e["resource_id"]) for e in entries_dict})
                )
            )
        )
        .scalars()
        .all()
    )
    resources_dict = {r.id: {"name": r.name} for r in resources}

    output_path = _temp_export_path("export_faculty", timetable.id)
    FacultyTimetableExporter().export(
        entries=entries_dict,
        faculty_map=faculties_dict,
        time_slots=time_slots_dict,
        resources=resources_dict,
        output_path=output_path,
    )
    return await _stream_export(output_path, f"faculty_timetable_{version.version_number}.xlsx")


@router.get("/{timetable_id}/export/master")
async def export_master_timetable(
    timetable_id: str,
    version_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_EXPORT)),
):
    from app.database.models import Faculty as FacultyModel

    timetable = await _get_timetable_or_404(db, _parse_uuid_or_404(timetable_id, "Timetable"))
    version = await _get_export_version(db, timetable.id, version_id)

    entries_dict, _required = await build_version_validation_context(db, version.id)
    resources = (
        (
            await db.execute(
                select(Resource).where(
                    Resource.id.in_({UUID(e["resource_id"]) for e in entries_dict})
                )
            )
        )
        .scalars()
        .all()
    )
    resources_dict = {r.id: {"name": r.name} for r in resources}
    time_slots = (
        (
            await db.execute(
                select(TimeSlot).where(
                    TimeSlot.id.in_({UUID(e["time_slot_id"]) for e in entries_dict})
                )
            )
        )
        .scalars()
        .all()
    )
    time_slots_dict = {
        t.id: {"day_of_week": t.day_of_week, "period_number": t.period_number} for t in time_slots
    }
    sections = (
        (
            await db.execute(
                select(Section).where(Section.id.in_({e["section_id"] for e in entries_dict}))
            )
        )
        .scalars()
        .all()
    )
    sections_dict = {s.id: {"name": s.name} for s in sections}
    faculties = (
        (
            await db.execute(
                select(FacultyModel).where(
                    FacultyModel.id.in_({UUID(e["faculty_id"]) for e in entries_dict})
                )
            )
        )
        .scalars()
        .all()
    )
    faculty_dict = {f.id: {"first_name": f.first_name, "last_name": f.last_name} for f in faculties}

    output_path = _temp_export_path("export_master", timetable.id)
    MasterTimetableExporter().export(
        entries=entries_dict,
        resources=resources_dict,
        time_slots=time_slots_dict,
        sections=sections_dict,
        faculty=faculty_dict,
        output_path=output_path,
    )
    return await _stream_export(output_path, f"master_timetable_{version.version_number}.xlsx")


@router.get("/{timetable_id}/export/resource-allocation")
async def export_resource_allocation(
    timetable_id: str,
    version_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_EXPORT)),
):
    timetable = await _get_timetable_or_404(db, _parse_uuid_or_404(timetable_id, "Timetable"))
    version = await _get_export_version(db, timetable.id, version_id)
    version = (
        await db.execute(
            select(TimetableVersion)
            .options(
                selectinload(TimetableVersion.entries).selectinload(TimetableEntry.subject),
                selectinload(TimetableVersion.entries).selectinload(TimetableEntry.faculty),
                selectinload(TimetableVersion.entries).selectinload(TimetableEntry.section),
            )
            .where(TimetableVersion.id == version.id)
        )
    ).scalar_one_or_none()

    entries_dict, _required = await build_version_validation_context(db, version.id)
    names = {e["id"]: e for e in entries_dict}
    for e in version.entries:
        merged = names.get(e.id, {})
        merged["subject_name"] = e.subject.name if e.subject else ""
        merged["faculty_name"] = (
            f"{e.faculty.first_name} {e.faculty.last_name}" if e.faculty else ""
        )
        merged["section_name"] = e.section.name if e.section else ""

    resources = (
        (
            await db.execute(
                select(Resource).where(
                    Resource.id.in_({UUID(e["resource_id"]) for e in entries_dict})
                )
            )
        )
        .scalars()
        .all()
    )
    resources_dict = {r.id: {"name": r.name, "resource_type": r.resource_type} for r in resources}
    time_slots = (
        (
            await db.execute(
                select(TimeSlot).where(
                    TimeSlot.id.in_({UUID(e["time_slot_id"]) for e in entries_dict})
                )
            )
        )
        .scalars()
        .all()
    )
    time_slots_dict = {
        t.id: {
            "day_of_week": t.day_of_week,
            "period_number": t.period_number,
            "start_time": t.start_time,
            "end_time": t.end_time,
        }
        for t in time_slots
    }

    output_path = _temp_export_path("export_resource_allocation", timetable.id)
    ResourceAllocationExporter().export(
        entries=entries_dict,
        resources=resources_dict,
        time_slots=time_slots_dict,
        output_path=output_path,
    )
    return await _stream_export(output_path, f"resource_allocation_{version.version_number}.xlsx")


@router.get("/{timetable_id}/export/change-history")
async def export_change_history(
    timetable_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_EXPORT)),
):
    timetable = await _get_timetable_or_404(db, _parse_uuid_or_404(timetable_id, "Timetable"))
    versions = (
        (
            await db.execute(
                select(TimetableVersion)
                .where(TimetableVersion.timetable_id == timetable.id)
                .order_by(TimetableVersion.version_number.desc())
            )
        )
        .scalars()
        .all()
    )
    output_path = _temp_export_path("export_change_history", timetable.id)
    ChangeHistoryExporter().export(versions, output_path)
    return await _stream_export(output_path, f"change_history_{timetable_id}.xlsx")
