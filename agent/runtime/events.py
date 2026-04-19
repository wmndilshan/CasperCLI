from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class RuntimeEventType(str, Enum):
    TEAM_SYNTHESIZED = "team_synthesized"
    TASK_GRAPH_CREATED = "task_graph_created"
    TASK_READY = "task_ready"
    TASK_STARTED = "task_started"
    TASK_BLOCKED = "task_blocked"
    TASK_COMPLETED = "task_completed"
    TASK_INVALIDATED = "task_invalidated"
    LOCK_ACQUIRED = "lock_acquired"
    LOCK_DENIED = "lock_denied"
    LOCK_RELEASED = "lock_released"
    PATCH_PROPOSED = "patch_proposed"
    PATCH_VALIDATED = "patch_validated"
    PATCH_REJECTED = "patch_rejected"
    CONFLICT_DETECTED = "conflict_detected"
    MERGE_COMPLETED = "merge_completed"
    RESOURCE_DENIED = "resource_denied"
    VERIFICATION_STARTED = "verification_started"
    VERIFICATION_FAILED = "verification_failed"
    COMMIT_APPLIED = "commit_applied"


@dataclass(slots=True)
class RuntimeEvent:
    type: RuntimeEventType
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RuntimeEventBus:
    """A tiny in-process event bus suitable for tests and the CLI runtime."""

    def __init__(self) -> None:
        self._events: list[RuntimeEvent] = []
        self._subscribers: list[Callable[[RuntimeEvent], None]] = []

    @property
    def events(self) -> list[RuntimeEvent]:
        return list(self._events)

    def subscribe(self, callback: Callable[[RuntimeEvent], None]) -> None:
        self._subscribers.append(callback)

    def emit(self, event_type: RuntimeEventType, **payload: Any) -> RuntimeEvent:
        event = RuntimeEvent(type=event_type, payload=payload)
        self._events.append(event)
        for subscriber in self._subscribers:
            subscriber(event)
        return event

    def of_type(self, event_type: RuntimeEventType) -> list[RuntimeEvent]:
        return [event for event in self._events if event.type == event_type]
