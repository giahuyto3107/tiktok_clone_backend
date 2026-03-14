from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CommentCreate(BaseModel):
    """Request body when creating a new comment or reply."""

    content: str
    parent_id: Optional[int] = Field(default=None, alias="parentId")


class CommentResponse(BaseModel):
    """Comment response aligned với Android `Comment` data class.

    Client hiện dùng:
      id: String
      postId: String
      userId: String
      ...
    """

    id: str
    post_id: str = Field(..., serialization_alias="postId")
    user_id: str = Field(..., serialization_alias="userId")

    content: str

    like_count: int = Field(0, serialization_alias="likeCount")
    is_liked: bool = Field(False, serialization_alias="isLiked")
    parent_id: Optional[str] = Field(default=None, serialization_alias="parentId")
    reply_count: int = Field(0, serialization_alias="replyCount")
    created_at: int = Field(..., serialization_alias="createdAt")  # milliseconds

    model_config = ConfigDict(from_attributes=True)


class CommentListResponse(BaseModel):
    """List of comments for a post."""

    comments: list[CommentResponse]
    """total: int"""

