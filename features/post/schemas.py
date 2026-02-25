# features/post/schemas.py - Pydantic Schemas for Post (aligned with client)
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from .models import PostType, PostStatus


# --- Request schemas ---
class PostCreate(BaseModel):
    """Schema for creating a post (form data)"""
    title: Optional[str] = None
    description: Optional[str] = None
    user_id: Optional[str] = Field(None, alias="userId")


# --- Response schemas (camelCase for client) ---
class PostResponse(BaseModel):
    """Post response matching client Post data class"""
    id: int
    user_id: str = Field(..., serialization_alias="userId")
    type: PostType
    media_url: str = Field("", serialization_alias="mediaUrl")
    thumbnail_url: str = Field("", serialization_alias="thumbnailUrl")
    description: str = ""
    music_name: str = Field("Original Sound", serialization_alias="musicName")
    like_count: int = Field(0, serialization_alias="likeCount")
    comment_count: int = Field(0, serialization_alias="commentCount")
    created_at: int = Field(..., serialization_alias="createdAt")  # milliseconds

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_post(cls, post) -> "PostResponse":
        """Build response from ORM with created_at as milliseconds."""
        return cls(
            id=post.id,
            user_id=post.user_id,
            type=post.type,
            media_url=post.media_url or "",
            thumbnail_url=post.thumbnail_url or "",
            description=post.description or "",
            music_name=post.music_name or "Original Sound",
            like_count=post.like_count or 0,
            comment_count=post.comment_count or 0,
            created_at=int(post.created_at.timestamp() * 1000) if post.created_at else 0,
        )


class PostUploadResponse(BaseModel):
    """Response after uploading a post (video or image)"""
    post_id: int = Field(..., serialization_alias="postId")
    status: PostStatus
    message: str

    model_config = ConfigDict(from_attributes=True)


class PostStatusResponse(BaseModel):
    """Response for post processing status (video)"""
    post_id: int = Field(..., serialization_alias="postId")
    status: PostStatus
    media_url: Optional[str] = Field(None, serialization_alias="mediaUrl")
    thumbnail_url: Optional[str] = Field(None, serialization_alias="thumbnailUrl")
    error_message: Optional[str] = Field(None, serialization_alias="errorMessage")

    model_config = ConfigDict(from_attributes=True)


class PostListResponse(BaseModel):
    """Paginated list of posts"""
    posts: list[PostResponse]
    total: int
    page: int
    page_size: int = Field(..., serialization_alias="pageSize")

    model_config = ConfigDict()
