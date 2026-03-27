# CasperCode Production Redesign

## 1. Target System

CasperCode should become an async-first terminal AI coding agent with:

- strict planner/executor model separation
- a task-graph session core instead of linear chat state
- background jobs for indexing, builds, tests, and long-running shell work
- repository semantic memory with hybrid search
- policy-driven safety and approval
- minimal-diff code editing with validation hooks
- resumable autonomous execution
- multi-agent execution with coordinator + frontend/backend/qa specialists

This design assumes DeepSeek models through the OpenAI-compatible API:

- planner model: `deepseek-reasoner`
- executor model: `deepseek-coder`

## 2. Current Gaps In The Existing Codebase

Current modules:

- `agent/session.py`: single-model session orchestration
- `client/llm_client.py`: one generic LLM client with no role separation
- `context/manager.py`: linear message list with basic pruning
- `tools/registry.py`: tool invocation registry without scheduling or capability routing
- `tools/builtin/edit_file.py`: exact string replacement, not semantic patching
- `tools/mcp/mcp_manager.py`: eager MCP startup and flat registration
- `ui/tui.py`: rich CLI panels but no persistent live task graph or jobs view

Primary limitations:

- planner and executor are coupled
- no task graph, only turn-by-turn message history
- no background scheduler
- no repository semantic memory
- no durable autonomous loop state machine
- no patch validation pipeline
- safety is approval-centric but not policy/risk driven

## 3. New Folder Structure

```text
CasperCode/
  agent/
    runtime/
      orchestrator.py
      autonomous_loop.py
      inngest_bridge.py
      state_machine.py
    planner/
      planner_client.py
      plan_models.py
      plan_engine.py
      replan_engine.py
    executor/
      executor_client.py
      execution_engine.py
      patch_engine.py
      validation_pipeline.py
    sessions/
      session_store.py
      task_graph.py
      checkpoint_store.py
      artifacts.py
  memory/
    short_term/
      conversation_buffer.py
      tool_output_buffer.py
    mid_term/
      task_notes.py
      plan_state.py
      summary_store.py
      todo_graph.py
    long_term/
      vector_index.py
      embedder.py
      chunker.py
      retriever.py
      reranker.py
      dependency_graph.py
      symbol_graph.py
      index_jobs.py
  jobs/
    scheduler.py
    queue.py
    worker_pool.py
    job_models.py
    cancellation.py
    resource_manager.py
    progress_stream.py
  tools/
    core/
      registry.py
      capability_router.py
      tool_models.py
      tool_runtime.py
    builtin/
      fs/
      shell/
      search/
      vcs/
      validation/
    mcp/
      manager.py
      discovery.py
      capability_index.py
      routing.py
  safety/
    policy_engine.py
    risk_classifier.py
    sandbox.py
    audit_log.py
    checkpoint_guard.py
  repo/
    workspace.py
    file_snapshot.py
    git_monitor.py
    language_detection.py
    parsers/
    ast/
  context/
    packer.py
    token_budget.py
    compression.py
    retrieval_plan.py
  ui/
    cli.py
    dashboard.py
    live_views/
      plan_view.py
      jobs_view.py
      diff_view.py
      graph_view.py
      metrics_view.py
  config/
    models.py
    loader.py
    defaults.py
  observability/
    metrics.py
    tracing.py
    logging.py
  docs/
    PRODUCTION_REDESIGN.md
```

## 4. Core Architecture

### 4.1 High-Level Runtime

```text
User Request
  -> SessionOrchestrator
  -> PlannerEngine(deepseek-reasoner)
  -> TaskGraph update
  -> ExecutionEngine(deepseek-coder)
  -> ToolRuntime / Inngest Runtime / PatchEngine
  -> Result Evaluator
  -> PlannerEngine replan or finalize
  -> Memory update + checkpoint
  -> UI stream
```

### 4.2 Core Services

1. `SessionOrchestrator`
   - owns active session runtime
   - coordinates planner, executor, memory, tools, jobs, safety

2. `PlannerEngine`
   - builds and updates structured plan trees
   - selects concurrency strategy
   - decides when to launch background work

3. `ExecutionEngine`
   - converts approved steps into executable actions
   - uses executor model only for implementation and local patch reasoning

4. `InngestRuntime`
   - runs background and concurrent tasks
   - exposes progress events back to the orchestrator

5. `MemoryManager`
   - merges short, mid, and long-term memory
   - performs retrieval and compression

6. `SafetyPolicyEngine`
   - classifies risk and enforces policy gates

7. `PatchEngine`
   - generates minimal diffs
   - validates syntax, semantics, formatting, and type correctness

### 4.3 Multi-Agent Roles and A2A Runtime

The runtime uses explicit specialist roles coordinated by a single coordinator agent:

- `coordinator`: owns plan decomposition, dependency ordering, and replanning
- `frontend`: owns UI/client-facing implementation tasks
- `backend`: owns runtime/API/storage/indexing implementation tasks
- `qa`: owns validation strategy, regression checks, and release gating

Agent communication follows A2A-style envelopes carried through Inngest durable workflows.

```python
class A2AEnvelope(BaseModel):
    message_id: str
    session_id: str
    task_id: str
    sender_role: Literal["coordinator", "frontend", "backend", "qa"]
    recipient_role: Literal["coordinator", "frontend", "backend", "qa"]
    message_type: Literal[
        "task.assigned",
        "task.progress",
        "task.blocked",
        "task.handoff.requested",
        "task.completed",
        "task.validation.passed",
        "task.validation.failed",
    ]
    payload: dict
```

Coordinator is the only authority that commits task-graph state transitions.
## 5. Planner / Executor Separation

### 5.1 Planner Responsibilities

Planner uses `deepseek-reasoner`.

Inputs:

- user goal
- task graph state
- recent tool outputs
- retrieved repository context
- current jobs and job completion events
- safety and environment metadata

Outputs:

- structured plan tree
- execution decisions
- job scheduling decisions
- context retrieval requests
- replanning directives

Planner response schema:

```python
from pydantic import BaseModel
from typing import Literal


class ToolIntent(BaseModel):
    tool_name: str
    purpose: str
    args_hint: dict
    run_mode: Literal["foreground", "background"]
    risk: Literal["safe", "medium", "dangerous"]


class StepPlan(BaseModel):
    step_id: str
    title: str
    objective: str
    depends_on: list[str]
    status: Literal["pending", "ready", "running", "blocked", "done", "failed"]
    execution_mode: Literal["llm_executor", "tool_only", "background_job", "manual_gate"]
    acceptance_criteria: list[str]
    retrieval_queries: list[str]
    tool_intents: list[ToolIntent]
    retry_budget: int = 2
    confidence: float


class PlanTree(BaseModel):
    goal: str
    summary: str
    steps: list[StepPlan]
    next_frontier: list[str]
    planner_notes: str
```

### 5.2 Executor Responsibilities

Executor uses `deepseek-coder`.

Inputs:

- single approved step
- exact target files or symbols
- retrieved code context
- tool result summaries
- patch constraints
- validation requirements

Outputs:

- code edits
- test additions
- shell command proposals
- patch explanations for audit

Hard rule:

- executor cannot create or reorder top-level task plans
- executor cannot expand scope without planner approval

### 5.3 Orchestration Loop

```python
class SessionOrchestrator:
    async def handle_goal(self, session_id: str, goal: str) -> None:
        state = await self.sessions.load_or_create(session_id, goal)
        await self.memory.refresh_workspace_snapshot(state.workspace_id)

        while not state.task_graph.is_goal_terminal():
            retrieval = await self.memory.build_planner_context(state)
            plan = await self.planner.plan(state=state, retrieval=retrieval)
            state.task_graph.apply_plan(plan)

            ready_steps = state.task_graph.ready_frontier()
            dispatches = self.execution_router.select_dispatches(ready_steps, state)

            for dispatch in dispatches.foreground_steps:
                await self.execute_step(state, dispatch.step_id)

            for job in dispatches.background_jobs:
                await self.jobs.enqueue(job)

            completed_events = await self.jobs.poll_events(session_id=session_id)
            state.apply_job_events(completed_events)

            if state.needs_replan():
                continue

            await self.sessions.checkpoint(state)
```

## 6. Task Graph Session Model

Replace linear session storage with a persistent task graph.

### 6.1 Data Model

```python
class ArtifactRef(BaseModel):
    artifact_id: str
    kind: str
    path: str | None = None
    job_id: str | None = None
    metadata: dict = {}


class TaskNode(BaseModel):
    id: str
    title: str
    objective: str
    status: Literal["pending", "ready", "running", "blocked", "done", "failed", "cancelled"]
    depends_on: list[str] = []
    children: list[str] = []
    assigned_mode: Literal["planner", "executor", "tool", "job"]
    priority: int = 50
    retry_count: int = 0
    max_retries: int = 2
    confidence: float = 0.0
    acceptance_criteria: list[str] = []
    artifacts: list[ArtifactRef] = []
    notes: list[str] = []


class SessionState(BaseModel):
    session_id: str
    goal: str
    workspace_root: str
    status: Literal["active", "paused", "completed", "failed"]
    task_graph: dict[str, TaskNode]
    root_tasks: list[str]
    active_jobs: list[str]
    memory_refs: dict[str, str]
    checkpoints: list[str]
```

### 6.2 Why This Replaces The Current Session

Current `Session` stores transient client, context, and runtime state only. The new session state:

- survives process restarts
- can resume autonomous work accurately
- supports dependency-aware execution
- enables `/plan`, `/graph`, `/jobs`, and `/resume` with real structure

## 7. Background Job System

This is a first-class subsystem, not a helper utility. It should be implemented on top of Inngest durable functions instead of an in-process event bus.

### 7.1 Job Types

- repository indexing
- shell execution
- test suite execution
- lint/type-check/build
- long grep or symbol search
- MCP tasks
- code validation
- diff preview generation
- multi-file refactor batches

### 7.2 Job Model

```python
from datetime import datetime


class ResourceSpec(BaseModel):
    cpu_weight: int = 1
    memory_mb: int = 512
    io_priority: int = 5
    max_runtime_sec: int = 1800


class JobSpec(BaseModel):
    job_id: str
    kind: str
    session_id: str
    task_id: str | None = None
    priority: int = 50
    depends_on: list[str] = []
    cancellable: bool = True
    resource_spec: ResourceSpec
    payload: dict


class JobState(BaseModel):
    spec: JobSpec
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    progress: float = 0.0
    message: str = ""
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result_ref: str | None = None
    error: str | None = None
```

### 7.3 Scheduler Design

```python
class InngestScheduler:
    def __init__(
        self,
        queue: PriorityJobQueue,
        workers: WorkerPool,
        resources: ResourceManager,
        inngest_client: InngestClientAdapter,
    ) -> None:
        self.queue = queue
        self.workers = workers
        self.resources = resources
        self.inngest = inngest_client

    async def enqueue(self, spec: JobSpec) -> str:
        await self.queue.push(spec)
        await self.inngest.send_job_queued(spec)
        return spec.job_id

    async def tick(self) -> None:
        ready = await self.queue.pop_ready_batch(self.resources.snapshot())
        for spec in ready:
            token = CancellationToken()
            await self.workers.start(spec, token)

    async def handle_result(self, result: JobResult) -> None:
        await self.inngest.send_job_completed(result)
```

### 7.4 Scheduling Rules

- planner can mark steps as background-capable
- scheduler honors dependencies
- high-priority foreground validation preempts indexing
- per-session concurrency cap prevents one repo from starving others
- resource manager enforces CPU and memory budgets

### 7.5 Required UX

- `/jobs` lists active, queued, failed, and completed jobs
- live status streaming in the CLI
- planner receives Inngest run completion updates and can replan immediately
- `/agents` shows coordinator/frontend/backend/qa status and current assignments

## 8. Vector Store Repository Intelligence

Use a local hybrid retrieval architecture.

### 8.1 Recommended Default Stack

- vector storage: `LanceDB` as default for local developer UX
- optional alternatives:
  - `FAISS` for pure speed
  - `Qdrant` for larger persistent teams/workstations
  - `sqlite-vec` for minimal installs
- lexical retrieval: BM25 or Tantivy-backed inverted index
- embedding model: configurable local/remote embedding provider

Reasoning:

- `LanceDB` gives easy local persistence, metadata filtering, and AI-native ergonomics
- `FAISS` can be added as a performance mode later via the same repository memory interface

### 8.2 Index Units

Chunk types:

- function
- class
- module
- config file
- README
- docs sections
- scripts
- test files

### 8.3 Metadata Schema

```python
class CodeChunk(BaseModel):
    chunk_id: str
    repo_id: str
    path: str
    language: str
    chunk_type: Literal["function", "class", "module", "config", "readme", "doc", "script", "test"]
    symbol_name: str | None = None
    parent_symbol: str | None = None
    start_line: int
    end_line: int
    content: str
    hash: str
    imports: list[str] = []
    referenced_symbols: list[str] = []
    last_modified_ts: float
    git_commit: str | None = None
    recency_score: float = 0.0
    importance_score: float = 0.0
```

### 8.4 Incremental Indexing

Sources:

- initial lazy repo scan
- file save events
- git diff against last indexed commit
- explicit `/index` command
- background idle indexing

Incremental flow:

```text
Git change or fs event
  -> changed files set
  -> parse AST where supported
  -> re-chunk only dirty files
  -> upsert vector rows
  -> update lexical index
  -> update symbol and dependency graph
```

### 8.5 AST-Aware Chunking

Per language parser abstraction:

```python
class Chunker(Protocol):
    def chunk(self, path: Path, content: str) -> list[CodeChunk]: ...


class PythonChunker:
    def chunk(self, path: Path, content: str) -> list[CodeChunk]:
        tree = ast.parse(content)
        chunks = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                chunks.append(build_symbol_chunk(node, content, path))
        chunks.append(build_module_chunk(tree, content, path))
        return chunks
```

Supported parser strategy:

- tree-sitter for most languages
- stdlib AST for Python fast path
- regex fallback for unsupported languages

### 8.6 Retrieval Pipeline

```text
User prompt
  -> query expansion by planner
  -> vector search top 40
  -> lexical search top 40
  -> graph expansion on top symbols
  -> rerank with cross-encoder or heuristic reranker
  -> token-aware context packing
  -> planner context
```

Scoring:

```python
final_score = (
    0.35 * semantic_score +
    0.20 * lexical_score +
    0.15 * recency_score +
    0.15 * importance_score +
    0.15 * dependency_proximity_score
)
```

### 8.7 Dependency And Symbol Graph

Maintain:

- symbol definition map
- file import graph
- call/reference graph
- test-to-source linkage
- config-to-runtime linkage

Use cases:

- planner asks for "all code paths touching auth token refresh"
- retriever expands from one symbol to neighbors
- refactor tasks identify affected files automatically

## 9. Multi-Layer Memory Architecture

### 9.1 Short-Term Memory

Contains:

- current conversation turns
- latest tool outputs
- latest patches
- latest validation outputs

Storage:

- in-memory ring buffer
- token-bounded

### 9.2 Mid-Term Memory

Contains:

- task graph
- session notes
- active assumptions
- planner summaries
- outstanding TODO graph
- failure history

Storage:

- persistent local database
- cheap to serialize and reload

### 9.3 Long-Term Memory

Contains:

- vectorized repository memory
- user preferences
- prior architecture summaries
- resolved issue summaries

### 9.4 Context Packing

```python
class ContextPacker:
    async def pack_for_planner(self, state: SessionState, budget: int) -> PlannerContext:
        budgeter = TokenBudget(budget)
        blocks = []

        blocks += budgeter.take(self.short_term.recent_messages(limit=8))
        blocks += budgeter.take(self.mid_term.plan_frontier(state.session_id))
        blocks += budgeter.take(self.mid_term.open_failures(state.session_id))
        blocks += budgeter.take(await self.long_term.retrieve_for_goal(state.goal, k=20))
        blocks += budgeter.take(self.mid_term.architecture_summary(state.workspace_root))

        return PlannerContext(blocks=blocks)
```

Packing rules:

- task frontier first
- recent failures second
- retrieved code third
- historical summaries fourth
- raw tool outputs are compressed before inclusion

### 9.5 Semantic Compression

Replace current compaction with:

- tool output summarization by type
- compile/test output compression with failure focus
- code block canonicalization
- plan-state snapshotting
- architecture summary rolling updates

## 10. Autonomous Loop Engine

### 10.1 Main Loop

```python
class AutonomousLoop:
    async def run(self, session_id: str) -> None:
        state = await self.sessions.load(session_id)

        while True:
            if state.status in {"completed", "failed", "paused"}:
                return

            signal = self.detector.inspect(state)
            if signal.should_pause:
                state.status = "paused"
                await self.audit.log_pause(state.session_id, signal.reason)
                return

            planner_context = await self.context.pack_for_planner(state, budget=64000)
            plan = await self.planner.plan(state, planner_context)
            state.task_graph.apply_plan(plan)

            step = state.task_graph.select_next_step()
            if step is None:
                state.status = "completed"
                return

            outcome = await self.runtime.execute_step(state, step)
            state.record_outcome(step.id, outcome)
            await self.memory.update_from_outcome(state, outcome)
            await self.sessions.checkpoint(state)
```

### 10.2 Safety Controls In The Loop

- loop detection: repeated identical tool pattern
- stagnation detection: no meaningful artifact changes over N iterations
- confidence gating: low confidence blocks autonomy escalation
- retry budget: bounded retries per node
- rollback trigger: revert to checkpoint on validation failure cluster

### 10.3 Failure Recovery

Strategies:

- executor failure -> planner re-evaluates step with error summary
- tool failure -> retry with adapted parameters if safe
- validation failure -> patch rollback and regenerate targeted diff
- scheduler overload -> defer low priority jobs and continue reasoning

## 11. Intelligent Code Editing Engine

Current `edit` tool is exact string substitution. Replace with a patch pipeline.

### 11.1 Patch Engine Components

- diff planner
- AST patch applicator
- textual fallback patcher
- conflict detector
- syntax validator
- formatter runner
- type-check/test hooks
- semantic validator

### 11.2 Patch Strategy

```python
class PatchRequest(BaseModel):
    task_id: str
    target_files: list[str]
    intent: str
    constraints: list[str]
    require_ast_safe: bool = True
    require_minimal_diff: bool = True


class PatchEngine:
    async def apply(self, request: PatchRequest) -> PatchResult:
        draft = await self.executor.generate_patch(request)
        parsed = self.diff_parser.parse(draft.unified_diff)
        checked = await self.conflicts.check(parsed)
        if not checked.ok:
            return PatchResult.failed("conflict_detected")

        applied = await self.applier.apply(parsed)
        syntax = await self.validators.syntax(applied.paths)
        if not syntax.ok:
            await self.rollback.restore(applied.checkpoint_id)
            return PatchResult.failed("syntax_failed")

        await self.formatters.run(applied.paths)
        semantic = await self.validators.semantic(applied.paths, request)
        if not semantic.ok:
            await self.rollback.restore(applied.checkpoint_id)
            return PatchResult.failed("semantic_failed")

        return PatchResult.success(applied)
```

### 11.3 Validation Pipeline

Validation stages:

1. parse diff
2. detect overlap/conflicts
3. syntax parse changed files
4. run formatter on changed files only
5. run targeted type checks
6. run impacted tests
7. optional planner acceptance review for risky changes

### 11.4 Minimal Diff Rules

- prefer symbol-level edits
- preserve file ordering and formatting style
- do not rewrite whole file unless:
  - file is generated or templated
  - AST rewrite requires broad formatting
  - planner explicitly approves large rewrite

## 12. Safety Policy Redesign

### 12.1 Risk Levels

```python
class RiskLevel(str, Enum):
    SAFE = "safe"
    MEDIUM = "medium"
    DANGEROUS = "dangerous"
```

### 12.2 Policy Engine

```python
class PolicyDecision(BaseModel):
    allowed: bool
    requires_confirmation: bool
    risk: RiskLevel
    reason: str
    dry_run_required: bool = False


class PolicyEngine:
    def evaluate(self, action: ActionEnvelope) -> PolicyDecision:
        if action.kind == "shell" and matches_destructive_command(action.command):
            return deny_or_confirm("dangerous destructive shell command")
        if action.kind == "patch" and action.touches in {"env", "secrets", "infra"}:
            return PolicyDecision(
                allowed=True,
                requires_confirmation=True,
                risk=RiskLevel.DANGEROUS,
                reason="sensitive files affected",
                dry_run_required=True,
            )
        if action.kind == "read":
            return PolicyDecision(
                allowed=True,
                requires_confirmation=False,
                risk=RiskLevel.SAFE,
                reason="read only",
            )
```

### 12.3 Required Features

- dry-run mode for shell and patch actions
- sandbox mode profiles
- rollback checkpoints before dangerous edits
- append-only audit log
- path and secret classifiers
- policy override scopes:
  - session
  - workspace
  - command class

### 12.4 Dangerous Actions

- `rm`, `del`, destructive git reset/clean
- env rewrites
- credential or key exposure
- database migrations
- production infra changes
- mass rename/refactors outside retrieved scope

## 13. MCP Upgrade

### 13.1 Problems In Current MCP Layer

- all tools are registered flat
- no capability ranking
- no semantic routing
- no parallel streaming integration

### 13.2 New MCP Architecture

Components:

- `MCPDiscoveryService`
- `MCPCapabilityIndex`
- `MCPRouter`
- `MCPExecutionRuntime`

Tool capability model:

```python
class ToolCapability(BaseModel):
    tool_id: str
    server_name: str
    description: str
    tags: list[str]
    input_schema: dict
    embedding: list[float]
    latency_ms_p50: float | None = None
    reliability_score: float = 1.0
```

Routing flow:

```text
planner says "need test results from CI-like environment"
  -> MCPRouter semantic matches tools
  -> filters by availability and policy
  -> ranks by capability + latency + reliability
  -> dispatches selected tool
```

Parallelism:

- MCP tools can run as background jobs
- streaming responses fed through Inngest run status
- planner can spawn MCP-backed subtasks

## 14. CLI UX Redesign

### 14.1 New Commands

- `/plan`: show current plan frontier and acceptance criteria
- `/graph`: render task graph with dependencies and status
- `/jobs`: live job monitor
- `/agents`: show coordinator and specialist agent state with latest A2A activity
- `/index`: trigger repo indexing or show index status
- `/search`: hybrid semantic and keyword search
- `/autonomous`: enable, pause, or inspect autonomous loop
- `/safe-mode`: switch policy mode
- `/diff`: preview current pending or last applied patch
- `/metrics`: token, latency, job throughput, retrieval timings

### 14.2 Live Views

1. Planner view
   - current goal
   - next steps
   - blocked nodes
   - planner confidence

2. Job monitor
   - queue depth
   - active workers
   - progress bars
   - failures and retries

3. Diff view
   - changed files
   - unified diff
   - validation status

4. Retrieval view
   - top retrieved files/symbols
   - why they were chosen
   - index freshness

### 14.3 Inngest-Backed UI Update Model

```python
class UIEvent(str, Enum):
    PLAN_UPDATED = "plan_updated"
    TASK_STATUS_CHANGED = "task_status_changed"
    JOB_PROGRESS = "job_progress"
    DIFF_READY = "diff_ready"
    INDEX_PROGRESS = "index_progress"
    METRICS_UPDATED = "metrics_updated"
```

UI should read task and job state from the Inngest-backed runtime projection instead of relying on an in-process event bus.

## 15. Performance Engineering

### 15.1 Non-Negotiable Rules

- async I/O everywhere for network, jobs, and shell process handling
- lazy retrieval and lazy indexing
- cache embeddings by content hash
- only re-embed changed chunks
- bounded in-memory buffers
- separate planner and executor token budgets
- targeted validation on changed files only
- background tasks must be cancellable

### 15.2 Performance Budget Targets

- planner first token latency: under 2.5s on warm state
- executor patch generation latency: under 3.0s for focused edits
- semantic search: under 250ms on warmed index for top-k retrieval
- incremental indexing: under 2s for single-file update
- UI refresh cadence: 100-250ms event-driven

### 15.3 Caching Layers

- content-hash file cache
- AST parse cache
- embedding cache
- retrieval result cache per query fingerprint
- validation cache for unchanged file sets

## 16. Concrete Class Structure

```python
class PlannerClient:
    model_name = "deepseek-reasoner"
    async def complete(self, prompt: str, schema: type[BaseModel]) -> BaseModel: ...


class ExecutorClient:
    model_name = "deepseek-coder"
    async def complete(self, prompt: str, schema: type[BaseModel]) -> BaseModel: ...


class PlanEngine:
    async def create_plan(self, state: SessionState, context: PlannerContext) -> PlanTree: ...
    async def replan(self, state: SessionState, failures: list[str]) -> PlanTree: ...


class ExecutionEngine:
    async def execute(self, state: SessionState, task: TaskNode) -> ExecutionOutcome: ...


class RepositoryMemory:
    async def ensure_index(self, workspace_root: str) -> None: ...
    async def retrieve(self, query: str, filters: dict, k: int) -> list[CodeChunk]: ...


class PatchValidationPipeline:
    async def run(self, changed_files: list[str], scope: ValidationScope) -> ValidationReport: ...


class SafetyPolicyEngine:
    async def evaluate(self, envelope: ActionEnvelope) -> PolicyDecision: ...


class MCPRouter:
    async def rank_tools(self, intent: str, candidate_tools: list[ToolCapability]) -> list[ToolCapability]: ...


class SessionStore:
    async def load_or_create(self, session_id: str, goal: str) -> SessionState: ...
    async def checkpoint(self, state: SessionState) -> str: ...
```

## 17. End-To-End Execution Flow

### 17.1 Example: "Refactor auth caching and update tests"

```text
1. User enters request
2. Orchestrator creates session state with root goal node
3. Planner retrieves:
   - auth-related chunks
   - cache-related chunks
   - related tests
4. Planner emits plan:
   - inspect auth cache design
   - locate mutation points
   - patch implementation
   - update targeted tests
   - run tests in background
5. Scheduler launches background jobs:
   - incremental index refresh
   - targeted test discovery
6. Executor performs focused code edit on implementation files
7. Patch engine validates syntax and formatting
8. QA agent publishes validation outcome through Inngest A2A events
9. Planner replans to fix broken tests
10. Executor patches tests
11. Validation job reruns impacted tests
12. Planner checks acceptance criteria
13. Session checkpoint and final result emitted
```

### 17.2 Example: Long Running Background Work

```text
1. Planner decides full repo indexing is useful but non-blocking
2. Schedules low priority indexing job
3. Continues using lexical and partial retrieval meanwhile
4. Job emits progress updates
5. Once indexing finishes, planner upgrades retrieval strategy on next loop
```

## 18. Migration Plan From Current CasperCode

### Phase 1. Separate Models And Introduce Session State

Replace:

- `client/llm_client.py` -> split into planner and executor clients
- `agent/session.py` -> lightweight runtime bootstrap only

Add:

- `agent/planner/*`
- `agent/executor/*`
- `agent/sessions/task_graph.py`

Keep old CLI behavior compatible.

### Phase 2. Introduce Inngest Runtime And Job Scheduler

Add:

- `jobs/*`
- Inngest client and serve handler
- shell/test/index jobs

Migrate:

- long-running shell and MCP calls into jobs

### Phase 3. Replace Context Manager With Memory Hierarchy

Deprecate:

- `context/manager.py`
- `context/compaction.py`

Add:

- `memory/*`
- `context/packer.py`
- `context/token_budget.py`

### Phase 4. Add Repository Intelligence

Add:

- chunkers
- vector index
- lexical index
- symbol and dependency graphs

Expose `/index` and `/search`.

### Phase 5. Replace Edit Tool With Patch Engine

Deprecate:

- simplistic exact string edit as primary editing mechanism

Retain as fallback:

- exact replace tool for tiny safe edits

Add:

- unified diff generation
- validation pipeline
- rollback checkpoints

### Phase 6. Safety And Audit Upgrade

Replace:

- approval-only gating

With:

- risk classification
- dry run
- checkpoint before dangerous actions
- append-only action log

### Phase 7. UX Upgrade

Add:

- `/plan`, `/graph`, `/jobs`, `/index`, `/search`, `/autonomous`, `/safe-mode`
- live Rich views driven by Inngest-backed run state

## 19. Immediate Refactor Mapping To Existing Files

Existing files and their likely fate:

- `agent/session.py`
  - keep only as thin runtime compatibility layer
- `client/llm_client.py`
  - split into `planner_client.py` and `executor_client.py`
- `context/manager.py`
  - replace with `ContextPacker` + memory hierarchy
- `tools/registry.py`
  - refactor into tool runtime plus capability routing
- `tools/mcp/mcp_manager.py`
  - refactor into discovery, capability index, router, and runtime
- `tools/builtin/edit_file.py`
  - demote to fallback textual patcher
- `ui/tui.py`
  - split into live panels and event-driven dashboard widgets

## 20. Production Readiness Requirements

Before calling the redesign production-ready, CasperCode should have:

- deterministic plan schema validation
- durable session checkpoints
- resumable background jobs
- append-only audit logs
- targeted validation for changed files
- crash-safe rollback points for dangerous writes
- retrieval freshness tracking
- bounded memory usage under large repos
- observability metrics for latency, token use, job throughput, and error rates

## 21. Final Engineering Position

The correct redesign is not a larger monolithic agent loop. It is a coordinated runtime with:

- planner/executor role separation
- durable task graph state
- Inngest durable workflow orchestration
- hybrid repository memory
- minimal-diff patching with validation
- explicit policy enforcement

That architecture is the shortest path from the current CasperCode implementation to a real production terminal coding agent that can handle large repositories, long-running work, and concurrent reasoning safely.




