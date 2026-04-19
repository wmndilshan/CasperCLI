from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

from agent.runtime.events import RuntimeEventBus, RuntimeEventType
from agent.runtime.lock_manager import LockLease, LockManager, LockRequest, LockType
from agent.runtime.resource_manager import (
    ResourceGrant,
    ResourceManager,
    ResourceRequest,
)
from agent.runtime.task_graph import (
    DependencyResolver,
    ReadyQueue,
    TaskGraph,
    TaskNode,
    TaskResult,
    TaskStatus,
)


TaskHandler = Callable[["TaskExecutionContext"], Awaitable[TaskResult]]
AgentSelector = Callable[[TaskNode], str]


@dataclass
class TaskExecutionContext:
    task: TaskNode
    assigned_agent_id: str
    lock_leases: list[LockLease]
    resource_grants: list[ResourceGrant]


@dataclass
class SchedulerRunResult:
    results: dict[str, TaskResult]
    started_at: datetime
    finished_at: datetime


class Scheduler:
    """Runs a real DAG with concurrency, leases, and coarse-grained resources."""

    def __init__(
        self,
        *,
        max_parallelism: int,
        lock_manager: LockManager,
        resource_manager: ResourceManager,
        event_bus: RuntimeEventBus | None = None,
    ) -> None:
        self.max_parallelism = max_parallelism
        self.lock_manager = lock_manager
        self.resource_manager = resource_manager
        self.event_bus = event_bus or RuntimeEventBus()
        self.dependency_resolver = DependencyResolver()

    async def run(
        self,
        graph: TaskGraph,
        handler: TaskHandler,
        select_agent: AgentSelector,
    ) -> SchedulerRunResult:
        started_at = datetime.now(timezone.utc)
        ready_queue = ReadyQueue()
        running: dict[str, asyncio.Task[tuple[str, TaskResult]]] = {}
        results: dict[str, TaskResult] = {}

        while True:
            ready_nodes = self.dependency_resolver.resolve_ready(graph)
            ready_queue.extend(ready_nodes)
            for node in ready_nodes:
                self.event_bus.emit(
                    RuntimeEventType.TASK_READY,
                    task_id=node.id,
                    role=node.role,
                )

            while len(running) < self.max_parallelism and ready_queue:
                node = ready_queue.pop(graph)
                if node is None:
                    break

                try:
                    context = await self._acquire_execution_context(node, select_agent(node))
                except Exception as exc:
                    graph.mark_status(node.id, TaskStatus.BLOCKED)
                    self.event_bus.emit(
                        RuntimeEventType.TASK_BLOCKED,
                        task_id=node.id,
                        reason=str(exc),
                    )
                    continue

                graph.mark_status(node.id, TaskStatus.RUNNING)
                self.event_bus.emit(
                    RuntimeEventType.TASK_STARTED,
                    task_id=node.id,
                    agent_id=context.assigned_agent_id,
                )
                running[node.id] = asyncio.create_task(self._run_task(handler, context))

            if not running:
                if graph.is_goal_terminal():
                    break
                if not graph.ready_nodes():
                    break
                await asyncio.sleep(0)
                continue

            completed, _ = await asyncio.wait(
                list(running.values()),
                return_when=asyncio.FIRST_COMPLETED,
            )
            for future in completed:
                task_id, result = await future
                running.pop(task_id, None)
                results[task_id] = result
                if result.status == TaskStatus.COMPLETED:
                    graph.mark_status(task_id, TaskStatus.COMPLETED)
                    self.event_bus.emit(
                        RuntimeEventType.TASK_COMPLETED,
                        task_id=task_id,
                        output=result.output,
                    )
                else:
                    node = graph.get(task_id)
                    if node.retry_count < node.max_retries:
                        node.retry_count += 1
                        graph.mark_status(task_id, TaskStatus.PENDING)
                    else:
                        graph.mark_status(task_id, TaskStatus.FAILED)
                        self.event_bus.emit(
                            RuntimeEventType.TASK_BLOCKED,
                            task_id=task_id,
                            reason=result.error or "task_failed",
                        )

        return SchedulerRunResult(
            results=results,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
        )

    async def _acquire_execution_context(
        self,
        task: TaskNode,
        agent_id: str,
    ) -> TaskExecutionContext:
        lock_requests = [
            LockRequest(
                resource_id=Path(path).as_posix(),
                lock_type=LockType.WRITE,
                owner_id=f"{agent_id}:{task.id}",
            )
            for path in task.affected_paths
        ]
        resource_requests = [
            ResourceRequest(resource_name=name, owner_id=f"{agent_id}:{task.id}")
            for name in task.required_resources
        ]
        lock_leases = await self.lock_manager.acquire_many(lock_requests)
        try:
            resource_grants = await self.resource_manager.acquire_many(resource_requests)
        except Exception:
            await self.lock_manager.release_many(lock_leases)
            raise

        for lease in lock_leases:
            self.event_bus.emit(
                RuntimeEventType.LOCK_ACQUIRED,
                task_id=task.id,
                resource_id=lease.resource_id,
                lock_type=lease.lock_type.value,
            )
        return TaskExecutionContext(
            task=task,
            assigned_agent_id=agent_id,
            lock_leases=lock_leases,
            resource_grants=resource_grants,
        )

    async def _run_task(
        self,
        handler: TaskHandler,
        context: TaskExecutionContext,
    ) -> tuple[str, TaskResult]:
        try:
            result = await handler(context)
            return context.task.id, result
        finally:
            await self.resource_manager.release_many(context.resource_grants)
            await self.lock_manager.release_many(context.lock_leases)
            for lease in context.lock_leases:
                self.event_bus.emit(
                    RuntimeEventType.LOCK_RELEASED,
                    task_id=context.task.id,
                    resource_id=lease.resource_id,
                    lock_type=lease.lock_type.value,
                )
