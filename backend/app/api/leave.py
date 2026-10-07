from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, require_permissions
from app.api.substitutions import router as substitutions_router
from app.core.permissions import Permission
from app.database.transactions import transaction
from app.schemas.leave import LeaveCreate, LeaveResponse, LeaveUpdate
from app.services.leave_service import LeaveService

router = APIRouter(prefix="/leave", tags=["leave"])

# Substitution handlers live in app/api/substitutions.py. Mounting the same
# router here keeps the historical /leave/substitutions paths served by one
# implementation instead of a copy that can drift. include_router already
# inherits this router's "/leave" prefix, so no extra prefix may be passed.
router.include_router(substitutions_router)


# no-slash twin: the SPA calls /leave and /leave/substitutions without the
# trailing slash the decorators below would otherwise require.
@router.get("")
@router.get("/")
async def list_leaves(
    status: str | None = Query(None),
    faculty_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.LEAVE_READ)),
):
    service = LeaveService(db)
    leaves = await service.get_all(status=status, faculty_id=faculty_id)
    return {"leaves": leaves}


@router.get("/{leave_id}", response_model=LeaveResponse)
async def get_leave(
    leave_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.LEAVE_READ)),
):
    service = LeaveService(db)
    leave = await service.get_by_id(leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")
    return leave


@router.post("", response_model=LeaveResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=LeaveResponse, status_code=status.HTTP_201_CREATED)
async def create_leave(
    leave_data: LeaveCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.LEAVE_CREATE)),
):
    service = LeaveService(db)
    async with transaction(db):
        leave = await service.create(leave_data.model_dump(), actor_id=current_user.id)
    return leave


@router.put("/{leave_id}", response_model=LeaveResponse)
async def update_leave(
    leave_id: UUID,
    leave_data: LeaveUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.LEAVE_UPDATE)),
):
    service = LeaveService(db)
    try:
        async with transaction(db):
            leave = await service.update(
                leave_id, leave_data.model_dump(exclude_unset=True), actor_id=current_user.id
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")
    return leave


@router.delete("/{leave_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_leave(
    leave_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.LEAVE_DELETE)),
):
    service = LeaveService(db)
    async with transaction(db):
        deleted = await service.delete(leave_id, actor_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Leave not found")


@router.post("/{leave_id}/approve", response_model=LeaveResponse)
async def approve_leave(
    leave_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.LEAVE_APPROVE)),
):
    service = LeaveService(db)
    try:
        async with transaction(db):
            leave = await service.approve(leave_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")
    return leave


@router.post("/{leave_id}/reject", response_model=LeaveResponse)
async def reject_leave(
    leave_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.LEAVE_APPROVE)),
):
    service = LeaveService(db)
    try:
        async with transaction(db):
            leave = await service.reject(leave_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")
    return leave


@router.post("/{leave_id}/cancel", response_model=LeaveResponse)
async def cancel_leave(
    leave_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permissions(Permission.LEAVE_UPDATE)),
):
    service = LeaveService(db)
    try:
        async with transaction(db):
            leave = await service.cancel(leave_id, cancelled_by=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")
    return leave
