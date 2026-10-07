from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db, require_roles
from app.core.permissions import MANAGEMENT_ROLES
from app.database.transactions import transaction
from app.schemas.academic_term import (
    AcademicTermCreate,
    AcademicTermListResponse,
    AcademicTermResponse,
    AcademicTermUpdate,
)
from app.services.academic_term_service import AcademicTermService

router = APIRouter(prefix="/academic-terms", tags=["academic-terms"])


@router.get("", response_model=AcademicTermListResponse)
async def list_academic_terms(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_active: bool | None = Query(None),
    is_current: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = AcademicTermService(db)
    terms, total = await service.get_all(
        page=page,
        page_size=page_size,
        is_active=is_active,
        is_current=is_current,
    )
    return AcademicTermListResponse(
        items=[AcademicTermResponse.model_validate(item) for item in terms],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/current", response_model=AcademicTermResponse)
async def get_current_academic_term(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = AcademicTermService(db)
    term = await service.get_current()
    if not term:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No current academic term set"
        )
    return term


@router.get("/{term_id}", response_model=AcademicTermResponse)
async def get_academic_term(
    term_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = AcademicTermService(db)
    term = await service.get_by_id(term_id)
    if not term:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic term not found")
    return term


@router.post("", response_model=AcademicTermResponse, status_code=status.HTTP_201_CREATED)
async def create_academic_term(
    data: AcademicTermCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    service = AcademicTermService(db)

    # Check for duplicate
    existing = await service.get_by_year_semester(data.academic_year, data.semester)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Academic term {data.academic_year} Semester {data.semester} already exists",
        )

    async with transaction(db):
        term = await service.create(data, user_id=current_user.id)
    return term


@router.put("/{term_id}", response_model=AcademicTermResponse)
async def update_academic_term(
    term_id: UUID,
    data: AcademicTermUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    service = AcademicTermService(db)
    async with transaction(db):
        term = await service.update(term_id, data, user_id=current_user.id)
    if not term:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic term not found")
    return term


@router.delete("/{term_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_academic_term(
    term_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles(*MANAGEMENT_ROLES)),
):
    service = AcademicTermService(db)
    async with transaction(db):
        success = await service.delete(term_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic term not found")
