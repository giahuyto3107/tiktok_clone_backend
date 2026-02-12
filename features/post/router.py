# features/post/router.py - Post API (video + image)
import os
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from .models import PostType, PostStatus
from .schemas import (
    PostUploadResponse,
    PostResponse,
    PostStatusResponse,
    PostListResponse,
)
from .service import PostService, process_video_background

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_RAW_DIR = "uploads/raw"
UPLOAD_IMAGES_DIR = "uploads/images"
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10 MB
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def get_media_url(post) -> Optional[str]:
    """Public media URL for a post (video or image)."""
    if post.type == PostType.IMAGE:
        return post.media_url
    if post.status == PostStatus.READY and post.media_url:
        return post.media_url
    return None


def get_thumbnail_url(post) -> Optional[str]:
    """Thumbnail URL (video: thumbnail or media; image: media_url)."""
    if post.thumbnail_url:
        return post.thumbnail_url
    return get_media_url(post)


@router.post("/upload/video", response_model=PostUploadResponse)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    author_id: Optional[int] = Form(0),
    description: Optional[str] = Form(None),
    music_name: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a video file. Creates a post with type=VIDEO; processing runs in background.
    Supported: MP4, MOV, AVI, MKV, WEBM. Max 100 MB.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Supported: {', '.join(ALLOWED_VIDEO_EXTENSIONS)}",
        )

    content = await file.read()
    file_size = len(content)
    if file_size > MAX_VIDEO_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_VIDEO_SIZE // (1024 * 1024)} MB",
        )

    unique_filename = PostService.generate_unique_filename(file.filename, for_video=True)
    raw_file_path = os.path.join(UPLOAD_RAW_DIR, unique_filename)

    try:
        with open(raw_file_path, "wb") as f:
            f.write(content)
        logger.info(f"Saved raw video: {raw_file_path} ({file_size} bytes)")
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save video file")

    post = await PostService.create_video_post(
        db=db,
        author_id=author_id or 0,
        original_filename=file.filename,
        raw_file_path=raw_file_path,
        file_size=file_size,
        description=description,
        music_name=music_name,
    )
    background_tasks.add_task(process_video_background, post.id, raw_file_path)

    return PostUploadResponse(
        post_id=post.id,
        status=post.status,
        message="Video uploaded successfully. Processing started.",
    )


@router.post("/upload/image", response_model=PostUploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    author_id: Optional[int] = Form(0),
    description: Optional[str] = Form(None),
    music_name: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload an image. Creates a post with type=IMAGE, status=READY immediately.
    Supported: JPG, PNG, GIF, WEBP. Max 10 MB.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Supported: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}",
        )

    content = await file.read()
    file_size = len(content)
    if file_size > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_IMAGE_SIZE // (1024 * 1024)} MB",
        )

    unique_filename = PostService.generate_unique_filename(file.filename, for_video=False)
    image_path = os.path.join(UPLOAD_IMAGES_DIR, unique_filename)

    try:
        with open(image_path, "wb") as f:
            f.write(content)
        logger.info(f"Saved image: {image_path} ({file_size} bytes)")
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save image file")

    media_url = f"/uploads/images/{unique_filename}"
    post = await PostService.create_image_post(
        db=db,
        author_id=author_id or 0,
        media_url=media_url,
        description=description,
        music_name=music_name,
    )

    return PostUploadResponse(
        post_id=post.id,
        status=post.status,
        message="Image uploaded successfully.",
    )


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a single post by ID (response matches client Post)."""
    post = await PostService.get_post_by_id(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return PostResponse.from_post(post)


@router.get("/{post_id}/status", response_model=PostStatusResponse)
async def get_post_status(
    post_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Check processing status (for video posts)."""
    post = await PostService.get_post_by_id(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return PostStatusResponse(
        post_id=post.id,
        status=post.status,
        media_url=get_media_url(post),
        thumbnail_url=get_thumbnail_url(post),
        error_message=post.error_message,
    )


@router.get("", response_model=PostListResponse)
async def list_posts(
    page: int = 1,
    page_size: int = 20,
    type: Optional[PostType] = Query(None, alias="type"),
    status: Optional[PostStatus] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    List posts with pagination.
    type: VIDEO | IMAGE. status: PROCESSING | READY | FAILED (for videos).
    """
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100

    skip = (page - 1) * page_size
    posts, total = await PostService.get_posts(
        db=db,
        skip=skip,
        limit=page_size,
        post_type=type,
        status=status,
    )

    return PostListResponse(
        posts=[PostResponse.from_post(p) for p in posts],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete("/{post_id}")
async def delete_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a post and its files (raw/compressed video or image)."""
    post = await PostService.get_post_by_id(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if post.raw_file_path:
        PostService.delete_file(post.raw_file_path)
    if post.compressed_file_path:
        PostService.delete_file(post.compressed_file_path)
    # Xóa thumbnail (video) nếu có — thumbnail_url có dạng /uploads/thumbnails/xxx.jpg
    if post.thumbnail_url and post.thumbnail_url.startswith("/uploads/thumbnails/"):
        thumb_path = post.thumbnail_url.lstrip("/")
        if os.path.exists(thumb_path):
            PostService.delete_file(thumb_path)
    if post.type == PostType.IMAGE and post.media_url:
        # media_url is like /uploads/images/xxx.jpg -> path is uploads/images/xxx.jpg
        path = post.media_url.lstrip("/")
        if os.path.exists(path):
            PostService.delete_file(path)

    await db.delete(post)
    await db.commit()
    return {"message": f"Post {post_id} deleted successfully"}
