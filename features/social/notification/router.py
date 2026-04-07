from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from core.auth import get_current_user
from core.time_utils import to_epoch_ms_utc
from database import get_db

from .models import (
    NotificationActionType,
    NotificationReceiptStatus,
    SocialNotification,
)
from .schemas import (
    MarkReceiptSeenResponse,
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
    LatestNotificationResponse,
)
from .service import NotificationService

router = APIRouter(tags=["Social"])


@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List social notifications for current user."""
    uid = current_user["uid"]
    total, rows = await NotificationService.list_for_user(
        db,
        user_id=uid,
        limit=limit,
        offset=offset,
    )

    notifications: list[NotificationResponse] = []
    for notif, receipt_status in rows:
        notifications.append(
            NotificationResponse(
                id=notif.id,
                from_user_id=notif.from_user_id,
                post_id=notif.post_id,
                action_type=notif.action_type,
                comment_id=notif.comment_id,
                created_at=to_epoch_ms_utc(notif.created_at),
                receipt_status=receipt_status,
            )
        )

    return NotificationListResponse(notifications=notifications, total=total)


@router.post("/notifications/{notification_id}/seen", response_model=MarkReceiptSeenResponse)
async def mark_notification_seen(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Mark a notification receipt as SEEN for current user."""
    uid = current_user["uid"]
    ok = await NotificationService.mark_seen(
        db,
        user_id=uid,
        notification_id=notification_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")
    return MarkReceiptSeenResponse()


# @router.post("/notifications/seen-all", response_model=UnreadCountResponse)
@router.post("/notifications/seenAll", response_model=UnreadCountResponse)
async def mark_notifications_seen_all(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    uid = current_user["uid"]
    unread = await NotificationService.mark_seen_all(db, user_id=uid)
    return UnreadCountResponse(unreadCount=unread)


@router.get("/notifications/unread-count", response_model=UnreadCountResponse)
async def get_notifications_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    uid = current_user["uid"]
    # Count notifications that are not SEEN yet.
    stmt = NotificationService.build_unread_count_stmt(uid)
    res = await db.execute(stmt)
    unread = res.scalar_one()
    return UnreadCountResponse(unreadCount=unread)


@router.get("/notifications/latest", response_model=LatestNotificationResponse)
async def get_latest_social_notification(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    uid = current_user["uid"]
    latest = await NotificationService.get_latest_for_user(db, user_id=uid)
    if not latest:
        return LatestNotificationResponse(notification=None)
    notif, receipt_status = latest
    return LatestNotificationResponse(
        notification=NotificationResponse(
            id=notif.id,
            from_user_id=notif.from_user_id,
            post_id=notif.post_id,
            action_type=notif.action_type,
            comment_id=notif.comment_id,
            created_at=to_epoch_ms_utc(notif.created_at),
            receipt_status=receipt_status,
        )
    )

