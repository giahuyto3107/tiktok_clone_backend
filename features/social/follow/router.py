import logging
from collections.abc import Callable, Iterable
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from firebase_admin import auth as firebase_auth
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from database import get_db
from core.realtime.ws_manager import ws_manager
from features.post.schemas import PostAuthor
from .models import Follow
from .schemas import (
    FollowActionResponse,
    SocialCounts,
    SocialUser,
    SocialUserListResponse,
)
from .service import FollowService
from ..follow_notification.service import FollowNotificationService

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolve_profile(uid: str) -> Optional[PostAuthor]:
    try:
        user = firebase_auth.get_user(uid)
        display_name = user.display_name
        photo_url = user.photo_url
        email = user.email
        # Fallback: Auth user record đôi khi không sync từ client (updateProfile);
        # lấy từ provider (Google, Facebook, ...) nếu có.
        if (not display_name or not photo_url) and user.provider_data:
            for provider in user.provider_data:
                if not display_name and getattr(provider, "display_name", None):
                    display_name = provider.display_name
                if not photo_url and getattr(provider, "photo_url", None):
                    photo_url = provider.photo_url
                if display_name and photo_url:
                    break
        return PostAuthor(
            uid=user.uid,
            display_name=display_name or None,
            avatar_url=photo_url or None,
            email=email,
        )
    except Exception as exc:  # pragma: no cover - best-effort only
        logger.warning("Failed to resolve Firebase user %s: %s", uid, exc)
        return None


async def _is_following(
    db: AsyncSession,
    follower_id: str,
    followee_id: str,
) -> bool:
    """Check if follower_id is following followee_id."""
    if follower_id == followee_id:
        return False
    stmt = select(Follow.follower_id).where(
        Follow.follower_id == follower_id,
        Follow.followee_id == followee_id,
    ).limit(1)
    result = await db.execute(stmt)
    return result.first() is not None


def _ensure_not_self_action(uid: str, target_uid: str, action: str) -> None:
    if uid == target_uid:
        raise HTTPException(status_code=400, detail=f"Cannot {action} yourself")


async def _build_social_users(
    db: AsyncSession,
    current_uid: str,
    rows: Iterable[Follow],
    target_uid_getter: Callable[[Follow], str],
) -> list[SocialUser]:
    users: list[SocialUser] = []
    for follow in rows:
        target_uid = target_uid_getter(follow)
        profile = _resolve_profile(target_uid)
        if not profile:
            continue
        is_following = await _is_following(db, current_uid, target_uid)
        users.append(SocialUser(profile=profile, is_following=is_following))
    return users


@router.post(
    "/follow/{target_uid}",
    response_model=FollowActionResponse,
    tags=["Social"],
)
async def follow_user(
    target_uid: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Current user follows `target_uid`."""
    uid = current_user["uid"]
    _ensure_not_self_action(uid, target_uid, "follow")

    created = await FollowService.follow(db, uid, target_uid)
    if created:
        await FollowNotificationService.create_follow_notification(
            db,
            follower_id=uid,
            followee_id=target_uid,
        )
    await ws_manager.broadcast_user(
        uid,
        {
            "event": "follow_changed",
            "followerId": uid,
            "followeeId": target_uid,
            "isFollowing": True,
        },
    )
    await ws_manager.broadcast_user(
        target_uid,
        {
            "event": "follow_changed",
            "followerId": uid,
            "followeeId": target_uid,
            "isFollowing": True,
        },
    )
    return FollowActionResponse(
        follower_id=uid,
        followee_id=target_uid,
        is_following=True,
    )


@router.delete(
    "/follow/{target_uid}",
    response_model=FollowActionResponse,
    tags=["Social"],
)
async def unfollow_user(
    target_uid: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Current user unfollows `target_uid`."""
    uid = current_user["uid"]
    _ensure_not_self_action(uid, target_uid, "unfollow")

    await FollowService.unfollow(db, uid, target_uid)
    await ws_manager.broadcast_user(
        uid,
        {
            "event": "follow_changed",
            "followerId": uid,
            "followeeId": target_uid,
            "isFollowing": False,
        },
    )
    await ws_manager.broadcast_user(
        target_uid,
        {
            "event": "follow_changed",
            "followerId": uid,
            "followeeId": target_uid,
            "isFollowing": False,
        },
    )
    return FollowActionResponse(
        follower_id=uid,
        followee_id=target_uid,
        is_following=False,
    )


@router.get(
    "/{uid}/counts",
    response_model=SocialCounts,
    tags=["Social"],
)
async def get_social_counts(
    uid: str,
    db: AsyncSession = Depends(get_db),
):
    """Get follower/following counts for a user."""
    follower_count, following_count = await FollowService.get_counts(db, uid)
    return SocialCounts(
        user_id=uid,
        follower_count=follower_count,
        following_count=following_count,
    )


@router.get(
    "/{uid}/followers",
    response_model=SocialUserListResponse,
    tags=["Social"],
)
async def list_followers(
    uid: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List followers for a user."""
    rows = await FollowService.get_followers(db, uid, limit=limit, offset=offset)
    current_uid = current_user["uid"]

    users = await _build_social_users(
        db=db,
        current_uid=current_uid,
        rows=rows,
        target_uid_getter=lambda follow: follow.follower_id,
    )

    return SocialUserListResponse(users=users, total=len(users))


@router.get(
    "/{uid}/following",
    response_model=SocialUserListResponse,
    tags=["Social"],
)
async def list_following(
    uid: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List users that `uid` is following."""
    rows = await FollowService.get_following(db, uid, limit=limit, offset=offset)
    current_uid = current_user["uid"]

    users = await _build_social_users(
        db=db,
        current_uid=current_uid,
        rows=rows,
        target_uid_getter=lambda follow: follow.followee_id,
    )

    return SocialUserListResponse(users=users, total=len(users))
