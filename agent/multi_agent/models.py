from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AgentRole(str, Enum):
    COORDINATOR = "coordinator"
    PLANNER = "planner"
    BACKEND = "backend"
    FRONTEND = "frontend"
    QA = "qa"


class AgentStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    RUNNING = "running"
    BLOCKED = "blocked"
    REVIEWING = "reviewing"


class AgentCapability(BaseModel):
    name: str
    description: str
    keywords: list[str] = Field(default_factory=list)


class AgentProfile(BaseModel):
    agent_id: str
    role: str
    name: str
    model_name: str
    color: str = "bright_cyan"
    powers: list[str] = Field(default_factory=list)
    system_prompt: str | None = None
    source: str = "built_in"
    status: AgentStatus = AgentStatus.IDLE
    capabilities: list[AgentCapability] = Field(default_factory=list)
    current_task_id: str | None = None


class AgentDesignDraft(BaseModel):
    name: str
    role: str
    color: str = "bright_cyan"
    powers: list[str] = Field(default_factory=list)
    mission: str
    system_prompt: str | None = None
    keywords: list[str] = Field(default_factory=list)
    model_name: str | None = None
    design_source: str = "heuristic"


class TaskAssignment(BaseModel):
    task_id: str
    primary_agent_id: str
    supporting_agent_ids: list[str] = Field(default_factory=list)
    reason: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
