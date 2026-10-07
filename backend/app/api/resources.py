from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db, require_permissions
from app.core.permissions import Permission
from app.database.transactions import transaction
from app.schemas.resource import (
    ResourceCreate,
    ResourceListResponse,
    ResourceResponse,
    ResourceUpdate,
)
from app.services.resource_service import ResourceService

router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("", response_model=ResourceListResponse)
async def list_resources(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    resource_type: str | None = Query(None),
    is_active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = ResourceService(db)
    resources, total = await service.get_all(
        page=page,
        page_size=page_size,
        search=search,
        resource_type=resource_type,
        is_active=is_active,
    )
    return ResourceListResponse(
        items=[ResourceResponse.model_validate(item) for item in resources],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{resource_id}", response_model=ResourceResponse)
async def get_resource(
    resource_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = ResourceService(db)
    resource = await service.get_by_id(resource_id)
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    return resource


@router.post("", response_model=ResourceResponse, status_code=status.HTTP_201_CREATED)
async def create_resource(
    data: ResourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.RESOURCE_CREATE)),
):
    service = ResourceService(db)
    try:
        async with transaction(db):
            resource = await service.create(data, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return resource


@router.put("/{resource_id}", response_model=ResourceResponse)
async def update_resource(
    resource_id: UUID,
    data: ResourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.RESOURCE_UPDATE)),
):
    service = ResourceService(db)
    try:
        async with transaction(db):
            resource = await service.update(resource_id, data, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    if not resource:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    return resource


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(
    resource_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.RESOURCE_DELETE)),
):
    service = ResourceService(db)
    async with transaction(db):
        success = await service.delete(resource_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
