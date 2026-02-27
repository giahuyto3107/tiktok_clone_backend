# features/post/service.py - Post service (video + image)
import os
import subprocess
import uuid
import logging
import shutil
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from .models import Post, PostType, PostStatus

logger = logging.getLogger(__name__)

# Find FFmpeg/FFprobe executables - use full path on Windows to avoid PATH issues
FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE_PATH = shutil.which("ffprobe") or "ffprobe"
logger.info(f"FFmpeg path: {FFMPEG_PATH}")
logger.info(f"FFprobe path: {FFPROBE_PATH}")

# Directories
UPLOAD_RAW_DIR = os.path.abspath("uploads/raw")
UPLOAD_COMPRESSED_DIR = os.path.abspath("uploads/compressed")
UPLOAD_IMAGES_DIR = os.path.abspath("uploads/images")
UPLOAD_THUMBNAILS_DIR = os.path.abspath("uploads/thumbnails")

# Video
FFMPEG_PRESET = "fast"
FFMPEG_CRF = "28"
FFMPEG_RESOLUTION = "720"
# Thumbnail: frame at this time (seconds); fallback to first frame if video shorter
THUMBNAIL_SEEK_SECONDS = 1

# Image extensions (no processing)
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


class PostService:
    """Service for post operations (video and image)."""

    @staticmethod
    async def create_video_post(
        db: AsyncSession,
        user_id: str,
        original_filename: str,
        raw_file_path: str,
        file_size: int,
        caption: str | None = None,
        music_name: str | None = None,
    ) -> Post:
        """Create a new post with type=VIDEO and status=PROCESSING."""
        # Normalize path to fix Windows backslash issues
        logger.info(f"Original raw_file_path: {repr(raw_file_path)}")
        normalized_path = os.path.normpath(raw_file_path)
        logger.info(f"Normalized path: {repr(normalized_path)}")
        post = Post(
            user_id=user_id,
            type=PostType.VIDEO,
            caption=caption or "",
            music_name=music_name or "Original Sound",
            original_filename=original_filename,
            raw_file_path=normalized_path,
            file_size=file_size,
            status=PostStatus.PROCESSING,
        )
        db.add(post)
        await db.commit()
        await db.refresh(post)
        logger.info(f"Created video post id={post.id}, filename={original_filename}, path={normalized_path}")
        return post

    @staticmethod
    async def create_image_post(
        db: AsyncSession,
        user_id: str,
        media_url: str,
        caption: str | None = None,
        music_name: str | None = None,
    ) -> Post:
        """Create a new post with type=IMAGE, status=READY, media_url set."""
        post = Post(
            user_id=user_id,
            type=PostType.IMAGE,
            media_url=media_url,
            thumbnail_url=media_url,  # image: use same as media
            caption=caption or "",
            music_name=music_name or "Original Sound",
            status=PostStatus.READY,
        )
        db.add(post)
        await db.commit()
        await db.refresh(post)
        logger.info(f"Created image post id={post.id}")
        return post

    @staticmethod
    async def get_post_by_id(db: AsyncSession, post_id: int) -> Post | None:
        """Get post by ID."""
        result = await db.execute(select(Post).where(Post.id == post_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_posts(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        post_type: PostType | None = None,
        status: PostStatus | None = None,
    ) -> tuple[list[Post], int]:
        """Get posts with pagination. Optional filter by type and status."""
        query = select(Post)
        if post_type is not None:
            query = query.where(Post.type == post_type)
        if status is not None:
            query = query.where(Post.status == status)

        count_query = select(func.count(Post.id))
        if post_type is not None:
            count_query = count_query.where(Post.type == post_type)
        if status is not None:
            count_query = count_query.where(Post.status == status)
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        query = query.order_by(Post.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        posts = result.scalars().all()
        return list(posts), total

    @staticmethod
    async def update_post_status(
        db: AsyncSession,
        post_id: int,
        status: PostStatus,
        media_url: str | None = None,
        thumbnail_url: str | None = None,
        compressed_file_path: str | None = None,
        compressed_size: int | None = None,
        duration: int | None = None,
        error_message: str | None = None,
    ) -> Post | None:
        """Update post status after video processing."""
        post = await PostService.get_post_by_id(db, post_id)
        if not post:
            return None

        post.status = status
        if media_url is not None:
            post.media_url = media_url
        if thumbnail_url is not None:
            post.thumbnail_url = thumbnail_url
        if compressed_file_path is not None:
            post.compressed_file_path = compressed_file_path
        if compressed_size is not None:
            post.compressed_size = compressed_size
        if duration is not None:
            post.duration = duration
        if error_message is not None:
            post.error_message = error_message

        await db.commit()
        await db.refresh(post)
        logger.info(f"Updated post {post_id} status to {status}")
        return post

    @staticmethod
    def generate_unique_filename(original_filename: str, for_video: bool = True) -> str:
        """Generate a unique filename using UUID."""
        ext = Path(original_filename).suffix.lower()
        if for_video:
            if ext not in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
                ext = ".mp4"
        else:
            if ext not in ALLOWED_IMAGE_EXTENSIONS:
                ext = ".jpg"
        return f"{uuid.uuid4().hex}{ext}"

    @staticmethod
    def get_video_duration(file_path: str) -> int | None:
        """Get video duration in seconds using FFprobe."""
        try:
            logger.info(f"Getting video duration for: {file_path}")
            if not os.path.exists(file_path):
                logger.error(f"Video file does not exist: {file_path}")
                return None
                
            cmd = [
                FFPROBE_PATH,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                duration_str = result.stdout.strip()
                if duration_str:
                    duration = int(float(duration_str))
                    logger.info(f"Video duration: {duration} seconds")
                    return duration
                else:
                    logger.error("FFprobe returned empty duration")
                    return None
            else:
                logger.error(f"FFprobe failed with return code {result.returncode}: {result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            logger.error("FFprobe timeout while getting video duration")
            return None
        except Exception as e:
            logger.error(f"Failed to get video duration: {e}")
            return None

    @staticmethod
    def compress_video_sync(
        input_path: str,
        output_path: str,
        max_height: int = 720,
        crf: str = "28",
        preset: str = "fast",
    ) -> bool:
        """Compress video with FFmpeg. Returns True on success."""
        try:
            cmd = [
                FFMPEG_PATH,
                "-y",
                "-i", input_path,
                "-vf", f"scale=-2:{max_height}",
                "-c:v", "libx264",
                "-crf", crf,
                "-preset", preset,
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                output_path,
            ]
            logger.info(f"Starting video compression: {input_path} -> {output_path}")
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600
            )
            if result.returncode == 0:
                logger.info(f"Video compression completed: {output_path}")
                return True
            logger.error(f"FFmpeg error: {result.stderr}")
            return False
        except subprocess.TimeoutExpired:
            logger.error("Video compression timed out")
            return False
        except Exception as e:
            logger.error(f"Video compression failed: {e}")
            return False

    @staticmethod
    def extract_thumbnail_sync(
        video_path: str,
        output_path: str,
        seek_seconds: int = 1,
    ) -> bool:
        """
        Chuẩn hóa hậu kỳ: trích xuất ảnh bìa (thumbnail) từ video bằng FFmpeg.
        Lấy frame tại seek_seconds; nếu video ngắn hơn thì lấy frame đầu.
        """
        try:
            # -ss trước -i: fast seek (không decode toàn bộ). -vframes 1: 1 frame. -q:v 2: chất lượng JPEG.
            cmd = [
                FFMPEG_PATH,
                "-y",
                "-ss", str(seek_seconds),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                "-f", "image2",
                output_path,
            ]
            logger.info(f"Extracting thumbnail: {video_path} -> {output_path}")
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"Thumbnail extracted: {output_path}")
                return True
            # Fallback: lấy frame tại 0 (đầu video) nếu seek vượt duration
            cmd_fallback = [
                FFMPEG_PATH,
                "-y",
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "2",
                "-f", "image2",
                output_path,
            ]
            result = subprocess.run(
                cmd_fallback, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"Thumbnail extracted (first frame): {output_path}")
                return True
            logger.error(f"FFmpeg thumbnail error: {result.stderr}")
            return False
        except subprocess.TimeoutExpired:
            logger.error("Thumbnail extraction timed out")
            return False
        except Exception as e:
            logger.error(f"Thumbnail extraction failed: {e}")
            return False

    @staticmethod
    def delete_file(file_path: str) -> bool:
        """Delete a file safely."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
        return False


async def process_video_background(post_id: int, raw_file_path: str):
    """
    Background task (Bước 6–8):
    - Nén video 720p, Fast Start (metadata lên đầu file).
    - Chuẩn hóa hậu kỳ: trích ảnh bìa (thumbnail) bằng FFmpeg.
    - Cập nhật DB: status READY, media_url, thumbnail_url.
    """
    from database import async_session_maker

    logger.info(f"Starting background processing for post (video) {post_id}")
    
    # Convert to absolute path to avoid working directory issues
    if not os.path.isabs(raw_file_path):
        raw_file_path = os.path.abspath(raw_file_path)
    
    logger.info(f"Raw file path (absolute): {raw_file_path}")
    
    # Check if file exists before processing
    if not os.path.exists(raw_file_path):
        logger.error(f"Raw video file not found: {raw_file_path}")
        async with async_session_maker() as db:
            await PostService.update_post_status(
                db=db,
                post_id=post_id,
                status=PostStatus.FAILED,
                error_message="Source video file not found",
            )
        return

    output_filename = f"{uuid.uuid4().hex}.mp4"
    output_path = os.path.join(UPLOAD_COMPRESSED_DIR, output_filename)
    duration = PostService.get_video_duration(raw_file_path)

    # Bước 6–7: Nén + Fast Start (movflags +faststart đã có trong compress_video_sync)
    success = PostService.compress_video_sync(
        input_path=raw_file_path,
        output_path=output_path,
        max_height=int(FFMPEG_RESOLUTION),
        crf=FFMPEG_CRF,
        preset=FFMPEG_PRESET,
    )

    thumbnail_url: str | None = None

    if success:
        # Bước 7: Chuẩn hóa hậu kỳ — trích ảnh bìa từ video đã nén
        thumb_filename = f"{uuid.uuid4().hex}.jpg"
        thumbnail_path = os.path.join(UPLOAD_THUMBNAILS_DIR, thumb_filename)
        if PostService.extract_thumbnail_sync(
            output_path,
            thumbnail_path,
            seek_seconds=THUMBNAIL_SEEK_SECONDS,
        ):
            thumbnail_url = f"/uploads/thumbnails/{thumb_filename}"
        else:
            thumbnail_url = f"/uploads/compressed/{output_filename}"

    async with async_session_maker() as db:
        if success:
            compressed_size = os.path.getsize(output_path) if os.path.exists(output_path) else None
            media_url = f"/uploads/compressed/{os.path.basename(output_path)}"
            await PostService.update_post_status(
                db=db,
                post_id=post_id,
                status=PostStatus.READY,
                media_url=media_url,
                thumbnail_url=thumbnail_url or media_url,
                compressed_file_path=output_path,
                compressed_size=compressed_size,
                duration=duration,
            )
            PostService.delete_file(raw_file_path)
            logger.info(f"Post {post_id} (video) processing completed — media + thumbnail ready")
        else:
            await PostService.update_post_status(
                db=db,
                post_id=post_id,
                status=PostStatus.FAILED,
                error_message="FFmpeg compression failed",
            )
            logger.error(f"Post {post_id} (video) processing failed")
