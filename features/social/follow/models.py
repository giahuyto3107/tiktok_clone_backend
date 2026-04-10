from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from core.time_utils import now_utc
from database import Base


class Follow(Base):
    """Follow relationship between two users (using Firebase UID as ID)."""

    __tablename__ = "follows"

    follower_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    followee_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )

