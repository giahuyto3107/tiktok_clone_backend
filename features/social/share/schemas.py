from pydantic import BaseModel, Field


class PostShareResponse(BaseModel):
    """Result after share / unshare a post."""

    post_id: int = Field(..., serialization_alias="postId")
    share_count: int = Field(..., serialization_alias="shareCount")
    is_share: bool = Field(..., serialization_alias="isShare")

