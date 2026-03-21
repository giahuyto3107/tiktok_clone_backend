import asyncio
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect


class WSManager:
    """
    Simple in-memory WebSocket group manager.

    Group keys:
    - chats: int chat_id
    - posts: int post_id

    Note: in-memory means it only works for a single backend process.
    """

    def __init__(self) -> None:
        self._chat_connections: dict[int, set[WebSocket]] = {}
        self._post_connections: dict[int, set[WebSocket]] = {}
        self._user_connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect_chat(self, chat_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._chat_connections.setdefault(chat_id, set()).add(ws)

    async def disconnect_chat(self, chat_id: int, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._chat_connections.get(chat_id)
            if not conns:
                return
            conns.discard(ws)
            if not conns:
                self._chat_connections.pop(chat_id, None)

    async def connect_post(self, post_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._post_connections.setdefault(post_id, set()).add(ws)

    async def disconnect_post(self, post_id: int, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._post_connections.get(post_id)
            if not conns:
                return
            conns.discard(ws)
            if not conns:
                self._post_connections.pop(post_id, None)

    async def broadcast_chat(self, chat_id: int, payload: dict[str, Any]) -> None:
        async with self._lock:
            conns = list(self._chat_connections.get(chat_id, set()))

        for ws in conns:
            try:
                await ws.send_json(payload)
            except WebSocketDisconnect:
                # ignore, cleanup happens when disconnect handler runs
                pass
            except Exception:
                # Best-effort: if send fails, drop connection
                try:
                    await ws.close()
                except Exception:
                    pass

    async def broadcast_post(self, post_id: int, payload: dict[str, Any]) -> None:
        async with self._lock:
            conns = list(self._post_connections.get(post_id, set()))

        for ws in conns:
            try:
                await ws.send_json(payload)
            except WebSocketDisconnect:
                pass
            except Exception:
                try:
                    await ws.close()
                except Exception:
                    pass

    async def connect_user(self, user_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._user_connections.setdefault(user_id, set()).add(ws)

    async def disconnect_user(self, user_id: str, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._user_connections.get(user_id)
            if not conns:
                return
            conns.discard(ws)
            if not conns:
                self._user_connections.pop(user_id, None)

    async def broadcast_user(self, user_id: str, payload: dict[str, Any]) -> None:
        async with self._lock:
            conns = list(self._user_connections.get(user_id, set()))

        for ws in conns:
            try:
                await ws.send_json(payload)
            except WebSocketDisconnect:
                pass
            except Exception:
                try:
                    await ws.close()
                except Exception:
                    pass


ws_manager = WSManager()

