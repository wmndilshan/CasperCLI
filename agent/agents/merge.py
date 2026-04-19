from __future__ import annotations

from agent.agents.base import BaseRuntimeAgent
from agent.runtime.merge_manager import MergeManager, MergeResult, MergeStrategy
from agent.team.models import AgentSpec


class MergeAgent(BaseRuntimeAgent):
    def __init__(
        self,
        spec: AgentSpec,
        manager: MergeManager | None = None,
    ) -> None:
        super().__init__(spec)
        self.manager = manager

    def merge(self, proposals: list, strategy: MergeStrategy = MergeStrategy.AUTO_SAFE) -> MergeResult:
        if not self.manager:
            raise RuntimeError("MergeManager is not attached")
        return self.manager.merge(proposals, strategy=strategy)
