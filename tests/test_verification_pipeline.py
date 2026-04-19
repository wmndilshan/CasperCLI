from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from agent.verification import VerificationPipeline, VerificationRequest
from agent.verification.validators import BoundaryConsistencyValidator, ChangedFilesValidator


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
