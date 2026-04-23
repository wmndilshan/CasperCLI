# Hybrid multi-agent desktop stack

This repository includes a **control-plane backend** (`backend/`) and an **Electron + React** IDE shell (`frontend/`) for the hybrid multi-agent runtime: team synthesis, DAG scheduling, locks, transactional patches, conflict detection, verification, and WebSocket events.

## Desktop UI layout

- **Left:** Activity bar + file explorer (and search).
- **Center:** Monaco editor (multi-tab, save to workspace API).
- **Right:** Runtime dashboard — agents, DAG, tasks, locks, **resources**, patches, conflicts, verification, teams.
- **Bottom:** Events (WebSocket), terminal hints, chat, problems, output.

## Architecture

```text
Electron (React + Monaco + Zustand + React Flow)
        │  REST + WebSocket
        ▼
FastAPI (`backend/api/main.py`)
        │
        ├── Team synthesizer (`runtime/team_synthesizer.py`)
        ├── Orchestrator + event bus (`runtime/orchestrator.py`, `runtime/event_bus.py`)
        ├── DAG scheduler — networkx (`scheduler/dag_scheduler.py`)
        ├── Lock manager — asyncio RW locks (`locks/manager.py`)
        ├── Patch pipeline (`patches/pipeline.py`)
        ├── Conflict detector (`conflicts/detector.py`)
        ├── Verification pipeline (`verification/pipeline.py`)
        └── Agent registry (`agents/` — LLM, rule, boundary, scheduler, execution, conflict, merge, verification, integrator)
```

Event types on `ws://…/ws/events` match the contract: `TASK_STARTED`, `TASK_COMPLETED`, `LOCK_ACQUIRED`, `PATCH_PROPOSED`, `CONFLICT_DETECTED`, `VERIFICATION_RESULT`.

## Prerequisites

- Python **3.10+** with `pip`
- Node.js **18+** and `npm`

## Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8765
```

Health check: `curl http://127.0.0.1:8765/health`

### Example API usage

```bash
# Synthesize team (optional before run; /run also builds a fresh team)
curl -s -X POST http://127.0.0.1:8765/team/synthesize \
  -H 'Content-Type: application/json' \
  -d '{"goal":"Harden patch pipeline","project_root":".","team_size":6,"strict":true}'

# Start hybrid DAG run (async)
curl -s -X POST http://127.0.0.1:8765/run \
  -H 'Content-Type: application/json' \
  -d '{"goal":"Demo parallel tasks","project_root":".","team_size":6,"strict":true,"parallel":true,"max_parallel_tasks":4}'

curl -s http://127.0.0.1:8765/run/status
curl -s http://127.0.0.1:8765/tasks
curl -s http://127.0.0.1:8765/locks
curl -s http://127.0.0.1:8765/resources
curl -s http://127.0.0.1:8765/patches
curl -s http://127.0.0.1:8765/conflicts
```

### Tests

```bash
cd backend
pip install -r requirements.txt
pytest
```

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

This starts **Vite** on port **5173** and launches **Electron** pointed at the dev server. The UI expects the API at `http://127.0.0.1:8765` (override with `VITE_API_URL`).

Production-ish build:

```bash
cd frontend
npm run build
NODE_ENV=production electron .
```

(Loads static files from `frontend/dist/`; ensure the backend is still reachable at the configured API URL.)

## Workspace files

The editor uses:

- `GET /workspace/list?path=…`
- `GET /workspace/file?path=…`
- `PUT /workspace/file` with JSON `{ "path", "content" }`

Paths are rooted at the **last synthesized or executed** `project_root` on the default session.

## Notes

- Agent “LLM” workers **simulate** patches (no external LLM call) so the DAG, locks, patch queue, conflicts, and verification wiring can be exercised end-to-end.
- Approve patches via `POST /patch/approve`, then optionally `POST /patch/commit` to write approved hunks under `project_root`.
- Verification runs `ruff`, `pytest`, and `npm run build` when those tools exist; otherwise steps are skipped with a log message.
