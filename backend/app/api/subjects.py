from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db, require_permissions
from app.core.permissions import Permission
from app.database.transactions import transaction
from app.schemas.subject import SubjectCreate, SubjectListResponse, SubjectResponse, SubjectUpdate
from app.services.subject_service import SubjectService

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get("", response_model=SubjectListResponse)
async def list_subjects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    subject_type: str | None = Query(None),
    semester: int | None = Query(None),
    department: str | None = Query(None),
    is_active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = SubjectService(db)
    subjects, total = await service.get_all(
        page=page,
        page_size=page_size,
        search=search,
        subject_type=subject_type,
        semester=semester,
        department=department,
        is_active=is_active,
    )
    return SubjectListResponse(
        items=[SubjectResponse.model_validate(item) for item in subjects],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{subject_id}", response_model=SubjectResponse)
async def get_subject(
    subject_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = SubjectService(db)
    subject = await service.get_by_id(subject_id)
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    return subject


@router.post("", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    data: SubjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.SUBJECT_CREATE)),
):
    service = SubjectService(db)
    try:
        async with transaction(db):
            subject = await service.create(data, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return subject


@router.put("/{subject_id}", response_model=SubjectResponse)
async def update_subject(
    subject_id: UUID,
    data: SubjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.SUBJECT_UPDATE)),
):
    service = SubjectService(db)
    try:
        async with transaction(db):
            subject = await service.update(subject_id, data, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    if not subject:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    return subject


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(
    subject_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.SUBJECT_DELETE)),
):
    service = SubjectService(db)
    async with transaction(db):
        success = await service.delete(subject_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
