from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog

from models.schemas import EventType, WSEnvelope

logger = structlog.get_logger(__name__)

Subscriber = Callable[[WSEnvelope], Awaitable[None]]


class EventBus:
    """In-process pub/sub for orchestration; fans out to WebSocket clients."""

    def __init__(self) -> None:
        self._subs: list[Subscriber] = []
        self._lock = asyncio.Lock()

    async def subscribe(self, handler: Subscriber) -> None:
        async with self._lock:
            self._subs.append(handler)

    async def unsubscribe(self, handler: Subscriber) -> None:
        async with self._lock:
            self._subs = [sub for sub in self._subs if sub is not handler]

    async def publish(
        self,
        session_id: str,
        event_type: EventType,
        payload: dict[str, Any] | None = None,
    ) -> WSEnvelope:
        envelope = WSEnvelope(
            type=event_type,
            session_id=session_id,
            payload=payload or {},
            ts=datetime.now(timezone.utc).isoformat(),
        )
        logger.debug("event", type=event_type.value, session_id=session_id)
        async with self._lock:
            handlers = list(self._subs)
        await asyncio.gather(
            *[self._safe_dispatch(handler, envelope) for handler in handlers],
            return_exceptions=True,
        )
        return envelope

    async def _safe_dispatch(self, handler: Subscriber, envelope: WSEnvelope) -> None:
        try:
            await handler(envelope)
        except Exception:  # pragma: no cover - defensive
            logger.exception("subscriber_failed", handler=str(handler))


def new_session_id() -> str:
    return f"sess_{uuid4().hex[:12]}"
