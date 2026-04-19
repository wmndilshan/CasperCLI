from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from pydantic import BaseModel, Field

from agent.artifacts.models import ArtifactRecord
from agent.runtime.patch_pipeline import CommitDecision, PatchProposal
from agent.runtime.task_graph import TaskGraph
from agent.team.models import TeamSpec
from agent.verification.pipeline import VerificationReport


class HybridSessionRecord(BaseModel):
    session_id: str
    goal: str
    workspace_root: Path
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    team_spec: TeamSpec
    task_graph: TaskGraph
    pending_proposals: list[PatchProposal] = Field(default_factory=list)
    commit_history: list[CommitDecision] = Field(default_factory=list)
    verification_reports: list[VerificationReport] = Field(default_factory=list)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    event_log: list[dict[str, object]] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class HybridSessionStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, record: HybridSessionRecord) -> Path:
        record.updated_at = datetime.now(timezone.utc)
        path = self.session_path(record.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(record.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return path

    def load(self, session_id: str) -> HybridSessionRecord:
        path = self.session_path(session_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return HybridSessionRecord(**payload)

    def list_sessions(self) -> list[dict[str, str]]:
        records: list[dict[str, str]] = []
        for path in sorted(self.root.glob("*/session.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            records.append(
                {
                    "session_id": payload["session_id"],
                    "goal": payload["goal"],
                    "updated_at": payload["updated_at"],
                }
            )
        return records

    def session_dir(self, session_id: str) -> Path:
        return self.root / session_id

    def session_path(self, session_id: str) -> Path:
        return self.session_dir(session_id) / "session.json"
