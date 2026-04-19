from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from agent.policies.boundary_rules import BoundaryPolicyEngine
from agent.runtime.conflict_detector import ConflictDetector, ConflictRecord, ConflictType
from agent.runtime.events import RuntimeEventBus, RuntimeEventType
from agent.runtime.patch_pipeline import PatchBundle, PatchProposal


class MergeStrategy(str, Enum):
    AUTO_SAFE = "auto_safe"
    OWNERSHIP_WINS = "ownership_wins"
    ESCALATE = "escalate"
    SERIALIZE = "serialize"


class MergeResult(BaseModel):
    bundle: PatchBundle
    conflicts: list[ConflictRecord] = Field(default_factory=list)
    strategy: MergeStrategy = MergeStrategy.AUTO_SAFE
    escalated: bool = False


class MergeManager:
    def __init__(
        self,
        *,
        conflict_detector: ConflictDetector,
        boundary_engine: BoundaryPolicyEngine,
        event_bus: RuntimeEventBus | None = None,
    ) -> None:
        self.conflict_detector = conflict_detector
        self.boundary_engine = boundary_engine
        self.event_bus = event_bus or RuntimeEventBus()

    def merge(
        self,
        proposals: list[PatchProposal],
        *,
        strategy: MergeStrategy = MergeStrategy.AUTO_SAFE,
    ) -> MergeResult:
        if not proposals:
            return MergeResult(bundle=PatchBundle(proposals=[]), strategy=strategy)

        conflicts = self.conflict_detector.detect_file_conflicts(proposals)
        merged: list[PatchProposal] = []

        if not conflicts:
            merged = proposals
        elif strategy == MergeStrategy.OWNERSHIP_WINS:
            by_file: dict[str, PatchProposal] = {}
            unresolved_conflicts: list[ConflictRecord] = []
            for proposal in proposals:
                accepted = True
                for fragment in proposal.fragments:
                    owner = self.boundary_engine.owner_for_path(fragment.path)
                    if owner and owner != proposal.agent_id:
                        accepted = False
                        break
                    existing = by_file.get(fragment.path)
                    if existing and existing.proposal_id != proposal.proposal_id:
                        accepted = False
                        unresolved_conflicts.append(
                            ConflictRecord(
                                conflict_id=f"conflict-ownership-overlap-{existing.proposal_id}-{proposal.proposal_id}-{fragment.path}",
                                type=ConflictType.PATCH_OVERLAP,
                                message=f"Ownership-wins cannot auto-merge overlapping proposals for {fragment.path}",
                                files=[fragment.path],
                                proposals=[existing.proposal_id, proposal.proposal_id],
                                severity="error",
                                resolution_hint="escalate-to-integrator",
                            )
                        )
                        break
                if accepted:
                    merged.append(proposal)
                    for fragment in proposal.fragments:
                        by_file[fragment.path] = proposal
            conflicts = [
                conflict
                for conflict in conflicts
                if not all(path in by_file for path in conflict.files)
            ]
            conflicts.extend(unresolved_conflicts)
        else:
            merged = [
                proposal
                for proposal in proposals
                if not any(
                    fragment.path in {path for conflict in conflicts for path in conflict.files}
                    for fragment in proposal.fragments
                )
            ]

        escalated = bool(conflicts)
        result = MergeResult(
            bundle=PatchBundle(proposals=merged),
            conflicts=conflicts,
            strategy=strategy,
            escalated=escalated,
        )
        self.event_bus.emit(
            RuntimeEventType.MERGE_COMPLETED,
            bundle_id=result.bundle.bundle_id,
            conflict_count=len(conflicts),
            strategy=strategy.value,
            escalated=escalated,
        )
        return result
