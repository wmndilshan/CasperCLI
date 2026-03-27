from __future__ import annotations

import json
from pathlib import Path

from agent.multi_agent.models import AgentProfile


class AgentProfileStore:
    def __init__(self) -> None:
        self._path = Path.cwd() / ".CasperCode" / "agent_profiles.json"

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> list[AgentProfile]:
        if not self._path.exists():
            return []

        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            rows = payload.get("agents", [])
            return [AgentProfile(**row) for row in rows]
        except Exception:
            return []

    def save(self, agents: list[AgentProfile]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"agents": [agent.model_dump(mode="json") for agent in agents]}
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def upsert(self, agent: AgentProfile) -> None:
        agents = self.load()
        remaining = [
            item
            for item in agents
            if item.agent_id != agent.agent_id and item.name.lower() != agent.name.lower()
        ]
        remaining.append(agent)
        self.save(remaining)

    def delete(self, identifier: str) -> bool:
        agents = self.load()
        remaining = [
            item
            for item in agents
            if item.agent_id != identifier and item.name.lower() != identifier.lower()
        ]

        if len(remaining) == len(agents):
            return False

        self.save(remaining)
        return True
