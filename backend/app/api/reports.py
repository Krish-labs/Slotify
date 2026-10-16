from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status as http_status

from app.api.dependencies import get_db, require_permissions
from app.core.permissions import Permission
from app.database.models import (
    Resource,
    Timetable,
    TimetableEntry,
    TimetableVersion,
)

router = APIRouter(prefix="/reports", tags=["reports"])

REPORTABLE_VERSION_STATUSES = ("GENERATED", "VALIDATED", "UNDER_REVIEW", "APPROVED", "PUBLISHED")


async def _report_version(
    db: AsyncSession, timetable_id: UUID, version_id: UUID | None = None
) -> TimetableVersion | None:
    if version_id:
        version = await db.get(TimetableVersion, version_id)
        if version and version.timetable_id == timetable_id and version.status in REPORTABLE_VERSION_STATUSES:
            return version
        return None
    return (
        await db.execute(
            select(TimetableVersion)
            .where(TimetableVersion.timetable_id == timetable_id)
            .where(TimetableVersion.status.in_(REPORTABLE_VERSION_STATUSES))
            .order_by(TimetableVersion.version_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


@router.get("/faculty-load")
async def faculty_load_report(
    academic_term_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.LOAD_READ)),
):
    """Faculty teaching load distribution report."""
    from app.services.load_service import LoadService

    service = LoadService(db)
    summary = await service.get_faculty_load_summary(academic_term_id)
    return {"academic_term_id": academic_term_id, "summary": summary}


@router.get("/timetable-summary")
async def timetable_summary_report(
    timetable_id: UUID = Query(...),
    version_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_READ)),
):
    """Timetable summary report."""
    timetable = await db.get(Timetable, timetable_id)
    if not timetable:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Timetable not found"
        )

    latest_version = await _report_version(db, timetable_id, version_id)

    if not latest_version:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="No version found for this timetable"
        )

    entries = (
        (
            await db.execute(
                select(TimetableEntry).where(TimetableEntry.version_id == latest_version.id)
            )
        )
        .scalars()
        .all()
    )

    entries_by_type: dict[str, int] = {}
    entries_by_section: dict[str, int] = {}
    entries_by_faculty: dict[str, int] = {}
    entries_by_resource: dict[str, int] = {}

    for entry in entries:
        entries_by_type[entry.session_type] = entries_by_type.get(entry.session_type, 0) + 1
        if entry.section_id:
            entries_by_section[str(entry.section_id)] = (
                entries_by_section.get(str(entry.section_id), 0) + 1
            )
        if entry.faculty_id:
            entries_by_faculty[str(entry.faculty_id)] = (
                entries_by_faculty.get(str(entry.faculty_id), 0) + 1
            )
        if entry.resource_id:
            entries_by_resource[str(entry.resource_id)] = (
                entries_by_resource.get(str(entry.resource_id), 0) + 1
            )

    return {
        "timetable_id": str(timetable_id),
        "timetable_name": timetable.name,
        "version_number": latest_version.version_number,
        "version_status": latest_version.status,
        "total_entries": len(entries),
        "entries_by_type": entries_by_type,
        "entries_by_section": entries_by_section,
        "entries_by_faculty": entries_by_faculty,
        "entries_by_resource": entries_by_resource,
    }


@router.get("/resource-utilization")
async def resource_utilization_report(
    timetable_id: UUID = Query(...),
    version_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_READ)),
):
    """Resource utilization statistics for classrooms, software labs, and hardware labs."""
    timetable = await db.get(Timetable, timetable_id)
    if not timetable:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Timetable not found"
        )

    latest_version = await _report_version(db, timetable_id, version_id)

    if not latest_version:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="No validated version found"
        )

    entries = (
        (
            await db.execute(
                select(TimetableEntry).where(TimetableEntry.version_id == latest_version.id)
            )
        )
        .scalars()
        .all()
    )

    resource_ids = {e.resource_id for e in entries if e.resource_id}
    resources = (
        (await db.execute(select(Resource).where(Resource.id.in_(resource_ids)))).scalars().all()
    )
    resources_dict = {r.id: r for r in resources}

    time_slot_ids = {e.time_slot_id for e in entries if e.time_slot_id}
    from app.database.models import TimeSlot

    time_slots = (
        (await db.execute(select(TimeSlot).where(TimeSlot.id.in_(time_slot_ids)))).scalars().all()
    )
    time_slots_dict = {t.id: t for t in time_slots}

    total_slots = len(time_slots)
    utilization: dict[str, dict[str, Any]] = {}

    for entry in entries:
        if not entry.resource_id or not entry.time_slot_id:
            continue
        resource = resources_dict.get(entry.resource_id)
        time_slot = time_slots_dict.get(entry.time_slot_id)
        if not resource or not time_slot:
            continue

        key = str(resource.id)
        if key not in utilization:
            utilization[key] = {
                "resource_id": str(resource.id),
                "resource_name": resource.name,
                "resource_type": resource.resource_type,
                "capacity": resource.capacity,
                "used_slots": 0,
                "total_slots": total_slots,
            }
        utilization[key]["used_slots"] += 1

    for data in utilization.values():
        data["utilization_percent"] = round((data["used_slots"] / data["total_slots"]) * 100, 2)

    return {
        "timetable_id": str(timetable_id),
        "total_resources": len(resources),
        "total_time_slots": total_slots,
        "utilization": list(utilization.values()),
    }


@router.get("/conflicts")
async def conflicts_report(
    timetable_id: UUID = Query(...),
    version_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_READ)),
):
    """Detected scheduling conflicts."""
    from app.validators.timetable_validator import TimetableValidator

    timetable = await db.get(Timetable, timetable_id)
    if not timetable:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Timetable not found"
        )

    latest_version = await _report_version(db, timetable_id, version_id)

    if not latest_version:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="No version found")

    entries = (
        (
            await db.execute(
                select(TimetableEntry).where(TimetableEntry.version_id == latest_version.id)
            )
        )
        .scalars()
        .all()
    )

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
            "session_type": e.session_type,
        }
        for e in entries
    ]

    validator = TimetableValidator()
    validation = validator.validate(entries_dict, required_hours={})

    return {
        "timetable_id": str(timetable_id),
        "version_number": latest_version.version_number,
        "is_valid": validation.is_valid,
        "errors": validation.errors,
        "warnings": validation.warnings,
        "violations": dict(validation.violations),
    }


@router.get("/validation")
async def validation_report(
    timetable_id: UUID = Query(...),
    version_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.TIMETABLE_READ)),
):
    """Timetable validation results."""
    from app.validators.timetable_validator import TimetableValidator

    timetable = await db.get(Timetable, timetable_id)
    if not timetable:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="Timetable not found"
        )

    latest_version = await _report_version(db, timetable_id, version_id)

    if not latest_version:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="No version found")

    entries = (
        (
            await db.execute(
                select(TimetableEntry).where(TimetableEntry.version_id == latest_version.id)
            )
        )
        .scalars()
        .all()
    )

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
            "session_type": e.session_type,
        }
        for e in entries
    ]

    validator = TimetableValidator()
    validation = validator.validate(entries_dict, required_hours={})

    validation_status = (
        "PASS" if validation.is_valid else "FAIL" if validation.errors else "WARNING"
    )

    return {
        "timetable_id": str(timetable_id),
        "version_number": latest_version.version_number,
        "status": validation_status,
        "is_valid": validation.is_valid,
        "errors": validation.errors,
        "warnings": validation.warnings,
        "violations": dict(validation.violations),
        "total_entries": len(entries),
    }
