import logging
import mimetypes
import os
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import case, func, select, update
from firebase_admin import auth as firebase_auth

from core.auth import get_current_user
from core.realtime.ws_manager import ws_manager
from core.time_utils import to_epoch_ms_utc
from database import get_db
from .models import (
    Chat,
    ChatParticipant,
    Message,
    MessageReceipt,
    MessageStatus,
    MessageType,
    ReceiptStatus,
)
from .schemas import (
    ChatListResponse,
    ChatSummary,
    InboxContactListResponse,
    InboxContactResponse,
    MessageCreate,
    MessageListResponse,
    MessageResponse,
)
from .service import InboxService

logger = logging.getLogger(__name__)

router = APIRouter()


INBOX_IMAGE_DIR = "uploads/inbox/images"
INBOX_VIDEO_DIR = "uploads/inbox/videos"
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
IMAGE_CONTENT_TYPE_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}
VIDEO_CONTENT_TYPE_TO_EXT = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "video/x-matroska": ".mkv",
    "video/webm": ".webm",
}

os.makedirs(INBOX_IMAGE_DIR, exist_ok=True)
os.makedirs(INBOX_VIDEO_DIR, exist_ok=True)


def make_absolute_media_url(request: Request, relative_path: str | None) -> str | None:
    """
    Convert a stored relative media path (starting with /uploads/...)
    to an absolute URL based on the incoming request.
    """
    if not relative_path:
        return None
    # Nếu FE đã lưu absolute URL (bắt đầu bằng http) thì trả nguyên
    if relative_path.startswith("http://") or relative_path.startswith("https://"):
        return relative_path
    base = str(request.base_url).rstrip("/")
    return f"{base}{relative_path}"


def _to_message_response(
    request: Request,
    message: Message,
    receipt_status: ReceiptStatus | None = None,
) -> MessageResponse:
    """Serialize Message ORM -> API response with absolute media URL."""
    return MessageResponse(
        id=message.id,
        content=message.content,
        sender_id=message.sender_id,
        timestamp=to_epoch_ms_utc(message.created_at),
        type=message.type,
        status=message.status,
        image_uri=make_absolute_media_url(request, message.image_url),
        receipt_status=receipt_status,
    )


def _ensure_not_self_chat(uid: str, other_uid: str) -> None:
    if uid == other_uid:
        raise HTTPException(status_code=400, detail="Cannot send message to yourself")


def _ensure_chat_participant(chat: Chat | None, uid: str) -> None:
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if uid not in {chat.user1_id, chat.user2_id}:
        raise HTTPException(status_code=403, detail="Not a participant of this chat")


def _resolve_profile(uid: str) -> InboxContactResponse | None:
    """Resolve username/avatar from Firebase Auth."""
    try:
        user = firebase_auth.get_user(uid)
        display_name = user.display_name
        photo_url = user.photo_url
        if (not display_name or not photo_url) and user.provider_data:
            for provider in user.provider_data:
                if not display_name and getattr(provider, "display_name", None):
                    display_name = provider.display_name
                if not photo_url and getattr(provider, "photo_url", None):
                    photo_url = provider.photo_url
                if display_name and photo_url:
                    break
        return InboxContactResponse(
            uid=user.uid,
            username=display_name or None,
            avatar_url=photo_url or None,
        )
    except Exception:
        return None


def _relative_media_url(media_type: MessageType, unique_name: str) -> str:
    if media_type == MessageType.IMAGE:
        return f"/uploads/inbox/images/{unique_name}"
    return f"/uploads/inbox/videos/{unique_name}"


def _normalize_upload_type(type_value: str | None) -> MessageType | None:
    """
    Normalize upload type from form data.
    Accepts IMAGE/VIDEO (case-insensitive). Returns None if missing.
    """
    if type_value is None:
        return None
    normalized = type_value.strip().upper()
    if not normalized:
        return None
    try:
        parsed = MessageType(normalized)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid type. Use IMAGE or VIDEO for upload endpoint.",
        )
    if parsed not in {MessageType.IMAGE, MessageType.VIDEO}:
        raise HTTPException(
            status_code=400,
            detail="Unsupported type for file upload. Use IMAGE or VIDEO.",
        )
    return parsed


def _infer_media_type(ext: str, content_type: str) -> MessageType | None:
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return MessageType.IMAGE
    if ext in ALLOWED_VIDEO_EXTENSIONS:
        return MessageType.VIDEO
    if content_type.startswith("image/"):
        return MessageType.IMAGE
    if content_type.startswith("video/"):
        return MessageType.VIDEO
    return None


def _ensure_extension(ext: str, content_type: str, media_type: MessageType) -> str:
    if ext:
        return ext
    if media_type == MessageType.IMAGE:
        return IMAGE_CONTENT_TYPE_TO_EXT.get(
            content_type,
            mimetypes.guess_extension(content_type) or ".jpg",
        )
    return VIDEO_CONTENT_TYPE_TO_EXT.get(
        content_type,
        mimetypes.guess_extension(content_type) or ".mp4",
    )


@router.get("/chats", response_model=ChatListResponse)
async def list_chats(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Danh sách chat 1–1 cho user hiện tại (dùng cho màn inbox)."""
    uid = current_user["uid"]
    chats = await InboxService.list_chats_for_user(db, uid, limit=limit, offset=offset)

    summaries: list[ChatSummary] = []
    chat_ids = [c.id for c in chats]

    # unreadCount per chat from message_receipts (DELIVERED but not SEEN)
    unread_stmt = (
        select(Message.chat_id, func.count(MessageReceipt.message_id))
        .join(Message, Message.id == MessageReceipt.message_id)
        .where(
            Message.chat_id.in_(chat_ids),
            MessageReceipt.user_id == uid,
            MessageReceipt.status == ReceiptStatus.DELIVERED,
        )
        .group_by(Message.chat_id)
    )
    unread_res = await db.execute(unread_stmt)
    unread_map: dict[int, int] = {row[0]: row[1] for row in unread_res.all()}

    for chat in chats:
        other = chat.user2_id if chat.user1_id == uid else chat.user1_id

        last_msg: Optional[MessageResponse] = None
        if chat.last_message_id:
            msg = await db.get(Message, chat.last_message_id)
            if msg:
                # Hiển thị receiptStatus theo logic:
                # - Nếu current user là sender => hiển thị receipt của recipient (other)
                # - Nếu current user là recipient => hiển thị receipt của current user
                receipt_user_id = other if msg.sender_id == uid else uid
                receipt_stmt = (
                    select(MessageReceipt.status)
                    .where(
                        MessageReceipt.user_id == receipt_user_id,
                        MessageReceipt.message_id == msg.id,
                    )
                    .limit(1)
                )
                receipt_row = await db.execute(receipt_stmt)
                receipt_status = receipt_row.scalar_one_or_none()
                last_msg = _to_message_response(
                    request,
                    msg,
                    receipt_status=receipt_status,
                )

        summaries.append(
            ChatSummary(
                chat_id=chat.id,
                other_user_id=other,
                last_message=last_msg,
                unread_count=unread_map.get(chat.id, 0),
            )
        )

    return ChatListResponse(chats=summaries, total=len(summaries))


@router.get("/contacts", response_model=InboxContactListResponse)
async def list_inbox_contacts(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Trả về danh sách user đã từng nhắn tin (có ít nhất 1 message) với current user.
    """
    uid = current_user["uid"]

    other_uid_expr = case(
        (Chat.user1_id == uid, Chat.user2_id),
        else_=Chat.user1_id,
    )

    base = (
        select(
            other_uid_expr.label("other_uid"),
            func.max(Chat.updated_at).label("last_updated_at"),
        )
        .where((Chat.user1_id == uid) | (Chat.user2_id == uid))
        .where(Chat.last_message_id.is_not(None))
        .group_by(other_uid_expr)
    )

    total_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(total_stmt)).scalar_one()

    stmt = (
        base.order_by(func.max(Chat.updated_at).desc())
        .offset(offset)
        .limit(limit)
    )
    res = await db.execute(stmt)
    other_uids = [row[0] for row in res.all() if row[0]]

    users: list[InboxContactResponse] = []
    for other_uid in other_uids:
        profile = _resolve_profile(other_uid)
        if profile:
            users.append(profile)

    return InboxContactListResponse(users=users, total=int(total))


@router.get("/chats/{chat_id}/messages", response_model=MessageListResponse)
async def list_messages(
    chat_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Danh sách message trong 1 chat."""
    uid = current_user["uid"]
    chat = await db.get(Chat, chat_id)
    _ensure_chat_participant(chat, uid)

    msgs, total = await InboxService.list_messages_for_chat(
        db,
        chat_id=chat_id,
        limit=limit,
        offset=offset,
    )

    items = [_to_message_response(request, m) for m in msgs]

    # Mark receipts as SEEN for current user for messages returned,
    # and update last_read_message_id for chat_participants.
    if msgs:
        ids = [m.id for m in msgs]
        other_uid = chat.user2_id if chat.user1_id == uid else chat.user1_id

        # Update receipts
        await db.execute(
            update(MessageReceipt)
            .where(
                MessageReceipt.user_id == uid,
                MessageReceipt.message_id.in_(ids),
            )
            .values(status=ReceiptStatus.SEEN)
        )
        # Update last read message pointer
        await db.execute(
            update(ChatParticipant)
            .where(ChatParticipant.chat_id == chat_id, ChatParticipant.user_id == uid)
            .values(last_read_message_id=max(ids))
        )
        await db.commit()

        # Build receiptStatus per message (trả đúng label cho sender/recipient):
        # - Nếu message.sender_id == current user => trả receipt của recipient (other)
        # - Ngược lại => trả receipt của current user
        receipts_stmt = (
            select(
                MessageReceipt.message_id,
                MessageReceipt.user_id,
                MessageReceipt.status,
            )
            .where(
                MessageReceipt.message_id.in_(ids),
                MessageReceipt.user_id.in_({uid, other_uid}),
            )
        )
        receipts_res = await db.execute(receipts_stmt)
        receipt_map: dict[tuple[int, str], ReceiptStatus] = {
            (row[0], row[1]): row[2] for row in receipts_res.all()
        }

        rebuilt: list[MessageResponse] = []
        for m in msgs:
            receipt_user_id = other_uid if m.sender_id == uid else uid
            rebuilt.append(
                _to_message_response(
                    request,
                    m,
                    receipt_status=receipt_map.get((m.id, receipt_user_id)),
                )
            )
        items = rebuilt
    return MessageListResponse(messages=items, total=total)


@router.post(
    "/chats/{other_uid}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    other_uid: str,
    payload: MessageCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Gửi message mới tới một user khác (tự tạo chat nếu chưa có)."""
    uid = current_user["uid"]
    _ensure_not_self_chat(uid, other_uid)

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

    # Hiển thị receiptStatus theo logic label:
    # - Nam gửi message => hiển thị receipt của recipient (other_uid)
    receipt_stmt = (
        select(MessageReceipt.status)
        .where(
            MessageReceipt.user_id == other_uid,
            MessageReceipt.message_id == msg.id,
        )
        .limit(1)
    )
    receipt_row = await db.execute(receipt_stmt)
    recipient_receipt_status = receipt_row.scalar_one_or_none()
    message_resp = _to_message_response(
        request,
        msg,
        receipt_status=recipient_receipt_status,
    )
    await ws_manager.broadcast_chat(
        chat.id,
        {
            "event": "message_created",
            "chatId": chat.id,
            "message": message_resp.model_dump(by_alias=True, mode="json"),
        },
    )
    # user-level WS: chỉ đẩy event cho FE refresh chat list.
    # Strict contract: user-level emits `inbox_message_created` (not `message_created`).
    await ws_manager.broadcast_user(
        uid,
        {
            "event": "inbox_message_created",
            "data": {
                "chatId": chat.id,
                "otherUserId": other_uid,
                "messageId": msg.id,
            },
        },
    )
    await ws_manager.broadcast_user(
        other_uid,
        {
            "event": "inbox_message_created",
            "data": {
                "chatId": chat.id,
                "otherUserId": uid,
                "messageId": msg.id,
            },
        },
    )
    return message_resp


@router.post(
    "/chats/{other_uid}/messages/upload",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message_with_media(
    other_uid: str,
    request: Request,
    file: UploadFile = File(...),
    type: str | None = Form(None),
    content: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Gửi message có kèm media (ảnh / video).

    - Lưu file vào `uploads/inbox/images` hoặc `uploads/inbox/videos`.
    - Tạo message với `imageUri` trỏ tới đường dẫn `/uploads/...`.
    """
    uid = current_user["uid"]
    _ensure_not_self_chat(uid, other_uid)

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    raw_content_type = (file.content_type or "").lower()
    ext = os.path.splitext(file.filename)[1].lower()

    declared_type = _normalize_upload_type(type)
    inferred_type = _infer_media_type(ext, raw_content_type)
    if declared_type and inferred_type and declared_type != inferred_type:
        raise HTTPException(
            status_code=400,
            detail=(
                "Mismatched media type and file. "
                "Please ensure `type` matches the uploaded file."
            ),
        )

    media_type = declared_type or inferred_type
    if media_type is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot determine media type. "
                "Provide `type` as IMAGE/VIDEO or use a supported file extension."
            ),
        )

    ext = _ensure_extension(ext, raw_content_type, media_type)
    try:
        content_bytes = await file.read()
        file_size = len(content_bytes)

        if media_type == MessageType.IMAGE:
            if ext not in ALLOWED_IMAGE_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"File type not allowed for IMAGE. "
                        f"Supported: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}"
                    ),
                )
            if file_size > MAX_IMAGE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"File too large. Maximum size for image: "
                        f"{MAX_IMAGE_SIZE // (1024 * 1024)} MB"
                    ),
                )
            unique_name = f"{uid}_msg_{os.urandom(8).hex()}{ext}"
            disk_path = os.path.normpath(os.path.join(INBOX_IMAGE_DIR, unique_name))
        else:
            if ext not in ALLOWED_VIDEO_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"File type not allowed for VIDEO. "
                        f"Supported: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}"
                    ),
                )
            if file_size > MAX_VIDEO_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"File too large. Maximum size for video: "
                        f"{MAX_VIDEO_SIZE // (1024 * 1024)} MB"
                    ),
                )
            unique_name = f"{uid}_msg_{os.urandom(8).hex()}{ext}"
            disk_path = os.path.normpath(os.path.join(INBOX_VIDEO_DIR, unique_name))

        with open(disk_path, "wb") as f:
            f.write(content_bytes)
        logger.info("Saved inbox media file: %s (%d bytes)", disk_path, file_size)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to save inbox media file: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save media file")

    # Đường dẫn public tương đối (được phục vụ bởi StaticFiles ở `/uploads`)
    relative_url = _relative_media_url(media_type, unique_name)

    chat = await InboxService.get_or_create_chat(db, uid, other_uid)

    msg = await InboxService.create_message(
        db=db,
        chat_id=chat.id,
        sender_id=uid,
        content=content,
        image_url=relative_url,
        type_=media_type,
    )

    msg.status = MessageStatus.SENT
    await db.commit()
    await db.refresh(msg)

    # Hiển thị receiptStatus theo logic label:
    # - message do sender (current user) tạo => hiển thị receipt của recipient (other_uid)
    receipt_stmt = (
        select(MessageReceipt.status)
        .where(
            MessageReceipt.user_id == other_uid,
            MessageReceipt.message_id == msg.id,
        )
        .limit(1)
    )
    receipt_row = await db.execute(receipt_stmt)
    recipient_receipt_status = receipt_row.scalar_one_or_none()
    message_resp = _to_message_response(
        request,
        msg,
        receipt_status=recipient_receipt_status,
    )
    await ws_manager.broadcast_chat(
        chat.id,
        {
            "event": "message_created",
            "chatId": chat.id,
            "message": message_resp.model_dump(by_alias=True, mode="json"),
        },
    )
    await ws_manager.broadcast_user(
        uid,
        {
            "event": "inbox_message_created",
            "data": {
                "chatId": chat.id,
                "otherUserId": other_uid,
                "messageId": msg.id,
            },
        },
    )
    await ws_manager.broadcast_user(
        other_uid,
        {
            "event": "inbox_message_created",
            "data": {
                "chatId": chat.id,
                "otherUserId": uid,
                "messageId": msg.id,
            },
        },
    )
    return message_resp

