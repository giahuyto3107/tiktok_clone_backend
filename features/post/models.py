# features/post/models.py - SQLAlchemy Post Model (shared for video & image)
import enum
from datetime import datetime
from sqlalchemy import String, Text, Enum, DateTime, Integer, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class PostType(str, enum.Enum):
    """Post content type"""
    VIDEO = "VIDEO"
    IMAGE = "IMAGE"


class PostStatus(str, enum.Enum):
    """Processing status (used for video; image is READY immediately)"""
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class Post(Base):
    """Post model for video and image content (aligned with client Post)"""
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, default="0")

    # Content type and public URLs (client-facing)
    type: Mapped[PostType] = mapped_column(Enum(PostType), default=PostType.VIDEO, nullable=False)
    media_url: Mapped[str] = mapped_column(String(512), nullable=True, default="")
    thumbnail_url: Mapped[str] = mapped_column(String(512), nullable=True, default="")
    caption: Mapped[str] = mapped_column(Text, nullable=True, default="")
    music_name: Mapped[str] = mapped_column(String(255), nullable=False, default="Original Sound")

    # Counts
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Timestamps (client uses ms; we store datetime and can expose ms in API)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # --- Video processing only (internal) ---
    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus),
        default=PostStatus.PROCESSING,
        nullable=False
    )
    raw_file_path: Mapped[str] = mapped_column(String(512), nullable=True)
    compressed_file_path: Mapped[str] = mapped_column(String(512), nullable=True)
    duration: Mapped[int] = mapped_column(Integer, nullable=True)  # seconds
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=True)
    compressed_size: Mapped[int] = mapped_column(BigInteger, nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(100), default="video/mp4", nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Post(id={self.id}, type={self.type}, status={self.status})>"
