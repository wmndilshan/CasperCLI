from __future__ import annotations

from agent.agents.base import BaseRuntimeAgent
from agent.agents.boundary import BoundaryAgent
from agent.agents.execution_agent import ExecutionAgent
from agent.agents.integrator import IntegratorAgent
from agent.agents.llm_worker import LLMWorkerAgent
from agent.agents.merge import MergeAgent
from agent.agents.rule_based import RuleBasedAgent
from agent.agents.scheduler_agent import RationalSchedulerAgent
from agent.agents.verifier import VerificationAgent
from agent.agents.conflict import ConflictDetectionAgent
from agent.team.models import AgentType, TeamSpec


class TeamCompiler:
    """Compiles a TeamSpec into runtime agent objects with real services attached."""

    def __init__(
        self,
        *,
        boundary_agent: BoundaryAgent | None = None,
        scheduler_agent: RationalSchedulerAgent | None = None,
        execution_agent: ExecutionAgent | None = None,
        conflict_agent: ConflictDetectionAgent | None = None,
        merge_agent: MergeAgent | None = None,
        verification_agent: VerificationAgent | None = None,
        integrator_agent: IntegratorAgent | None = None,
    ) -> None:
        self._specialized_agents = {
            "boundary": boundary_agent,
            "scheduler": scheduler_agent,
            "execution": execution_agent,
            "conflicts": conflict_agent,
            "merge": merge_agent,
            "verification": verification_agent,
            "integrator": integrator_agent,
        }

    def compile(self, team_spec: TeamSpec) -> dict[str, BaseRuntimeAgent]:
        compiled: dict[str, BaseRuntimeAgent] = {}
        for spec in team_spec.agents:
            if spec.id in self._specialized_agents and self._specialized_agents[spec.id]:
                compiled[spec.id] = self._specialized_agents[spec.id]  # type: ignore[assignment]
                continue

            if spec.type == AgentType.LLM_WORKER:
                compiled[spec.id] = LLMWorkerAgent(spec)
            elif spec.type == AgentType.RULE_BASED:
                compiled[spec.id] = RuleBasedAgent(spec)
            elif spec.type == AgentType.BOUNDARY:
                compiled[spec.id] = BoundaryAgent(spec)
            elif spec.type == AgentType.RATIONAL_SCHEDULER:
                compiled[spec.id] = RationalSchedulerAgent(spec)
            elif spec.type == AgentType.EXECUTION:
                compiled[spec.id] = ExecutionAgent(spec)
            elif spec.type == AgentType.CONFLICT_DETECTOR:
                compiled[spec.id] = ConflictDetectionAgent(spec)
            elif spec.type == AgentType.MERGE:
                compiled[spec.id] = MergeAgent(spec)
            elif spec.type == AgentType.VERIFICATION:
                compiled[spec.id] = VerificationAgent(spec)
            elif spec.type == AgentType.INTEGRATOR:
                compiled[spec.id] = IntegratorAgent(spec)
            else:
                compiled[spec.id] = BaseRuntimeAgent(spec)
        return compiled
