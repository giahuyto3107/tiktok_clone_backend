# features/video/service.py - Video Processing Service with FFmpeg
import os
import subprocess
import uuid
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .models import Video, VideoStatus

logger = logging.getLogger(__name__)

# Configuration
UPLOAD_RAW_DIR = "uploads/raw"
UPLOAD_COMPRESSED_DIR = "uploads/compressed"

# FFmpeg compression settings
FFMPEG_PRESET = "fast"  # Options: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
FFMPEG_CRF = "28"  # Quality: 0-51, lower = better quality, 28 is good for mobile
FFMPEG_RESOLUTION = "720"  # Max height in pixels


class VideoService:
    """Service class for video operations"""

    @staticmethod
    async def create_video_record(
        db: AsyncSession,
        original_filename: str,
        raw_file_path: str,
        file_size: int,
        title: str | None = None,
        description: str | None = None,
    ) -> Video:
        """Create a new video record in database with PROCESSING status"""
        video = Video(
            title=title,
            description=description,
            original_filename=original_filename,
            raw_file_path=raw_file_path,
            file_size=file_size,
            status=VideoStatus.PROCESSING,
        )
        db.add(video)
        await db.commit()
        await db.refresh(video)
        logger.info(f"Created video record: id={video.id}, filename={original_filename}")
        return video

    @staticmethod
    async def get_video_by_id(db: AsyncSession, video_id: int) -> Video | None:
        """Get video by ID"""
        result = await db.execute(select(Video).where(Video.id == video_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all_videos(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        status: VideoStatus | None = None,
    ) -> tuple[list[Video], int]:
        """Get all videos with pagination"""
        query = select(Video)
        if status:
            query = query.where(Video.status == status)
        
        # Count total
        from sqlalchemy import func
        count_query = select(func.count(Video.id))
        if status:
            count_query = count_query.where(Video.status == status)
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # Get paginated results
        query = query.order_by(Video.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        videos = result.scalars().all()
        
        return list(videos), total

    @staticmethod
    async def update_video_status(
        db: AsyncSession,
        video_id: int,
        status: VideoStatus,
        compressed_file_path: str | None = None,
        compressed_size: int | None = None,
        duration: int | None = None,
        error_message: str | None = None,
    ) -> Video | None:
        """Update video status after processing"""
        video = await VideoService.get_video_by_id(db, video_id)
        if not video:
            return None

        video.status = status
        video.updated_at = datetime.utcnow()

        if compressed_file_path:
            video.compressed_file_path = compressed_file_path
        if compressed_size:
            video.compressed_size = compressed_size
        if duration:
            video.duration = duration
        if error_message:
            video.error_message = error_message

        await db.commit()
        await db.refresh(video)
        logger.info(f"Updated video {video_id} status to {status}")
        return video

    @staticmethod
    def generate_unique_filename(original_filename: str) -> str:
        """Generate a unique filename using UUID"""
        ext = Path(original_filename).suffix.lower()
        if ext not in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
            ext = ".mp4"
        return f"{uuid.uuid4().hex}{ext}"

    @staticmethod
    def get_video_duration(file_path: str) -> int | None:
        """Get video duration using FFprobe"""
        try:
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                duration = float(result.stdout.strip())
                return int(duration)
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
        """
        Compress video using FFmpeg (synchronous).
        
        This function runs FFmpeg as a subprocess to compress the video.
        - Scales video to max_height while maintaining aspect ratio
        - Uses H.264 codec for broad compatibility
        - Uses AAC audio codec
        
        Args:
            input_path: Path to input video file
            output_path: Path for compressed output file
            max_height: Maximum height in pixels (default: 720)
            crf: Constant Rate Factor for quality (0-51, lower=better, default: 28)
            preset: FFmpeg preset for encoding speed (default: fast)
        
        Returns:
            True if compression succeeded, False otherwise
        """
        try:
            # FFmpeg command for compression
            # -y: Overwrite output file if exists
            # -i: Input file
            # -vf: Video filter for scaling (maintain aspect ratio, max height)
            # -c:v libx264: Use H.264 video codec
            # -crf: Quality (0-51, lower is better)
            # -preset: Encoding speed/compression ratio tradeoff
            # -c:a aac: Use AAC audio codec
            # -b:a 128k: Audio bitrate
            # -movflags +faststart: Enable fast start for streaming
            cmd = [
                "ffmpeg",
                "-y",
                "-i", input_path,
                "-vf", f"scale=-2:{max_height}",
                "-c:v", "libx264",
                "-crf", crf,
                "-preset", preset,
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                output_path
            ]

            logger.info(f"Starting video compression: {input_path} -> {output_path}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )

            if result.returncode == 0:
                logger.info(f"Video compression completed: {output_path}")
                return True
            else:
                logger.error(f"FFmpeg error: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Video compression timed out")
            return False
        except Exception as e:
            logger.error(f"Video compression failed: {e}")
            return False

    @staticmethod
    def delete_file(file_path: str) -> bool:
        """Delete a file safely"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
        return False


async def process_video_background(video_id: int, raw_file_path: str):
    """
    Background task to process video.
    
    This function is called by BackgroundTasks and runs after the response is sent.
    It compresses the video using FFmpeg and updates the database status.
    
    Args:
        video_id: ID of the video record in database
        raw_file_path: Path to the raw uploaded file
    """
    from database import async_session_maker
    
    logger.info(f"Starting background processing for video {video_id}")
    
    # Generate output path
    output_filename = f"{uuid.uuid4().hex}.mp4"
    output_path = os.path.join(UPLOAD_COMPRESSED_DIR, output_filename)
    
    # Get video duration before compression
    duration = VideoService.get_video_duration(raw_file_path)
    
    # Run FFmpeg compression
    success = VideoService.compress_video_sync(
        input_path=raw_file_path,
        output_path=output_path,
        max_height=int(FFMPEG_RESOLUTION),
        crf=FFMPEG_CRF,
        preset=FFMPEG_PRESET,
    )
    
    async with async_session_maker() as db:
        if success:
            # Get compressed file size
            compressed_size = os.path.getsize(output_path) if os.path.exists(output_path) else None
            
            # Update database with READY status
            await VideoService.update_video_status(
                db=db,
                video_id=video_id,
                status=VideoStatus.READY,
                compressed_file_path=output_path,
                compressed_size=compressed_size,
                duration=duration,
            )
            
            # Delete raw file to save storage
            VideoService.delete_file(raw_file_path)
            
            logger.info(f"Video {video_id} processing completed successfully")
        else:
            # Update database with FAILED status
            await VideoService.update_video_status(
                db=db,
                video_id=video_id,
                status=VideoStatus.FAILED,
                error_message="FFmpeg compression failed",
            )
            logger.error(f"Video {video_id} processing failed")
