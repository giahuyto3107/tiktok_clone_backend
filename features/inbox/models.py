from datetime import datetime
import enum

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class MessageType(str, enum.Enum):
    """Match frontend MessageType: TEXT, IMAGE, VIDEO."""

    TEXT = "TEXT"
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"


class MessageStatus(str, enum.Enum):
    """Server-side lifecycle of a message row itself.

    - NEW:   server vừa tạo, chưa chắc gửi ra client khác.
    - SENT:  server đã chấp nhận, có thể phân phối cho các client.

    Trạng thái theo từng người nhận (DELIVERED/SEEN) được tách sang MessageReceipt.
    """

    NEW = "NEW"
    SENT = "SENT"


class Chat(Base):
    """1–1 chat thread between two users."""

    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    user1_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user2_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # optional last message pointer for fast inbox previews
    last_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class Message(Base):
    """Single message within a chat (aligned with frontend `Message` model)."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sender_id: Mapped[str] = mapped_column(String(255), nullable=False)

    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    type: Mapped[MessageType] = mapped_column(
        default=MessageType.TEXT,
        nullable=False,
    )
    status: Mapped[MessageStatus] = mapped_column(
        default=MessageStatus.NEW,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class ReceiptStatus(str, enum.Enum):
    """Per-user message status inside a chat (DELIVERED / SEEN)."""

    DELIVERED = "DELIVERED"
    SEEN = "SEEN"


class MessageReceipt(Base):
    """Per-user status của một message (ai đã nhận / ai đã seen)."""

    __tablename__ = "message_receipts"

    message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    status: Mapped[ReceiptStatus] = mapped_column(
        default=ReceiptStatus.DELIVERED,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class ChatParticipant(Base):
    """Thông tin mỗi user trong một chat (để tính unread, last seen)."""

    __tablename__ = "chat_participants"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), primary_key=True)

    last_read_message_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

