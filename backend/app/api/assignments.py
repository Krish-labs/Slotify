from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user, get_db, require_roles
from app.core.permissions import MANAGEMENT_ROLES
from app.database.models.teaching_assignment import TeachingAssignment
from app.database.transactions import transaction
from app.schemas.assignment import (
    TeachingAssignmentCreate,
    TeachingAssignmentResponse,
    TeachingAssignmentUpdate,
)
from app.services.assignment_derivation_service import AssignmentDerivationService

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.get("", response_model=list[TeachingAssignmentResponse])
async def list_assignments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    faculty_id: UUID | None = Query(None),
    academic_term_id: UUID | None = Query(None),
    subject_id: UUID | None = Query(None),
    section_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = select(TeachingAssignment).options(
        selectinload(TeachingAssignment.faculty),
        selectinload(TeachingAssignment.subject),
        selectinload(TeachingAssignment.section),
        selectinload(TeachingAssignment.batch),
    )

    if faculty_id:
        query = query.where(TeachingAssignment.faculty_id == faculty_id)
    if academic_term_id:
        query = query.where(TeachingAssignment.academic_term_id == academic_term_id)
    if subject_id:
        query = query.where(TeachingAssignment.subject_id == subject_id)
    if section_id:
        query = query.where(TeachingAssignment.section_id == section_id)

    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(TeachingAssignment.created_at.desc())

    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{assignment_id}", response_model=TeachingAssignmentResponse)
async def get_assignment(
    assignment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = (
        select(TeachingAssignment)
        .options(
            selectinload(TeachingAssignment.faculty),
            selectinload(TeachingAssignment.subject),
            selectinload(TeachingAssignment.section),
            selectinload(TeachingAssignment.batch),
        )
        .where(TeachingAssignment.id == assignment_id)
    )

    result = await db.execute(query)
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return assignment


@router.post("", response_model=TeachingAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    data: TeachingAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    async with transaction(db):
        assignment = TeachingAssignment(**data.model_dump())
        db.add(assignment)
    return assignment


@router.put("/{assignment_id}", response_model=TeachingAssignmentResponse)
async def update_assignment(
    assignment_id: UUID,
    data: TeachingAssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    async with transaction(db):
        result = await db.execute(
            select(TeachingAssignment).where(TeachingAssignment.id == assignment_id)
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found"
            )

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(assignment, key, value)

        # Either field may be sent alone, so check the combined result.
        hours, duration = assignment.hours_per_week, assignment.session_duration or 1
        if hours % duration != 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"hours_per_week ({hours}) must be a multiple of session_duration ({duration})",
            )
    return assignment


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(
    assignment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    async with transaction(db):
        result = await db.execute(
            select(TeachingAssignment).where(TeachingAssignment.id == assignment_id)
        )
        assignment = result.scalar_one_or_none()
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found"
            )
        await db.delete(assignment)


@router.post("/derive")
async def derive_assignments(
    academic_term_id: UUID = Query(...),
    force: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    """Derive teaching assignments from approved faculty loads"""
    service = AssignmentDerivationService(db)
    async with transaction(db):
        result = await service.derive_assignments(academic_term_id, current_user.id, force=force)
    return result


@router.get("/derive/preview")
async def preview_derivation(
    academic_term_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    """Preview what assignments would be derived"""
    service = AssignmentDerivationService(db)
    preview = await service.get_derivation_preview(academic_term_id)
    return preview
