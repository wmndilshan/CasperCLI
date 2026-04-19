from __future__ import annotations

from abc import ABC, abstractmethod

from agent.verification.pipeline import VerificationOutcome, VerificationRequest


class BaseValidator(ABC):
    name = "base"

    @abstractmethod
    async def run(self, request: VerificationRequest) -> VerificationOutcome:
        raise NotImplementedError
