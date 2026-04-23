from __future__ import annotations

import uuid
from typing import Iterable

from models.schemas import ConflictRecord, FileHunk, PatchProposal


def _ranges_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return not (a_end < b_start or b_end < a_start)


class ConflictDetector:
    """Detect overlapping edits on the same file (line-range overlap)."""

    def detect(self, patches: Iterable[PatchProposal]) -> list[ConflictRecord]:
        by_file: dict[str, list[tuple[PatchProposal, FileHunk]]] = {}
        for patch in patches:
            if patch.status.value in {"rejected"}:
                continue
            for hunk in patch.hunks:
                by_file.setdefault(hunk.path, []).append((patch, hunk))

        conflicts: list[ConflictRecord] = []
        for path, entries in by_file.items():
            for i, (p1, h1) in enumerate(entries):
                for p2, h2 in entries[i + 1 :]:
                    if p1.id == p2.id:
                        continue
                    if _ranges_overlap(h1.start_line, h1.end_line, h2.start_line, h2.end_line):
                        conflicts.append(
                            ConflictRecord(
                                id=f"conflict_{uuid.uuid4().hex[:8]}",
                                patch_ids=sorted({p1.id, p2.id}),
                                description=(
                                    f"Overlapping edits in {path} between patches "
                                    f"{p1.id} and {p2.id}"
                                ),
                                files=[path],
                                resolution=None,
                            )
                        )
        return conflicts

    def schema_hint_conflict(self, patches: Iterable[PatchProposal]) -> ConflictRecord | None:
        """Lightweight placeholder for API/schema mismatch detection."""
        metas = [p.metadata.get("schema_signature") for p in patches if p.metadata]
        signatures = [m for m in metas if m]
        if len(set(signatures)) > 1:
            patch_ids = [p.id for p in patches]
            return ConflictRecord(
                id=f"conflict_{uuid.uuid4().hex[:8]}",
                patch_ids=patch_ids,
                description="Conflicting schema signatures across patches",
                files=[],
                resolution=None,
            )
        return None
