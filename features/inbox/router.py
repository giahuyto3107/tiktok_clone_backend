import logging
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


INBOX_IMAGE_DIR = "uploads/inbox/images"
INBOX_VIDEO_DIR = "uploads/inbox/videos"
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

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
    request: Request,
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
            image_uri=make_absolute_media_url(request, m.image_url),
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
    request: Request,
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
        image_uri=make_absolute_media_url(request, msg.image_url),
    )


@router.post(
    "/chats/{other_uid}/messages/upload",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message_with_media(
    other_uid: str,
    request: Request,
    file: UploadFile = File(...),
    type: MessageType = Form(MessageType.IMAGE),
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
    if uid == other_uid:
        raise HTTPException(status_code=400, detail="Cannot send message to yourself")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = os.path.splitext(file.filename)[1].lower()

    if type == MessageType.IMAGE:
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"File type not allowed for IMAGE. "
                    f"Supported: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}"
                ),
            )
        content_bytes = await file.read()
        file_size = len(content_bytes)
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
    elif type == MessageType.VIDEO:
        if ext not in ALLOWED_VIDEO_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"File type not allowed for VIDEO. "
                    f"Supported: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}"
                ),
            )
        content_bytes = await file.read()
        file_size = len(content_bytes)
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
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported type for file upload. Use IMAGE or VIDEO.",
        )

    try:
        with open(disk_path, "wb") as f:
            f.write(content_bytes)
        logger.info("Saved inbox media file: %s (%d bytes)", disk_path, file_size)
    except Exception as exc:
        logger.error("Failed to save inbox media file: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to save media file")

    # Đường dẫn public tương đối (được phục vụ bởi StaticFiles ở `/uploads`)
    relative_url = None
    if type == MessageType.IMAGE:
        relative_url = f"/uploads/inbox/images/{unique_name}"
    elif type == MessageType.VIDEO:
        relative_url = f"/uploads/inbox/videos/{unique_name}"

    chat = await InboxService.get_or_create_chat(db, uid, other_uid)

    msg = await InboxService.create_message(
        db=db,
        chat_id=chat.id,
        sender_id=uid,
        content=content,
        image_url=relative_url,
        type_=type,
    )

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
        image_uri=make_absolute_media_url(request, msg.image_url),
    )

