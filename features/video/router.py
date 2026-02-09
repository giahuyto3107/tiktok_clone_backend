# features/video/router.py - Video API Endpoints
import os
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from .models import VideoStatus
from .schemas import VideoUploadResponse, VideoResponse, VideoStatusResponse, VideoListResponse
from .service import VideoService, process_video_background

logger = logging.getLogger(__name__)

router = APIRouter()

# Configuration
UPLOAD_RAW_DIR = "uploads/raw"
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB max
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def get_video_url(video) -> Optional[str]:
    """Generate video URL from file path"""
    if video.status == VideoStatus.READY and video.compressed_file_path:
        # Return relative URL for static file serving
        return f"/uploads/compressed/{os.path.basename(video.compressed_file_path)}"
    return None


@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a video file.
    
    - Accepts video via Multipart Form
    - Saves raw file to /uploads/raw
    - Creates database record with PROCESSING status
    - Triggers background compression task
    - Returns video_id immediately
    
    **Supported formats**: MP4, MOV, AVI, MKV, WEBM
    **Max file size**: 100 MB
    """
    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Supported: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Validate file size
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)} MB"
        )

    # Generate unique filename and save raw file
    unique_filename = VideoService.generate_unique_filename(file.filename)
    raw_file_path = os.path.join(UPLOAD_RAW_DIR, unique_filename)

    try:
        with open(raw_file_path, "wb") as f:
            f.write(content)
        logger.info(f"Saved raw file: {raw_file_path} ({file_size} bytes)")
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save video file")

    # Create database record
    video = await VideoService.create_video_record(
        db=db,
        original_filename=file.filename,
        raw_file_path=raw_file_path,
        file_size=file_size,
        title=title,
        description=description,
    )

    # Add background task for video compression
    background_tasks.add_task(process_video_background, video.id, raw_file_path)

    return VideoUploadResponse(
        video_id=video.id,
        status=video.status,
        message="Video uploaded successfully. Processing started.",
    )


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get video details by ID.
    
    Returns video metadata including processing status and video URL (if ready).
    """
    video = await VideoService.get_video_by_id(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    return VideoResponse(
        id=video.id,
        title=video.title,
        description=video.description,
        status=video.status,
        duration=video.duration,
        file_size=video.file_size,
        compressed_size=video.compressed_size,
        original_filename=video.original_filename,
        mime_type=video.mime_type,
        video_url=get_video_url(video),
        error_message=video.error_message,
        created_at=video.created_at,
        updated_at=video.updated_at,
    )


@router.get("/{video_id}/status", response_model=VideoStatusResponse)
async def get_video_status(
    video_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Check video processing status.
    
    Use this endpoint to poll for video processing completion.
    - PROCESSING: Video is being compressed
    - READY: Video is ready to play
    - FAILED: Processing failed
    """
    video = await VideoService.get_video_by_id(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    return VideoStatusResponse(
        video_id=video.id,
        status=video.status,
        video_url=get_video_url(video),
        error_message=video.error_message,
    )


@router.get("/", response_model=VideoListResponse)
async def list_videos(
    page: int = 1,
    page_size: int = 20,
    status: Optional[VideoStatus] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    List all videos with pagination.
    
    - **page**: Page number (starting from 1)
    - **page_size**: Number of items per page (default: 20, max: 100)
    - **status**: Filter by status (PROCESSING, READY, FAILED)
    """
    # Validate pagination
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    skip = (page - 1) * page_size

    videos, total = await VideoService.get_all_videos(
        db=db,
        skip=skip,
        limit=page_size,
        status=status,
    )

    video_responses = [
        VideoResponse(
            id=v.id,
            title=v.title,
            description=v.description,
            status=v.status,
            duration=v.duration,
            file_size=v.file_size,
            compressed_size=v.compressed_size,
            original_filename=v.original_filename,
            mime_type=v.mime_type,
            video_url=get_video_url(v),
            error_message=v.error_message,
            created_at=v.created_at,
            updated_at=v.updated_at,
        )
        for v in videos
    ]

    return VideoListResponse(
        videos=video_responses,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete("/{video_id}")
async def delete_video(
    video_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a video by ID.
    
    This will delete:
    - The database record
    - The raw file (if exists)
    - The compressed file (if exists)
    """
    video = await VideoService.get_video_by_id(db, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Delete files
    if video.raw_file_path:
        VideoService.delete_file(video.raw_file_path)
    if video.compressed_file_path:
        VideoService.delete_file(video.compressed_file_path)

    # Delete database record
    await db.delete(video)
    await db.commit()

    return {"message": f"Video {video_id} deleted successfully"}
