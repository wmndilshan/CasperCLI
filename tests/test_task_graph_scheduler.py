from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path
import unittest

from agent.runtime.lock_manager import LockManager
from agent.runtime.resource_manager import ResourceManager
from agent.runtime.scheduler import Scheduler
from agent.runtime.task_graph import TaskGraph, TaskNode, TaskResult, TaskStatus


class TaskGraphTests(unittest.TestCase):
    def test_dependency_resolution_marks_only_unblocked_tasks_ready(self) -> None:
        graph = TaskGraph(session_id="session", goal="goal")
        graph.add_task(TaskNode(id="plan", title="Plan", objective="plan", role="planner"))
        graph.add_task(
            TaskNode(
                id="implement",
                title="Implement",
                objective="implement",
                role="backend",
                dependencies=["plan"],
            )
        )

        self.assertEqual([task.id for task in graph.ready_nodes()], ["plan"])
        graph.mark_status("plan", TaskStatus.COMPLETED)
        self.assertEqual([task.id for task in graph.ready_nodes()], ["implement"])


class SchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_scheduler_runs_independent_tasks_concurrently(self) -> None:
        graph = TaskGraph(session_id="session", goal="goal")
        graph.add_task(TaskNode(id="a", title="A", objective="A", role="backend"))
        graph.add_task(TaskNode(id="b", title="B", objective="B", role="frontend"))
        graph.add_task(
            TaskNode(
                id="c",
                title="C",
                objective="C",
                role="verification",
                dependencies=["a", "b"],
            )
        )

        scheduler = Scheduler(
            max_parallelism=2,
            lock_manager=LockManager(),
            resource_manager=ResourceManager(),
        )

        async def handler(context):
            await asyncio.sleep(0.05)
            return TaskResult(task_id=context.task.id, status=TaskStatus.COMPLETED)

        started = time.perf_counter()
        await scheduler.run(graph, handler, lambda task: task.role)
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.14)
        self.assertEqual(graph.get("c").status, TaskStatus.COMPLETED)
