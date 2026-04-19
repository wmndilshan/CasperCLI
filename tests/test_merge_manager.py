from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from agent.policies.boundary_rules import BoundaryPolicyEngine
from agent.runtime.conflict_detector import ConflictDetector
from agent.runtime.conflict_detector import ConflictType
from agent.runtime.merge_manager import MergeManager, MergeStrategy
from agent.runtime.patch_pipeline import PatchFragment, PatchOperation, PatchProposal
from agent.team import TeamSynthesisOptions, TeamSynthesizer


class MergeManagerTests(unittest.TestCase):
    def test_same_owner_overlaps_still_escalate_in_ownership_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "agent").mkdir()
            (root / "agent" / "service.py").write_text("print('old')\n", encoding="utf-8")

            team = TeamSynthesizer().synthesize(
                "update backend",
                root,
                TeamSynthesisOptions(team="backend-platform", team_size=4, strict=True),
            )
            boundary = BoundaryPolicyEngine(team)
            manager = MergeManager(
                conflict_detector=ConflictDetector(),
                boundary_engine=boundary,
            )

            first = PatchProposal(
                agent_id="backend",
                task_id="implement-backend",
                title="first",
                rationale="first",
                fragments=[
                    PatchFragment(
                        path="agent/service.py",
                        operation=PatchOperation.UPDATE,
                        new_content="print('one')\n",
                        line_start=1,
                        line_end=2,
                    )
                ],
            )
            second = PatchProposal(
                agent_id="backend",
                task_id="implement-backend-2",
                title="second",
                rationale="second",
                fragments=[
                    PatchFragment(
                        path="agent/service.py",
                        operation=PatchOperation.UPDATE,
                        new_content="print('two')\n",
                        line_start=1,
                        line_end=2,
                    )
                ],
            )

            result = manager.merge([first, second], strategy=MergeStrategy.OWNERSHIP_WINS)
            self.assertTrue(result.escalated)
            self.assertTrue(any(conflict.type == ConflictType.PATCH_OVERLAP for conflict in result.conflicts))
