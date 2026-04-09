# features/user/models.py - SQLAlchemy User Models
import uuid
from datetime import datetime, date
from sqlalchemy import String, Text, Boolean, DateTime, Date, Integer, BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.mysql import CHAR

from database import Base


class User(Base):
    """User model storing data not kept in Firebase"""
    __tablename__ = "users"

    # Using CHAR(36) for UUID in MySQL
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=True)
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=True)
    
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=True)
    bio: Mapped[str] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str] = mapped_column(String(512), nullable=True)
    
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    stats: Mapped["UserStats"] = relationship("UserStats", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, firebase_uid={self.firebase_uid})>"


class UserStats(Base):
    """User statistics model (followers, following, likes)"""
    __tablename__ = "user_stats"

    user_id: Mapped[str] = mapped_column(CHAR(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    
    followers_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    following_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    likes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="stats")

    def __repr__(self) -> str:
        return f"<UserStats(user_id={self.user_id}, followers={self.followers_count})>"


class UserProfile(Base):
    """
    Lightweight profile cache keyed by Firebase UID.

    This table is intentionally minimal and is used for search/join operations
    without requiring Firebase lookups.
    """

    __tablename__ = "user_profiles"

    uid: Mapped[str] = mapped_column(String(128), primary_key=True)
    username: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    avatar: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
