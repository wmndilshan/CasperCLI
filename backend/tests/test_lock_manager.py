import pytest

from locks.manager import LockAcquisitionError, FileLockManager, LockType


@pytest.mark.asyncio
async def test_write_lock_excludes_second_writer():
    mgr = FileLockManager()
    first = await mgr.acquire("src/a.py", "agent-1", LockType.WRITE, timeout_sec=1.0)
    with pytest.raises(LockAcquisitionError):
        await mgr.acquire("src/a.py", "agent-2", LockType.WRITE, timeout_sec=0.2)
    await mgr.release(first)


@pytest.mark.asyncio
async def test_multiple_readers_allowed():
    mgr = FileLockManager()
    a = await mgr.acquire("README.md", "r1", LockType.READ, timeout_sec=1.0)
    b = await mgr.acquire("README.md", "r2", LockType.READ, timeout_sec=1.0)
    await mgr.release(a)
    await mgr.release(b)


@pytest.mark.asyncio
async def test_reader_blocks_writer():
    mgr = FileLockManager()
    reader = await mgr.acquire("x.txt", "r1", LockType.READ, timeout_sec=1.0)
    with pytest.raises(LockAcquisitionError):
        await mgr.acquire("x.txt", "w1", LockType.WRITE, timeout_sec=0.2)
    await mgr.release(reader)
