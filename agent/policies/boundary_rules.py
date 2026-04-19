from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from pydantic import BaseModel, Field

from agent.team.models import AgentSpec, OwnershipMode, TeamSpec


GENERATED_PATTERNS = ["dist/**", "build/**", "*.generated.*", "*.lock", "*.pyc"]
DEPENDENCY_PATTERNS = ["requirements*.txt", "pyproject.toml", "package.json", "package-lock.json"]
SCHEMA_PATTERNS = ["migrations/**", "schema/**", "**/*.sql"]
API_PATTERNS = ["api/**", "openapi/**", "schemas/**", "**/*contract*"]


class BoundaryDecision(BaseModel):
    allowed: bool
    reasons: list[str] = Field(default_factory=list)
    required_reviews: list[str] = Field(default_factory=list)
    escalations: list[str] = Field(default_factory=list)
    ownership_owner: str | None = None


class BoundaryPolicyEngine:
    """Enforces file, tool, and patch boundaries across a synthesized team."""

    def __init__(self, team_spec: TeamSpec) -> None:
        self.team_spec = team_spec
        self._agents = {agent.id: agent for agent in team_spec.agents}

    def validate_path(
        self,
        agent: AgentSpec,
        path: str,
        action: str,
    ) -> BoundaryDecision:
        normalized = Path(path).as_posix()
        owner = self.owner_for_path(normalized)
        reasons: list[str] = []
        required_reviews: list[str] = []
        escalations: list[str] = []
        is_mutation = action in {"write", "delete"}

        if is_mutation:
            if self._matches_any(normalized, GENERATED_PATTERNS):
                return BoundaryDecision(
                    allowed=False,
                    reasons=["generated-files-are-read-only"],
                    ownership_owner=owner,
                )
            if agent.role == "qa" and not self._matches_any(
                normalized,
                agent.scope.writable_patterns or ["tests/**", "docs/**"],
            ):
                return BoundaryDecision(
                    allowed=False,
                    reasons=["qa-cannot-implement-business-logic"],
                    ownership_owner=owner,
                )

        if owner and owner != agent.id and is_mutation:
            if self.team_spec.coordination_policy.ownership_mode == OwnershipMode.STRICT:
                return BoundaryDecision(
                    allowed=False,
                    reasons=[f"path-owned-by-{owner}"],
                    ownership_owner=owner,
                )
            required_reviews.append("cross-scope-review")
            escalations.append("ownership-flex")

        if is_mutation and not self._path_is_allowed_for_write(agent, normalized):
            return BoundaryDecision(
                allowed=False,
                reasons=["path-outside-agent-scope"],
                required_reviews=required_reviews,
                escalations=escalations,
                ownership_owner=owner,
            )

        if action == "read" and not self._path_is_allowed_for_read(agent, normalized):
            return BoundaryDecision(
                allowed=False,
                reasons=["path-outside-readable-scope"],
                ownership_owner=owner,
            )

        if self._matches_any(normalized, DEPENDENCY_PATTERNS) and is_mutation:
            required_reviews.append("dependency-review")
        if self._matches_any(normalized, API_PATTERNS) and is_mutation:
            required_reviews.append("contract-review")
        if self._matches_any(normalized, SCHEMA_PATTERNS) and is_mutation:
            required_reviews.append("migration-review")

        return BoundaryDecision(
            allowed=True,
            reasons=reasons,
            required_reviews=sorted(set(required_reviews)),
            escalations=sorted(set(escalations)),
            ownership_owner=owner,
        )

    def validate_tool(self, agent: AgentSpec, tool_name: str) -> BoundaryDecision:
        if tool_name in agent.allowed_tools:
            return BoundaryDecision(allowed=True)
        return BoundaryDecision(
            allowed=False,
            reasons=[f"tool-{tool_name}-not-allowed-for-{agent.role}"],
        )

    def validate_patch(self, agent: AgentSpec, proposal: Any) -> BoundaryDecision:
        reasons: list[str] = []
        required_reviews: list[str] = []
        escalations: list[str] = []
        owners: set[str] = set()
        touched_paths: list[str] = []

        fragments = getattr(proposal, "fragments", [])
        for fragment in fragments:
            path = Path(fragment.path).as_posix()
            touched_paths.append(path)
            decision = self.validate_path(
                agent,
                path,
                "delete" if getattr(fragment, "operation", "") == "delete" else "write",
            )
            if not decision.allowed:
                reasons.extend(decision.reasons)
            required_reviews.extend(decision.required_reviews)
            escalations.extend(decision.escalations)
            if decision.ownership_owner:
                owners.add(decision.ownership_owner)

            if getattr(fragment, "operation", "") == "delete" and not fragment.metadata.get(
                "approved_delete"
            ):
                reasons.append("deletions-require-explicit-approval")

        if self._touches_dependency_files(touched_paths):
            required_reviews.append("dependency-review")
        if self._touches_schema_files(touched_paths) and not self._includes_migration_artifact(proposal):
            reasons.append("schema-change-requires-migration-artifact")
        if self._touches_api_contract(touched_paths) and not self._includes_contract_artifact(proposal):
            reasons.append("api-change-requires-contract-artifact")

        if len(owners) > 1:
            escalations.append("cross-cutting-change")

        return BoundaryDecision(
            allowed=not reasons,
            reasons=sorted(set(reasons)),
            required_reviews=sorted(set(required_reviews)),
            escalations=sorted(set(escalations)),
            ownership_owner=next(iter(owners)) if len(owners) == 1 else None,
        )

    def owner_for_path(self, path: str) -> str | None:
        normalized = Path(path).as_posix()
        for agent in self.team_spec.agents:
            if agent.type != "llm_worker":
                continue
            if self._matches_any(normalized, agent.scope.writable_patterns or agent.scope.include_patterns):
                return agent.id
        return None

    def _path_is_allowed_for_write(self, agent: AgentSpec, path: str) -> bool:
        if self._matches_any(path, agent.scope.exclude_patterns):
            return False
        allowed_patterns = agent.scope.writable_patterns or agent.scope.include_patterns
        return self._matches_any(path, allowed_patterns) or self._matches_any(
            path,
            agent.scope.shared_patterns,
        )

    def _path_is_allowed_for_read(self, agent: AgentSpec, path: str) -> bool:
        if self._matches_any(path, agent.scope.exclude_patterns):
            return False
        if self._matches_any(path, agent.scope.read_only_patterns):
            return True
        return self._matches_any(path, agent.scope.include_patterns) or self._matches_any(
            path,
            agent.scope.shared_patterns,
        )

    def _touches_dependency_files(self, paths: Iterable[str]) -> bool:
        return any(self._matches_any(path, DEPENDENCY_PATTERNS) for path in paths)

    def _touches_schema_files(self, paths: Iterable[str]) -> bool:
        return any(self._matches_any(path, SCHEMA_PATTERNS) for path in paths)

    def _touches_api_contract(self, paths: Iterable[str]) -> bool:
        return any(self._matches_any(path, API_PATTERNS) for path in paths)

    def _includes_migration_artifact(self, proposal: Any) -> bool:
        artifacts = set(getattr(proposal, "required_artifacts", []))
        touched = [Path(fragment.path).as_posix() for fragment in getattr(proposal, "fragments", [])]
        return "schema_contract" in artifacts or any(
            path.startswith("migrations/") for path in touched
        )

    def _includes_contract_artifact(self, proposal: Any) -> bool:
        artifacts = set(getattr(proposal, "required_artifacts", []))
        return "api_contract" in artifacts or "schema_contract" in artifacts

    def _matches_any(self, path: str, patterns: list[str]) -> bool:
        if not patterns:
            return False
        normalized = Path(path).as_posix()
        path_obj = PurePosixPath(normalized)
        for pattern in patterns:
            candidate_patterns = [pattern]
            if pattern.startswith("**/"):
                candidate_patterns.append(pattern[3:])
            for candidate in candidate_patterns:
                if (
                    fnmatch(normalized, candidate)
                    or fnmatch(Path(normalized).name, candidate)
                    or path_obj.match(candidate)
                ):
                    return True
        return False
