from __future__ import annotations

from agent.agents.base import BaseRuntimeAgent
from agent.team.models import AgentSpec
from agent.verification.pipeline import VerificationPipeline, VerificationReport, VerificationRequest


class VerificationAgent(BaseRuntimeAgent):
    def __init__(
        self,
        spec: AgentSpec,
        pipeline: VerificationPipeline | None = None,
    ) -> None:
        super().__init__(spec)
        self.pipeline = pipeline

    async def verify(self, request: VerificationRequest) -> VerificationReport:
        if not self.pipeline:
            raise RuntimeError("VerificationPipeline is not attached")
        return await self.pipeline.run(request)
