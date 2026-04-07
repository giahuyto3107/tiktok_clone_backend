import logging
import os
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user, get_optional_user
from core.realtime.ws_manager import ws_manager
from core.time_utils import to_epoch_ms_utc
from database import get_db
from .models import Comment, CommentLike
from .schemas import CommentCreate, CommentResponse
from ..notification.models import NotificationActionType
from ..notification.service import NotificationService

logger = logging.getLogger(__name__)

router = APIRouter()
COMMENT_IMAGE_DIR = "uploads/comments/images"
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

os.makedirs(COMMENT_IMAGE_DIR, exist_ok=True)


def make_absolute_media_url(request: Request, relative_path: Optional[str]) -> Optional[str]:
    if not relative_path:
        return None
    if relative_path.startswith("http://") or relative_path.startswith("https://"):
        return relative_path
    base = str(request.base_url).rstrip("/")
    return f"{base}{relative_path}"


def parse_parent_id(parent_id: Optional[str]) -> Optional[int]:
    if parent_id is None:
        return None
    stripped = parent_id.strip()
    if not stripped or stripped.lower() == "null":
        return None
    try:
        return int(stripped)
    except (ValueError, TypeError):
        return None


async def _increment_parent_reply_count(
    db: AsyncSession,
    parent_id: Optional[int],
) -> None:
    if parent_id is None:
        return
    parent_stmt = select(Comment).where(Comment.id == parent_id)
    parent_res = await db.execute(parent_stmt)
    parent = parent_res.scalar_one_or_none()
    if parent:
        parent.reply_count = (parent.reply_count or 0) + 1


async def _create_comment(
    db: AsyncSession,
    post_id: int,
    user_id: str,
    content: str,
    parent_id: Optional[int],
    image_url: Optional[str],
) -> Comment:
    comment = Comment(
        post_id=post_id,
        user_id=user_id,
        content=content,
        parent_id=parent_id,
        image_url=image_url,
    )
    db.add(comment)
    await db.flush()
    await _increment_parent_reply_count(db, parent_id)
    await db.commit()
    await db.refresh(comment)
    return comment


def _to_response(
    comment: Comment,
    is_liked: bool,
    image_uri: Optional[str] = None,
) -> CommentResponse:
    """Map ORM Comment -> API CommentResponse (ids as String for client)."""
    return CommentResponse(
        id=str(comment.id),
        post_id=str(comment.post_id),
        user_id=comment.user_id,
        content=comment.content,
        image_uri=image_uri,
        like_count=comment.like_count,
        is_liked=is_liked,
        parent_id=str(comment.parent_id) if comment.parent_id is not None else None,
        reply_count=comment.reply_count,
        created_at=to_epoch_ms_utc(comment.created_at),
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
    comment_ids = [c.id for c in comments]

    liked_map: dict[int, bool] = {}
    if current_user and comments:
        uid = current_user["uid"]
        likes_stmt = select(CommentLike.comment_id).where(
            CommentLike.user_id == uid,
            CommentLike.comment_id.in_(comment_ids),
        )
        likes_res = await db.execute(likes_stmt)
        liked_ids = {row[0] for row in likes_res.all()}
        liked_map = {cid: cid in liked_ids for cid in comment_ids}

    items: list[CommentResponse] = []
    for c in comments:
        is_liked = liked_map.get(c.id, False)
        items.append(
            _to_response(
                c,
                is_liked,
                image_uri=make_absolute_media_url(request, c.image_url),
            )
        )

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
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new comment (or reply if parentId provided) for a post."""
    uid = current_user["uid"]

    resolved_parent_id = payload.parent_id_int

    comment = await _create_comment(
        db=db,
        post_id=post_id,
        user_id=uid,
        content=payload.content,
        parent_id=resolved_parent_id,
        image_url=payload.image_uri,
    )

    comment_resp = _to_response(
        comment,
        is_liked=False,
        image_uri=make_absolute_media_url(request, payload.image_uri),
    )

    # If parentId is provided => this is a reply to another comment.
    # Notify the parent comment owner; otherwise notify the post owner.
    if resolved_parent_id is None:
        await NotificationService.create_for_post_owner(
            db,
            from_user_id=uid,
            post_id=post_id,
            action_type=NotificationActionType.COMMENT,
            comment_id=comment.id,
        )
    else:
        parent_comment = await db.get(Comment, resolved_parent_id)
        if parent_comment:
            await NotificationService.create_for_user(
                db,
                from_user_id=uid,
                to_user_id=parent_comment.user_id,
                post_id=post_id,
                action_type=NotificationActionType.COMMENT_REPLY,
                comment_id=comment.id,
            )
    await ws_manager.broadcast_post(
        post_id,
        {
            "event": "comments_changed",
            "postId": post_id,
            "comment": comment_resp.model_dump(by_alias=True, mode="json"),
        },
    )
    return comment_resp


@router.post(
    "/posts/{post_id}/comments/upload",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_image_comment_for_post(
    post_id: int,
    request: Request,
    file: UploadFile = File(...),
    content: Optional[str] = Form(None),
    parent_id: Optional[str] = Form(default=None, alias="parentId"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a comment with image upload (similar to inbox media upload)."""
    uid = current_user["uid"]

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"File type not allowed for comment image. "
                f"Supported: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}"
            ),
        )

    content_bytes = await file.read()
    file_size = len(content_bytes)
    if file_size > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_IMAGE_SIZE // (1024 * 1024)} MB",
        )

    unique_name = f"{uid}_comment_{os.urandom(8).hex()}{ext}"
    disk_path = os.path.normpath(os.path.join(COMMENT_IMAGE_DIR, unique_name))
    try:
        with open(disk_path, "wb") as f:
            f.write(content_bytes)
    except Exception as exc:
        logger.error("Failed to save comment image: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save comment image")

    relative_url = f"/uploads/comments/images/{unique_name}"
    resolved_parent_id = parse_parent_id(parent_id)

    comment = await _create_comment(
        db=db,
        post_id=post_id,
        user_id=uid,
        content=(content or "").strip(),
        parent_id=resolved_parent_id,
        image_url=relative_url,
    )
    comment_resp = _to_response(
        comment,
        is_liked=False,
        image_uri=make_absolute_media_url(request, relative_url),
    )

    if resolved_parent_id is None:
        await NotificationService.create_for_post_owner(
            db,
            from_user_id=uid,
            post_id=post_id,
            action_type=NotificationActionType.COMMENT,
            comment_id=comment.id,
        )
    else:
        parent_comment = await db.get(Comment, resolved_parent_id)
        if parent_comment:
            await NotificationService.create_for_user(
                db,
                from_user_id=uid,
                to_user_id=parent_comment.user_id,
                post_id=post_id,
                action_type=NotificationActionType.COMMENT_REPLY,
                comment_id=comment.id,
            )
    await ws_manager.broadcast_post(
        post_id,
        {
            "event": "comments_changed",
            "postId": post_id,
            "comment": comment_resp.model_dump(by_alias=True, mode="json"),
        },
    )
    return comment_resp


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

    if comment.user_id != uid:
        await NotificationService.create_for_user(
            db,
            from_user_id=uid,
            to_user_id=comment.user_id,
            post_id=comment.post_id,
            action_type=NotificationActionType.COMMENT_LIKE,
            comment_id=comment.id,
        )


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

