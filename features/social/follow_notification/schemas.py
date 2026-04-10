from pydantic import BaseModel, Field, ConfigDict

from .models import FollowNotificationReceiptStatus


class FollowNotificationResponse(BaseModel):
    id: int = Field(..., serialization_alias="id")
    follower_id: str = Field(..., serialization_alias="followerId")
    created_at: int = Field(..., serialization_alias="createdAt")  # ms
    receipt_status: FollowNotificationReceiptStatus = Field(
        ..., serialization_alias="receiptStatus"
    )

    model_config = ConfigDict(from_attributes=True)


class FollowNotificationListResponse(BaseModel):
    notifications: list[FollowNotificationResponse]
    total: int


class FollowNotificationUnreadCountResponse(BaseModel):
    unreadCount: int


class FollowNotificationSeenAllResponse(BaseModel):
    ok: bool = True
    unreadCount: int = Field(..., serialization_alias="unreadCount")


class FollowNotificationLatestResponse(BaseModel):
    notification: FollowNotificationResponse | None

