from __future__ import annotations

import difflib
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from agent.artifacts.models import ArtifactKind
from agent.artifacts.store import ArtifactStore
from agent.policies.boundary_rules import BoundaryDecision, BoundaryPolicyEngine
from agent.runtime.conflict_detector import ConflictDetector, ConflictRecord
from agent.runtime.events import RuntimeEventBus, RuntimeEventType
from agent.runtime.lock_manager import LockManager, LockRequest, LockType
from agent.team.models import AgentSpec
from agent.verification.pipeline import VerificationPipeline, VerificationReport, VerificationRequest


class PatchOperation(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class CommitStatus(str, Enum):
    DRY_RUN = "dry_run"
    APPLIED = "applied"
    REJECTED = "rejected"


class PatchFragment(BaseModel):
    path: str
    operation: PatchOperation
    new_content: str | None = None
    expected_old_content: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    rationale: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PatchProposal(BaseModel):
    proposal_id: str = Field(default_factory=lambda: f"proposal-{uuid4().hex[:8]}")
    agent_id: str
    task_id: str
    title: str
    fragments: list[PatchFragment]
    rationale: str
    dependencies: list[str] = Field(default_factory=list)
    contract_changes: list[str] = Field(default_factory=list)
    required_artifacts: list[str] = Field(default_factory=list)
    affected_resources: list[str] = Field(default_factory=list)
    base_artifact_versions: dict[str, int] = Field(default_factory=dict)
    risk_metadata: dict[str, Any] = Field(default_factory=dict)

    def touched_files(self) -> list[str]:
        return [fragment.path for fragment in self.fragments]


class PatchValidationResult(BaseModel):
    proposal_id: str
    accepted: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    boundary_decision: BoundaryDecision = Field(default_factory=lambda: BoundaryDecision(allowed=True))
    conflicts: list[ConflictRecord] = Field(default_factory=list)
    diff_by_path: dict[str, str] = Field(default_factory=dict)


class PatchBundle(BaseModel):
    bundle_id: str = Field(default_factory=lambda: f"bundle-{uuid4().hex[:8]}")
    proposals: list[PatchProposal] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def changed_files(self) -> list[str]:
        files: list[str] = []
        for proposal in self.proposals:
            files.extend(proposal.touched_files())
        return sorted(set(files))


class CommitDecision(BaseModel):
    bundle_id: str
    status: CommitStatus
    applied_paths: list[str] = Field(default_factory=list)
    rejected_reasons: list[str] = Field(default_factory=list)
    verification_passed: bool = True
    verification_report: VerificationReport | None = None


class PatchPipeline:
    """Validates, stages, and commits structured patch proposals."""

    def __init__(
        self,
        *,
        workspace_root: Path,
        lock_manager: LockManager,
        boundary_engine: BoundaryPolicyEngine,
        conflict_detector: ConflictDetector,
        artifact_store: ArtifactStore,
        verification_pipeline: VerificationPipeline | None = None,
        event_bus: RuntimeEventBus | None = None,
    ) -> None:
        self.workspace_root = workspace_root
        self.lock_manager = lock_manager
        self.boundary_engine = boundary_engine
        self.conflict_detector = conflict_detector
        self.artifact_store = artifact_store
        self.verification_pipeline = verification_pipeline
        self.event_bus = event_bus or RuntimeEventBus()
        self._pending: dict[str, PatchProposal] = {}

    def pending_proposals(self) -> list[PatchProposal]:
        return list(self._pending.values())

    def validate(self, agent: AgentSpec, proposal: PatchProposal) -> PatchValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        boundary = self.boundary_engine.validate_patch(agent, proposal)
        conflicts = self.conflict_detector.detect_proposal_conflicts(
            proposal,
            [item for item in self._pending.values() if item.proposal_id != proposal.proposal_id],
            artifact_versions=self.artifact_store.version_map(),
        )

        diff_by_path: dict[str, str] = {}
        for fragment in proposal.fragments:
            file_path = self.workspace_root / fragment.path
            current = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
            if fragment.operation == PatchOperation.CREATE and file_path.exists():
                errors.append(f"{fragment.path} already exists")
            if fragment.operation == PatchOperation.UPDATE and not file_path.exists():
                errors.append(f"{fragment.path} does not exist")
            if fragment.operation == PatchOperation.DELETE and not file_path.exists():
                errors.append(f"{fragment.path} does not exist for deletion")
            if fragment.operation in {PatchOperation.CREATE, PatchOperation.UPDATE} and fragment.new_content is None:
                errors.append(f"{fragment.path} is missing new content")
            if fragment.expected_old_content is not None and current != fragment.expected_old_content:
                errors.append(f"{fragment.path} no longer matches expected base content")
            diff_by_path[fragment.path] = self._build_diff(
                fragment.path,
                current,
                fragment.new_content if fragment.operation != PatchOperation.DELETE else "",
            )

        for conflict in conflicts:
            if conflict.severity == "error":
                errors.append(conflict.message)
            else:
                warnings.append(conflict.message)

        accepted = boundary.allowed and not errors
        result = PatchValidationResult(
            proposal_id=proposal.proposal_id,
            accepted=accepted,
            errors=sorted(set(errors)),
            warnings=sorted(set(warnings)),
            boundary_decision=boundary,
            conflicts=conflicts,
            diff_by_path=diff_by_path,
        )
        self.event_bus.emit(
            RuntimeEventType.PATCH_VALIDATED if accepted else RuntimeEventType.PATCH_REJECTED,
            proposal_id=proposal.proposal_id,
            errors=result.errors,
            warnings=result.warnings,
        )
        return result

    def stage(
        self,
        agent: AgentSpec,
        proposal: PatchProposal,
    ) -> PatchValidationResult:
        result = self.validate(agent, proposal)
        if result.accepted:
            self._pending[proposal.proposal_id] = proposal
            self.event_bus.emit(
                RuntimeEventType.PATCH_PROPOSED,
                proposal_id=proposal.proposal_id,
                agent_id=proposal.agent_id,
                task_id=proposal.task_id,
            )
        return result

    def build_bundle(self, proposals: list[PatchProposal] | None = None) -> PatchBundle:
        return PatchBundle(
            proposals=proposals or list(self._pending.values()),
        )

    async def commit(
        self,
        bundle: PatchBundle,
        *,
        apply_changes: bool,
        verification_request: VerificationRequest | None = None,
    ) -> CommitDecision:
        verification_report: VerificationReport | None = None
        if self.verification_pipeline and verification_request:
            verification_report = await self.verification_pipeline.run(verification_request)
            if not verification_report.passed:
                return CommitDecision(
                    bundle_id=bundle.bundle_id,
                    status=CommitStatus.REJECTED,
                    rejected_reasons=["verification-failed"],
                    verification_passed=False,
                    verification_report=verification_report,
                )

        lock_requests = [
            LockRequest(
                resource_id=fragment.path,
                lock_type=LockType.WRITE,
                owner_id=f"commit:{bundle.bundle_id}",
            )
            for proposal in bundle.proposals
            for fragment in proposal.fragments
        ]
        leases = await self.lock_manager.acquire_many(lock_requests)
        try:
            preflight_errors = self._validate_bundle_against_workspace(bundle)
            if preflight_errors:
                self.event_bus.emit(
                    RuntimeEventType.PATCH_REJECTED,
                    bundle_id=bundle.bundle_id,
                    errors=preflight_errors,
                )
                return CommitDecision(
                    bundle_id=bundle.bundle_id,
                    status=CommitStatus.REJECTED,
                    rejected_reasons=sorted(set(preflight_errors)),
                    verification_passed=verification_report.passed if verification_report else True,
                    verification_report=verification_report,
                )
            applied_paths: list[str] = []
            if apply_changes:
                for proposal in bundle.proposals:
                    for fragment in proposal.fragments:
                        self._apply_fragment(fragment)
                        applied_paths.append(fragment.path)
                        self._pending.pop(proposal.proposal_id, None)
                self.artifact_store.put(
                    kind=ArtifactKind.PATCH_BUNDLE,
                    key=bundle.bundle_id,
                    content=bundle.model_dump(mode="json"),
                    created_by="integrator",
                )
                self.artifact_store.save()
                self.event_bus.emit(
                    RuntimeEventType.COMMIT_APPLIED,
                    bundle_id=bundle.bundle_id,
                    applied_paths=applied_paths,
                )
                return CommitDecision(
                    bundle_id=bundle.bundle_id,
                    status=CommitStatus.APPLIED,
                    applied_paths=sorted(set(applied_paths)),
                    verification_report=verification_report,
                )
            return CommitDecision(
                bundle_id=bundle.bundle_id,
                status=CommitStatus.DRY_RUN,
                applied_paths=sorted(set(bundle.changed_files())),
                verification_report=verification_report,
            )
        finally:
            await self.lock_manager.release_many(leases)

    def _validate_bundle_against_workspace(self, bundle: PatchBundle) -> list[str]:
        errors: list[str] = []
        for proposal in bundle.proposals:
            for fragment in proposal.fragments:
                file_path = self.workspace_root / fragment.path
                exists = file_path.exists()
                current = file_path.read_text(encoding="utf-8") if exists else ""
                if fragment.operation == PatchOperation.CREATE and exists:
                    errors.append(f"{fragment.path} already exists at commit time")
                if fragment.operation == PatchOperation.UPDATE and not exists:
                    errors.append(f"{fragment.path} disappeared before commit")
                if fragment.operation == PatchOperation.DELETE and not exists:
                    errors.append(f"{fragment.path} disappeared before delete commit")
                if fragment.operation in {PatchOperation.CREATE, PatchOperation.UPDATE} and fragment.new_content is None:
                    errors.append(f"{fragment.path} is missing new content")
                if fragment.expected_old_content is not None and current != fragment.expected_old_content:
                    errors.append(f"{fragment.path} changed after staging")
        return errors

    def _apply_fragment(self, fragment: PatchFragment) -> None:
        path = self.workspace_root / fragment.path
        if fragment.operation == PatchOperation.DELETE:
            if path.exists():
                path.unlink()
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        if fragment.new_content is None:
            raise ValueError(f"Patch fragment for {fragment.path} is missing new_content")
        path.write_text(fragment.new_content, encoding="utf-8")

    def _build_diff(self, path: str, old: str, new: str) -> str:
        diff = difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
        return "\n".join(diff)
