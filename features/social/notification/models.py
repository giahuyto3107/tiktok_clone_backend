import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from core.time_utils import now_utc
from database import Base


class NotificationActionType(str, enum.Enum):
    LIKE = "LIKE"
    COMMENT = "COMMENT"
    SHARE = "SHARE"
    SAVE = "SAVE"
    REPOST = "REPOST"
    COMMENT_LIKE = "COMMENT_LIKE"
    COMMENT_REPLY = "COMMENT_REPLY"


class NotificationReceiptStatus(str, enum.Enum):
    DELIVERED = "DELIVERED"
    SEEN = "SEEN"


class SocialNotification(Base):
    """Notification created when another user interacts with your post.

    This table stores the interaction event.
    Per-user delivery/seen state lives in SocialNotificationReceipt.
    """

    __tablename__ = "social_notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    from_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    post_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Store as text to avoid DB enum migration issues.
    action_type: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional metadata depending on action type.
    comment_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )


class SocialNotificationReceipt(Base):
    """Per-recipient status (DELIVERED/SEEN)."""

    __tablename__ = "social_notification_receipts"

    notification_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        String(255), primary_key=True
    )

    status: Mapped[NotificationReceiptStatus] = mapped_column(
        SAEnum(NotificationReceiptStatus),
        nullable=False,
        default=NotificationReceiptStatus.DELIVERED,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )

