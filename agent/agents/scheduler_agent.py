from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

from agent.agents.base import BaseRuntimeAgent
from agent.runtime.task_graph import TaskNode


class RationalSchedulerAgent(BaseRuntimeAgent):
    def select_agent(self, task: TaskNode, agents: list[BaseRuntimeAgent]) -> BaseRuntimeAgent:
        ranked = sorted(
            agents,
            key=lambda candidate: self._score_agent(candidate, task),
            reverse=True,
        )
        return ranked[0]

    def _score_agent(self, agent: BaseRuntimeAgent, task: TaskNode) -> int:
        score = 0
        if agent.spec.role == task.role:
            score += 10
        for capability in task.required_capabilities:
            if capability in agent.spec.capabilities:
                score += 4
        for path in task.affected_paths:
            normalized = Path(path).as_posix()
            if any(
                fnmatch(normalized, pattern)
                for pattern in agent.spec.scope.writable_patterns or agent.spec.scope.include_patterns
            ):
                score += 2
        return score
