from pydantic import BaseModel, Field, ConfigDict


class FrontendVideoResult(BaseModel):
    """
    Matches Android `VideoResult`:
    - authorAvatar (camelCase)
    - createdAt (ms)
    - durationSeconds
    """

    model_config = ConfigDict(populate_by_name=True)

    id: int = 0
    thumbnail: str = ""
    title: str = ""
    author: str = ""
    likes: int = 0
    author_avatar: str = Field(default="", alias="authorAvatar")
    created_at: int | None = Field(default=None, alias="createdAt")
    duration_seconds: int = Field(default=0, alias="durationSeconds")


class FrontendUserItem(BaseModel):
    """Matches Android `UserItem` (camelCase fields)."""

    model_config = ConfigDict(populate_by_name=True)

    id: int = 0
    display_name: str = Field(default="", alias="displayName")
    handle: str = ""
    avatar: str = ""
    follower_count: int = Field(default=0, alias="followerCount")
    total_likes: int = Field(default=0, alias="totalLikes")
    is_followed: bool = Field(default=False, alias="isFollowed")


class FrontendProductItem(BaseModel):
    id: int = 0
    name: str = ""
    image: str = ""
    price: float = 0.0


class FrontendSearchResponse(BaseModel):
    videos: list[FrontendVideoResult] | None = None
    users: list[FrontendUserItem] | None = None
    products: list[FrontendProductItem] | None = None
    images: list[str] | None = None
    lives: list[str] | None = None


class DiscoverItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    keyword: str = ""
    hot: bool = False
    preview_thumb: str | None = Field(default=None, alias="previewThumb")


class DiscoverResponse(BaseModel):
    items: list[DiscoverItem] = Field(default_factory=list)

