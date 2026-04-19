from __future__ import annotations

from typing import Callable

from agent.agents.base import BaseRuntimeAgent


class RuleBasedAgent(BaseRuntimeAgent):
    def evaluate(
        self,
        payload: dict[str, object],
        rules: list[Callable[[dict[str, object]], bool]],
    ) -> bool:
        return all(rule(payload) for rule in rules)
