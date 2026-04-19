from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ConflictType(str, Enum):
    FILE_COLLISION = "file_collision"
    PATCH_OVERLAP = "patch_overlap"
    SEMANTIC = "semantic"
    STALE_WORK = "stale_work"
    RESOURCE = "resource"


class ConflictRecord(BaseModel):
    conflict_id: str
    type: ConflictType
    message: str
    files: list[str] = Field(default_factory=list)
    proposals: list[str] = Field(default_factory=list)
    severity: str = "error"
    resolution_hint: str = ""


class ConflictDetector:
    """Detects file, semantic, stale-work, and resource conflicts between patches."""

    def detect_proposal_conflicts(
        self,
        proposal,
        existing_proposals: list,
        artifact_versions: dict[str, int] | None = None,
    ) -> list[ConflictRecord]:
        conflicts: list[ConflictRecord] = []
        touched_by_path: dict[str, list[str]] = {}
        ranges_by_path: dict[str, list[tuple[int | None, int | None, str]]] = {}

        for existing in existing_proposals:
            for fragment in existing.fragments:
                touched_by_path.setdefault(fragment.path, []).append(existing.proposal_id)
                ranges_by_path.setdefault(fragment.path, []).append(
                    (fragment.line_start, fragment.line_end, existing.proposal_id)
                )

        for fragment in proposal.fragments:
            if fragment.path in touched_by_path:
                conflicts.append(
                    ConflictRecord(
                        conflict_id=f"conflict-file-{proposal.proposal_id}-{fragment.path}",
                        type=ConflictType.FILE_COLLISION,
                        message=f"Another proposal already touches {fragment.path}",
                        files=[fragment.path],
                        proposals=[proposal.proposal_id, *touched_by_path[fragment.path]],
                        resolution_hint="serialize-or-merge",
                    )
                )

            for start, end, other_id in ranges_by_path.get(fragment.path, []):
                if self._ranges_overlap(
                    fragment.line_start,
                    fragment.line_end,
                    start,
                    end,
                ):
                    conflicts.append(
                        ConflictRecord(
                            conflict_id=f"conflict-overlap-{proposal.proposal_id}-{fragment.path}",
                            type=ConflictType.PATCH_OVERLAP,
                            message=f"Line ranges overlap in {fragment.path}",
                            files=[fragment.path],
                            proposals=[proposal.proposal_id, other_id],
                            resolution_hint="ownership-or-manual-merge",
                        )
                    )

        if artifact_versions:
            for key, version in proposal.base_artifact_versions.items():
                if artifact_versions.get(key, version) != version:
                    conflicts.append(
                        ConflictRecord(
                            conflict_id=f"conflict-stale-{proposal.proposal_id}-{key}",
                            type=ConflictType.STALE_WORK,
                            message=f"Proposal {proposal.proposal_id} was produced against stale artifact {key}",
                            proposals=[proposal.proposal_id],
                            severity="warning",
                            resolution_hint="replan-or-regenerate",
                        )
                    )

        if proposal.contract_changes:
            for existing in existing_proposals:
                overlap = set(existing.contract_changes) & set(proposal.contract_changes)
                if overlap:
                    conflicts.append(
                        ConflictRecord(
                            conflict_id=f"conflict-semantic-{proposal.proposal_id}-{existing.proposal_id}",
                            type=ConflictType.SEMANTIC,
                            message=f"Contract changes overlap: {', '.join(sorted(overlap))}",
                            proposals=[proposal.proposal_id, existing.proposal_id],
                            severity="error",
                            resolution_hint="escalate-to-integrator",
                        )
                    )

        overlapping_resources = set(proposal.affected_resources)
        for existing in existing_proposals:
            shared_resources = overlapping_resources & set(existing.affected_resources)
            if shared_resources:
                conflicts.append(
                    ConflictRecord(
                        conflict_id=f"conflict-resource-{proposal.proposal_id}-{existing.proposal_id}",
                        type=ConflictType.RESOURCE,
                        message=f"Exclusive resources overlap: {', '.join(sorted(shared_resources))}",
                        proposals=[proposal.proposal_id, existing.proposal_id],
                        severity="warning",
                        resolution_hint="serialize-hotspot",
                    )
                )

        return conflicts

    def detect_file_conflicts(self, proposals: list) -> list[ConflictRecord]:
        conflicts: list[ConflictRecord] = []
        for index, proposal in enumerate(proposals):
            conflicts.extend(self.detect_proposal_conflicts(proposal, proposals[:index]))
        return conflicts

    def _ranges_overlap(
        self,
        start_a: int | None,
        end_a: int | None,
        start_b: int | None,
        end_b: int | None,
    ) -> bool:
        if None in {start_a, end_a, start_b, end_b}:
            return False
        return max(start_a, start_b) <= min(end_a, end_b)
