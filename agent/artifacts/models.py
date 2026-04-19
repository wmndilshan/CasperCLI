from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ArtifactKind(str, Enum):
    ARCHITECTURE_SPEC = "architecture_spec"
    TASK_GRAPH = "task_graph"
    API_CONTRACT = "api_contract"
    SCHEMA_CONTRACT = "schema_contract"
    TEST_PLAN = "test_plan"
    FILE_OWNERSHIP_MAP = "file_ownership_map"
    DEPENDENCY_IMPACT_REPORT = "dependency_impact_report"
    REVIEW_REPORT = "review_report"
    PATCH_BUNDLE = "patch_bundle"
    DECISION_LOG = "decision_log"


class ArtifactRecord(BaseModel):
    artifact_id: str
    kind: ArtifactKind
    key: str
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str
    task_id: str | None = None
    content: Any
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionLogEntry(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)
