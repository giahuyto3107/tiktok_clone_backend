from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from core.time_utils import to_epoch_ms_utc
from database import get_db

from .models import FollowNotification
from .schemas import (
    FollowNotificationListResponse,
    FollowNotificationResponse,
    FollowNotificationSeenAllResponse,
    FollowNotificationUnreadCountResponse,
    FollowNotificationLatestResponse,
)
from .service import FollowNotificationService


router = APIRouter(tags=["Social"])


@router.get("/follow/notifications", response_model=FollowNotificationListResponse)
async def list_follow_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    uid = current_user["uid"]
    total, rows = await FollowNotificationService.list_for_user(
        db,
        user_id=uid,
        limit=limit,
        offset=offset,
    )

    notifications: list[FollowNotificationResponse] = []
    for notif, receipt_status in rows:
        notifications.append(
            FollowNotificationResponse(
                id=notif.id,
                follower_id=notif.follower_id,
                created_at=to_epoch_ms_utc(notif.created_at),
                receipt_status=receipt_status,
            )
        )

    return FollowNotificationListResponse(notifications=notifications, total=total)


@router.get(
    "/follow/notifications/unread-count",
    response_model=FollowNotificationUnreadCountResponse,
)
async def unread_follow_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    uid = current_user["uid"]
    unread = await FollowNotificationService.get_unread_count(db, user_id=uid)
    return FollowNotificationUnreadCountResponse(unreadCount=unread)


@router.post(
    "/follow/notifications/seen-all",
    response_model=FollowNotificationSeenAllResponse,
)
async def seen_all_follow_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    uid = current_user["uid"]
    unread = await FollowNotificationService.mark_seen_all(db, user_id=uid)
    return FollowNotificationSeenAllResponse(unreadCount=unread)


@router.get("/follow/notifications/latest", response_model=FollowNotificationLatestResponse)
async def get_latest_follow_notification(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    uid = current_user["uid"]
    latest = await FollowNotificationService.get_latest_for_user(db, user_id=uid)
    if not latest:
        return FollowNotificationLatestResponse(notification=None)
    notif, receipt_status = latest
    return FollowNotificationLatestResponse(
        notification=FollowNotificationResponse(
            id=notif.id,
            follower_id=notif.follower_id,
            created_at=to_epoch_ms_utc(notif.created_at),
            receipt_status=receipt_status,
        )
    )

