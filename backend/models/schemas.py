from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    LOCK_ACQUIRED = "LOCK_ACQUIRED"
    PATCH_PROPOSED = "PATCH_PROPOSED"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"
    VERIFICATION_RESULT = "VERIFICATION_RESULT"


class AgentKind(str, Enum):
    LLM_WORKER = "llm_worker"
    RULE_BASED = "rule_based"
    BOUNDARY = "boundary"
    SCHEDULER = "scheduler"
    EXECUTION = "execution"
    CONFLICT_DETECTION = "conflict_detection"
    MERGE = "merge"
    VERIFICATION = "verification"
    INTEGRATOR = "integrator"


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    BLOCKED = "blocked"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class PatchStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMMITTED = "committed"


class AgentSpec(BaseModel):
    id: str
    kind: AgentKind
    role: str
    scope_paths: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    status: AgentStatus = AgentStatus.IDLE
    current_tasks: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OwnershipRules(BaseModel):
    strict: bool = True
    default_owner: str | None = None
    path_prefix_owners: dict[str, str] = Field(default_factory=dict)


class TeamSpec(BaseModel):
    team_id: str
    project_root: str
    goal: str
    agents: list[AgentSpec]
    ownership: OwnershipRules = Field(default_factory=OwnershipRules)
    synthesis_notes: list[str] = Field(default_factory=list)


class TaskSpec(BaseModel):
    id: str
    title: str
    dependencies: list[str] = Field(default_factory=list)
    assigned_agent_id: str
    required_resources: list[str] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    priority: int = 0
    status: TaskStatus = TaskStatus.PENDING
    risk_notes: list[str] = Field(default_factory=list)
    error: str | None = None
    patch_hint: dict[str, Any] = Field(default_factory=dict)


class FileHunk(BaseModel):
    path: str
    start_line: int
    end_line: int
    content: str


class PatchProposal(BaseModel):
    id: str
    task_id: str
    agent_id: str
    status: PatchStatus = PatchStatus.PROPOSED
    hunks: list[FileHunk] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    depends_on_patch_ids: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


class ConflictRecord(BaseModel):
    id: str
    patch_ids: list[str]
    description: str
    files: list[str]
    resolution: str | None = None


class VerificationResult(BaseModel):
    id: str
    lint_ok: bool
    test_ok: bool
    build_ok: bool
    details: dict[str, Any] = Field(default_factory=dict)


class WSEnvelope(BaseModel):
    type: EventType
    session_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: str | None = None


class RunRequest(BaseModel):
    goal: str
    project_root: str = "."
    team_size: int = Field(default=4, ge=1, le=16)
    strict: bool = True
    parallel: bool = True
    max_parallel_tasks: int = Field(default=4, ge=1, le=32)


class SynthesizeTeamRequest(BaseModel):
    project_context: str = ""
    goal: str
    team_size: int = Field(default=4, ge=1, le=16)
    strict: bool = True
    project_root: str = "."


class PatchDecisionBody(BaseModel):
    patch_id: str


class ConflictResolveBody(BaseModel):
    conflict_id: str
    resolution: str


class WorkspaceWriteBody(BaseModel):
    path: str
    content: str
