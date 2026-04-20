from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import websockets

JsonDict = dict[str, Any]
EventHandler = Callable[[JsonDict], Awaitable[None]]


class TuiWsClient:
    def __init__(self, url: str, token: str = "") -> None:
        self.url = url
        self.token = token
        self._socket: websockets.WebSocketClientProtocol | None = None

    async def connect(self) -> None:
        headers: list[tuple[str, str]] = []
        if self.token:
            headers.append(("X-MetaAgent-Token", self.token))
        self._socket = await websockets.connect(self.url, additional_headers=headers)

    async def close(self) -> None:
        if self._socket is not None:
            await self._socket.close()
            self._socket = None

    async def send(self, payload: JsonDict) -> None:
        if self._socket is None:
            raise RuntimeError("WebSocket is not connected.")
        await self._socket.send(json.dumps(payload, ensure_ascii=False))

    async def receive_loop(self, on_event: EventHandler) -> None:
        if self._socket is None:
            raise RuntimeError("WebSocket is not connected.")
        async for raw in self._socket:
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict):
                await on_event(message)
            await asyncio.sleep(0)
