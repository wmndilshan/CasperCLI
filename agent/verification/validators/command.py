from __future__ import annotations

import asyncio
import shlex

from agent.verification.pipeline import VerificationOutcome, VerificationRequest
from agent.verification.validators.base import BaseValidator


class CommandValidator(BaseValidator):
    def __init__(self, name: str, command: str) -> None:
        self.name = name
        self.command = command

    async def run(self, request: VerificationRequest) -> VerificationOutcome:
        proc = await asyncio.create_subprocess_exec(
            *shlex.split(self.command),
            cwd=str(request.workspace_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        passed = proc.returncode == 0
        return VerificationOutcome(
            validator=self.name,
            passed=passed,
            status="passed" if passed else "failed",
            summary=self.command,
            details={
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "returncode": proc.returncode,
            },
        )


class ChangedFilesValidator(BaseValidator):
    name = "changed_files"

    async def run(self, request: VerificationRequest) -> VerificationOutcome:
        passed = bool(request.changed_files)
        return VerificationOutcome(
            validator=self.name,
            passed=passed,
            status="passed" if passed else "failed",
            summary="changed files are present" if passed else "no changed files submitted",
        )


class BoundaryConsistencyValidator(BaseValidator):
    name = "boundary_consistency"

    async def run(self, request: VerificationRequest) -> VerificationOutcome:
        duplicates = {
            path for path in request.changed_files if request.changed_files.count(path) > 1
        }
        passed = not duplicates
        return VerificationOutcome(
            validator=self.name,
            passed=passed,
            status="passed" if passed else "failed",
            summary="changed files have no duplicate ownership entries"
            if passed
            else f"duplicate changed files detected: {', '.join(sorted(duplicates))}",
        )
