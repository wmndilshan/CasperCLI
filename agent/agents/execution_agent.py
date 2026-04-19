from __future__ import annotations

from typing import Awaitable, Callable

from agent.agents.base import BaseRuntimeAgent
from agent.runtime.scheduler import TaskExecutionContext
from agent.runtime.task_graph import TaskResult


TaskExecutor = Callable[[TaskExecutionContext], Awaitable[TaskResult]]


class ExecutionAgent(BaseRuntimeAgent):
    async def execute(
        self,
        context: TaskExecutionContext,
        executor: TaskExecutor,
    ) -> TaskResult:
        return await executor(context)
