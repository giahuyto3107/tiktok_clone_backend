# features/video/schemas.py - Pydantic Schemas for Video
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from .models import VideoStatus


class VideoCreate(BaseModel):
    """Schema for creating a new video (used with form data)"""
    title: Optional[str] = None
    description: Optional[str] = None


class VideoUploadResponse(BaseModel):
    """Response schema after uploading a video"""
    video_id: int
    status: VideoStatus
    message: str

    model_config = ConfigDict(from_attributes=True)


class VideoResponse(BaseModel):
    """Full video response schema"""
    id: int
    title: Optional[str] = None
    description: Optional[str] = None
    status: VideoStatus
    duration: Optional[int] = None
    file_size: Optional[int] = None
    compressed_size: Optional[int] = None
    original_filename: Optional[str] = None
    mime_type: str
    video_url: Optional[str] = None  # URL to access the video
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VideoStatusResponse(BaseModel):
    """Response schema for video status check"""
    video_id: int
    status: VideoStatus
    video_url: Optional[str] = None
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class VideoListResponse(BaseModel):
    """Response schema for list of videos"""
    videos: list[VideoResponse]
    total: int
    page: int
    page_size: int
