from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from agent.artifacts.store import ArtifactStore
from agent.policies.boundary_rules import BoundaryPolicyEngine
from agent.runtime.conflict_detector import ConflictDetector
from agent.runtime.lock_manager import LockManager
from agent.runtime.patch_pipeline import PatchFragment, PatchOperation, PatchPipeline, PatchProposal
from agent.team import TeamSynthesisOptions, TeamSynthesizer
from agent.verification import VerificationPipeline


class PatchPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_validation_and_commit_flow_applies_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("print('old')\n", encoding="utf-8")

            team = TeamSynthesizer().synthesize(
                "update app",
                root,
                TeamSynthesisOptions(team="solo", team_size=1),
            )
            generalist = next(agent for agent in team.agents if agent.id == "generalist")
            pipeline = PatchPipeline(
                workspace_root=root,
                lock_manager=LockManager(),
                boundary_engine=BoundaryPolicyEngine(team),
                conflict_detector=ConflictDetector(),
                artifact_store=ArtifactStore(),
                verification_pipeline=VerificationPipeline([]),
            )
            proposal = PatchProposal(
                agent_id="generalist",
                task_id="implement-generalist",
                title="update app",
                rationale="simple edit",
                fragments=[
                    PatchFragment(
                        path="app.py",
                        operation=PatchOperation.UPDATE,
                        expected_old_content="print('old')\n",
                        new_content="print('new')\n",
                    )
                ],
            )

            validation = pipeline.stage(generalist, proposal)
            self.assertTrue(validation.accepted)

            decision = await pipeline.commit(
                pipeline.build_bundle(),
                apply_changes=True,
            )

            self.assertEqual(decision.status.value, "applied")
            self.assertEqual((root / "app.py").read_text(encoding="utf-8"), "print('new')\n")

    async def test_validation_rejects_stale_expected_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("print('actual')\n", encoding="utf-8")

            team = TeamSynthesizer().synthesize(
                "update app",
                root,
                TeamSynthesisOptions(team="solo", team_size=1),
            )
            generalist = next(agent for agent in team.agents if agent.id == "generalist")
            pipeline = PatchPipeline(
                workspace_root=root,
                lock_manager=LockManager(),
                boundary_engine=BoundaryPolicyEngine(team),
                conflict_detector=ConflictDetector(),
                artifact_store=ArtifactStore(),
            )
            proposal = PatchProposal(
                agent_id="generalist",
                task_id="implement-generalist",
                title="stale edit",
                rationale="should fail",
                fragments=[
                    PatchFragment(
                        path="app.py",
                        operation=PatchOperation.UPDATE,
                        expected_old_content="print('old')\n",
                        new_content="print('new')\n",
                    )
                ],
            )

            validation = pipeline.validate(generalist, proposal)
            self.assertFalse(validation.accepted)
            self.assertIn("app.py no longer matches expected base content", validation.errors)

    async def test_commit_rejects_changes_that_became_stale_after_staging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            file_path = root / "app.py"
            file_path.write_text("print('old')\n", encoding="utf-8")

            team = TeamSynthesizer().synthesize(
                "update app",
                root,
                TeamSynthesisOptions(team="solo", team_size=1),
            )
            generalist = next(agent for agent in team.agents if agent.id == "generalist")
            pipeline = PatchPipeline(
                workspace_root=root,
                lock_manager=LockManager(),
                boundary_engine=BoundaryPolicyEngine(team),
                conflict_detector=ConflictDetector(),
                artifact_store=ArtifactStore(),
            )
            proposal = PatchProposal(
                agent_id="generalist",
                task_id="implement-generalist",
                title="update app",
                rationale="staged before concurrent edit",
                fragments=[
                    PatchFragment(
                        path="app.py",
                        operation=PatchOperation.UPDATE,
                        expected_old_content="print('old')\n",
                        new_content="print('new')\n",
                    )
                ],
            )

            validation = pipeline.stage(generalist, proposal)
            self.assertTrue(validation.accepted)
            file_path.write_text("print('concurrent')\n", encoding="utf-8")

            decision = await pipeline.commit(
                pipeline.build_bundle(),
                apply_changes=True,
            )

            self.assertEqual(decision.status.value, "rejected")
            self.assertIn("app.py changed after staging", decision.rejected_reasons)
            self.assertEqual(file_path.read_text(encoding="utf-8"), "print('concurrent')\n")
