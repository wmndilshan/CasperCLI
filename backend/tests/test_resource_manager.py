import pytest

from runtime.resource_manager import ResourceManager


@pytest.mark.asyncio
async def test_resource_claim_and_release():
    rm = ResourceManager()
    assert await rm.claim("merge_lane", "agent-a") is True
    assert await rm.claim("merge_lane", "agent-b") is False
    await rm.release("merge_lane", "agent-a")
    assert await rm.claim("merge_lane", "agent-b") is True


@pytest.mark.asyncio
async def test_same_agent_reclaim():
    rm = ResourceManager()
    assert await rm.claim("slot", "a") is True
    assert await rm.claim("slot", "a") is True
    await rm.release("slot", "a")
