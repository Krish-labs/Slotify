from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.notification import Notification


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def send_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        type: str = "INFO",
        reference_type: str | None = None,
        reference_id: UUID | None = None,
    ) -> Notification:
        notification = Notification(
            user_id=UUID(user_id),
            title=title,
            message=message,
            type=type,
            reference_type=reference_type,
            reference_id=reference_id,
            is_read=False,
        )
        self.db.add(notification)
        await self.db.flush()
        return notification

    async def send_bulk_notification(
        self,
        user_ids: list[str],
        title: str,
        message: str,
        type: str = "INFO",
        reference_type: str | None = None,
        reference_id: UUID | None = None,
    ) -> list[Notification]:
        notifications = [
            Notification(
                user_id=UUID(uid),
                title=title,
                message=message,
                type=type,
                reference_type=reference_type,
                reference_id=reference_id,
                is_read=False,
            )
            for uid in user_ids
        ]
        self.db.add_all(notifications)
        await self.db.flush()
        return notifications

    async def get_notifications(
        self, user_id: str, unread_only: bool = False, limit: int = 50
    ) -> list[Notification]:
        query = (
            select(Notification)
            .where(Notification.user_id == UUID(user_id))
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        if unread_only:
            query = query.where(Notification.is_read.is_(False))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def mark_as_read(self, notification_id: UUID) -> Notification | None:
        result = await self.db.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        notification = result.scalar_one_or_none()
        if notification:
            notification.is_read = True
            await self.db.flush()
        return notification

    async def mark_all_as_read(self, user_id: str) -> int:
        result = await self.db.execute(
            select(Notification).where(
                Notification.user_id == UUID(user_id),
                Notification.is_read.is_(False),
            )
        )
        count = 0
        for notification in result.scalars().all():
            notification.is_read = True
            count += 1
        await self.db.flush()
        return count

    async def get_unread_count(self, user_id: str) -> int:
        result = await self.db.execute(
            select(Notification).where(
                Notification.user_id == UUID(user_id),
                Notification.is_read.is_(False),
            )
        )
        return len(result.scalars().all())
