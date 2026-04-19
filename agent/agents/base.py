from __future__ import annotations

from agent.runtime.task_graph import TaskNode
from agent.team.models import AgentSpec


class BaseRuntimeAgent:
    """Base runtime agent wrapper used by scheduler, policy, and integration layers."""

    def __init__(self, spec: AgentSpec) -> None:
        self.spec = spec

    @property
    def id(self) -> str:
        return self.spec.id

    def assign_task(self, task_id: str) -> None:
        if task_id not in self.spec.active_task_ids:
            self.spec.active_task_ids.append(task_id)
        self.spec.status = "running"

    def release_task(self, task_id: str) -> None:
        self.spec.active_task_ids = [
            current for current in self.spec.active_task_ids if current != task_id
        ]
        self.spec.status = "idle" if not self.spec.active_task_ids else self.spec.status

    def supports_task(self, task: TaskNode) -> bool:
        if task.role == self.spec.role:
            return True
        return any(
            capability in task.required_capabilities for capability in self.spec.capabilities
        )

    def snapshot(self) -> dict[str, object]:
        return self.spec.model_dump(mode="json")
