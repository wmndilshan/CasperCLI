from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from agent.runtime.events import RuntimeEventBus, RuntimeEventType


class VerificationRequest(BaseModel):
    session_id: str
    workspace_root: Path
    goal: str
    changed_files: list[str] = Field(default_factory=list)
    bundle_id: str | None = None
    mode: str = "lightweight"
    commands: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class VerificationOutcome(BaseModel):
    validator: str
    passed: bool
    status: str
    summary: str
    details: dict[str, object] = Field(default_factory=dict)


class VerificationReport(BaseModel):
    mode: str
    passed: bool
    started_at: datetime
    finished_at: datetime
    outcomes: list[VerificationOutcome] = Field(default_factory=list)


class Validator(Protocol):
    name: str

    async def run(self, request: VerificationRequest) -> VerificationOutcome: ...


class VerificationPipeline:
    def __init__(
        self,
        validators: list[Validator] | None = None,
        *,
        event_bus: RuntimeEventBus | None = None,
    ) -> None:
        self.validators = validators or []
        self.event_bus = event_bus

    async def run(self, request: VerificationRequest) -> VerificationReport:
        started_at = datetime.now(timezone.utc)
        outcomes: list[VerificationOutcome] = []
        if self.event_bus:
            self.event_bus.emit(
                RuntimeEventType.VERIFICATION_STARTED,
                session_id=request.session_id,
                mode=request.mode,
                bundle_id=request.bundle_id,
            )

        for validator in self.validators:
            outcome = await validator.run(request)
            outcomes.append(outcome)
            if self.event_bus and not outcome.passed:
                self.event_bus.emit(
                    RuntimeEventType.VERIFICATION_FAILED,
                    session_id=request.session_id,
                    validator=validator.name,
                    summary=outcome.summary,
                )

        return VerificationReport(
            mode=request.mode,
            passed=all(outcome.passed for outcome in outcomes) if outcomes else True,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            outcomes=outcomes,
        )
