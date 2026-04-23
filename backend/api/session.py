from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from locks.manager import FileLockManager
from models.schemas import TeamSpec
from patches.pipeline import PatchPipeline
from runtime.event_bus import EventBus
from runtime.orchestrator import HybridOrchestrator


@dataclass
class SessionState:
    session_id: str
    bus: EventBus
    team: TeamSpec | None = None
    orchestrator: HybridOrchestrator | None = None
    run_task: asyncio.Task | None = None
    run_result: dict | None = None
    lock_manager: FileLockManager = field(default_factory=FileLockManager)
    patch_pipeline: PatchPipeline | None = None


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = asyncio.Lock()

    async def create(self, session_id: str, bus: EventBus) -> SessionState:
        async with self._lock:
            state = SessionState(session_id=session_id, bus=bus)
            self._sessions[session_id] = state
            return state

    async def get(self, session_id: str) -> SessionState:
        async with self._lock:
            return self._sessions[session_id]

    async def update_team(self, session_id: str, team: TeamSpec, project_root: Path) -> SessionState:
        async with self._lock:
            state = self._sessions[session_id]
            state.team = team
            state.patch_pipeline = PatchPipeline(project_root, strict=team.ownership.strict)
            state.lock_manager = FileLockManager()
            return state

    async def attach_orchestrator(self, session_id: str, orchestrator: HybridOrchestrator) -> None:
        async with self._lock:
            state = self._sessions[session_id]
            state.orchestrator = orchestrator
            state.team = orchestrator.team
            state.patch_pipeline = orchestrator.patch_pipeline
            state.lock_manager = orchestrator.lock_manager
