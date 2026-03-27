from __future__ import annotations

from typing import Any

from config.config import Config
from jobs.job_models import JobResult, JobSpec

try:
    import inngest
except ImportError:  # pragma: no cover
    inngest = None


class InngestRuntime:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._history: dict[str, list[JobResult]] = {}
        self._client = None

        if inngest is not None:
            self._client = inngest.Inngest(app_id=self.config.inngest_app_id)

    @property
    def client(self) -> Any:
        return self._client

    async def send_job_queued(self, spec: JobSpec) -> None:
        if spec.session_id not in self._history:
            self._history[spec.session_id] = []

    async def trigger_job(self, spec: JobSpec) -> None:
        if self._client is None:
            return

        await self._client.send(
            {
                "name": "caspercode/job.requested",
                "data": spec.model_dump(mode="json"),
            }
        )

    async def send_job_completed(self, result: JobResult) -> None:
        self._history.setdefault(result.session_id, []).append(result)

        if self._client is None:
            return

        await self._client.send(
            {
                "name": "caspercode/job.completed",
                "data": result.model_dump(mode="json"),
            }
        )

    async def poll_session_updates(self, session_id: str) -> list[JobResult]:
        updates = self._history.get(session_id, [])
        self._history[session_id] = []
        return updates
