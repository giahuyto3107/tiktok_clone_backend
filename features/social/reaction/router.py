from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from database import get_db
from .schemas import PostLikeResponse, PostSaveResponse, PostSocialState
from .service import ReactionService
from core.realtime.ws_manager import ws_manager
from ..notification.models import NotificationActionType
from ..notification.service import NotificationService

router = APIRouter(tags=["Social"])


def _uid(current_user: dict) -> str:
    return current_user["uid"]


@router.post("/posts/{post_id}/like", response_model=PostLikeResponse)
async def like_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    actor_uid = _uid(current_user)
    created = await ReactionService.like_post(db, actor_uid, post_id)
    if created:
        await NotificationService.create_for_post_owner(
            db,
            from_user_id=actor_uid,
            post_id=post_id,
            action_type=NotificationActionType.LIKE,
        )
    await ws_manager.broadcast_post(
        post_id,
        {"event": "post_state_changed", "postId": post_id},
    )
    return PostLikeResponse(post_id=post_id, is_liked=True)


@router.delete("/posts/{post_id}/like", response_model=PostLikeResponse)
async def unlike_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await ReactionService.unlike_post(db, _uid(current_user), post_id)
    await ws_manager.broadcast_post(
        post_id,
        {"event": "post_state_changed", "postId": post_id},
    )
    return PostLikeResponse(post_id=post_id, is_liked=False)


@router.post("/posts/{post_id}/save", response_model=PostSaveResponse)
async def save_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    actor_uid = _uid(current_user)
    created = await ReactionService.save_post(db, actor_uid, post_id)
    await ws_manager.broadcast_post(
        post_id,
        {"event": "post_state_changed", "postId": post_id},
    )
    return PostSaveResponse(post_id=post_id, is_saved=True)


@router.delete("/posts/{post_id}/save", response_model=PostSaveResponse)
async def unsave_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await ReactionService.unsave_post(db, _uid(current_user), post_id)
    await ws_manager.broadcast_post(
        post_id,
        {"event": "post_state_changed", "postId": post_id},
    )
    return PostSaveResponse(post_id=post_id, is_saved=False)

@router.get("/posts/{post_id}/state", response_model=PostSocialState)
async def get_post_social_state(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get social state (likes/saves/shares/comments) for a post and current user.

    Các count được tính trực tiếp từ các bảng social (post_likes, comments, post_shares).
    """
    uid = _uid(current_user)
    like_count, comment_count, share_count, save_count, is_liked, is_saved, is_shared = (
        await ReactionService.get_post_social_state(
            db,
            uid,
            post_id,
        )
    )

    return PostSocialState(
        post_id=post_id,
        like_count=like_count,
        comment_count=comment_count,
        share_count=share_count,
        save_count=save_count,
        is_liked=is_liked,
        is_saved=is_saved,
        is_shared=is_shared,
    )

