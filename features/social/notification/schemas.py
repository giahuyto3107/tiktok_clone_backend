from pydantic import BaseModel, ConfigDict, Field

from .models import NotificationActionType, NotificationReceiptStatus


class NotificationResponse(BaseModel):
    """Align với list notification trên FE."""

    id: int
    from_user_id: str = Field(..., serialization_alias="fromUserId")
    post_id: int = Field(..., serialization_alias="postId")
    action_type: NotificationActionType = Field(
        ..., serialization_alias="actionType"
    )
    comment_id: int | None = Field(default=None, serialization_alias="commentId")
    created_at: int = Field(..., serialization_alias="createdAt")  # ms

    receipt_status: NotificationReceiptStatus = Field(
        ..., serialization_alias="receiptStatus"
    )

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    total: int


class MarkReceiptSeenResponse(BaseModel):
    ok: bool = True


class UnreadCountResponse(BaseModel):
    unreadCount: int = Field(..., serialization_alias="unreadCount")


class LatestNotificationResponse(BaseModel):
    notification: NotificationResponse | None

