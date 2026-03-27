from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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
    depends_on: list[str] = Field(default_factory=list)
    cancellable: bool = True
    resource_spec: ResourceSpec = Field(default_factory=ResourceSpec)
    payload: dict[str, Any] = Field(default_factory=dict)


class JobResult(BaseModel):
    job_id: str
    session_id: str
    status: str
    output: str = ""
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobState(BaseModel):
    spec: JobSpec
    status: str = "queued"
    progress: float = 0.0
    message: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result_ref: str | None = None
    error: str | None = None
