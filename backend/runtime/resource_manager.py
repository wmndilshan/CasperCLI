"""Tracks exclusive logical resources (e.g. merge slots) separate from file locks."""

from __future__ import annotations

import asyncio
from typing import Any


class ResourceManager:
    """
    Exclusive resource claims per agent. Used for slots like package_manager, merge_slot.
    File-level I/O remains in FileLockManager.
    """

    def __init__(self) -> None:
        self._claims: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def claim(self, resource_id: str, agent_id: str) -> bool:
        """Return True if this agent now owns the resource; False if held by another."""
        async with self._lock:
            owner = self._claims.get(resource_id)
            if owner == agent_id:
                return True
            if owner is not None:
                return False
            self._claims[resource_id] = agent_id
            return True

    async def release(self, resource_id: str, agent_id: str) -> None:
        async with self._lock:
            if self._claims.get(resource_id) == agent_id:
                del self._claims[resource_id]

    def snapshot(self) -> list[dict[str, Any]]:
        return [{"resource": r, "agent_id": a} for r, a in sorted(self._claims.items())]
