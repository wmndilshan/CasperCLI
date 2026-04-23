from __future__ import annotations

from pathlib import Path

import structlog

from conflicts.detector import ConflictDetector
from models.schemas import ConflictRecord, PatchProposal, PatchStatus

logger = structlog.get_logger(__name__)


class PatchPipeline:
    """
    Transactional patch flow:
    1) propose -> 2) boundary validate -> 3) conflict check -> 4) merge/escalate -> 5) commit
    """

    def __init__(self, project_root: Path, strict: bool = True) -> None:
        self.project_root = project_root.resolve()
        self.strict = strict
        self._patches: dict[str, PatchProposal] = {}
        self._conflicts: list[ConflictRecord] = []
        self._detector = ConflictDetector()

    def list_proposals(self) -> list[PatchProposal]:
        return list(self._patches.values())

    def get(self, patch_id: str) -> PatchProposal | None:
        return self._patches.get(patch_id)

    def register_proposal(self, proposal: PatchProposal) -> PatchProposal:
        validated = self._validate_boundaries(proposal)
        self._patches[validated.id] = validated
        self._recompute_conflicts()
        return validated

    def approve(self, patch_id: str) -> PatchProposal:
        patch = self._patches[patch_id]
        patch.status = PatchStatus.APPROVED
        self._patches[patch_id] = patch
        return patch

    def reject(self, patch_id: str) -> PatchProposal:
        patch = self._patches[patch_id]
        patch.status = PatchStatus.REJECTED
        self._patches[patch_id] = patch
        self._recompute_conflicts()
        return patch

    def commit_approved(self) -> list[Path]:
        """Apply approved patches to disk (simple full-file replace for demo hunks)."""
        written: list[Path] = []
        for proposal in self._patches.values():
            if proposal.status != PatchStatus.APPROVED:
                continue
            for hunk in proposal.hunks:
                target = (self.project_root / hunk.path).resolve()
                if not str(target).startswith(str(self.project_root)):
                    raise ValueError(f"Path escapes project root: {hunk.path}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(hunk.content, encoding="utf-8")
                written.append(target)
            proposal.status = PatchStatus.COMMITTED
        return written

    def conflicts(self) -> list[ConflictRecord]:
        return list(self._conflicts)

    def resolve_conflict(self, conflict_id: str, resolution: str) -> None:
        for conflict in self._conflicts:
            if conflict.id == conflict_id:
                conflict.resolution = resolution
                return
        raise KeyError(conflict_id)

    def _validate_boundaries(self, proposal: PatchProposal) -> PatchProposal:
        for hunk in proposal.hunks:
            target = (self.project_root / hunk.path).resolve()
            if not str(target).startswith(str(self.project_root)):
                raise ValueError(f"Patch escapes workspace: {hunk.path}")
        return proposal

    def _recompute_conflicts(self) -> None:
        active = [p for p in self._patches.values() if p.status == PatchStatus.PROPOSED]
        found = self._detector.detect(active)
        schema_conflict = self._detector.schema_hint_conflict(active)
        if schema_conflict:
            found.append(schema_conflict)
        self._conflicts = found
        if self._conflicts:
            logger.info("conflicts_detected", count=len(self._conflicts))
