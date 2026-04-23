from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from api.session import SessionManager, SessionState
from api.ws_manager import WebSocketManager
from models.schemas import (
    ConflictResolveBody,
    PatchDecisionBody,
    RunRequest,
    SynthesizeTeamRequest,
    TeamSpec,
    WorkspaceWriteBody,
)
from runtime.event_bus import EventBus, new_session_id
from runtime.orchestrator import run_demo_session
from runtime.team_synthesizer import TeamSynthesizer

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger(__name__)

session_manager = SessionManager()
ws_manager = WebSocketManager()
DEFAULT_SESSION = "default"


async def get_default_session() -> SessionState:
    try:
        return await session_manager.get(DEFAULT_SESSION)
    except KeyError:
        raise HTTPException(status_code=500, detail="Session not initialized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    bus = EventBus()
    await session_manager.create(DEFAULT_SESSION, bus)
    await bus.subscribe(ws_manager.handle_bus_event)
    logger.info("backend_ready", session=DEFAULT_SESSION)
    yield


app = FastAPI(title="Casper Hybrid Desktop Control Plane", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/team/synthesize")
async def synthesize_team(
    body: SynthesizeTeamRequest, session: SessionState = Depends(get_default_session)
) -> TeamSpec:
    root = Path(body.project_root).resolve()
    synth = TeamSynthesizer()
    team = synth.synthesize(
        project_root=root,
        goal=body.goal,
        team_size=body.team_size,
        strict=body.strict,
        project_context=body.project_context,
    )
    await session_manager.update_team(session.session_id, team, root)
    return team


@app.get("/team")
async def get_team(session: SessionState = Depends(get_default_session)) -> TeamSpec:
    if not session.team:
        raise HTTPException(status_code=400, detail="Team not synthesized yet")
    return session.team


@app.get("/tasks")
async def list_tasks(session: SessionState = Depends(get_default_session)) -> dict[str, Any]:
    orch = session.orchestrator
    if not orch:
        return {"tasks": {}}
    return {"tasks": {k: v.model_dump(mode="json") for k, v in orch.tasks.items()}}


@app.get("/locks")
async def list_locks(session: SessionState = Depends(get_default_session)) -> dict[str, Any]:
    mgr = session.orchestrator.lock_manager if session.orchestrator else session.lock_manager
    return {"locks": mgr.snapshot()}


@app.get("/resources")
async def list_resources(session: SessionState = Depends(get_default_session)) -> dict[str, Any]:
    if session.orchestrator:
        return {"resources": session.orchestrator.resource_manager.snapshot()}
    return {"resources": []}


@app.get("/patches")
async def list_patches(session: SessionState = Depends(get_default_session)) -> dict[str, Any]:
    pipeline = session.patch_pipeline or (
        session.orchestrator.patch_pipeline if session.orchestrator else None
    )
    if not pipeline:
        return {"patches": []}
    return {"patches": [p.model_dump(mode="json") for p in pipeline.list_proposals()]}


@app.post("/patch/approve")
async def approve_patch(
    body: PatchDecisionBody, session: SessionState = Depends(get_default_session)
) -> dict[str, Any]:
    pipeline = _require_pipeline(session)
    patch = pipeline.approve(body.patch_id)
    return patch.model_dump(mode="json")


@app.post("/patch/reject")
async def reject_patch(
    body: PatchDecisionBody, session: SessionState = Depends(get_default_session)
) -> dict[str, Any]:
    pipeline = _require_pipeline(session)
    patch = pipeline.reject(body.patch_id)
    return patch.model_dump(mode="json")


@app.post("/patch/commit")
async def commit_patches(session: SessionState = Depends(get_default_session)) -> dict[str, Any]:
    pipeline = _require_pipeline(session)
    paths = pipeline.commit_approved()
    return {"written": [str(p) for p in paths]}


@app.get("/conflicts")
async def list_conflicts(session: SessionState = Depends(get_default_session)) -> dict[str, Any]:
    pipeline = _require_pipeline(session)
    return {"conflicts": [c.model_dump(mode="json") for c in pipeline.conflicts()]}


@app.post("/conflict/resolve")
async def resolve_conflict(
    body: ConflictResolveBody, session: SessionState = Depends(get_default_session)
) -> dict[str, str]:
    pipeline = _require_pipeline(session)
    pipeline.resolve_conflict(body.conflict_id, body.resolution)
    return {"status": "ok", "conflict_id": body.conflict_id}


def _require_pipeline(session: SessionState):
    pipeline = session.patch_pipeline or (
        session.orchestrator.patch_pipeline if session.orchestrator else None
    )
    if not pipeline:
        raise HTTPException(status_code=400, detail="Patch pipeline not initialized")
    return pipeline


async def _execute_run(session: SessionState, body: RunRequest) -> None:
    session.run_result = None
    root = Path(body.project_root).resolve()
    orch = await run_demo_session(
        session_id=session.session_id,
        bus=session.bus,
        goal=body.goal,
        project_root=root,
        team_size=body.team_size,
        strict=body.strict,
        parallel=body.parallel,
        max_parallel_tasks=body.max_parallel_tasks,
        project_context="",
    )
    await session_manager.attach_orchestrator(session.session_id, orch)
    result = await orch.run()
    session.run_result = result


@app.post("/run")
async def run_hybrid(
    body: RunRequest, session: SessionState = Depends(get_default_session)
) -> dict[str, Any]:
    if session.run_task and not session.run_task.done():
        raise HTTPException(status_code=409, detail="Run already in progress")

    session.run_task = asyncio.create_task(_execute_run(session, body))
    return {"status": "started", "session_id": session.session_id}


@app.get("/run/status")
async def run_status(session: SessionState = Depends(get_default_session)) -> dict[str, Any]:
    if not session.run_task:
        return {"status": "idle"}
    if not session.run_task.done():
        return {"status": "running"}
    exc = session.run_task.exception()
    if exc:
        return {"status": "failed", "error": str(exc)}
    return {"status": "completed", "result": session.run_result}


@app.get("/workspace/list")
async def workspace_list(
    path: str = ".", session: SessionState = Depends(get_default_session)
) -> dict[str, Any]:
    root = _workspace_root(session)
    target = (root / path).resolve()
    if not str(target).startswith(str(root)):
        raise HTTPException(status_code=400, detail="Path escapes workspace")
    if not target.exists():
        raise HTTPException(status_code=404, detail="Not found")
    entries: list[dict[str, Any]] = []
    if target.is_dir():
        for child in sorted(target.iterdir()):
            if child.name.startswith(".") and child.name not in {".casper"}:
                continue
            entries.append(
                {
                    "name": child.name,
                    "path": str(child.relative_to(root)),
                    "is_dir": child.is_dir(),
                }
            )
    return {"root": str(root), "path": str(target.relative_to(root)), "entries": entries}


@app.get("/workspace/file")
async def workspace_read(
    path: str, session: SessionState = Depends(get_default_session)
) -> dict[str, Any]:
    root = _workspace_root(session)
    target = (root / path).resolve()
    if not str(target).startswith(str(root)):
        raise HTTPException(status_code=400, detail="Path escapes workspace")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Not a file")
    return {
        "path": str(target.relative_to(root)),
        "content": target.read_text(encoding="utf-8", errors="replace"),
    }


@app.put("/workspace/file")
async def workspace_write(
    body: WorkspaceWriteBody,
    session: SessionState = Depends(get_default_session),
) -> dict[str, str]:
    root = _workspace_root(session)
    target = (root / body.path).resolve()
    if not str(target).startswith(str(root)):
        raise HTTPException(status_code=400, detail="Path escapes workspace")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body.content, encoding="utf-8")
    return {"status": "ok", "path": str(target.relative_to(root))}


def _workspace_root(session: SessionState) -> Path:
    if session.team:
        return Path(session.team.project_root).resolve()
    return Path(".").resolve()


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def main() -> None:
    uvicorn.run("api.main:app", host="0.0.0.0", port=8765, reload=False)


if __name__ == "__main__":
    main()
