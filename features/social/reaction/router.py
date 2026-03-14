from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from database import get_db
from .schemas import PostLikeResponse, PostSaveResponse, PostSocialState
from .service import ReactionService

router = APIRouter(tags=["Social"])


@router.post("/posts/{post_id}/like", response_model=PostLikeResponse)
async def like_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    uid = current_user["uid"]
    await ReactionService.like_post(db, uid, post_id)
    return PostLikeResponse(post_id=post_id, is_liked=True)


@router.delete("/posts/{post_id}/like", response_model=PostLikeResponse)
async def unlike_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    uid = current_user["uid"]
    await ReactionService.unlike_post(db, uid, post_id)
    return PostLikeResponse(post_id=post_id, is_liked=False)


@router.post("/posts/{post_id}/save", response_model=PostSaveResponse)
async def save_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    uid = current_user["uid"]
    await ReactionService.save_post(db, uid, post_id)
    return PostSaveResponse(post_id=post_id, is_saved=True)


@router.delete("/posts/{post_id}/save", response_model=PostSaveResponse)
async def unsave_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    uid = current_user["uid"]
    await ReactionService.unsave_post(db, uid, post_id)
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
    uid = current_user["uid"]
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

