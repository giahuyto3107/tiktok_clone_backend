from pydantic import BaseModel, ConfigDict, Field

from .models import MessageReceipt, MessageStatus, MessageType, ReceiptStatus


class MessageCreate(BaseModel):
    """Body khi gửi tin nhắn mới."""

    content: str | None = None
    image_uri: str | None = Field(default=None, alias="imageUri")
    type: MessageType = MessageType.TEXT


class MessageResponse(BaseModel):
    """Align với `Message.kt` bên Android."""

    id: int
    content: str | None = None
    sender_id: str = Field(..., serialization_alias="senderId")
    timestamp: int = Field(..., serialization_alias="timestamp")
    type: MessageType
    status: MessageStatus
    image_uri: str | None = Field(default=None, serialization_alias="imageUri")
    receipt_status: ReceiptStatus | None = Field(
        default=None,
        serialization_alias="receiptStatus",
    )

    model_config = ConfigDict(from_attributes=True)


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]
    total: int


class ChatSummary(BaseModel):
    """Item cho list inbox (đơn giản: 1–1 chat)."""

    chat_id: int = Field(..., serialization_alias="chatId")
    other_user_id: str = Field(..., serialization_alias="otherUserId")
    last_message: MessageResponse | None = Field(
        default=None,
        serialization_alias="lastMessage",
    )
    unread_count: int = Field(0, serialization_alias="unreadCount")


class ChatListResponse(BaseModel):
    chats: list[ChatSummary]
    total: int

