from pydantic import BaseModel, Field


class SearchVideoItem(BaseModel):
    id: int
    thumbnail: str
    title: str
    author: str
    likes: int = 0


class SearchUserItem(BaseModel):
    uid: str
    username: str = ""
    avatar: str = ""


class SearchProductItem(BaseModel):
    id: int
    name: str
    image: str
    price: float = 0.0


class SearchResponse(BaseModel):
    videos: list[SearchVideoItem] = Field(default_factory=list)
    users: list[SearchUserItem] = Field(default_factory=list)
    products: list[SearchProductItem] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    lives: list[str] = Field(default_factory=list)
