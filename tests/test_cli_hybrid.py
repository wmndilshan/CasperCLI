from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from click.testing import CliRunner

from main import hybrid_main


class HybridCLITests(unittest.TestCase):
    def test_inspect_team_command_parses_new_flags(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "agent").mkdir()
            (root / "agent" / "service.py").write_text("print('ok')\n", encoding="utf-8")
            result = runner.invoke(
                hybrid_main,
                [
                    "inspect-team",
                    "--goal",
                    "build auth",
                    "--cwd",
                    str(root),
                    "--team",
                    "fullstack",
                    "--team-size",
                    "5",
                    "--strict",
                    "--verify",
                    "strict",
                    "--ownership-mode",
                    "flexible",
                ],
            )

            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertIn("Hybrid Team", result.output)

    def test_run_command_executes_hybrid_runtime(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
            result = runner.invoke(
                hybrid_main,
                [
                    "run",
                    "improve app",
                    "--cwd",
                    str(root),
                    "--team",
                    "solo",
                    "--team-size",
                    "1",
                    "--dry-run",
                    "--show-task-graph",
                    "--show-team",
                ],
            )

            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertIn("Hybrid session", result.output)
            self.assertIn("Task Graph", result.output)
