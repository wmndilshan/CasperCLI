from __future__ import annotations

from agent.agents.base import BaseRuntimeAgent
from agent.runtime.patch_pipeline import CommitDecision, PatchBundle, PatchPipeline
from agent.team.models import AgentSpec
from agent.verification.pipeline import VerificationRequest


class IntegratorAgent(BaseRuntimeAgent):
    def __init__(
        self,
        spec: AgentSpec,
        pipeline: PatchPipeline | None = None,
    ) -> None:
        super().__init__(spec)
        self.pipeline = pipeline

    async def integrate(
        self,
        bundle: PatchBundle,
        *,
        apply_changes: bool,
        verification_request: VerificationRequest | None = None,
    ) -> CommitDecision:
        if not self.pipeline:
            raise RuntimeError("PatchPipeline is not attached")
        return await self.pipeline.commit(
            bundle,
            apply_changes=apply_changes,
            verification_request=verification_request,
        )
