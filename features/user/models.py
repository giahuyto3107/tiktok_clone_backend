from datetime import datetime

from sqlalchemy import DateTime, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from core.time_utils import now_utc
from database import Base


class UserProfile(Base):
    """
    Lightweight user profile cache for fast search / display.

    Auth source of truth remains Firebase; this table is a denormalized cache to avoid
    scanning Firebase users for every search request.
    """

    __tablename__ = "user_profiles"

    uid: Mapped[str] = mapped_column(String(255), primary_key=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
        nullable=False,
    )


Index("ix_user_profiles_username", UserProfile.username)
Index("ix_user_profiles_email", UserProfile.email)
Index(
    "ft_user_profiles_username_email",
    UserProfile.username,
    UserProfile.email,
    mysql_prefix="FULLTEXT",
)

