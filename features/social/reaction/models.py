from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class PostLike(Base):
    """Which users liked which posts."""

    __tablename__ = "post_likes"

    user_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    post_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class PostSave(Base):
    """Posts saved/bookmarked by a user."""

    __tablename__ = "post_saves"

    user_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    post_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

