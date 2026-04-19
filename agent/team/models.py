from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    LLM_WORKER = "llm_worker"
    RULE_BASED = "rule_based"
    BOUNDARY = "boundary"
    RATIONAL_SCHEDULER = "rational_scheduler"
    EXECUTION = "execution"
    CONFLICT_DETECTOR = "conflict_detector"
    MERGE = "merge"
    VERIFICATION = "verification"
    INTEGRATOR = "integrator"


class OwnershipMode(str, Enum):
    STRICT = "strict"
    FLEXIBLE = "flexible"


class VerificationMode(str, Enum):
    LIGHTWEIGHT = "lightweight"
    STRICT = "strict"
    ENTERPRISE = "enterprise"


class ProjectProfile(str, Enum):
    GENERIC = "generic"
    PYTHON_SERVICE = "python_service"
    WEB_APP = "web_app"
    FULLSTACK = "fullstack"
    DEVOPS = "devops"
    AI_ML = "ai_ml"


class ScopeSpec(BaseModel):
    """Defines the file and module territory an agent is allowed to own."""

    name: str
    description: str = ""
    include_patterns: list[str] = Field(default_factory=list)
    exclude_patterns: list[str] = Field(default_factory=list)
    writable_patterns: list[str] = Field(default_factory=list)
    read_only_patterns: list[str] = Field(default_factory=list)
    shared_patterns: list[str] = Field(default_factory=list)
    artifact_requirements: list[str] = Field(default_factory=list)


class CoordinationPolicy(BaseModel):
    scheduling_mode: str = "dag"
    ownership_mode: OwnershipMode = OwnershipMode.STRICT
    parallelism: int = Field(default=4, ge=1, le=32)
    lock_timeout_sec: float = Field(default=5.0, ge=0.1)
    lock_lease_sec: float = Field(default=30.0, ge=1.0)
    max_retries: int = Field(default=1, ge=0, le=10)
    allow_cross_scope_reads: bool = True
    hotspot_patterns: list[str] = Field(default_factory=list)


class ReviewPolicy(BaseModel):
    mode: VerificationMode = VerificationMode.LIGHTWEIGHT
    validators: list[str] = Field(default_factory=list)
    required_reviewers: list[str] = Field(default_factory=list)
    require_separation_of_duties: bool = True
    dependency_changes_require_elevated_review: bool = True
    contract_changes_require_review: bool = True


class ResourcePolicy(BaseModel):
    max_parallel_agents: int = Field(default=4, ge=1, le=32)
    llm_request_budget: int = Field(default=32, ge=0)
    token_budget: int = Field(default=200_000, ge=0)
    cost_budget_usd: float = Field(default=10.0, ge=0.0)
    tool_slots: dict[str, int] = Field(
        default_factory=lambda: {
            "shell": 2,
            "tests": 1,
            "build": 1,
            "package_manager": 1,
        }
    )
    exclusive_resources: list[str] = Field(
        default_factory=lambda: ["package_manager", "migration_slot"]
    )


class AgentSpec(BaseModel):
    id: str
    type: AgentType
    role: str
    scope: ScopeSpec
    capabilities: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    status: str = "idle"
    active_task_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    output_contract: dict[str, Any] = Field(default_factory=dict)
    model_name: str | None = None


class TeamPresetBlueprint(BaseModel):
    name: str
    description: str
    worker_roles: list[str]
    default_verification_mode: VerificationMode = VerificationMode.LIGHTWEIGHT
    default_ownership_mode: OwnershipMode = OwnershipMode.STRICT
    recommended_parallelism: int = 4
    strict_default: bool = False


class TeamSpec(BaseModel):
    team_id: str
    name: str
    preset_name: str
    project_profile: ProjectProfile
    goal: str
    strict: bool
    team_size: int
    synthesized_by: str = "heuristic"
    agents: list[AgentSpec] = Field(default_factory=list)
    coordination_policy: CoordinationPolicy
    review_policy: ReviewPolicy
    resource_policy: ResourcePolicy
    ownership_map: dict[str, list[str]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TeamSynthesisOptions(BaseModel):
    team: str = "auto"
    team_size: int = Field(default=4, ge=1, le=16)
    strict: bool = False
    quality_target: str = "balanced"
    ownership_mode: OwnershipMode = OwnershipMode.STRICT
    verification_mode: VerificationMode = VerificationMode.LIGHTWEIGHT
    planner_model: str | None = None
    worker_model: str | None = None
    budget_tokens: int = Field(default=200_000, ge=0)
    budget_usd: float = Field(default=10.0, ge=0.0)


class WorkspaceSummary(BaseModel):
    root: Path
    file_count: int = 0
    top_level_dirs: list[str] = Field(default_factory=list)
    dominant_languages: list[str] = Field(default_factory=list)
    config_files: list[str] = Field(default_factory=list)
    has_frontend: bool = False
    has_backend: bool = False
    has_tests: bool = False
    has_infra: bool = False
    has_ml: bool = False
    project_profile: ProjectProfile = ProjectProfile.GENERIC
    ownership_hints: dict[str, list[str]] = Field(default_factory=dict)
