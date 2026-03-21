from datetime import datetime
import enum

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.time_utils import now_utc
from database import Base


class FollowNotificationReceiptStatus(str, enum.Enum):
    DELIVERED = "DELIVERED"
    SEEN = "SEEN"


class FollowNotification(Base):
    """Event: user A followed user B."""

    __tablename__ = "follow_notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    follower_id: Mapped[str] = mapped_column(String(255), nullable=False)
    followee_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )


class FollowNotificationReceipt(Base):
    """Per-user receipt status for follow notifications."""

    __tablename__ = "follow_notification_receipts"

    notification_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    status: Mapped[FollowNotificationReceiptStatus] = mapped_column(
        Text,
        nullable=False,
        default=FollowNotificationReceiptStatus.DELIVERED.value,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        nullable=False,
    )

