# features/video/models.py - SQLAlchemy Video Model
import enum
from datetime import datetime
from sqlalchemy import String, Text, Enum, DateTime, Integer, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class VideoStatus(str, enum.Enum):
    """Video processing status"""
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class Video(Base):
    """Video model for storing video metadata"""
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Video metadata
    title: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    
    # File paths
    raw_file_path: Mapped[str] = mapped_column(String(512), nullable=True)
    compressed_file_path: Mapped[str] = mapped_column(String(512), nullable=True)
    
    # Processing status
    status: Mapped[VideoStatus] = mapped_column(
        Enum(VideoStatus),
        default=VideoStatus.PROCESSING,
        nullable=False
    )
    
    # Video info
    duration: Mapped[int] = mapped_column(Integer, nullable=True)  # Duration in seconds
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=True)  # File size in bytes
    compressed_size: Mapped[int] = mapped_column(BigInteger, nullable=True)  # Compressed size
    
    # Original filename
    original_filename: Mapped[str] = mapped_column(String(255), nullable=True)
    
    # MIME type
    mime_type: Mapped[str] = mapped_column(String(100), default="video/mp4")
    
    # Error message if processing failed
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<Video(id={self.id}, status={self.status}, title={self.title})>"
