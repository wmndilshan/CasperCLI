from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from agent.team import OwnershipMode, ProjectProfile, TeamSynthesisOptions, TeamSynthesizer


class TeamSynthesizerTests(unittest.TestCase):
    def test_workspace_scan_ignores_virtualenv_and_build_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".venv").mkdir()
            (root / ".venv" / "ignored.py").write_text("print('ignored')\n", encoding="utf-8")
            (root / "dist").mkdir()
            (root / "dist" / "bundle.py").write_text("print('ignored')\n", encoding="utf-8")
            (root / "agent").mkdir()
            (root / "agent" / "service.py").write_text("print('backend')\n", encoding="utf-8")

            synthesizer = TeamSynthesizer()
            workspace = synthesizer.inspect_workspace(root)

            self.assertEqual(workspace.file_count, 1)
            self.assertEqual(workspace.dominant_languages, ["python"])

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
            backend = next(agent for agent in team.agents if agent.id == "backend")
            self.assertIn("grep", backend.allowed_tools)
            self.assertIn("glob", backend.allowed_tools)
            self.assertNotIn("grep_search", backend.allowed_tools)
            self.assertNotIn("glob_search", backend.allowed_tools)
