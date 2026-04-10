from pydantic import BaseModel, Field


class PostLikeResponse(BaseModel):
    """Result for like/unlike on a post."""

    post_id: int = Field(..., serialization_alias="postId")
    is_liked: bool = Field(..., serialization_alias="isLiked")


class PostSaveResponse(BaseModel):
    """Result for save/unsave on a post."""

    post_id: int = Field(..., serialization_alias="postId")
    is_saved: bool = Field(..., serialization_alias="isSaved")


class PostSocialState(BaseModel):
    """Full social state for a single post and current user."""

    post_id: int = Field(..., serialization_alias="postId")
    like_count: int = Field(..., serialization_alias="likeCount")
    comment_count: int = Field(..., serialization_alias="commentCount")
    share_count: int = Field(..., serialization_alias="shareCount")
    save_count: int = Field(..., serialization_alias="saveCount")
    is_liked: bool = Field(..., serialization_alias="isLiked")
    is_saved: bool = Field(..., serialization_alias="isSaved")
    is_shared: bool = Field(..., serialization_alias="isShared")

