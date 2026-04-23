from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import structlog

from agents.registry import build_default_registry
from locks.manager import FileLockManager, LockType
from models.schemas import (
    AgentStatus,
    EventType,
    TaskSpec,
    TaskStatus,
    TeamSpec,
)
from patches.pipeline import PatchPipeline
from runtime.event_bus import EventBus
from runtime.resource_manager import ResourceManager
from runtime.team_synthesizer import TeamSynthesizer
from scheduler.dag_scheduler import DagScheduler
from verification.pipeline import VerificationPipeline

logger = structlog.get_logger(__name__)


def _pick(team: TeamSpec, role: str) -> str:
    for agent in team.agents:
        if agent.role == role:
            return agent.id
    raise KeyError(f"No agent with role {role}")


def build_default_task_graph(team: TeamSpec) -> dict[str, TaskSpec]:
    """Construct a demo DAG spanning control-plane and parallel LLM workers."""
    scheduler = _pick(team, "scheduler")
    boundary = _pick(team, "boundary")
    execution = _pick(team, "execution")
    conflict = _pick(team, "conflict")
    merge = _pick(team, "merge")
    verification = _pick(team, "verification")
    integrator = _pick(team, "integrator")

    llm_ids = [a.id for a in team.agents if a.role == "llm_worker"]
    track_b_agent = llm_ids[1] if len(llm_ids) > 1 else llm_ids[0]

    tasks = {
        "t_plan": TaskSpec(
            id="t_plan",
            title="Plan DAG rollout",
            dependencies=[],
            assigned_agent_id=scheduler,
            affected_files=[".casper/schedule_notes.txt"],
            priority=10,
        ),
        "t_scope": TaskSpec(
            id="t_scope",
            title="Validate ownership boundaries",
            dependencies=["t_plan"],
            assigned_agent_id=boundary,
            affected_files=["backend/", "frontend/"],
            priority=9,
        ),
        "t_impl_a": TaskSpec(
            id="t_impl_a",
            title="Implementation track A",
            dependencies=["t_scope"],
            assigned_agent_id=execution,
            affected_files=[".casper/shared_demo.txt"],
            priority=5,
            patch_hint={"start_line": 1, "end_line": 6},
        ),
        "t_impl_b": TaskSpec(
            id="t_impl_b",
            title="Implementation track B",
            dependencies=["t_scope"],
            assigned_agent_id=track_b_agent,
            affected_files=[".casper/shared_demo.txt"],
            priority=5,
            patch_hint={"start_line": 4, "end_line": 9},
        ),
        "t_conflict": TaskSpec(
            id="t_conflict",
            title="Conflict scan",
            dependencies=["t_impl_a", "t_impl_b"],
            assigned_agent_id=conflict,
            affected_files=[".casper/shared_demo.txt"],
            priority=4,
        ),
        "t_merge": TaskSpec(
            id="t_merge",
            title="Merge proposals",
            dependencies=["t_conflict"],
            assigned_agent_id=merge,
            affected_files=[],
            priority=3,
            required_resources=["merge_lane"],
        ),
        "t_verify": TaskSpec(
            id="t_verify",
            title="Prepare verification",
            dependencies=["t_merge"],
            assigned_agent_id=verification,
            affected_files=[],
            priority=2,
            required_resources=["ci_runner"],
        ),
        "t_integrate": TaskSpec(
            id="t_integrate",
            title="Integration checkpoint",
            dependencies=["t_verify"],
            assigned_agent_id=integrator,
            affected_files=[],
            priority=1,
        ),
    }

    return tasks


class HybridOrchestrator:
    def __init__(
        self,
        *,
        session_id: str,
        bus: EventBus,
        team: TeamSpec,
        tasks: dict[str, TaskSpec],
        patch_pipeline: PatchPipeline,
        lock_manager: FileLockManager,
        resource_manager: ResourceManager | None = None,
        max_parallel: int = 4,
    ) -> None:
        self.session_id = session_id
        self.bus = bus
        self.team = team
        self.tasks = tasks
        self.patch_pipeline = patch_pipeline
        self.lock_manager = lock_manager
        self.resource_manager = resource_manager or ResourceManager()
        self.max_parallel = max_parallel
        self.registry = build_default_registry(team.agents)
        self.scheduler = DagScheduler(tasks)
        self._run_lock = asyncio.Lock()

    async def run(self) -> dict[str, Any]:
        async with self._run_lock:
            project_root = Path(self.team.project_root)

            async def execute_task(task_id: str) -> None:
                task = self.tasks[task_id]
                agent = self.registry.get(task.assigned_agent_id)
                agent.spec.status = AgentStatus.RUNNING
                agent.attach_task(task_id)
                self.scheduler.mark_running(task_id)
                await self.bus.publish(
                    self.session_id,
                    EventType.TASK_STARTED,
                    {"task_id": task_id, "agent_id": agent.id, "title": task.title},
                )

                leases = []
                claimed_resources: list[str] = []
                try:
                    for rid in task.required_resources:
                        ok = await self.resource_manager.claim(rid, agent.id)
                        if not ok:
                            raise RuntimeError(f"Resource in use: {rid}")
                        claimed_resources.append(rid)

                    for path in task.affected_files:
                        if path.endswith("/"):
                            continue
                        lease = await self.lock_manager.acquire(
                            path,
                            agent.id,
                            LockType.WRITE,
                            lease_sec=60.0,
                            timeout_sec=15.0,
                        )
                        leases.append(lease)
                        await self.bus.publish(
                            self.session_id,
                            EventType.LOCK_ACQUIRED,
                            {
                                "path": path,
                                "agent_id": agent.id,
                                "lock_type": "write",
                                "task_id": task_id,
                            },
                        )

                    proposal = await agent.synthesize_patch(task, project_root)
                    self.patch_pipeline.register_proposal(proposal)
                    await self.bus.publish(
                        self.session_id,
                        EventType.PATCH_PROPOSED,
                        {
                            "patch_id": proposal.id,
                            "task_id": task_id,
                            "agent_id": agent.id,
                            "files": [h.path for h in proposal.hunks],
                        },
                    )

                    self.scheduler.mark_completed(task_id)
                    await self.bus.publish(
                        self.session_id,
                        EventType.TASK_COMPLETED,
                        {
                            "task_id": task_id,
                            "agent_id": agent.id,
                            "status": TaskStatus.COMPLETED.value,
                        },
                    )
                except Exception as exc:  # pragma: no cover - surfaced to logs
                    logger.exception("task_failed", task_id=task_id)
                    self.scheduler.mark_failed(task_id, str(exc))
                    await self.bus.publish(
                        self.session_id,
                        EventType.TASK_COMPLETED,
                        {
                            "task_id": task_id,
                            "agent_id": agent.id,
                            "status": TaskStatus.FAILED.value,
                            "error": str(exc),
                        },
                    )
                finally:
                    for lease in leases:
                        await self.lock_manager.release(lease)
                    for rid in claimed_resources:
                        await self.resource_manager.release(rid, agent.id)
                    agent.detach_task(task_id)
                    agent.spec.status = (
                        AgentStatus.RUNNING
                        if agent.spec.current_tasks
                        else AgentStatus.IDLE
                    )

            while True:
                ready = self.scheduler.ready()
                if not ready:
                    if any(spec.status == TaskStatus.PENDING for spec in self.tasks.values()):
                        logger.warning(
                            "scheduler_stopped_with_pending_tasks",
                            pending=[
                                tid
                                for tid, spec in self.tasks.items()
                                if spec.status == TaskStatus.PENDING
                            ],
                        )
                    break

                batch = ready[: self.max_parallel]
                await asyncio.gather(*(execute_task(task_id) for task_id in batch))

            for conflict in self.patch_pipeline.conflicts():
                await self.bus.publish(
                    self.session_id,
                    EventType.CONFLICT_DETECTED,
                    {
                        "conflict_id": conflict.id,
                        "patches": conflict.patch_ids,
                        "description": conflict.description,
                        "files": conflict.files,
                    },
                )

            verifier = VerificationPipeline(project_root)
            result = await verifier.run()
            await self.bus.publish(
                self.session_id,
                EventType.VERIFICATION_RESULT,
                result.model_dump(mode="json"),
            )

            return {
                "tasks": {k: v.model_dump(mode="json") for k, v in self.tasks.items()},
                "verification": result.model_dump(mode="json"),
            }


async def run_demo_session(
    *,
    session_id: str,
    bus: EventBus,
    goal: str,
    project_root: Path,
    team_size: int,
    strict: bool,
    parallel: bool,
    max_parallel_tasks: int,
    project_context: str = "",
) -> HybridOrchestrator:
    synthesizer = TeamSynthesizer()
    team = synthesizer.synthesize(
        project_root=project_root,
        goal=goal,
        team_size=team_size,
        strict=strict,
        project_context=project_context,
    )
    tasks = build_default_task_graph(team)
    patch_pipeline = PatchPipeline(project_root, strict=strict)
    lock_manager = FileLockManager()
    resource_manager = ResourceManager()
    orchestrator = HybridOrchestrator(
        session_id=session_id,
        bus=bus,
        team=team,
        tasks=tasks,
        patch_pipeline=patch_pipeline,
        lock_manager=lock_manager,
        resource_manager=resource_manager,
        max_parallel=max_parallel_tasks if parallel else 1,
    )
    return orchestrator
