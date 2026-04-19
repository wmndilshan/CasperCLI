from __future__ import annotations

from agent.agents.base import BaseRuntimeAgent
from agent.runtime.task_graph import TaskNode


class LLMWorkerAgent(BaseRuntimeAgent):
    def build_work_order(self, task: TaskNode) -> dict[str, object]:
        return {
            "task_id": task.id,
            "title": task.title,
            "objective": task.objective,
            "role": self.spec.role,
            "allowed_tools": self.spec.allowed_tools,
            "scope": self.spec.scope.model_dump(mode="json"),
            "output_contract": self.spec.output_contract,
        }
