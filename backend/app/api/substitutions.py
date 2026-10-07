from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, require_permissions
from app.core.permissions import Permission
from app.database.transactions import transaction
from app.schemas.substitution import SubstitutionCreate, SubstitutionResponse, SubstitutionUpdate
from app.services.leave_service import SubstitutionService

router = APIRouter(prefix="/substitutions", tags=["substitutions"])


# The collection is registered with and without a trailing slash: the UI calls
# "/leave/substitutions", and without this alias that path is swallowed by the
# leave router's "/{leave_id}" catch-all (422) instead of listing substitutions.
@router.get("")
@router.get("/")
async def list_substitutions(
    status: str | None = Query(None),
    faculty_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.SUBSTITUTION_READ)),
):
    service = SubstitutionService(db)
    subs = await service.get_all(status=status, faculty_id=faculty_id)
    return {"substitutions": subs}


@router.get("/{substitution_id}", response_model=SubstitutionResponse)
async def get_substitution(
    substitution_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.SUBSTITUTION_READ)),
):
    service = SubstitutionService(db)
    sub = await service.get_by_id(substitution_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Substitution not found")
    return sub


@router.post("", response_model=SubstitutionResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=SubstitutionResponse, status_code=status.HTTP_201_CREATED)
async def create_substitution(
    data: SubstitutionCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.SUBSTITUTION_CREATE)),
):
    service = SubstitutionService(db)
    try:
        async with transaction(db):
            sub = await service.create(data.model_dump(), actor_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return sub


@router.put("/{substitution_id}", response_model=SubstitutionResponse)
async def update_substitution(
    substitution_id: UUID,
    data: SubstitutionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.SUBSTITUTION_UPDATE)),
):
    service = SubstitutionService(db)
    try:
        async with transaction(db):
            sub = await service.update(
                substitution_id, data.model_dump(exclude_unset=True), actor_id=current_user.id
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    if not sub:
        raise HTTPException(status_code=404, detail="Substitution not found")
    return sub


@router.delete("/{substitution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_substitution(
    substitution_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.SUBSTITUTION_DELETE)),
):
    service = SubstitutionService(db)
    async with transaction(db):
        deleted = await service.delete(substitution_id, actor_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Substitution not found")


@router.post("/{substitution_id}/approve", response_model=SubstitutionResponse)
async def approve_substitution(
    substitution_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.SUBSTITUTION_APPROVE)),
):
    service = SubstitutionService(db)
    try:
        async with transaction(db):
            sub = await service.approve(substitution_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    if not sub:
        raise HTTPException(status_code=404, detail="Substitution not found")
    return sub


@router.post("/{substitution_id}/reject", response_model=SubstitutionResponse)
async def reject_substitution(
    substitution_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.SUBSTITUTION_APPROVE)),
):
    service = SubstitutionService(db)
    try:
        async with transaction(db):
            sub = await service.reject(substitution_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    if not sub:
        raise HTTPException(status_code=404, detail="Substitution not found")
    return sub
