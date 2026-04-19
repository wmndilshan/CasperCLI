from __future__ import annotations

import sys
import tempfile
from pathlib import Path
import unittest

from agent.runtime.orchestrator import HybridOrchestrator
from agent.team import TeamSynthesisOptions, VerificationMode
from agent.verification import VerificationPipeline, VerificationRequest
from agent.verification.validators import (
    BoundaryConsistencyValidator,
    ChangedFilesValidator,
    CommandValidator,
)


class VerificationPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_pipeline_dispatches_all_validators(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            request = VerificationRequest(
                session_id="session",
                workspace_root=Path(tmp_dir),
                goal="goal",
                changed_files=["app.py"],
                mode="strict",
            )
            pipeline = VerificationPipeline(
                [ChangedFilesValidator(), BoundaryConsistencyValidator()]
            )

            report = await pipeline.run(request)

            self.assertTrue(report.passed)
            self.assertEqual([outcome.validator for outcome in report.outcomes], ["changed_files", "boundary_consistency"])

    async def test_orchestrator_scopes_verification_commands_to_project_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".venv").mkdir()
            (root / ".venv" / "ignored.py").write_text("print('ignored')\n", encoding="utf-8")
            (root / "agent").mkdir()
            (root / "agent" / "service.py").write_text("print('ok')\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "test_service.py").write_text(
                "def test_ok():\n    assert True\n",
                encoding="utf-8",
            )
            (root / "main.py").write_text("print('main')\n", encoding="utf-8")

            orchestrator = HybridOrchestrator(root)
            team_spec = orchestrator.inspect_team(
                "improve service",
                TeamSynthesisOptions(
                    team="backend-platform",
                    team_size=3,
                    strict=True,
                    verification_mode=VerificationMode.STRICT,
                ),
            )
            pipeline = orchestrator._build_verification_pipeline(team_spec, root)
            commands = [
                validator.command
                for validator in pipeline.validators
                if isinstance(validator, CommandValidator)
            ]

            self.assertIn(
                f"{sys.executable} -m unittest discover -s tests",
                commands,
            )
            syntax_command = next(
                command for command in commands if f"{sys.executable} -m compileall" in command
            )
            compile_targets = syntax_command.split(" -m compileall ", maxsplit=1)[1]
            self.assertIn("agent", syntax_command)
            self.assertIn("tests", syntax_command)
            self.assertIn("main.py", syntax_command)
            self.assertNotIn(".venv", compile_targets)
            self.assertNotIn("compileall .", syntax_command)
