import logging

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from firebase_admin import auth as firebase_auth
from sqlalchemy.ext.asyncio import AsyncSession
from database import async_session_maker

from core.realtime.ws_manager import ws_manager
from features.inbox.models import Chat


logger = logging.getLogger(__name__)

router = APIRouter()


def _extract_bearer_token(headers: dict[str, str], token_query: str | None) -> str:
    auth_header = headers.get("authorization") or headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ").strip()
    if token_query:
        return token_query.strip()
    raise HTTPException(status_code=401, detail="Missing Firebase ID token")


async def _get_current_uid_from_ws(ws: WebSocket, token_query: str | None) -> str:
    token = _extract_bearer_token(ws.headers, token_query)
    try:
        decoded = firebase_auth.verify_id_token(token)
        return decoded["uid"]
    except Exception as e:
        logger.warning("WS auth failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid Firebase ID token")


@router.websocket("/api/v1/ws/inbox/chats/{chat_id}")
async def inbox_chat_ws(
    websocket: WebSocket,
    chat_id: int,
    token: str | None = Query(default=None, description="Firebase ID token (optional; use Authorization header if possible)"),
):
    """
    WS for realtime messages in a specific chat.
    Client must be an authenticated participant of that chat.
    """
    await websocket.accept()
    try:
        uid = await _get_current_uid_from_ws(websocket, token)
        async with async_session_maker() as db:  # type: AsyncSession
            chat = await db.get(Chat, chat_id)
        if not chat or uid not in {chat.user1_id, chat.user2_id}:
            await websocket.close(code=4403)
            return

        await ws_manager.connect_chat(chat_id, websocket)
        try:
            while True:
                # Keep the socket alive; ignore client messages for now.
                await websocket.receive_text()
        except WebSocketDisconnect:
            return
    except HTTPException as e:
        await websocket.close(code=4401)
        logger.info("WS closed: %s", e.detail)
    finally:
        # Ensure we disconnect from group (safe even if not connected yet)
        try:
            await ws_manager.disconnect_chat(chat_id, websocket)
        except Exception:
            pass


@router.websocket("/api/v1/ws/social/posts/{post_id}")
async def social_post_ws(
    websocket: WebSocket,
    post_id: int,
    token: str | None = Query(default=None, description="Firebase ID token (optional; use Authorization header if possible)"),
):
    """
    WS for realtime social updates on a post (like/save/share/comment).
    Any authenticated user can subscribe; FE should refetch state on events.
    """
    await websocket.accept()
    try:
        _uid = await _get_current_uid_from_ws(websocket, token)
        await ws_manager.connect_post(post_id, websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            return
    except HTTPException:
        await websocket.close(code=4401)
    finally:
        try:
            await ws_manager.disconnect_post(post_id, websocket)
        except Exception:
            pass


@router.websocket("/api/v1/ws/social/users/{uid}")
async def social_user_ws(
    websocket: WebSocket,
    uid: str,
    token: str | None = Query(default=None, description="Firebase ID token (optional; use Authorization header if possible)"),
):
    """
    WS để realtime follow/unfollow ảnh hưởng tới user `uid`.
    Backend sẽ broadcast event theo uid này.
    """
    await websocket.accept()
    try:
        await _get_current_uid_from_ws(websocket, token)  # validate token
        await ws_manager.connect_user(uid, websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            return
    except HTTPException:
        await websocket.close(code=4401)
    finally:
        try:
            await ws_manager.disconnect_user(uid, websocket)
        except Exception:
            pass

