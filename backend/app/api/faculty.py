from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db, require_roles
from app.core.permissions import MANAGEMENT_ROLES
from app.database.transactions import transaction
from app.schemas.faculty import (
    FacultyCreate,
    FacultyListResponse,
    FacultyResponse,
    FacultyUpdate,
)
from app.services.faculty_service import FacultyService

router = APIRouter(prefix="/faculty", tags=["faculty"])


@router.get("", response_model=FacultyListResponse)
async def list_faculty(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    department: str | None = Query(None),
    is_active: bool | None = Query(None),
    include_archived: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = FacultyService(db)
    faculty_list, total = await service.get_all(
        page=page,
        page_size=page_size,
        search=search,
        department=department,
        is_active=is_active,
        include_archived=include_archived,
    )
    return FacultyListResponse(
        items=[FacultyResponse.model_validate(item) for item in faculty_list],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{faculty_id}", response_model=FacultyResponse)
async def get_faculty(
    faculty_id: UUID,
    include_archived: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = FacultyService(db)
    faculty = await service.get_by_id(faculty_id, include_archived=include_archived)
    if not faculty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty not found")
    return faculty


@router.post("", response_model=FacultyResponse, status_code=status.HTTP_201_CREATED)
async def create_faculty(
    data: FacultyCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    service = FacultyService(db)

    # Check for duplicate employee_id
    existing = await service.get_by_employee_id(data.employee_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Faculty with employee_id {data.employee_id} already exists",
        )

    # Check for duplicate email
    existing = await service.get_by_email(data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Faculty with email {data.email} already exists",
        )

    async with transaction(db):
        faculty = await service.create(data, user_id=current_user.id)
    return faculty


@router.put("/{faculty_id}", response_model=FacultyResponse)
async def update_faculty(
    faculty_id: UUID,
    data: FacultyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    service = FacultyService(db)

    # Check if email is being updated and if it conflicts
    if data.email:
        existing = await service.get_by_email(data.email)
        if existing and existing.id != faculty_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Faculty with email {data.email} already exists",
            )

    async with transaction(db):
        faculty = await service.update(faculty_id, data, user_id=current_user.id)
    if not faculty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty not found")
    return faculty


@router.patch("/{faculty_id}/archive", response_model=FacultyResponse)
async def archive_faculty(
    faculty_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    service = FacultyService(db)
    async with transaction(db):
        faculty = await service.archive(faculty_id, archived_by=current_user.id)
    if not faculty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty not found")
    return faculty


@router.patch("/{faculty_id}/restore", response_model=FacultyResponse)
async def restore_faculty(
    faculty_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    service = FacultyService(db)
    async with transaction(db):
        faculty = await service.restore(faculty_id, user_id=current_user.id)
    if not faculty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty not found")
    return faculty


@router.delete("/{faculty_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_faculty(
    faculty_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    service = FacultyService(db)
    async with transaction(db):
        success = await service.delete(faculty_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty not found")


@router.get("/{faculty_id}/load-summary")
async def get_faculty_load_summary(
    faculty_id: UUID,
    academic_term_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = FacultyService(db)
    faculty = await service.get_by_id(faculty_id)
    if not faculty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty not found")

    total_load = await service.get_total_load(faculty_id, academic_term_id)
    return {
        "faculty_id": faculty_id,
        "total_load_hours": total_load,
        "academic_term_id": academic_term_id,
    }
