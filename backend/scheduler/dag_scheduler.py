from __future__ import annotations

from typing import Iterable

import networkx as nx

from models.schemas import TaskSpec, TaskStatus


class DagScheduler:
    """networkx-backed DAG for task readiness and dependency tracking."""

    def __init__(self, tasks: dict[str, TaskSpec]) -> None:
        self.tasks = tasks
        self.graph = nx.DiGraph()
        for task_id, task in tasks.items():
            self.graph.add_node(task_id, task=task)
            for dep in task.dependencies:
                self.graph.add_edge(dep, task_id)
        if not nx.is_directed_acyclic_graph(self.graph):
            cycle = nx.find_cycle(self.graph)
            raise ValueError(f"Task graph contains a cycle: {cycle}")

    def ready(self) -> list[str]:
        pending = [
            node
            for node in self.graph.nodes
            if self.tasks[node].status == TaskStatus.PENDING
        ]

        def preds_done(node: str) -> bool:
            return all(self.tasks[p].status == TaskStatus.COMPLETED for p in self.graph.predecessors(node))

        ready_ids = [node for node in pending if preds_done(node)]
        return sorted(ready_ids, key=lambda tid: (-self.tasks[tid].priority, tid))

    def mark_running(self, task_id: str) -> None:
        self.tasks[task_id].status = TaskStatus.RUNNING

    def mark_completed(self, task_id: str) -> None:
        self.tasks[task_id].status = TaskStatus.COMPLETED
        self.tasks[task_id].error = None

    def mark_failed(self, task_id: str, message: str) -> None:
        self.tasks[task_id].status = TaskStatus.FAILED
        self.tasks[task_id].error = message

    @staticmethod
    def from_specs(specs: Iterable[TaskSpec]) -> DagScheduler:
        return DagScheduler({task.id: task for task in specs})
