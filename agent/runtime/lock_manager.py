from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

try:
    import fcntl
except ImportError:  # pragma: no cover - unavailable on some platforms
    fcntl = None


class LockType(str, Enum):
    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class LockRequest:
    resource_id: str
    lock_type: LockType
    owner_id: str
    lease_sec: float = 30.0
    timeout_sec: float = 5.0


@dataclass
class LockLease:
    lease_id: str
    resource_id: str
    owner_id: str
    lock_type: LockType
    acquired_at: datetime
    expires_at: datetime

    @property
    def expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at


@dataclass
class LockTable:
    leases: dict[str, list[LockLease]] = field(default_factory=dict)


class LockAcquisitionError(RuntimeError):
    pass


class LockManager:
    """Provides shared-read/exclusive-write leases with ordered acquisition."""

    def __init__(self, state_path: Path | None = None) -> None:
        self._leases: dict[str, list[LockLease]] = {}
        self._condition = asyncio.Condition()
        self._counter = 0
        self.state_path = state_path
        if self.state_path:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self._reload_from_disk()

    async def acquire(self, request: LockRequest) -> LockLease:
        start = asyncio.get_running_loop().time()
        async with self._condition:
            while True:
                self._reload_from_disk()
                self._cleanup_expired_locked()
                resource_id = self._canonicalize(request.resource_id)
                existing = self._leases.get(resource_id, [])
                if self._can_grant(existing, request.lock_type, request.owner_id):
                    self._counter += 1
                    now = datetime.now(timezone.utc)
                    lease = LockLease(
                        lease_id=f"lease-{self._counter}",
                        resource_id=resource_id,
                        owner_id=request.owner_id,
                        lock_type=request.lock_type,
                        acquired_at=now,
                        expires_at=now + timedelta(seconds=request.lease_sec),
                    )
                    self._leases.setdefault(resource_id, []).append(lease)
                    self._persist_locked_state()
                    return lease

                elapsed = asyncio.get_running_loop().time() - start
                remaining = request.timeout_sec - elapsed
                if remaining <= 0:
                    raise LockAcquisitionError(
                        f"Timed out acquiring {request.lock_type.value} lock on {resource_id}"
                    )
                try:
                    await asyncio.wait_for(self._condition.wait(), timeout=remaining)
                except asyncio.TimeoutError as exc:
                    raise LockAcquisitionError(
                        f"Timed out acquiring {request.lock_type.value} lock on {resource_id}"
                    ) from exc

    async def acquire_many(self, requests: list[LockRequest]) -> list[LockLease]:
        ordered = sorted(requests, key=lambda item: self._canonicalize(item.resource_id))
        acquired: list[LockLease] = []
        try:
            for request in ordered:
                acquired.append(await self.acquire(request))
        except Exception:
            await self.release_many(acquired)
            raise
        return acquired

    async def release(self, lease: LockLease) -> None:
        async with self._condition:
            self._reload_from_disk()
            resource_id = self._canonicalize(lease.resource_id)
            remaining = [
                current
                for current in self._leases.get(resource_id, [])
                if current.lease_id != lease.lease_id
            ]
            if remaining:
                self._leases[resource_id] = remaining
            else:
                self._leases.pop(resource_id, None)
            self._persist_locked_state()
            self._condition.notify_all()

    async def release_many(self, leases: list[LockLease]) -> None:
        for lease in reversed(leases):
            await self.release(lease)

    async def release_owner(self, owner_id: str) -> None:
        async with self._condition:
            self._reload_from_disk()
            for resource_id in list(self._leases):
                remaining = [
                    lease
                    for lease in self._leases[resource_id]
                    if lease.owner_id != owner_id
                ]
                if remaining:
                    self._leases[resource_id] = remaining
                else:
                    self._leases.pop(resource_id, None)
            self._persist_locked_state()
            self._condition.notify_all()

    def snapshot(self) -> LockTable:
        self._reload_from_disk()
        self._cleanup_expired()
        self._persist_locked_state()
        return LockTable(leases={key: list(value) for key, value in self._leases.items()})

    def _cleanup_expired(self) -> None:
        for resource_id in list(self._leases):
            remaining = [lease for lease in self._leases[resource_id] if not lease.expired]
            if remaining:
                self._leases[resource_id] = remaining
            else:
                self._leases.pop(resource_id, None)

    def _cleanup_expired_locked(self) -> None:
        self._cleanup_expired()

    def _persist_locked_state(self) -> None:
        if not self.state_path:
            return
        payload = {
            "leases": {
                resource_id: [
                    {
                        "lease_id": lease.lease_id,
                        "resource_id": lease.resource_id,
                        "owner_id": lease.owner_id,
                        "lock_type": lease.lock_type.value,
                        "acquired_at": lease.acquired_at.isoformat(),
                        "expires_at": lease.expires_at.isoformat(),
                    }
                    for lease in leases
                ]
                for resource_id, leases in self._leases.items()
            }
        }
        with self._file_lock():
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(
                "w",
                delete=False,
                dir=self.state_path.parent,
                encoding="utf-8",
            ) as tmp:
                json.dump(payload, tmp, indent=2)
                tmp_path = Path(tmp.name)
            tmp_path.replace(self.state_path)

    def _reload_from_disk(self) -> None:
        if not self.state_path or not self.state_path.exists():
            return
        with self._file_lock():
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        leases: dict[str, list[LockLease]] = {}
        max_counter = self._counter
        for resource_id, rows in payload.get("leases", {}).items():
            parsed: list[LockLease] = []
            for row in rows:
                lease = LockLease(
                    lease_id=row["lease_id"],
                    resource_id=row["resource_id"],
                    owner_id=row["owner_id"],
                    lock_type=LockType(row["lock_type"]),
                    acquired_at=datetime.fromisoformat(row["acquired_at"]),
                    expires_at=datetime.fromisoformat(row["expires_at"]),
                )
                parsed.append(lease)
                if lease.lease_id.startswith("lease-"):
                    try:
                        max_counter = max(max_counter, int(lease.lease_id.split("-", 1)[1]))
                    except ValueError:
                        pass
            if parsed:
                leases[resource_id] = parsed
        self._leases = leases
        self._counter = max_counter

    def _file_lock(self):
        if not self.state_path:
            return _NoOpLock()
        return _FileLock(self.state_path.with_suffix(f"{self.state_path.suffix}.lck"))

    def _can_grant(
        self,
        existing: list[LockLease],
        requested_type: LockType,
        owner_id: str,
    ) -> bool:
        active = [lease for lease in existing if not lease.expired]
        if not active:
            return True
        if requested_type == LockType.READ:
            return all(lease.lock_type == LockType.READ or lease.owner_id == owner_id for lease in active)
        return all(lease.owner_id == owner_id for lease in active)

    def _canonicalize(self, resource_id: str) -> str:
        return Path(resource_id).as_posix()


class _NoOpLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FileLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a+", encoding="utf-8")
        if fcntl is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._handle and fcntl is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        if self._handle:
            self._handle.close()
