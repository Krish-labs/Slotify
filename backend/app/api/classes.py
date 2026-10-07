from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db, require_permissions
from app.core.permissions import Permission
from app.database.transactions import transaction
from app.schemas.class_schema import ClassCreate, ClassListResponse, ClassResponse, ClassUpdate
from app.services.class_service import ClassService

router = APIRouter(prefix="/classes", tags=["classes"])


@router.get("", response_model=ClassListResponse)
async def list_classes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    academic_year: str | None = Query(None),
    is_active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = ClassService(db)
    classes, total = await service.get_all(
        page=page,
        page_size=page_size,
        search=search,
        academic_year=academic_year,
        is_active=is_active,
    )
    return ClassListResponse(
        items=[ClassResponse.model_validate(item) for item in classes],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{class_id}", response_model=ClassResponse)
async def get_class(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = ClassService(db)
    class_obj = await service.get_by_id(class_id)
    if not class_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    return class_obj


@router.post("", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
async def create_class(
    data: ClassCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.CLASS_CREATE)),
):
    service = ClassService(db)
    try:
        async with transaction(db):
            class_obj = await service.create(data, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return class_obj


@router.put("/{class_id}", response_model=ClassResponse)
async def update_class(
    class_id: UUID,
    data: ClassUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.CLASS_UPDATE)),
):
    service = ClassService(db)
    try:
        async with transaction(db):
            class_obj = await service.update(class_id, data, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    if not class_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    return class_obj


@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class(
    class_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.CLASS_DELETE)),
):
    service = ClassService(db)
    async with transaction(db):
        success = await service.delete(class_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
