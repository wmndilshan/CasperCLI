from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum


class LockType(str, Enum):
    READ = "read"
    WRITE = "write"


@dataclass
class LockLease:
    lease_id: str
    path: str
    agent_id: str
    lock_type: LockType
    acquired_at: datetime
    expires_at: datetime

    @property
    def expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at


class LockAcquisitionError(RuntimeError):
    pass


class FileLockManager:
    """Per-file reader/writer locks with optional lease timeout."""

    def __init__(self, default_lease_sec: float = 120.0) -> None:
        self._leases: dict[str, list[LockLease]] = {}
        self._condition = asyncio.Condition()
        self._default_lease_sec = default_lease_sec

    def _canonical(self, path: str) -> str:
        return path.replace("\\", "/").strip()

    def _cleanup_expired(self) -> None:
        now = datetime.now(timezone.utc)
        for resource, leases in list(self._leases.items()):
            kept = [lease for lease in leases if lease.expires_at > now]
            if kept:
                self._leases[resource] = kept
            else:
                del self._leases[resource]

    def _can_grant(self, existing: list[LockLease], lock_type: LockType) -> bool:
        writers = [lease for lease in existing if lease.lock_type == LockType.WRITE]
        readers = [lease for lease in existing if lease.lock_type == LockType.READ]
        if lock_type == LockType.WRITE:
            return not writers and not readers
        # READ: allow multiple readers, block if any writer
        return not writers

    async def acquire(
        self,
        path: str,
        agent_id: str,
        lock_type: LockType,
        *,
        lease_sec: float | None = None,
        timeout_sec: float = 30.0,
    ) -> LockLease:
        resource = self._canonical(path)
        lease_duration = lease_sec if lease_sec is not None else self._default_lease_sec
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_sec

        async with self._condition:
            while True:
                self._cleanup_expired()
                bucket = self._leases.get(resource, [])
                if self._can_grant(bucket, lock_type):
                    now = datetime.now(timezone.utc)
                    lease = LockLease(
                        lease_id=str(uuid.uuid4()),
                        path=resource,
                        agent_id=agent_id,
                        lock_type=lock_type,
                        acquired_at=now,
                        expires_at=now + timedelta(seconds=lease_duration),
                    )
                    self._leases.setdefault(resource, []).append(lease)
                    return lease

                wait_for = deadline - loop.time()
                if wait_for <= 0:
                    raise LockAcquisitionError(
                        f"Timeout acquiring {lock_type.value} lock on {resource}"
                    )
                try:
                    await asyncio.wait_for(self._condition.wait(), timeout=wait_for)
                except asyncio.TimeoutError as exc:
                    raise LockAcquisitionError(
                        f"Timeout acquiring {lock_type.value} lock on {resource}"
                    ) from exc

    async def release(self, lease: LockLease) -> None:
        async with self._condition:
            resource = self._canonical(lease.path)
            if resource not in self._leases:
                return
            self._leases[resource] = [
                item for item in self._leases[resource] if item.lease_id != lease.lease_id
            ]
            if not self._leases[resource]:
                del self._leases[resource]
            self._condition.notify_all()

    def snapshot(self) -> list[dict[str, object]]:
        self._cleanup_expired()
        rows: list[dict[str, object]] = []
        for leases in self._leases.values():
            for lease in leases:
                rows.append(
                    {
                        "path": lease.path,
                        "agent_id": lease.agent_id,
                        "lock_type": lease.lock_type.value,
                        "lease_id": lease.lease_id,
                        "expires_at": lease.expires_at.isoformat(),
                    }
                )
        return rows
