from typing import Iterable, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Follow


class FollowService:
    """Follow/unfollow + follower/following counts."""

    @staticmethod
    async def follow(
        db: AsyncSession,
        follower_id: str,
        followee_id: str,
    ) -> bool:
        """Create follow relationship. Returns True if a new row was created."""
        if follower_id == followee_id:
            return False

        stmt = select(Follow).where(
            Follow.follower_id == follower_id,
            Follow.followee_id == followee_id,
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return False

        db.add(Follow(follower_id=follower_id, followee_id=followee_id))
        await db.commit()
        return True

    @staticmethod
    async def unfollow(
        db: AsyncSession,
        follower_id: str,
        followee_id: str,
    ) -> bool:
        """Remove follow relationship. Returns True if something was deleted."""
        stmt = select(Follow).where(
            Follow.follower_id == follower_id,
            Follow.followee_id == followee_id,
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if not existing:
            return False

        await db.delete(existing)
        await db.commit()
        return True

    @staticmethod
    async def get_counts(
        db: AsyncSession,
        user_id: str,
    ) -> Tuple[int, int]:
        """Return (follower_count, following_count) for a user."""
        follower_stmt = select(func.count(Follow.follower_id)).where(
            Follow.followee_id == user_id
        )
        following_stmt = select(func.count(Follow.followee_id)).where(
            Follow.follower_id == user_id
        )

        follower_count = (await db.execute(follower_stmt)).scalar_one()
        following_count = (await db.execute(following_stmt)).scalar_one()
        return follower_count, following_count

    @staticmethod
    async def get_followers(
        db: AsyncSession,
        user_id: str,
        limit: int,
        offset: int,
    ) -> Iterable[Follow]:
        stmt = (
            select(Follow)
            .where(Follow.followee_id == user_id)
            .offset(offset)
            .limit(limit)
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    @staticmethod
    async def get_following(
        db: AsyncSession,
        user_id: str,
        limit: int,
        offset: int,
    ) -> Iterable[Follow]:
        stmt = (
            select(Follow)
            .where(Follow.follower_id == user_id)
            .offset(offset)
            .limit(limit)
        )
        res = await db.execute(stmt)
        return res.scalars().all()

