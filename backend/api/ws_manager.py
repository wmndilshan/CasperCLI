from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket
import structlog

from models.schemas import WSEnvelope

logger = structlog.get_logger(__name__)


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)

    async def broadcast_json(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._connections)
        dead: list[WebSocket] = []
        for connection in targets:
            try:
                await connection.send_text(json.dumps(payload))
            except Exception:
                dead.append(connection)
        for connection in dead:
            await self.disconnect(connection)

    async def handle_bus_event(self, envelope: WSEnvelope) -> None:
        await self.broadcast_json(envelope.model_dump(mode="json"))
