from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db, require_permissions
from app.core.permissions import Permission
from app.database.transactions import transaction
from app.schemas.section import SectionCreate, SectionListResponse, SectionResponse, SectionUpdate
from app.services.section_service import SectionService

router = APIRouter(prefix="/sections", tags=["sections"])


@router.get("", response_model=SectionListResponse)
async def list_sections(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    class_id: UUID | None = Query(None),
    is_active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = SectionService(db)
    sections, total = await service.get_all(
        page=page,
        page_size=page_size,
        search=search,
        class_id=class_id,
        is_active=is_active,
    )
    return SectionListResponse(
        items=[SectionResponse.model_validate(item) for item in sections],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{section_id}", response_model=SectionResponse)
async def get_section(
    section_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service = SectionService(db)
    section = await service.get_by_id(section_id)
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    return section


@router.post("", response_model=SectionResponse, status_code=status.HTTP_201_CREATED)
async def create_section(
    data: SectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.SECTION_CREATE)),
):
    service = SectionService(db)
    try:
        async with transaction(db):
            section = await service.create(data, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return section


@router.put("/{section_id}", response_model=SectionResponse)
async def update_section(
    section_id: UUID,
    data: SectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.SECTION_UPDATE)),
):
    service = SectionService(db)
    try:
        async with transaction(db):
            section = await service.update(section_id, data, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    return section


@router.delete("/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_section(
    section_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.SECTION_DELETE)),
):
    service = SectionService(db)
    async with transaction(db):
        success = await service.delete(section_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
