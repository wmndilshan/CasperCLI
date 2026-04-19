# Hybrid Multi-Agent Coding OS

## Architecture Diagnosis

The repository already had strong primitives:

- a working terminal chat agent loop
- tool registry and approval controls
- multi-agent role metadata and A2A messaging
- persistence/checkpointing scaffolding
- a redesign document pointing toward a richer runtime

The main production gaps were runtime, not ambition:

- tool work was effectively sequential
- role assignments were advisory rather than enforced
- task execution had no real DAG scheduler
- there were no file/resource leases
- patch application was direct and non-transactional
- conflict handling was mostly social, not deterministic
- verification was not a first-class integration gate

## Migration Plan

Phase 1:

- add structured team synthesis models and presets
- add policy-bound scopes and ownership rules
- add file/resource locking foundations
- add structured patch proposal models

Phase 2:

- add task graph, ready queue, and concurrent scheduler
- compile synthesized teams into runtime agent objects
- attach resource-aware scheduling and event emission

Phase 3:

- add conflict detection and merge policies
- add transactional patch validation and commit flow
- add verification pipeline and validator dispatch

Phase 4:

- wire the runtime into CLI commands
- persist hybrid sessions for inspection and replay
- add tests, examples, and operator documentation

## Implemented Subsystems

New packages now live under `agent/`:

- `agent/team/`
  - `models.py`
  - `presets.py`
  - `synthesizer.py`
  - `compiler.py`
- `agent/agents/`
  - base runtime agents
  - boundary, scheduler, merge, verifier, integrator adapters
- `agent/runtime/`
  - `events.py`
  - `task_graph.py`
  - `scheduler.py`
  - `lock_manager.py`
  - `resource_manager.py`
  - `conflict_detector.py`
  - `merge_manager.py`
  - `patch_pipeline.py`
  - `session_store.py`
  - upgraded `orchestrator.py`
- `agent/artifacts/`
  - structured shared artifacts and persistence
- `agent/policies/`
  - boundary and ownership enforcement
- `agent/verification/`
  - configurable verification pipeline and validators
- `agent/sessions/`
  - compatibility shim for the legacy task-graph import path

## Runtime Flow

1. `TeamSynthesizer` inspects the repo and goal, then emits a structured `TeamSpec`.
2. `HybridOrchestrator` builds a task DAG for planning, implementation, merge, verification, and integration.
3. `Scheduler` executes ready DAG nodes concurrently while respecting file locks and resource slots.
4. Worker tasks stage `PatchProposal` objects through `PatchPipeline` rather than writing files directly.
5. `BoundaryPolicyEngine`, `ConflictDetector`, and `MergeManager` validate and combine compatible work.
6. `VerificationPipeline` runs configured validators before the `IntegratorAgent` commits the bundle.
7. The session, artifacts, events, pending proposals, and commit history are persisted under `.CasperCode/hybrid_runtime/sessions/<session_id>/`.

## CLI Surface

The existing bare chat mode still works:

```bash
python main.py "refactor the auth module"
python main.py
```

The new hybrid commands are explicit:

```bash
python main.py run "add JWT auth, admin dashboard, tests, docker" --team auto --team-size 6 --strict --parallel --verify strict --show-team --show-task-graph
python main.py inspect-team --goal "build RAG API with evaluation" --team-size 5
python main.py show-task-graph --session <session_id>
python main.py show-locks
python main.py apply-pending-patches --session <session_id>
```

## Example Trace

```text
Hybrid Team
  preset: fullstack
  strict: True
  verify: strict
  agents: scheduler, boundary, conflicts, merge, verification, integrator, executor, planner, backend, frontend, qa

Task Graph
  plan-architecture -> implement-backend / implement-frontend / implement-qa -> merge-patches -> verify-bundle -> integrate

Patch Decision
  bundle: bundle-3f1e2d7c
  status: applied
  applied: agent/service.py, ui/page.tsx
```

## Extension Points

- Replace heuristic synthesis with an LLM-backed planner by swapping `TeamSynthesizer.inspect_workspace()` and `TeamSynthesizer.synthesize()`.
- Attach real LLM patch-generation workers by feeding validated `PatchProposal` objects into `HybridRunRequest.task_patches` or by adding a worker adapter in `agent/agents/llm_worker.py`.
- Add stronger validators in `agent/verification/validators/`.
- Extend `LockManager` from file-level leases to symbol-level or API-contract locks.
- Add durable background execution by plugging the scheduler into the existing job runtime.

## Current Boundaries

The hybrid OS foundations are production-structured and tested, but one major integration remains intentionally separate:

- the legacy conversational `Agent` tool loop still edits through the old tool path
- the new hybrid runtime already enforces transactional patches, but direct LLM-worker patch generation is the next adapter to build

That split is deliberate so the repo now has a stable deterministic core before the legacy write path is retired.
