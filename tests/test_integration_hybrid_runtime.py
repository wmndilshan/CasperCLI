from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from agent.runtime.orchestrator import HybridOrchestrator, HybridRunRequest
from agent.runtime.patch_pipeline import PatchFragment, PatchOperation, PatchProposal
from agent.team import VerificationMode


class HybridRuntimeIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_hybrid_run_commits_transactional_patch_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("print('old')\n", encoding="utf-8")

            orchestrator = HybridOrchestrator(root)
            proposal = PatchProposal(
                agent_id="generalist",
                task_id="implement-generalist",
                title="upgrade file",
                rationale="integration",
                fragments=[
                    PatchFragment(
                        path="app.py",
                        operation=PatchOperation.UPDATE,
                        expected_old_content="print('old')\n",
                        new_content="print('new')\n",
                    )
                ],
            )
            result = await orchestrator.run(
                HybridRunRequest(
                    goal="improve app",
                    workspace_root=root,
                    team="solo",
                    team_size=1,
                    verify=VerificationMode.LIGHTWEIGHT,
                    apply_patches=True,
                    task_patches={"implement-generalist": [proposal]},
                )
            )

            self.assertIsNotNone(result.commit_decision)
            self.assertEqual(result.commit_decision.status.value, "applied")
            self.assertEqual((root / "app.py").read_text(encoding="utf-8"), "print('new')\n")
            self.assertEqual(result.pending_proposals, [])
            event_types = {event.type.value for event in result.event_log}
            self.assertIn("team_synthesized", event_types)
            self.assertIn("task_graph_created", event_types)
            self.assertIn("commit_applied", event_types)
