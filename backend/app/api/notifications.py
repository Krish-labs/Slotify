from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.database.models.user import User
from app.database.transactions import transaction
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


# no-slash twin: the SPA calls /notifications without the trailing slash.
@router.get("")
@router.get("/")
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = NotificationService(db)
    notifications = await service.get_notifications(
        user_id=str(current_user.id), unread_only=unread_only, limit=limit
    )
    return {
        "notifications": [
            {
                "id": str(n.id),
                "title": n.title,
                "message": n.message,
                "type": n.type,
                "reference_type": n.reference_type,
                "reference_id": str(n.reference_id) if n.reference_id else None,
                "is_read": n.is_read,
                "created_at": n.created_at,
            }
            for n in notifications
        ]
    }


@router.get("/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = NotificationService(db)
    count = await service.get_unread_count(str(current_user.id))
    return {"unread_count": count}


@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = NotificationService(db)
    async with transaction(db):
        notification = await service.mark_as_read(notification_id)
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        if notification.user_id != current_user.id:
            # Raised inside the transaction so a foreign notification is never
            # marked read on the way to a 403.
            raise HTTPException(status_code=403, detail="Not your notification")
    return {"success": True}


@router.post("/read-all")
async def mark_all_as_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = NotificationService(db)
    async with transaction(db):
        count = await service.mark_all_as_read(str(current_user.id))
    return {"marked_count": count}
