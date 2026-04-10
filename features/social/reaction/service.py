import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import PostLike, PostSave
from ..share.models import PostShare
from ..comment.models import Comment


class ReactionService:
    """Like / save state for posts, and compute social state from social tables."""

    @staticmethod
    async def like_post(
        db: AsyncSession,
        user_id: str,
        post_id: int,
    ) -> bool:
        """Like a post. Returns True if a new like was created."""
        logging.getLogger(__name__).info(
            f"ReactionService.like_post user_id={user_id}, post_id={post_id}"
        )
        stmt = select(PostLike).where(
            PostLike.user_id == user_id,
            PostLike.post_id == post_id,
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return False

        db.add(PostLike(user_id=user_id, post_id=post_id))

        from features.post.models import Post  # local import to avoid circulars

        post = await db.get(Post, post_id)
        if post:
            post.like_count = (post.like_count or 0) + 1

        await db.commit()
        return True

    @staticmethod
    async def unlike_post(
        db: AsyncSession,
        user_id: str,
        post_id: int,
    ) -> bool:
        """Remove like from a post. Returns True if something was deleted."""
        logging.getLogger(__name__).info(
            f"ReactionService.unlike_post user_id={user_id}, post_id={post_id}"
        )
        stmt = select(PostLike).where(
            PostLike.user_id == user_id,
            PostLike.post_id == post_id,
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if not existing:
            return False

        await db.delete(existing)

        from features.post.models import Post  # local import

        post = await db.get(Post, post_id)
        if post and post.like_count and post.like_count > 0:
            post.like_count -= 1

        await db.commit()
        return True

    @staticmethod
    async def save_post(
        db: AsyncSession,
        user_id: str,
        post_id: int,
    ) -> bool:
        """Save/bookmark a post."""
        stmt = select(PostSave).where(
            PostSave.user_id == user_id,
            PostSave.post_id == post_id,
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return False

        db.add(PostSave(user_id=user_id, post_id=post_id))
        await db.commit()
        return True

    @staticmethod
    async def unsave_post(
        db: AsyncSession,
        user_id: str,
        post_id: int,
    ) -> bool:
        """Remove saved/bookmarked post."""
        stmt = select(PostSave).where(
            PostSave.user_id == user_id,
            PostSave.post_id == post_id,
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if not existing:
            return False

        await db.delete(existing)
        await db.commit()
        return True

    @staticmethod
    async def get_post_social_state(
        db: AsyncSession,
        user_id: str,
        post_id: int,
    ) -> tuple[int, int, int, int, bool, bool, bool]:
        """Return (like_count, comment_count, share_count, save_count, is_liked, is_saved, is_shared)."""
        logging.getLogger(__name__).info(
            f"ReactionService.get_post_social_state user_id={user_id}, post_id={post_id}"
        )
        # Đếm trực tiếp từ các bảng social để luôn đồng bộ, không phụ thuộc fields trên Post.

        # Tổng số like cho post
        like_count_stmt = select(func.count(PostLike.post_id)).where(
            PostLike.post_id == post_id
        )
        like_count = (await db.execute(like_count_stmt)).scalar_one()

        # Tổng số comment cho post
        comment_count_stmt = select(func.count(Comment.id)).where(
            Comment.post_id == post_id
        )
        comment_count = (await db.execute(comment_count_stmt)).scalar_one()

        # Tổng số share cho post
        share_count_stmt = select(func.count(PostShare.id)).where(
            PostShare.post_id == post_id
        )
        share_count = (await db.execute(share_count_stmt)).scalar_one()

        # Tổng số save cho post
        save_count_stmt = select(func.count(PostSave.post_id)).where(
            PostSave.post_id == post_id
        )
        save_count = (await db.execute(save_count_stmt)).scalar_one()

        # Trạng thái like/save cho user hiện tại
        like_check = select(PostLike).where(
            PostLike.user_id == user_id,
            PostLike.post_id == post_id,
        )
        save_check = select(PostSave).where(
            PostSave.user_id == user_id,
            PostSave.post_id == post_id,
        )
        is_liked = (await db.execute(like_check)).scalar_one_or_none() is not None
        is_saved = (await db.execute(save_check)).scalar_one_or_none() is not None

        # Current user đã share post này chưa (có record trong post_shares với user_id + post_id)
        share_check = select(PostShare.id).where(
            PostShare.user_id == user_id,
            PostShare.post_id == post_id,
        ).limit(1)
        share_row = (await db.execute(share_check)).first()
        is_shared = share_row is not None
        if not is_shared and logging.getLogger(__name__).isEnabledFor(logging.DEBUG):
            logging.getLogger(__name__).debug(
                "is_shared = false: no row in post_shares for user_id=%r post_id=%s",
                user_id,
                post_id,
            )
        return like_count, comment_count, share_count, save_count, is_liked, is_saved, is_shared


