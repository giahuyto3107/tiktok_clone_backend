from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from database import get_db
from .schemas import PostShareResponse
from .service import ShareService

router = APIRouter(tags=["Social"])


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
    await ShareService.share_post(db, uid, post_id, target=target)
    share_count = await ShareService.get_share_count(db, post_id)
    return PostShareResponse(post_id=post_id, share_count=share_count, is_shared=True)


@router.delete("/posts/{post_id}/share", response_model=PostShareResponse)
async def unshare_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Current user bỏ share post (unshare)."""
    uid = current_user["uid"]
    await ShareService.unshare_post(db, uid, post_id)
    share_count = await ShareService.get_share_count(db, post_id)
    return PostShareResponse(post_id=post_id, share_count=share_count, is_shared=False)

