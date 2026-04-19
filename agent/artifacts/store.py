from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from agent.artifacts.models import ArtifactKind, ArtifactRecord


class ArtifactStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._records: list[ArtifactRecord] = []
        if self._path and self._path.exists():
            self.load()

    def put(
        self,
        *,
        kind: ArtifactKind,
        key: str,
        content: object,
        created_by: str,
        task_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ArtifactRecord:
        version = 1
        for record in self._records:
            if record.kind == kind and record.key == key:
                version = max(version, record.version + 1)
        artifact = ArtifactRecord(
            artifact_id=f"artifact-{uuid4().hex[:8]}",
            kind=kind,
            key=key,
            version=version,
            created_by=created_by,
            task_id=task_id,
            content=content,
            metadata=metadata or {},
        )
        self._records.append(artifact)
        return artifact

    def get_latest(self, kind: ArtifactKind, key: str) -> ArtifactRecord | None:
        matches = [
            record
            for record in self._records
            if record.kind == kind and record.key == key
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.version)

    def list(self, kind: ArtifactKind | None = None) -> list[ArtifactRecord]:
        if kind is None:
            return list(self._records)
        return [record for record in self._records if record.kind == kind]

    def version_map(self) -> dict[str, int]:
        versions: dict[str, int] = {}
        for record in self._records:
            versions[f"{record.kind.value}:{record.key}"] = max(
                versions.get(f"{record.kind.value}:{record.key}", 0),
                record.version,
            )
        return versions

    def save(self) -> None:
        if not self._path:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"artifacts": [record.model_dump(mode="json") for record in self._records]}
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load(self) -> list[ArtifactRecord]:
        if not self._path or not self._path.exists():
            return []
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        rows = payload.get("artifacts", [])
        self._records = [ArtifactRecord(**row) for row in rows]
        return list(self._records)
