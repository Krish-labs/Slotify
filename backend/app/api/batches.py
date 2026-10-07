from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db, require_permissions
from app.core.permissions import Permission
from app.database.transactions import transaction
from app.schemas.batch import BatchCreate, BatchListResponse, BatchResponse, BatchUpdate
from app.services.batch_service import BatchService

router = APIRouter(prefix="/batches", tags=["batches"])


@router.get("", response_model=BatchListResponse)
async def list_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    section_id: UUID | None = Query(None),
    is_active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = BatchService(db)
    batches, total = await service.get_all(
        page=page,
        page_size=page_size,
        search=search,
        section_id=section_id,
        is_active=is_active,
    )
    return BatchListResponse(
        items=[BatchResponse.model_validate(item) for item in batches],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{batch_id}", response_model=BatchResponse)
async def get_batch(
    batch_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = BatchService(db)
    batch = await service.get_by_id(batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return batch


@router.post("", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
async def create_batch(
    data: BatchCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.BATCH_CREATE)),
):
    service = BatchService(db)
    try:
        async with transaction(db):
            batch = await service.create(data, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return batch


@router.put("/{batch_id}", response_model=BatchResponse)
async def update_batch(
    batch_id: UUID,
    data: BatchUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.BATCH_UPDATE)),
):
    service = BatchService(db)
    try:
        async with transaction(db):
            batch = await service.update(batch_id, data, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return batch


@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_batch(
    batch_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.BATCH_DELETE)),
):
    service = BatchService(db)
    async with transaction(db):
        success = await service.delete(batch_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
