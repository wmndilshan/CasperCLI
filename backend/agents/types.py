from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from models.schemas import AgentSpec, FileHunk, PatchProposal, PatchStatus, TaskSpec


class BaseAgent(ABC):
    """Runtime agent; produces patch proposals without writing files directly."""

    def __init__(self, spec: AgentSpec) -> None:
        self.spec = spec

    @property
    def id(self) -> str:
        return self.spec.id

    def attach_task(self, task_id: str) -> None:
        if task_id not in self.spec.current_tasks:
            self.spec.current_tasks.append(task_id)

    def detach_task(self, task_id: str) -> None:
        self.spec.current_tasks = [t for t in self.spec.current_tasks if t != task_id]

    @abstractmethod
    async def synthesize_patch(self, task: TaskSpec, project_root: Path) -> PatchProposal:
        raise NotImplementedError


class LLMWorkerAgent(BaseAgent):
    """Simulated LLM worker producing structured edits."""

    async def synthesize_patch(self, task: TaskSpec, project_root: Path) -> PatchProposal:
        hunks: list[FileHunk] = []
        for rel in task.affected_files or [".casper/demo.txt"]:
            path = Path(rel)
            start = int(task.patch_hint.get("start_line", 1))
            end = int(task.patch_hint.get("end_line", start + 2))
            text = f"# {task.title}\n# Goal fragment\n# agent={self.id}\n"
            hunks.append(FileHunk(path=str(path), start_line=start, end_line=end, content=text))
        return PatchProposal(
            id=f"patch_{uuid.uuid4().hex[:10]}",
            task_id=task.id,
            agent_id=self.id,
            status=PatchStatus.PROPOSED,
            hunks=hunks,
            metadata={"model": "simulated-llm"},
            risk_notes=list(task.risk_notes),
        )


class RuleBasedAgent(BaseAgent):
    """Deterministic transformations (stub)."""

    async def synthesize_patch(self, task: TaskSpec, project_root: Path) -> PatchProposal:
        return PatchProposal(
            id=f"patch_{uuid.uuid4().hex[:10]}",
            task_id=task.id,
            agent_id=self.id,
            status=PatchStatus.PROPOSED,
            hunks=[],
            metadata={"engine": "rules-v1"},
        )


class BoundaryAgent(BaseAgent):
    """Validates scope; emits metadata-only proposals."""

    async def synthesize_patch(self, task: TaskSpec, project_root: Path) -> PatchProposal:
        violations = [
            f
            for f in task.affected_files
            if self.spec.scope_paths and not any(f.startswith(p) for p in self.spec.scope_paths)
        ]
        return PatchProposal(
            id=f"patch_{uuid.uuid4().hex[:10]}",
            task_id=task.id,
            agent_id=self.id,
            status=PatchStatus.PROPOSED,
            hunks=[],
            metadata={"boundary_scan": True, "violations": violations},
            risk_notes=[f"scope violation: {v}" for v in violations],
        )


class SchedulerAgent(BaseAgent):
    """Scheduling hints / graph annotations."""

    async def synthesize_patch(self, task: TaskSpec, project_root: Path) -> PatchProposal:
        return PatchProposal(
            id=f"patch_{uuid.uuid4().hex[:10]}",
            task_id=task.id,
            agent_id=self.id,
            status=PatchStatus.PROPOSED,
            hunks=[
                FileHunk(
                    path=".casper/schedule_notes.txt",
                    start_line=1,
                    end_line=2,
                    content=f"task={task.id} priority={task.priority}\n",
                )
            ],
            metadata={"scheduler": True},
        )


class ExecutionAgent(BaseAgent):
    """Execution-focused worker (simulated patch)."""

    async def synthesize_patch(self, task: TaskSpec, project_root: Path) -> PatchProposal:
        worker = LLMWorkerAgent(self.spec)
        proposal = await worker.synthesize_patch(task, project_root)
        proposal.agent_id = self.id
        proposal.metadata["executor"] = True
        return proposal


class ConflictDetectionAgent(BaseAgent):
    """Produces diagnostic patch stubs after primary edits (demo)."""

    async def synthesize_patch(self, task: TaskSpec, project_root: Path) -> PatchProposal:
        return PatchProposal(
            id=f"patch_{uuid.uuid4().hex[:10]}",
            task_id=task.id,
            agent_id=self.id,
            hunks=[],
            metadata={"conflict_scan": True},
        )


class MergeAgent(BaseAgent):
    """Represents merge integration responsibilities."""

    async def synthesize_patch(self, task: TaskSpec, project_root: Path) -> PatchProposal:
        return PatchProposal(
            id=f"patch_{uuid.uuid4().hex[:10]}",
            task_id=task.id,
            agent_id=self.id,
            hunks=[],
            metadata={"merge": "noop-demo"},
        )


class VerificationAgent(BaseAgent):
    """Captures pre-verification intent; actual runs happen in pipeline."""

    async def synthesize_patch(self, task: TaskSpec, project_root: Path) -> PatchProposal:
        return PatchProposal(
            id=f"patch_{uuid.uuid4().hex[:10]}",
            task_id=task.id,
            agent_id=self.id,
            hunks=[],
            metadata={"verification_plan": ["lint", "tests", "build"]},
        )


class IntegratorAgent(BaseAgent):
    """Final integration agent."""

    async def synthesize_patch(self, task: TaskSpec, project_root: Path) -> PatchProposal:
        return PatchProposal(
            id=f"patch_{uuid.uuid4().hex[:10]}",
            task_id=task.id,
            agent_id=self.id,
            hunks=[],
            metadata={"integrator": True},
        )
