from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
from typing import Protocol
from uuid import uuid4

from agent.agents import (
    BoundaryAgent,
    ConflictDetectionAgent,
    ExecutionAgent,
    IntegratorAgent,
    MergeAgent,
    RationalSchedulerAgent,
    VerificationAgent,
)
from agent.artifacts.models import ArtifactKind
from agent.artifacts.store import ArtifactStore
from agent.multi_agent.coordinator import MultiAgentCoordinator
from agent.policies.boundary_rules import BoundaryPolicyEngine
from agent.runtime.conflict_detector import ConflictDetector
from agent.runtime.events import RuntimeEventBus, RuntimeEventType
from agent.runtime.lock_manager import LockManager
from agent.runtime.merge_manager import MergeManager, MergeStrategy
from agent.runtime.patch_pipeline import (
    CommitDecision,
    CommitStatus,
    PatchBundle,
    PatchPipeline,
    PatchProposal,
)
from agent.runtime.resource_manager import ResourceManager
from agent.runtime.scheduler import Scheduler, TaskExecutionContext
from agent.runtime.session_store import HybridSessionRecord, HybridSessionStore
from agent.sessions.task_graph import SessionState, TaskNode
from agent.team import (
    TeamCompiler,
    OwnershipMode,
    TeamSpec,
    TeamSynthesizer,
    TeamSynthesisOptions,
    VerificationMode,
)
from agent.verification import VerificationPipeline, VerificationReport, VerificationRequest
from agent.verification.validators import (
    BoundaryConsistencyValidator,
    ChangedFilesValidator,
    CommandValidator,
)
from jobs.inngest_scheduler import InngestScheduler
from agent.runtime.task_graph import TaskResult


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


@dataclass
class HybridRunRequest:
    goal: str
    workspace_root: Path
    team: str = "auto"
    team_size: int = 4
    strict: bool = False
    parallel: bool = True
    max_parallel_agents: int = 4
    verify: VerificationMode = VerificationMode.LIGHTWEIGHT
    planner_model: str | None = None
    worker_model: str | None = None
    dry_run: bool = False
    apply_patches: bool = False
    ownership_mode: OwnershipMode = OwnershipMode.STRICT
    quality_target: str = "balanced"
    session_id: str | None = None
    task_patches: dict[str, list[PatchProposal]] = field(default_factory=dict)


@dataclass
class HybridRunResult:
    session_id: str
    team_spec: TeamSpec
    task_graph: object
    commit_decision: CommitDecision | None
    verification_reports: list[VerificationReport]
    pending_proposals: list[PatchProposal]
    event_log: list[object]


@dataclass
class _HybridRuntimeServices:
    artifact_store: ArtifactStore
    boundary_engine: BoundaryPolicyEngine
    conflict_detector: ConflictDetector
    verification_pipeline: VerificationPipeline
    patch_pipeline: PatchPipeline
    merge_manager: MergeManager
    agents: dict[str, object]


@dataclass
class HybridOrchestrator:
    workspace_root: Path
    sessions_root: Path | None = None
    synthesizer: TeamSynthesizer = field(default_factory=TeamSynthesizer)
    event_bus: RuntimeEventBus = field(default_factory=RuntimeEventBus)
    lock_manager: LockManager = field(default_factory=LockManager)
    session_store: HybridSessionStore | None = None

    def __post_init__(self) -> None:
        if getattr(self.lock_manager, "state_path", None) is None:
            self.lock_manager = LockManager(
                self.workspace_root / ".CasperCode" / "hybrid_runtime" / "locks.json"
            )
        if self.session_store is None:
            root = self.sessions_root or (
                self.workspace_root / ".CasperCode" / "hybrid_runtime" / "sessions"
            )
            self.session_store = HybridSessionStore(root)

    def inspect_team(
        self,
        goal: str,
        options: TeamSynthesisOptions,
    ) -> TeamSpec:
        team_spec = self.synthesizer.synthesize(goal, self.workspace_root, options)
        self.event_bus.emit(
            RuntimeEventType.TEAM_SYNTHESIZED,
            team_id=team_spec.team_id,
            preset=team_spec.preset_name,
            team_size=team_spec.team_size,
        )
        return team_spec

    async def run(self, request: HybridRunRequest) -> HybridRunResult:
        session_id = request.session_id or f"session-{uuid4().hex[:8]}"
        options = TeamSynthesisOptions(
            team=request.team,
            team_size=request.team_size,
            strict=request.strict,
            quality_target=request.quality_target,
            ownership_mode=request.ownership_mode,
            verification_mode=request.verify,
            planner_model=request.planner_model,
            worker_model=request.worker_model,
        )
        team_spec = self.inspect_team(request.goal, options)
        task_graph = self._build_task_graph(session_id, request, team_spec)
        self.event_bus.emit(
            RuntimeEventType.TASK_GRAPH_CREATED,
            session_id=session_id,
            task_count=len(task_graph.nodes),
        )

        services = self._build_runtime_services(session_id, request.workspace_root, team_spec)
        services.artifact_store.put(
            kind=ArtifactKind.TASK_GRAPH,
            key=session_id,
            content=task_graph.model_dump(mode="json"),
            created_by="scheduler",
        )
        services.artifact_store.put(
            kind=ArtifactKind.FILE_OWNERSHIP_MAP,
            key=session_id,
            content=team_spec.ownership_map,
            created_by="boundary",
        )

        scheduler = Scheduler(
            max_parallelism=request.max_parallel_agents if request.parallel else 1,
            lock_manager=self.lock_manager,
            resource_manager=ResourceManager(
                team_spec.resource_policy.tool_slots,
                llm_request_budget=team_spec.resource_policy.llm_request_budget,
                token_budget=team_spec.resource_policy.token_budget,
                cost_budget_usd=team_spec.resource_policy.cost_budget_usd,
            ),
            event_bus=self.event_bus,
        )

        merge_state: dict[str, object] = {"bundle": PatchBundle(proposals=[])}
        verification_reports: list[VerificationReport] = []
        commit_decision: CommitDecision | None = None

        async def execute(context: TaskExecutionContext):
            task = context.task
            agent = services.agents[context.assigned_agent_id]
            agent.assign_task(task.id)
            try:
                if task.id == "plan-architecture":
                    services.artifact_store.put(
                        kind=ArtifactKind.ARCHITECTURE_SPEC,
                        key=session_id,
                        content={
                            "goal": request.goal,
                            "team": team_spec.name,
                            "ownership_map": team_spec.ownership_map,
                        },
                        created_by=agent.id,
                        task_id=task.id,
                    )
                    return TaskResult(
                        task_id=task.id,
                        output="architecture and ownership artifacts produced",
                        produced_artifacts=["architecture_spec", "file_ownership_map"],
                    )

                if task.id.startswith("implement-"):
                    staged = 0
                    task_validations: list[dict[str, object]] = []
                    for proposal in request.task_patches.get(task.id, []):
                        worker_spec = next(
                            spec for spec in team_spec.agents if spec.id == proposal.agent_id
                        )
                        validation = services.patch_pipeline.stage(worker_spec, proposal)
                        task_validations.append(validation.model_dump(mode="json"))
                        if validation.accepted:
                            staged += 1
                    services.artifact_store.put(
                        kind=ArtifactKind.DECISION_LOG,
                        key=f"{session_id}:{task.id}",
                        content={"staged": staged, "task": task.title},
                        created_by=agent.id,
                        task_id=task.id,
                    )
                    return TaskResult(
                        task_id=task.id,
                        output=f"staged {staged} proposal(s)",
                        metadata={"validations": task_validations},
                    )

                if task.id == "merge-patches":
                    strategy = (
                        MergeStrategy.OWNERSHIP_WINS
                        if team_spec.strict
                        else MergeStrategy.AUTO_SAFE
                    )
                    result = services.merge_manager.merge(
                        services.patch_pipeline.pending_proposals(),
                        strategy=strategy,
                    )
                    merge_state["bundle"] = result.bundle
                    services.artifact_store.put(
                        kind=ArtifactKind.PATCH_BUNDLE,
                        key=result.bundle.bundle_id,
                        content=result.bundle.model_dump(mode="json"),
                        created_by=agent.id,
                        task_id=task.id,
                        metadata={"conflicts": [item.model_dump(mode="json") for item in result.conflicts]},
                    )
                    return TaskResult(
                        task_id=task.id,
                        status="failed" if result.escalated else "completed",
                        output=f"merged {len(result.bundle.proposals)} proposal(s)",
                        metadata={
                            "conflict_count": len(result.conflicts),
                            "escalated": result.escalated,
                            "conflicts": [item.model_dump(mode="json") for item in result.conflicts],
                        },
                        error="merge-conflicts-detected" if result.escalated else None,
                    )

                if task.id == "verify-bundle":
                    bundle = merge_state["bundle"]
                    changed_files = bundle.changed_files()
                    if not changed_files:
                        report = VerificationReport(
                            mode=team_spec.review_policy.mode.value,
                            passed=True,
                            started_at=datetime.now(timezone.utc),
                            finished_at=datetime.now(timezone.utc),
                            outcomes=[],
                        )
                    else:
                        report = await services.verification_pipeline.run(
                            VerificationRequest(
                                session_id=session_id,
                                workspace_root=request.workspace_root,
                                goal=request.goal,
                                changed_files=changed_files,
                                bundle_id=bundle.bundle_id,
                                mode=team_spec.review_policy.mode.value,
                            )
                        )
                    verification_reports.append(report)
                    services.artifact_store.put(
                        kind=ArtifactKind.REVIEW_REPORT,
                        key=f"{session_id}:verification",
                        content=report.model_dump(mode="json"),
                        created_by=agent.id,
                        task_id=task.id,
                    )
                    return TaskResult(
                        task_id=task.id,
                        status="completed" if report.passed else "failed",
                        output="verification complete",
                        metadata={"passed": report.passed},
                    )

                if task.id == "integrate":
                    bundle = merge_state["bundle"]
                    nonlocal commit_decision
                    if not bundle.proposals:
                        commit_decision = CommitDecision(
                            bundle_id=bundle.bundle_id,
                            status=CommitStatus.DRY_RUN,
                            applied_paths=[],
                        )
                    else:
                        verification_request = None
                        if bundle.changed_files():
                            verification_request = VerificationRequest(
                                session_id=session_id,
                                workspace_root=request.workspace_root,
                                goal=request.goal,
                                changed_files=bundle.changed_files(),
                                bundle_id=bundle.bundle_id,
                                mode=team_spec.review_policy.mode.value,
                            )
                        commit_decision = await services.patch_pipeline.commit(
                            bundle,
                            apply_changes=request.apply_patches and not request.dry_run,
                            verification_request=verification_request,
                        )
                    return TaskResult(
                        task_id=task.id,
                        status="completed"
                        if commit_decision.status != "rejected"
                        else "failed",
                        output=commit_decision.status.value,
                        metadata=commit_decision.model_dump(mode="json"),
                    )

                return TaskResult(task_id=task.id, output="noop")
            finally:
                agent.release_task(task.id)

        def select_agent(task: TaskNode) -> str:
            agent_id = task.metadata.get("agent_id")
            if isinstance(agent_id, str):
                return agent_id
            if task.role in services.agents:
                return task.role
            worker_agents = [
                item
                for item in services.agents.values()
                if getattr(item.spec.type, "value", item.spec.type) == "llm_worker"
            ]
            scheduler_agent = services.agents["scheduler"]
            return scheduler_agent.select_agent(task, worker_agents).id

        await scheduler.run(task_graph, execute, select_agent)

        record = HybridSessionRecord(
            session_id=session_id,
            goal=request.goal,
            workspace_root=request.workspace_root,
            team_spec=team_spec,
            task_graph=task_graph,
            pending_proposals=services.patch_pipeline.pending_proposals(),
            commit_history=[commit_decision] if commit_decision else [],
            verification_reports=verification_reports,
            artifacts=services.artifact_store.list(),
            event_log=self._serialize_events(),
            metadata={"lock_snapshot": list(self.lock_manager.snapshot().leases.keys())},
        )
        self.session_store.save(record)
        services.artifact_store.save()
        return HybridRunResult(
            session_id=session_id,
            team_spec=team_spec,
            task_graph=task_graph,
            commit_decision=commit_decision,
            verification_reports=verification_reports,
            pending_proposals=services.patch_pipeline.pending_proposals(),
            event_log=self.event_bus.events,
        )

    def load_session(self, session_id: str) -> HybridSessionRecord:
        return self.session_store.load(session_id)

    def show_task_graph(self, session_id: str):
        return self.session_store.load(session_id).task_graph

    def show_locks(self) -> dict[str, list[dict[str, object]]]:
        snapshot = self.lock_manager.snapshot()
        return {
            resource_id: [
                {
                    "lease_id": lease.lease_id,
                    "owner_id": lease.owner_id,
                    "lock_type": lease.lock_type.value,
                    "expires_at": lease.expires_at.isoformat(),
                }
                for lease in leases
            ]
            for resource_id, leases in snapshot.leases.items()
        }

    async def apply_pending_patches(self, session_id: str) -> CommitDecision:
        record = self.session_store.load(session_id)
        services = self._build_runtime_services(session_id, record.workspace_root, record.team_spec)
        for proposal in record.pending_proposals:
            spec = next(agent for agent in record.team_spec.agents if agent.id == proposal.agent_id)
            services.patch_pipeline.stage(spec, proposal)
        merge_result = services.merge_manager.merge(
            services.patch_pipeline.pending_proposals(),
            strategy=MergeStrategy.OWNERSHIP_WINS if record.team_spec.strict else MergeStrategy.AUTO_SAFE,
        )
        if merge_result.escalated:
            decision = CommitDecision(
                bundle_id=merge_result.bundle.bundle_id,
                status=CommitStatus.REJECTED,
                rejected_reasons=["merge-conflicts-detected"],
            )
            record.commit_history.append(decision)
            self.session_store.save(record)
            return decision
        verification_request = None
        if merge_result.bundle.changed_files():
            verification_request = VerificationRequest(
                session_id=session_id,
                workspace_root=record.workspace_root,
                goal=record.goal,
                changed_files=merge_result.bundle.changed_files(),
                bundle_id=merge_result.bundle.bundle_id,
                mode=record.team_spec.review_policy.mode.value,
            )
        decision = await services.patch_pipeline.commit(
            merge_result.bundle,
            apply_changes=True,
            verification_request=verification_request,
        )
        record.pending_proposals = services.patch_pipeline.pending_proposals()
        record.commit_history.append(decision)
        record.artifacts = services.artifact_store.list()
        self.session_store.save(record)
        services.artifact_store.save()
        return decision

    def _build_runtime_services(
        self,
        session_id: str,
        workspace_root: Path,
        team_spec: TeamSpec,
    ) -> _HybridRuntimeServices:
        session_dir = self.session_store.session_dir(session_id)
        artifact_store = ArtifactStore(session_dir / "artifacts.json")
        boundary_engine = BoundaryPolicyEngine(team_spec)
        conflict_detector = ConflictDetector()
        verification_pipeline = self._build_verification_pipeline(team_spec, workspace_root)
        patch_pipeline = PatchPipeline(
            workspace_root=workspace_root,
            lock_manager=self.lock_manager,
            boundary_engine=boundary_engine,
            conflict_detector=conflict_detector,
            artifact_store=artifact_store,
            verification_pipeline=verification_pipeline,
            event_bus=self.event_bus,
        )
        merge_manager = MergeManager(
            conflict_detector=conflict_detector,
            boundary_engine=boundary_engine,
            event_bus=self.event_bus,
        )

        compiler = TeamCompiler(
            boundary_agent=BoundaryAgent(
                next(agent for agent in team_spec.agents if agent.id == "boundary"),
                boundary_engine,
            ),
            scheduler_agent=RationalSchedulerAgent(
                next(agent for agent in team_spec.agents if agent.id == "scheduler")
            ),
            execution_agent=ExecutionAgent(
                next(agent for agent in team_spec.agents if agent.id == "executor")
            ),
            conflict_agent=ConflictDetectionAgent(
                next(agent for agent in team_spec.agents if agent.id == "conflicts"),
                conflict_detector,
            ),
            merge_agent=MergeAgent(
                next(agent for agent in team_spec.agents if agent.id == "merge"),
                merge_manager,
            ),
            verification_agent=VerificationAgent(
                next(agent for agent in team_spec.agents if agent.id == "verification"),
                verification_pipeline,
            ),
            integrator_agent=IntegratorAgent(
                next(agent for agent in team_spec.agents if agent.id == "integrator"),
                patch_pipeline,
            ),
        )
        return _HybridRuntimeServices(
            artifact_store=artifact_store,
            boundary_engine=boundary_engine,
            conflict_detector=conflict_detector,
            verification_pipeline=verification_pipeline,
            patch_pipeline=patch_pipeline,
            merge_manager=merge_manager,
            agents=compiler.compile(team_spec),
        )

    def _build_verification_pipeline(
        self,
        team_spec: TeamSpec,
        workspace_root: Path,
    ) -> VerificationPipeline:
        validators = []
        for name in team_spec.review_policy.validators:
            if name == "changed_files":
                validators.append(ChangedFilesValidator())
            elif name == "boundary_consistency":
                validators.append(BoundaryConsistencyValidator())
            elif name == "tests" and (workspace_root / "tests").exists():
                validators.append(
                    CommandValidator("tests", f"{sys.executable} -m unittest discover")
                )
            elif name == "syntax" and any(workspace_root.rglob("*.py")):
                validators.append(
                    CommandValidator("syntax", f"{sys.executable} -m compileall .")
                )
            elif name == "typecheck" and any(workspace_root.rglob("*.py")):
                if shutil.which("mypy"):
                    validators.append(CommandValidator("typecheck", "mypy ."))
                elif shutil.which("pyright"):
                    validators.append(CommandValidator("typecheck", "pyright"))
            elif name == "lint" and any(workspace_root.rglob("*.py")):
                if shutil.which("ruff"):
                    validators.append(CommandValidator("lint", "ruff check ."))
                elif shutil.which("flake8"):
                    validators.append(CommandValidator("lint", "flake8 ."))
            elif name == "security" and any(workspace_root.rglob("*.py")):
                if shutil.which("bandit"):
                    validators.append(CommandValidator("security", "bandit -q -r ."))
        return VerificationPipeline(validators, event_bus=self.event_bus)

    def _build_task_graph(
        self,
        session_id: str,
        request: HybridRunRequest,
        team_spec: TeamSpec,
    ):
        from agent.runtime.task_graph import TaskGraph, TaskNode

        graph = TaskGraph(session_id=session_id, goal=request.goal)
        planner_owner = next(
            (agent.id for agent in team_spec.agents if agent.role == "planner"),
            "scheduler",
        )
        graph.add_task(
            TaskNode(
                id="plan-architecture",
                title="Architecture and ownership planning",
                objective="Produce architecture, ownership, and execution artifacts.",
                role="planner",
                priority=1,
                metadata={"agent_id": planner_owner},
                produced_artifacts=["architecture_spec", "file_ownership_map"],
            )
        )

        implementation_ids: list[str] = []
        for agent in team_spec.agents:
            if getattr(agent.type, "value", agent.type) != "llm_worker":
                continue
            if agent.role == "planner":
                continue
            task_id = f"implement-{agent.id}"
            implementation_ids.append(task_id)
            graph.add_task(
                TaskNode(
                    id=task_id,
                    title=f"Implement {agent.role} workstream",
                    objective=f"Produce patch proposals for the {agent.role} scope.",
                    role=agent.role,
                    dependencies=["plan-architecture"],
                    priority=2,
                    affected_paths=[
                        fragment.path
                        for proposal in request.task_patches.get(task_id, [])
                        for fragment in proposal.fragments
                    ],
                    required_resources=["shell"] if agent.role != "qa" else [],
                    metadata={"agent_id": agent.id},
                )
            )

        merge_dependencies = implementation_ids or ["plan-architecture"]
        graph.add_task(
            TaskNode(
                id="merge-patches",
                title="Merge compatible patches",
                objective="Detect conflicts and construct the next bundle candidate.",
                role="merge",
                dependencies=merge_dependencies,
                priority=3,
                metadata={"agent_id": "merge"},
                produced_artifacts=["patch_bundle"],
            )
        )
        graph.add_task(
            TaskNode(
                id="verify-bundle",
                title="Verify merged bundle",
                objective="Run configured verification gates before integration.",
                role="verification",
                dependencies=["merge-patches"],
                priority=4,
                required_resources=["tests"] if team_spec.review_policy.mode != VerificationMode.LIGHTWEIGHT else [],
                metadata={"agent_id": "verification"},
            )
        )
        graph.add_task(
            TaskNode(
                id="integrate",
                title="Integrate accepted patches",
                objective="Apply or preview the merged patch bundle transactionally.",
                role="integrator",
                dependencies=["verify-bundle"],
                priority=5,
                metadata={"agent_id": "integrator"},
            )
        )
        return graph

    def _serialize_events(self) -> list[dict[str, object]]:
        return [
            {
                "type": event.type.value,
                "payload": event.payload,
                "created_at": event.created_at.isoformat(),
            }
            for event in self.event_bus.events
        ]
