from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResourceRequest:
    resource_name: str
    owner_id: str
    units: int = 1
    timeout_sec: float = 5.0


@dataclass
class ResourceGrant:
    resource_name: str
    owner_id: str
    units: int


class ResourceDeniedError(RuntimeError):
    pass


class ResourceManager:
    """Tracks slots, quotas, and coarse-grained execution budgets."""

    def __init__(
        self,
        capacities: dict[str, int] | None = None,
        *,
        llm_request_budget: int = 0,
        token_budget: int = 0,
        cost_budget_usd: float = 0.0,
    ) -> None:
        self._capacities = capacities or {}
        self._in_use: defaultdict[str, int] = defaultdict(int)
        self._condition = asyncio.Condition()
        self._llm_request_budget = llm_request_budget
        self._token_budget = token_budget
        self._cost_budget_usd = cost_budget_usd
        self._usage: dict[str, Any] = {
            "llm_requests": 0,
            "tokens": 0,
            "cost_usd": 0.0,
        }

    async def acquire(self, request: ResourceRequest) -> ResourceGrant:
        start = asyncio.get_running_loop().time()
        async with self._condition:
            while True:
                capacity = self._capacities.get(request.resource_name)
                used = self._in_use[request.resource_name]
                if capacity is None or used + request.units <= capacity:
                    self._in_use[request.resource_name] += request.units
                    return ResourceGrant(
                        resource_name=request.resource_name,
                        owner_id=request.owner_id,
                        units=request.units,
                    )

                remaining = request.timeout_sec - (
                    asyncio.get_running_loop().time() - start
                )
                if remaining <= 0:
                    raise ResourceDeniedError(
                        f"Timed out waiting for resource {request.resource_name}"
                    )
                try:
                    await asyncio.wait_for(self._condition.wait(), timeout=remaining)
                except TimeoutError as exc:
                    raise ResourceDeniedError(
                        f"Timed out waiting for resource {request.resource_name}"
                    ) from exc

    async def acquire_many(self, requests: list[ResourceRequest]) -> list[ResourceGrant]:
        ordered = sorted(requests, key=lambda item: item.resource_name)
        grants: list[ResourceGrant] = []
        try:
            for request in ordered:
                grants.append(await self.acquire(request))
        except Exception:
            await self.release_many(grants)
            raise
        return grants

    async def release(self, grant: ResourceGrant) -> None:
        async with self._condition:
            self._in_use[grant.resource_name] = max(
                0,
                self._in_use[grant.resource_name] - grant.units,
            )
            self._condition.notify_all()

    async def release_many(self, grants: list[ResourceGrant]) -> None:
        for grant in reversed(grants):
            await self.release(grant)

    def spend_budget(
        self,
        *,
        llm_requests: int = 0,
        tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> bool:
        next_llm = self._usage["llm_requests"] + llm_requests
        next_tokens = self._usage["tokens"] + tokens
        next_cost = self._usage["cost_usd"] + cost_usd

        if self._llm_request_budget and next_llm > self._llm_request_budget:
            return False
        if self._token_budget and next_tokens > self._token_budget:
            return False
        if self._cost_budget_usd and next_cost > self._cost_budget_usd:
            return False

        self._usage["llm_requests"] = next_llm
        self._usage["tokens"] = next_tokens
        self._usage["cost_usd"] = next_cost
        return True

    def snapshot(self) -> dict[str, Any]:
        return {
            "capacities": dict(self._capacities),
            "in_use": dict(self._in_use),
            "usage": dict(self._usage),
        }
