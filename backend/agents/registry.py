from __future__ import annotations

from models.schemas import AgentKind, AgentSpec
from agents.types import (
    BaseAgent,
    BoundaryAgent,
    ConflictDetectionAgent,
    ExecutionAgent,
    IntegratorAgent,
    LLMWorkerAgent,
    MergeAgent,
    RuleBasedAgent,
    SchedulerAgent,
    VerificationAgent,
)


def _factory(kind: AgentKind):
    mapping: dict[AgentKind, type[BaseAgent]] = {
        AgentKind.LLM_WORKER: LLMWorkerAgent,
        AgentKind.RULE_BASED: RuleBasedAgent,
        AgentKind.BOUNDARY: BoundaryAgent,
        AgentKind.SCHEDULER: SchedulerAgent,
        AgentKind.EXECUTION: ExecutionAgent,
        AgentKind.CONFLICT_DETECTION: ConflictDetectionAgent,
        AgentKind.MERGE: MergeAgent,
        AgentKind.VERIFICATION: VerificationAgent,
        AgentKind.INTEGRATOR: IntegratorAgent,
    }
    return mapping[kind]


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, spec: AgentSpec) -> BaseAgent:
        agent = _factory(spec.kind)(spec)
        self._agents[spec.id] = agent
        return agent

    def seed_team(self, specs: list[AgentSpec]) -> None:
        self._agents.clear()
        for spec in specs:
            self.register(spec)

    def get(self, agent_id: str) -> BaseAgent:
        return self._agents[agent_id]

    def all(self) -> dict[str, BaseAgent]:
        return dict(self._agents)


def build_default_registry(specs: list[AgentSpec]) -> AgentRegistry:
    reg = AgentRegistry()
    reg.seed_team(specs)
    return reg
