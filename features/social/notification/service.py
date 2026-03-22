from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.realtime.ws_manager import ws_manager
from core.time_utils import to_epoch_ms_utc
from features.post.models import Post

from .models import (
    NotificationActionType,
    NotificationReceiptStatus,
    SocialNotification,
    SocialNotificationReceipt,
)
from .schemas import NotificationResponse


class NotificationService:
    """Service create/list/mark social notifications."""

    @staticmethod
    def build_unread_count_stmt(user_id: str):
        allowed_actions = {
            NotificationActionType.LIKE.value,
            NotificationActionType.COMMENT.value,
            NotificationActionType.COMMENT_REPLY.value,
            NotificationActionType.COMMENT_LIKE.value,
            NotificationActionType.REPOST.value,
        }
        return (
            select(func.count(SocialNotificationReceipt.notification_id))
            .join(
                SocialNotification,
                SocialNotificationReceipt.notification_id == SocialNotification.id,
            )
            .where(
                SocialNotificationReceipt.user_id == user_id,
                SocialNotification.action_type.in_(allowed_actions),
                SocialNotificationReceipt.status != NotificationReceiptStatus.SEEN.value,
            )
        )

    @staticmethod
    async def create_for_post_owner(
        db: AsyncSession,
        *,
        from_user_id: str,
        post_id: int,
        action_type: NotificationActionType,
        comment_id: Optional[int] = None,
    ) -> Optional[SocialNotification]:
        post = await db.get(Post, post_id)
        if not post or not post.user_id:
            return None
        return await NotificationService.create_for_user(
            db,
            from_user_id=from_user_id,
            to_user_id=post.user_id,
            post_id=post_id,
            action_type=action_type,
            comment_id=comment_id,
        )

    @staticmethod
    async def create_for_user(
        db: AsyncSession,
        *,
        from_user_id: str,
        to_user_id: str,
        post_id: int,
        action_type: NotificationActionType,
        comment_id: Optional[int] = None,
    ) -> Optional[SocialNotification]:
        """Create notification for an arbitrary recipient user."""
        if not to_user_id or to_user_id == from_user_id:
            return None

        notification = SocialNotification(
            from_user_id=from_user_id,
            post_id=post_id,
            action_type=action_type.value,
            comment_id=comment_id,
        )
        db.add(notification)
        await db.flush()

        db.add(
            SocialNotificationReceipt(
                notification_id=notification.id,
                user_id=to_user_id,
                status=NotificationReceiptStatus.DELIVERED.value,
            )
        )
        await db.commit()
        await db.refresh(notification)

        unread_stmt = NotificationService.build_unread_count_stmt(to_user_id)
        unread = (await db.execute(unread_stmt)).scalar_one()

        # best-effort realtime push
        await ws_manager.broadcast_user(
            to_user_id,
            {
                "event": "notification_created",
                "postId": post_id,
                "actionType": action_type.value,
                "notificationId": notification.id,
                "commentId": comment_id,
                "unreadCount": unread,
                "receiptStatus": NotificationReceiptStatus.DELIVERED.value,
                "createdAt": to_epoch_ms_utc(notification.created_at),
            },
        )
        return notification

    @staticmethod
    async def list_for_user(
        db: AsyncSession,
        *,
        user_id: str,
        limit: int,
        offset: int,
    ):
        allowed_actions = {
            NotificationActionType.LIKE.value,
            NotificationActionType.COMMENT.value,
            NotificationActionType.COMMENT_REPLY.value,
            NotificationActionType.COMMENT_LIKE.value,
            NotificationActionType.REPOST.value,
        }
        total_stmt = (
            select(func.count(SocialNotificationReceipt.notification_id))
            .join(
                SocialNotification,
                SocialNotificationReceipt.notification_id == SocialNotification.id,
            )
            .where(SocialNotificationReceipt.user_id == user_id)
            .where(SocialNotification.action_type.in_(allowed_actions))
        )
        total = (await db.execute(total_stmt)).scalar_one()

        stmt = (
            select(SocialNotification, SocialNotificationReceipt.status)
            .join(
                SocialNotificationReceipt,
                SocialNotificationReceipt.notification_id
                == SocialNotification.id,
            )
            .where(SocialNotificationReceipt.user_id == user_id)
            .where(SocialNotification.action_type.in_(allowed_actions))
            .order_by(SocialNotification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        res = await db.execute(stmt)
        rows = res.all()
        return total, rows

    @staticmethod
    async def get_latest_for_user(
        db: AsyncSession,
        *,
        user_id: str,
    ) -> Optional[tuple[SocialNotification, NotificationReceiptStatus]]:
        allowed_actions = {
            NotificationActionType.LIKE.value,
            NotificationActionType.COMMENT.value,
            NotificationActionType.COMMENT_REPLY.value,
            NotificationActionType.COMMENT_LIKE.value,
            NotificationActionType.REPOST.value,
        }
        stmt = (
            select(SocialNotification, SocialNotificationReceipt.status)
            .join(
                SocialNotificationReceipt,
                SocialNotificationReceipt.notification_id == SocialNotification.id,
            )
            .where(SocialNotificationReceipt.user_id == user_id)
            .where(SocialNotification.action_type.in_(allowed_actions))
            .order_by(SocialNotification.created_at.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        row = res.first()
        if not row:
            return None
        notif, receipt_status = row
        return notif, receipt_status

    @staticmethod
    async def mark_seen(
        db: AsyncSession,
        *,
        user_id: str,
        notification_id: int,
    ) -> bool:
        stmt = select(SocialNotificationReceipt).where(
            SocialNotificationReceipt.user_id == user_id,
            SocialNotificationReceipt.notification_id == notification_id,
        )
        res = await db.execute(stmt)
        receipt = res.scalar_one_or_none()
        if not receipt:
            return False
        receipt.status = NotificationReceiptStatus.SEEN.value
        await db.commit()

        # Recompute unread count for realtime badge update.
        unread_stmt = NotificationService.build_unread_count_stmt(user_id)
        unread = (await db.execute(unread_stmt)).scalar_one()

        await ws_manager.broadcast_user(
            user_id,
            {
                "event": "notification_updated",
                "unreadCount": unread,
                "notificationId": notification_id,
            },
        )
        return True

    @staticmethod
    async def mark_seen_all(
        db: AsyncSession,
        *,
        user_id: str,
    ) -> int:
        """Mark all unread social notifications as SEEN. Returns new unreadCount."""
        # Tắt hết receipts chưa SEEN của user. FE đã filter actionType theo backend,
        # nên không cần điều kiện action_type ở đây để tránh query phức tạp.
        await db.execute(
            update(SocialNotificationReceipt)
            .where(SocialNotificationReceipt.user_id == user_id)
            .where(SocialNotificationReceipt.status != NotificationReceiptStatus.SEEN.value)
            .values(status=NotificationReceiptStatus.SEEN.value)
        )
        await db.commit()

        unread_stmt = NotificationService.build_unread_count_stmt(user_id)
        unread = (await db.execute(unread_stmt)).scalar_one()

        await ws_manager.broadcast_user(
            user_id,
            {
                "event": "notification_updated",
                "unreadCount": unread,
            },
        )
        return int(unread)

    @staticmethod
    async def get_unread_count(db: AsyncSession, *, user_id: str) -> int:
        stmt = NotificationService.build_unread_count_stmt(user_id)
        res = await db.execute(stmt)
        return int(res.scalar_one())

