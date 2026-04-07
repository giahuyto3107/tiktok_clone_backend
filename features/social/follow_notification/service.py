from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.realtime.ws_manager import ws_manager
from core.time_utils import to_epoch_ms_utc

from .models import (
    FollowNotification,
    FollowNotificationReceipt,
    FollowNotificationReceiptStatus,
)

class FollowNotificationService:
    """Create/list/mark follow notifications."""

    @staticmethod
    def _unread_count_stmt(user_id: str):
        return (
            select(func.count(FollowNotificationReceipt.notification_id))
            .where(FollowNotificationReceipt.user_id == user_id)
            .where(
                FollowNotificationReceipt.status != FollowNotificationReceiptStatus.SEEN.value
            )
        )

    @staticmethod
    async def get_unread_count(db: AsyncSession, *, user_id: str) -> int:
        res = await db.execute(FollowNotificationService._unread_count_stmt(user_id))
        return int(res.scalar_one())

    @staticmethod
    async def create_follow_notification(
        db: AsyncSession,
        *,
        follower_id: str,
        followee_id: str,
    ) -> None:
        notification = FollowNotification(
            follower_id=follower_id,
            followee_id=followee_id,
        )
        db.add(notification)
        await db.flush()

        db.add(
            FollowNotificationReceipt(
                notification_id=notification.id,
                user_id=followee_id,
                status=FollowNotificationReceiptStatus.DELIVERED.value,
            )
        )
        await db.commit()
        await db.refresh(notification)

        unread = (await db.execute(FollowNotificationService._unread_count_stmt(followee_id))).scalar_one()

        await ws_manager.broadcast_user(
            followee_id,
            {
                "event": "follow_notification_created",
                "notificationId": notification.id,
                "followerId": follower_id,
                "createdAt": to_epoch_ms_utc(notification.created_at),
                "receiptStatus": FollowNotificationReceiptStatus.DELIVERED.value,
                "unreadCount": unread,
            },
        )

    @staticmethod
    async def list_for_user(
        db: AsyncSession,
        *,
        user_id: str,
        limit: int,
        offset: int,
    ) -> tuple[int, list[tuple[FollowNotification, FollowNotificationReceiptStatus]]]:
        total_stmt = (
            select(func.count(FollowNotificationReceipt.notification_id))
            .where(FollowNotificationReceipt.user_id == user_id)
        )
        total = (await db.execute(total_stmt)).scalar_one()

        stmt = (
            select(FollowNotification, FollowNotificationReceipt.status)
            .join(
                FollowNotificationReceipt,
                FollowNotificationReceipt.notification_id == FollowNotification.id,
            )
            .where(FollowNotificationReceipt.user_id == user_id)
            .order_by(FollowNotification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        res = await db.execute(stmt)
        rows = res.all()
        return total, rows

    @staticmethod
    async def mark_seen_all(
        db: AsyncSession,
        *,
        user_id: str,
    ) -> int:
        """Mark all unread follow notifications as SEEN. Returns new unreadCount."""
        await db.execute(
            update(FollowNotificationReceipt)
            .where(FollowNotificationReceipt.user_id == user_id)
            .where(
                FollowNotificationReceipt.status
                != FollowNotificationReceiptStatus.SEEN.value
            )
            .values(status=FollowNotificationReceiptStatus.SEEN.value)
        )
        await db.commit()

        unread = (await db.execute(FollowNotificationService._unread_count_stmt(user_id))).scalar_one()

        await ws_manager.broadcast_user(
            user_id,
            {
                "event": "follow_notification_updated",
                "unreadCount": unread,
            },
        )
        return int(unread)

    @staticmethod
    async def get_latest_for_user(
        db: AsyncSession,
        *,
        user_id: str,
    ) -> tuple[FollowNotification, FollowNotificationReceiptStatus] | None:
        stmt = (
            select(FollowNotification, FollowNotificationReceipt.status)
            .join(
                FollowNotificationReceipt,
                FollowNotificationReceipt.notification_id == FollowNotification.id,
            )
            .where(FollowNotificationReceipt.user_id == user_id)
            .order_by(FollowNotification.created_at.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        row = res.first()
        if not row:
            return None
        notif, receipt_status = row
        return notif, receipt_status

