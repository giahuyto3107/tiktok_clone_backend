import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from database import get_db
from .models import Chat, Message, MessageStatus, MessageType
from .schemas import (
    ChatListResponse,
    ChatSummary,
    MessageCreate,
    MessageListResponse,
    MessageResponse,
)
from .service import InboxService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/chats", response_model=ChatListResponse)
async def list_chats(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Danh sách chat 1–1 cho user hiện tại (dùng cho màn inbox)."""
    uid = current_user["uid"]
    chats = await InboxService.list_chats_for_user(db, uid, limit=limit, offset=offset)

    summaries: list[ChatSummary] = []
    for chat in chats:
        other = chat.user2_id if chat.user1_id == uid else chat.user1_id

        last_msg: Optional[MessageResponse] = None
        if chat.last_message_id:
            msg = await db.get(Message, chat.last_message_id)
            if msg:
                last_msg = MessageResponse(
                    id=msg.id,
                    content=msg.content,
                    sender_id=msg.sender_id,
                    timestamp=int(msg.created_at.timestamp() * 1000),
                    type=msg.type,
                    status=msg.status,
                    image_uri=msg.image_url,
                )

        summaries.append(
            ChatSummary(
                chat_id=chat.id,
                other_user_id=other,
                last_message=last_msg,
                unread_count=0,  # TODO: tính bằng ChatParticipant nếu cần
            )
        )

    return ChatListResponse(chats=summaries, total=len(summaries))


@router.get("/chats/{chat_id}/messages", response_model=MessageListResponse)
async def list_messages(
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Danh sách message trong 1 chat."""
    uid = current_user["uid"]
    chat = await db.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if uid not in {chat.user1_id, chat.user2_id}:
        raise HTTPException(status_code=403, detail="Not a participant of this chat")

    msgs, total = await InboxService.list_messages_for_chat(
        db,
        chat_id=chat_id,
        limit=limit,
        offset=offset,
    )

    items = [
        MessageResponse(
            id=m.id,
            content=m.content,
            sender_id=m.sender_id,
            timestamp=int(m.created_at.timestamp() * 1000),
            type=m.type,
            status=m.status,
            image_uri=m.image_url,
        )
        for m in msgs
    ]
    return MessageListResponse(messages=items, total=total)


@router.post(
    "/chats/{other_uid}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    other_uid: str,
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Gửi message mới tới một user khác (tự tạo chat nếu chưa có)."""
    uid = current_user["uid"]
    if uid == other_uid:
        raise HTTPException(status_code=400, detail="Cannot send message to yourself")

    chat = await InboxService.get_or_create_chat(db, uid, other_uid)

    msg = await InboxService.create_message(
        db=db,
        chat_id=chat.id,
        sender_id=uid,
        content=payload.content,
        image_url=payload.image_uri,
        type_=payload.type,
    )

    # Tin vừa gửi coi như đã SENT luôn (server xác nhận)
    msg.status = MessageStatus.SENT
    await db.commit()
    await db.refresh(msg)

    return MessageResponse(
        id=msg.id,
        content=msg.content,
        sender_id=msg.sender_id,
        timestamp=int(msg.created_at.timestamp() * 1000),
        type=msg.type,
        status=msg.status,
        image_uri=msg.image_url,
    )

