from __future__ import annotations

import unittest

from agent.runtime.conflict_detector import ConflictDetector, ConflictType
from agent.runtime.patch_pipeline import PatchFragment, PatchOperation, PatchProposal


class ConflictDetectorTests(unittest.TestCase):
    def test_file_and_patch_overlap_conflicts_are_detected(self) -> None:
        detector = ConflictDetector()
        first = PatchProposal(
            agent_id="backend",
            task_id="implement-backend",
            title="first",
            rationale="first",
            fragments=[
                PatchFragment(
                    path="app.py",
                    operation=PatchOperation.UPDATE,
                    new_content="print('one')\n",
                    line_start=1,
                    line_end=2,
                )
            ],
        )
        second = PatchProposal(
            agent_id="frontend",
            task_id="implement-frontend",
            title="second",
            rationale="second",
            fragments=[
                PatchFragment(
                    path="app.py",
                    operation=PatchOperation.UPDATE,
                    new_content="print('two')\n",
                    line_start=2,
                    line_end=3,
                )
            ],
        )

        conflicts = detector.detect_file_conflicts([first, second])
        conflict_types = {conflict.type for conflict in conflicts}
        self.assertIn(ConflictType.FILE_COLLISION, conflict_types)
        self.assertIn(ConflictType.PATCH_OVERLAP, conflict_types)

    def test_semantic_and_stale_conflicts_are_detected(self) -> None:
        detector = ConflictDetector()
        existing = PatchProposal(
            agent_id="backend",
            task_id="implement-backend",
            title="api change",
            rationale="api",
            contract_changes=["api:v1"],
            fragments=[
                PatchFragment(
                    path="app.py",
                    operation=PatchOperation.UPDATE,
                    new_content="print('api')\n",
                )
            ],
        )
        proposed = PatchProposal(
            agent_id="backend",
            task_id="implement-backend",
            title="stale api change",
            rationale="api",
            contract_changes=["api:v1"],
            base_artifact_versions={"architecture_spec:main": 1},
            fragments=[
                PatchFragment(
                    path="service.py",
                    operation=PatchOperation.UPDATE,
                    new_content="print('service')\n",
                )
            ],
        )

        conflicts = detector.detect_proposal_conflicts(
            proposed,
            [existing],
            artifact_versions={"architecture_spec:main": 2},
        )
        conflict_types = {conflict.type for conflict in conflicts}
        self.assertIn(ConflictType.SEMANTIC, conflict_types)
        self.assertIn(ConflictType.STALE_WORK, conflict_types)
