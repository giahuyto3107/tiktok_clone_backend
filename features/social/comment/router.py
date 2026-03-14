import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user, get_optional_user
from database import get_db
from .models import Comment, CommentLike
from .schemas import CommentCreate, CommentResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _to_response(
    comment: Comment,
    is_liked: bool,
) -> CommentResponse:
    """Map ORM Comment -> API CommentResponse (ids as String for client)."""
    return CommentResponse(
        id=str(comment.id),
        post_id=str(comment.post_id),
        user_id=comment.user_id,
        content=comment.content,
        like_count=comment.like_count,
        is_liked=is_liked,
        parent_id=str(comment.parent_id) if comment.parent_id is not None else None,
        reply_count=comment.reply_count,
        created_at=int(comment.created_at.timestamp() * 1000) if comment.created_at else 0,
    )


@router.get(
    "/posts/{post_id}/comments",
    response_model=list[CommentResponse],
)
async def list_comments_for_post(
    post_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(get_optional_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List comments for a given post."""
    stmt = (
        select(Comment)
        .where(Comment.post_id == post_id)
        .order_by(Comment.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    res = await db.execute(stmt)
    comments = res.scalars().all()

    liked_map: dict[int, bool] = {}
    if current_user and comments:
        uid = current_user["uid"]
        ids = [c.id for c in comments]
        likes_stmt = select(CommentLike.comment_id).where(
            CommentLike.user_id == uid,
            CommentLike.comment_id.in_(ids),
        )
        likes_res = await db.execute(likes_stmt)
        liked_ids = {row[0] for row in likes_res.all()}
        liked_map = {cid: cid in liked_ids for cid in ids}

    items: list[CommentResponse] = []
    for c in comments:
        is_liked = liked_map.get(c.id, False)
        items.append(_to_response(c, is_liked))

    # Trả thẳng list comment cho client
    return items


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment_for_post(
    post_id: int,
    payload: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new comment (or reply if parentId provided) for a post."""
    uid = current_user["uid"]

    comment = Comment(
        post_id=post_id,
        user_id=uid,
        content=payload.content,
        parent_id=payload.parent_id,
    )
    db.add(comment)

    if payload.parent_id is not None:
        parent_stmt = select(Comment).where(Comment.id == payload.parent_id)
        parent_res = await db.execute(parent_stmt)
        parent = parent_res.scalar_one_or_none()
        if parent:
            parent.reply_count = (parent.reply_count or 0) + 1

    await db.commit()
    await db.refresh(comment)

    return _to_response(comment, is_liked=False)


@router.post("/comments/{comment_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def like_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Like a comment for the current user."""
    uid = current_user["uid"]

    comment = await db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    stmt = select(CommentLike).where(
        CommentLike.comment_id == comment_id,
        CommentLike.user_id == uid,
    )
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        return

    db.add(CommentLike(user_id=uid, comment_id=comment_id))
    comment.like_count = (comment.like_count or 0) + 1

    await db.commit()


@router.delete("/comments/{comment_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def unlike_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Remove like from a comment for the current user."""
    uid = current_user["uid"]

    comment = await db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    stmt = select(CommentLike).where(
        CommentLike.comment_id == comment_id,
        CommentLike.user_id == uid,
    )
    res = await db.execute(stmt)
    like = res.scalar_one_or_none()
    if not like:
        return

    await db.delete(like)
    if comment.like_count and comment.like_count > 0:
        comment.like_count -= 1

    await db.commit()

