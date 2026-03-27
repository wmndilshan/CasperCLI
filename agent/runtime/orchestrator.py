from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from agent.multi_agent.coordinator import MultiAgentCoordinator
from agent.sessions.task_graph import SessionState, TaskNode
from jobs.inngest_scheduler import InngestScheduler


class Planner(Protocol):
    async def plan(self, state: SessionState, retrieval: object) -> object: ...


class ExecutionEngine(Protocol):
    async def execute_step(
        self,
        state: SessionState,
        step: TaskNode,
    ) -> object: ...


class SessionStore(Protocol):
    async def load_or_create(self, session_id: str, goal: str) -> SessionState: ...

    async def checkpoint(self, state: SessionState) -> str: ...


class MemoryManager(Protocol):
    async def refresh_workspace_snapshot(self, workspace_root: str) -> None: ...

    async def build_planner_context(self, state: SessionState) -> object: ...

    async def update_from_outcome(self, state: SessionState, outcome: object) -> None: ...


@dataclass
class SessionOrchestrator:
    sessions: SessionStore
    planner: Planner
    executor: ExecutionEngine
    memory: MemoryManager
    jobs: InngestScheduler
    coordinator: MultiAgentCoordinator | None = None

    async def handle_goal(self, session_id: str, goal: str) -> SessionState:
        state = await self.sessions.load_or_create(session_id, goal)
        await self.memory.refresh_workspace_snapshot(state.workspace_root)
        if self.coordinator:
            self.coordinator.ensure_team(state.session_id)

        while not state.is_goal_terminal():
            retrieval = await self.memory.build_planner_context(state)
            await self.planner.plan(state=state, retrieval=retrieval)

            for step in state.ready_frontier():
                if self.coordinator:
                    self.coordinator.assign_task(state, step)
                outcome = await self.executor.execute_step(state, step)
                if self.coordinator:
                    self.coordinator.record_outcome(state, step, outcome)
                await self.memory.update_from_outcome(state, outcome)

            completed = await self.jobs.poll_session_updates(session_id)
            if completed:
                if self.coordinator:
                    for result in completed:
                        self.coordinator.record_job_update(state, result)
                await self.sessions.checkpoint(state)

            await self.jobs.tick()

        await self.sessions.checkpoint(state)
        return state
