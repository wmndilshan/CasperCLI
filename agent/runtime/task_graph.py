from __future__ import annotations

from collections import defaultdict
import heapq
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(str):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    INVALIDATED = "invalidated"


TERMINAL_TASK_STATES = {
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.SKIPPED,
    TaskStatus.INVALIDATED,
}


class TaskNode(BaseModel):
    id: str
    title: str
    objective: str
    role: str
    status: str = TaskStatus.PENDING
    dependencies: list[str] = Field(default_factory=list)
    priority: int = Field(default=100, ge=0)
    estimated_cost: int = Field(default=1, ge=0)
    required_capabilities: list[str] = Field(default_factory=list)
    required_resources: list[str] = Field(default_factory=list)
    affected_paths: list[str] = Field(default_factory=list)
    produced_artifacts: list[str] = Field(default_factory=list)
    invalidated_by: list[str] = Field(default_factory=list)
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskEdge(BaseModel):
    source: str
    target: str
    kind: str = "depends_on"


class TaskResult(BaseModel):
    task_id: str
    status: str = TaskStatus.COMPLETED
    output: str | None = None
    produced_artifacts: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class TaskGraph(BaseModel):
    session_id: str
    goal: str
    nodes: dict[str, TaskNode] = Field(default_factory=dict)
    edges: list[TaskEdge] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_task(self, node: TaskNode) -> None:
        self.nodes[node.id] = node
        for dependency in node.dependencies:
            self.add_dependency(dependency, node.id)

    def add_dependency(self, source: str, target: str) -> None:
        edge = TaskEdge(source=source, target=target)
        if edge not in self.edges:
            self.edges.append(edge)
        target_node = self.nodes.get(target)
        if target_node and source not in target_node.dependencies:
            target_node.dependencies.append(source)

    def get(self, task_id: str) -> TaskNode:
        return self.nodes[task_id]

    def upstream(self, task_id: str) -> list[str]:
        return list(self.nodes[task_id].dependencies)

    def downstream(self, task_id: str) -> list[str]:
        return [edge.target for edge in self.edges if edge.source == task_id]

    def ready_nodes(self) -> list[TaskNode]:
        ready: list[TaskNode] = []
        for node in self.nodes.values():
            if node.status in TERMINAL_TASK_STATES | {TaskStatus.RUNNING}:
                continue
            if all(
                self.nodes[dependency].status == TaskStatus.COMPLETED
                for dependency in node.dependencies
            ):
                if node.status != TaskStatus.READY:
                    node.status = TaskStatus.READY
                ready.append(node)
        return sorted(ready, key=lambda item: (item.priority, item.estimated_cost, item.id))

    def blocked_nodes(self) -> list[TaskNode]:
        blocked: list[TaskNode] = []
        for node in self.nodes.values():
            if node.status in TERMINAL_TASK_STATES | {TaskStatus.RUNNING}:
                continue
            if any(
                self.nodes[dependency].status != TaskStatus.COMPLETED
                for dependency in node.dependencies
            ):
                node.status = TaskStatus.BLOCKED
                blocked.append(node)
        return blocked

    def mark_status(self, task_id: str, status: str) -> TaskNode:
        node = self.nodes[task_id]
        node.status = status
        return node

    def invalidate(self, task_id: str, reason: str) -> TaskNode:
        node = self.nodes[task_id]
        node.status = TaskStatus.INVALIDATED
        node.invalidated_by.append(reason)
        return node

    def is_goal_terminal(self) -> bool:
        return bool(self.nodes) and all(
            node.status in TERMINAL_TASK_STATES for node in self.nodes.values()
        )

    def summary(self) -> dict[str, int]:
        counts: defaultdict[str, int] = defaultdict(int)
        for node in self.nodes.values():
            counts[node.status] += 1
        return dict(sorted(counts.items()))


class DependencyResolver:
    def resolve_ready(self, graph: TaskGraph) -> list[TaskNode]:
        return graph.ready_nodes()


class ReadyQueue:
    def __init__(self) -> None:
        self._heap: list[tuple[int, int, str]] = []
        self._queued: set[str] = set()

    def extend(self, nodes: list[TaskNode]) -> None:
        for node in nodes:
            if node.id in self._queued:
                continue
            heapq.heappush(
                self._heap,
                (node.priority, node.estimated_cost, node.id),
            )
            self._queued.add(node.id)

    def pop(self, graph: TaskGraph) -> TaskNode | None:
        while self._heap:
            _, _, task_id = heapq.heappop(self._heap)
            self._queued.discard(task_id)
            node = graph.nodes.get(task_id)
            if node and node.status == TaskStatus.READY:
                return node
        return None

    def __bool__(self) -> bool:
        return bool(self._heap)
