from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import PostShare


class ShareService:
    """Track how many times a post is shared."""

    @staticmethod
    async def share_post(
        db: AsyncSession,
        user_id: str,
        post_id: int,
        target: str | None = None,
    ) -> bool:
        """Ghi nhận current user đã share post. Trả về True nếu tạo mới, False nếu đã share rồi (idempotent)."""
        stmt = select(PostShare).where(
            PostShare.user_id == user_id,
            PostShare.post_id == post_id,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            return False
        db.add(PostShare(user_id=user_id, post_id=post_id, target=target))
        await db.commit()
        return True

    @staticmethod
    async def unshare_post(
        db: AsyncSession,
        user_id: str,
        post_id: int,
    ) -> bool:
        """Bỏ share: xóa record share của user với post. Trả về True nếu đã xóa."""
        stmt = select(PostShare).where(
            PostShare.user_id == user_id,
            PostShare.post_id == post_id,
        )
        res = await db.execute(stmt)
        row = res.scalar_one_or_none()
        if not row:
            return False
        await db.delete(row)
        await db.commit()
        return True

    @staticmethod
    async def get_share_count(
        db: AsyncSession,
        post_id: int,
    ) -> int:
        stmt = select(func.count(PostShare.id)).where(PostShare.post_id == post_id)
        return (await db.execute(stmt)).scalar_one()

