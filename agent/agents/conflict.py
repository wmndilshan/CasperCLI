from __future__ import annotations

from agent.agents.base import BaseRuntimeAgent
from agent.runtime.conflict_detector import ConflictDetector, ConflictRecord
from agent.team.models import AgentSpec


class ConflictDetectionAgent(BaseRuntimeAgent):
    def __init__(
        self,
        spec: AgentSpec,
        detector: ConflictDetector | None = None,
    ) -> None:
        super().__init__(spec)
        self.detector = detector or ConflictDetector()

    def detect(self, proposal, existing: list, artifact_versions: dict[str, int] | None = None) -> list[ConflictRecord]:
        return self.detector.detect_proposal_conflicts(proposal, existing, artifact_versions)
