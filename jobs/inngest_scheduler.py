from __future__ import annotations

from typing import Protocol

from jobs.job_models import JobResult, JobSpec


class InngestClientAdapter(Protocol):
    async def send_job_queued(self, spec: JobSpec) -> None: ...

    async def trigger_job(self, spec: JobSpec) -> None: ...

    async def send_job_completed(self, result: JobResult) -> None: ...

    async def poll_session_updates(self, session_id: str) -> list[JobResult]: ...


class PriorityJobQueue:
    def __init__(self) -> None:
        self._items: list[JobSpec] = []

    async def push(self, spec: JobSpec) -> None:
        self._items.append(spec)
        self._items.sort(key=lambda item: item.priority, reverse=True)

    async def pop_ready_batch(self, limit: int = 4) -> list[JobSpec]:
        batch = self._items[:limit]
        self._items = self._items[limit:]
        return batch


class InngestScheduler:
    def __init__(
        self,
        queue: PriorityJobQueue,
        inngest_client: InngestClientAdapter,
    ) -> None:
        self.queue = queue
        self.inngest = inngest_client

    async def enqueue(self, spec: JobSpec) -> str:
        await self.queue.push(spec)
        await self.inngest.send_job_queued(spec)
        return spec.job_id

    async def tick(self) -> None:
        ready = await self.queue.pop_ready_batch()
        for spec in ready:
            await self.inngest.trigger_job(spec)

    async def poll_session_updates(self, session_id: str) -> list[JobResult]:
        return await self.inngest.poll_session_updates(session_id)
