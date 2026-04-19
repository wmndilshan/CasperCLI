from __future__ import annotations

from agent.agents.base import BaseRuntimeAgent
from agent.policies.boundary_rules import BoundaryDecision, BoundaryPolicyEngine
from agent.team.models import AgentSpec


class BoundaryAgent(BaseRuntimeAgent):
    def __init__(
        self,
        spec: AgentSpec,
        engine: BoundaryPolicyEngine | None = None,
    ) -> None:
        super().__init__(spec)
        self.engine = engine

    def attach_engine(self, engine: BoundaryPolicyEngine) -> None:
        self.engine = engine

    def validate_path(self, agent: AgentSpec, path: str, action: str) -> BoundaryDecision:
        if not self.engine:
            return BoundaryDecision(allowed=True)
        return self.engine.validate_path(agent, path, action)

    def validate_tool(self, agent: AgentSpec, tool_name: str) -> BoundaryDecision:
        if not self.engine:
            return BoundaryDecision(allowed=True)
        return self.engine.validate_tool(agent, tool_name)

    def validate_patch(self, agent: AgentSpec, proposal) -> BoundaryDecision:
        if not self.engine:
            return BoundaryDecision(allowed=True)
        return self.engine.validate_patch(agent, proposal)
