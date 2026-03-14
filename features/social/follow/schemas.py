from pydantic import BaseModel, Field

from features.post.schemas import PostAuthor


class SocialCounts(BaseModel):
    """Follower / following counts for a user."""

    user_id: str = Field(..., serialization_alias="userId")
    follower_count: int = Field(..., serialization_alias="followerCount")
    following_count: int = Field(..., serialization_alias="followingCount")


class FollowActionResponse(BaseModel):
    """Response after follow / unfollow."""

    follower_id: str = Field(..., serialization_alias="followerId")
    followee_id: str = Field(..., serialization_alias="followeeId")
    is_following: bool = Field(..., serialization_alias="isFollowing")


class SocialUser(BaseModel):
    """User info + social state (for follower/following list)."""

    profile: PostAuthor
    is_following: bool = Field(..., serialization_alias="isFollowing")


class SocialUserListResponse(BaseModel):
    users: list[SocialUser]
    total: int

