from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from core.realtime.ws_manager import ws_manager
from database import get_db
from .schemas import PostShareResponse
from .service import ShareService
from ..notification.models import NotificationActionType
from ..notification.service import NotificationService

router = APIRouter(tags=["Social"])


async def _build_share_response(
    db: AsyncSession,
    post_id: int,
    is_shared: bool,
) -> PostShareResponse:
    share_count = await ShareService.get_share_count(db, post_id)
    return PostShareResponse(post_id=post_id, share_count=share_count, is_shared=is_shared)


@router.post("/posts/{post_id}/share", response_model=PostShareResponse)
async def share_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    target: str | None = Query(
        default=None,
        description="Optional share target (friend uid, external, etc.)",
    ),
):
    """Current user share một post (idempotent: đã share rồi thì không tạo thêm record)."""
    uid = current_user["uid"]
    created = await ShareService.share_post(db, uid, post_id, target=target)
    resp = await _build_share_response(db, post_id, is_shared=True)
    await ws_manager.broadcast_post(
        post_id,
        {"event": "post_state_changed", "postId": post_id},
    )
    return resp


@router.delete("/posts/{post_id}/share", response_model=PostShareResponse)
async def unshare_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Current user bỏ share post (unshare)."""
    uid = current_user["uid"]
    await ShareService.unshare_post(db, uid, post_id)
    resp = await _build_share_response(db, post_id, is_shared=False)
    await ws_manager.broadcast_post(
        post_id,
        {"event": "post_state_changed", "postId": post_id},
    )
    return resp


@router.post("/posts/{post_id}/repost", response_model=PostShareResponse)
async def repost_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Repost một post (idempotent)."""
    uid = current_user["uid"]
    created = await ShareService.share_post(db, uid, post_id, target=None)
    if created:
        await NotificationService.create_for_post_owner(
            db,
            from_user_id=uid,
            post_id=post_id,
            action_type=NotificationActionType.REPOST,
        )
    resp = await _build_share_response(db, post_id, is_shared=True)
    await ws_manager.broadcast_post(
        post_id,
        {"event": "post_state_changed", "postId": post_id},
    )
    return resp


@router.delete("/posts/{post_id}/repost", response_model=PostShareResponse)
async def unrepost_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Undo repost."""
    uid = current_user["uid"]
    await ShareService.unshare_post(db, uid, post_id)
    resp = await _build_share_response(db, post_id, is_shared=False)
    await ws_manager.broadcast_post(
        post_id,
        {"event": "post_state_changed", "postId": post_id},
    )
    return resp

