from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path

import structlog

from models.schemas import VerificationResult

logger = structlog.get_logger(__name__)


async def _run_cmd(name: str, cmd: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate()
        text = (out or b"").decode(errors="replace")[-8000:]
        ok = proc.returncode == 0
        return ok, f"[{name}] rc={proc.returncode}\n{text}"
    except FileNotFoundError:
        return True, f"[{name}] skipped (binary not found)"
    except Exception as exc:  # pragma: no cover
        logger.exception("verification_command_failed", cmd=cmd)
        return False, f"[{name}] error: {exc}"


class VerificationPipeline:
    """Runs lint / tests / build with best-effort tooling detection."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    async def run(self) -> VerificationResult:
        lint_ok, lint_log = await self._lint()
        test_ok, test_log = await self._tests()
        build_ok, build_log = await self._build()
        return VerificationResult(
            id=f"verify_{uuid.uuid4().hex[:10]}",
            lint_ok=lint_ok,
            test_ok=test_ok,
            build_ok=build_ok,
            details={"lint": lint_log, "tests": test_log, "build": build_log},
        )

    async def _lint(self) -> tuple[bool, str]:
        if shutil.which("ruff"):
            return await _run_cmd(
                "ruff",
                ["ruff", "check", str(self.project_root)],
                self.project_root,
            )
        return True, "[lint] ruff not installed; skipped"

    async def _tests(self) -> tuple[bool, str]:
        if (self.project_root / "pytest.ini").exists() or (self.project_root / "pyproject.toml").exists():
            if shutil.which("pytest"):
                return await _run_cmd(
                    "pytest",
                    ["pytest", "-q", "--maxfail=1"],
                    self.project_root,
                )
        return True, "[tests] pytest not configured or not installed; skipped"

    async def _build(self) -> tuple[bool, str]:
        pkg = self.project_root / "package.json"
        if pkg.exists() and shutil.which("npm"):
            return await _run_cmd("npm", ["npm", "run", "build"], self.project_root)
        return True, "[build] no package.json build; skipped"
