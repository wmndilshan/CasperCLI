from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from agent.runtime.lock_manager import LockAcquisitionError, LockManager, LockRequest, LockType


class LockManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_shared_reads_and_release(self) -> None:
        manager = LockManager()
        read_one = await manager.acquire(LockRequest("app.py", LockType.READ, "reader-1"))
        read_two = await manager.acquire(LockRequest("app.py", LockType.READ, "reader-2"))

        self.assertEqual(len(manager.snapshot().leases["app.py"]), 2)

        await manager.release_many([read_one, read_two])
        self.assertEqual(manager.snapshot().leases, {})

    async def test_timeout_on_conflicting_write(self) -> None:
        manager = LockManager()
        write = await manager.acquire(
            LockRequest("app.py", LockType.WRITE, "writer-1", timeout_sec=0.01)
        )

        with self.assertRaises(LockAcquisitionError):
            await manager.acquire(
                LockRequest("app.py", LockType.WRITE, "writer-2", timeout_sec=0.01)
            )

        await manager.release(write)

    async def test_acquire_many_uses_canonical_order(self) -> None:
        manager = LockManager()
        leases = await manager.acquire_many(
            [
                LockRequest("b.py", LockType.WRITE, "writer"),
                LockRequest("a.py", LockType.WRITE, "writer"),
            ]
        )

        self.assertEqual([lease.resource_id for lease in leases], ["a.py", "b.py"])
        await manager.release_many(leases)

    async def test_snapshot_persists_across_manager_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            state_path = Path(tmp_dir) / "locks.json"
            first = LockManager(state_path)
            lease = await first.acquire(LockRequest("app.py", LockType.WRITE, "writer"))

            second = LockManager(state_path)
            snapshot = second.snapshot()
            self.assertIn("app.py", snapshot.leases)
            self.assertEqual(snapshot.leases["app.py"][0].owner_id, "writer")

            await first.release(lease)
