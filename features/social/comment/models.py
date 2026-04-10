from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.time_utils import now_utc
from database import Base


class Comment(Base):
    """Comment on a post (supports threaded replies via parent_id)."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    post_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    like_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    reply_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )


class CommentLike(Base):
    """Many-to-many: which users liked which comments."""

    __tablename__ = "comment_likes"

    user_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    comment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )

