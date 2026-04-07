from typing import Iterable, Tuple

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.time_utils import now_utc
from .models import (
    Chat,
    ChatParticipant,
    Message,
    MessageReceipt,
    MessageStatus,
    MessageType,
    ReceiptStatus,
)


class InboxService:
    """Service helpers cho inbox 1–1 chat."""

    @staticmethod
    async def get_or_create_chat(
        db: AsyncSession,
        user_a: str,
        user_b: str,
    ) -> Chat:
        """Lấy chat 1–1 giữa 2 user, nếu chưa có thì tạo mới."""
        if user_a == user_b:
            raise ValueError("Cannot create chat with yourself")

        stmt = select(Chat).where(
            or_(
                and_(Chat.user1_id == user_a, Chat.user2_id == user_b),
                and_(Chat.user1_id == user_b, Chat.user2_id == user_a),
            )
        )
        res = await db.execute(stmt)
        chat = res.scalar_one_or_none()
        if not chat:
            chat = Chat(user1_id=user_a, user2_id=user_b)
            db.add(chat)
            await db.commit()
            await db.refresh(chat)

        # Ensure chat participants exist for both users
        participants_needed = {chat.user1_id, chat.user2_id}
        participants_stmt = select(ChatParticipant.user_id).where(
            ChatParticipant.chat_id == chat.id,
            ChatParticipant.user_id.in_(participants_needed),
        )
        participants_res = await db.execute(participants_stmt)
        existing_user_ids = {row[0] for row in participants_res.all()}

        missing_user_ids = participants_needed - existing_user_ids
        for missing_uid in missing_user_ids:
            db.add(ChatParticipant(chat_id=chat.id, user_id=missing_uid))
        if missing_user_ids:
            await db.commit()

        return chat

    @staticmethod
    async def create_message(
        db: AsyncSession,
        chat_id: int,
        sender_id: str,
        content: str | None,
        image_url: str | None,
        type_: MessageType,
    ) -> Message:
        """Tạo message mới, default status = NEW."""
        msg = Message(
            chat_id=chat_id,
            sender_id=sender_id,
            content=content,
            image_url=image_url,
            type=type_,
            status=MessageStatus.NEW,
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)

        # Update last_message_id trên Chat + create per-user receipts
        chat = await db.get(Chat, chat_id)
        if chat:
            chat.last_message_id = msg.id
            chat.updated_at = now_utc()
            await db.commit()

            # Mark sender as SEEN (since they just sent),
            # recipient as DELIVERED.
            recipient_id = chat.user2_id if chat.user1_id == sender_id else chat.user1_id
            if recipient_id:
                db.add(
                    MessageReceipt(
                        message_id=msg.id,
                        user_id=sender_id,
                        status=ReceiptStatus.SEEN,
                    )
                )
                db.add(
                    MessageReceipt(
                        message_id=msg.id,
                        user_id=recipient_id,
                        status=ReceiptStatus.DELIVERED,
                    )
                )
                await db.commit()

        return msg

    @staticmethod
    async def list_chats_for_user(
        db: AsyncSession,
        uid: str,
        limit: int,
        offset: int,
    ) -> Iterable[Chat]:
        stmt = (
            select(Chat)
            .where(or_(Chat.user1_id == uid, Chat.user2_id == uid))
            .order_by(Chat.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    @staticmethod
    async def list_messages_for_chat(
        db: AsyncSession,
        chat_id: int,
        limit: int,
        offset: int,
    ) -> Tuple[list[Message], int]:
        count_stmt = select(func.count(Message.id)).where(Message.chat_id == chat_id)
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        res = await db.execute(stmt)
        msgs = res.scalars().all()
        return list(msgs), total

