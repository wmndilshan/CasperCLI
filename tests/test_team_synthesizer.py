from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from agent.team import OwnershipMode, ProjectProfile, TeamSynthesisOptions, TeamSynthesizer


class TeamSynthesizerTests(unittest.TestCase):
    def test_auto_synthesis_builds_hybrid_team(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "agent").mkdir()
            (root / "agent" / "service.py").write_text("print('backend')\n", encoding="utf-8")
            (root / "ui").mkdir()
            (root / "ui" / "page.tsx").write_text("export const Page = () => null;\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "test_service.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

            synthesizer = TeamSynthesizer()
            team = synthesizer.synthesize(
                "add auth, dashboard, regression tests, and deployment docs",
                root,
                TeamSynthesisOptions(team="auto", team_size=5, strict=True),
            )

            self.assertEqual(team.project_profile, ProjectProfile.FULLSTACK)
            self.assertEqual(team.coordination_policy.ownership_mode, OwnershipMode.STRICT)
            self.assertIn("scheduler", {agent.id for agent in team.agents})
            self.assertIn("boundary", {agent.id for agent in team.agents})
            worker_roles = [agent.role for agent in team.agents if agent.type.value == "llm_worker"]
            self.assertIn("backend", worker_roles)
            self.assertIn("frontend", worker_roles)
            self.assertIn("qa", worker_roles)
