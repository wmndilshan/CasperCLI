from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from uuid import uuid4

from agent.team.models import (
    AgentSpec,
    AgentType,
    CoordinationPolicy,
    OwnershipMode,
    ProjectProfile,
    ResourcePolicy,
    ReviewPolicy,
    ScopeSpec,
    TeamSpec,
    TeamSynthesisOptions,
    VerificationMode,
    WorkspaceSummary,
)
from agent.team.presets import get_team_preset


_LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".css": "css",
    ".scss": "css",
    ".html": "html",
    ".sql": "sql",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".tf": "terraform",
    ".ipynb": "notebook",
}

_IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
}


class TeamSynthesizer:
    """Builds a structured team topology from repo context and a user goal."""

    def inspect_workspace(self, workspace_root: Path) -> WorkspaceSummary:
        root = workspace_root.resolve()
        languages: Counter[str] = Counter()
        top_level_dirs: list[str] = []
        config_files: list[str] = []
        file_count = 0

        for child in sorted(root.iterdir()):
            if child.is_dir():
                top_level_dirs.append(child.name)
            elif child.is_file() and child.name in {
                "package.json",
                "pyproject.toml",
                "requirements.txt",
                "Dockerfile",
                "docker-compose.yml",
            }:
                config_files.append(child.name)

        for path in root.rglob("*"):
            if any(part in _IGNORED_DIRS for part in path.parts):
                continue
            if not path.is_file():
                continue
            file_count += 1
            language = _LANGUAGE_BY_SUFFIX.get(path.suffix.lower())
            if language:
                languages[language] += 1
            if path.name in {"package.json", "pyproject.toml", "requirements.txt"}:
                config_files.append(str(path.relative_to(root)))

        dominant_languages = [name for name, _ in languages.most_common(4)]
        lower_dirs = {item.lower() for item in top_level_dirs}
        has_frontend = bool(
            lower_dirs & {"ui", "web", "frontend", "client", "apps", "templates"}
        ) or "typescript" in dominant_languages or "javascript" in dominant_languages
        has_backend = bool(
            lower_dirs & {"api", "backend", "server", "services", "agent", "core"}
        ) or "python" in dominant_languages
        has_tests = any(item in lower_dirs for item in {"tests", "test"}) or (
            root / "tests"
        ).exists()
        has_infra = bool(
            lower_dirs & {"infra", "deploy", ".github", "docker", "ops"}
        ) or any(name.lower().startswith("docker") for name in config_files)
        has_ml = bool(lower_dirs & {"models", "ml", "notebooks", "pipelines"}) or (
            "notebook" in dominant_languages
        )

        profile = self._infer_project_profile(
            has_frontend=has_frontend,
            has_backend=has_backend,
            has_infra=has_infra,
            has_ml=has_ml,
        )

        return WorkspaceSummary(
            root=root,
            file_count=file_count,
            top_level_dirs=top_level_dirs,
            dominant_languages=dominant_languages,
            config_files=sorted(set(config_files)),
            has_frontend=has_frontend,
            has_backend=has_backend,
            has_tests=has_tests,
            has_infra=has_infra,
            has_ml=has_ml,
            project_profile=profile,
            ownership_hints=self._build_ownership_hints(top_level_dirs, profile),
        )

    def synthesize(
        self,
        goal: str,
        workspace_root: Path,
        options: TeamSynthesisOptions,
    ) -> TeamSpec:
        workspace = self.inspect_workspace(workspace_root)
        preset_name = options.team if options.team != "auto" else self._select_preset(goal, workspace)
        preset = get_team_preset(preset_name)
        strict = options.strict or preset.strict_default

        review_mode = options.verification_mode
        if options.team != "auto" and options.verification_mode == VerificationMode.LIGHTWEIGHT:
            review_mode = preset.default_verification_mode

        ownership_mode = options.ownership_mode
        if strict:
            ownership_mode = OwnershipMode.STRICT

        worker_roles = self._select_worker_roles(goal, workspace, preset.worker_roles, options.team_size)
        agents = [
            *self._build_governance_agents(
                goal=goal,
                workspace=workspace,
                ownership_mode=ownership_mode,
                review_mode=review_mode,
                options=options,
            ),
            *self._build_worker_agents(
                roles=worker_roles,
                workspace=workspace,
                options=options,
            ),
        ]
        ownership_map = {
            agent.id: list(agent.scope.writable_patterns or agent.scope.include_patterns)
            for agent in agents
            if agent.type == AgentType.LLM_WORKER
        }

        return TeamSpec(
            team_id=f"team-{uuid4().hex[:8]}",
            name=f"{preset_name.replace('-', ' ').title()} Team",
            preset_name=preset_name,
            project_profile=workspace.project_profile,
            goal=goal,
            strict=strict,
            team_size=options.team_size,
            synthesized_by="heuristic",
            agents=agents,
            coordination_policy=CoordinationPolicy(
                ownership_mode=ownership_mode,
                parallelism=max(1, min(options.team_size, preset.recommended_parallelism)),
                hotspot_patterns=["requirements.txt", "package.json", "pyproject.toml"],
            ),
            review_policy=ReviewPolicy(
                mode=review_mode,
                validators=self._validators_for_mode(review_mode, workspace),
                required_reviewers=["verification", "integrator"] if strict else ["verification"],
                require_separation_of_duties=strict,
            ),
            resource_policy=ResourcePolicy(
                max_parallel_agents=max(1, min(options.team_size + 2, 8)),
                token_budget=options.budget_tokens,
                cost_budget_usd=options.budget_usd,
            ),
            ownership_map=ownership_map,
            metadata={
                "workspace": workspace.model_dump(mode="json"),
                "worker_roles": worker_roles,
            },
        )

    def _infer_project_profile(
        self,
        *,
        has_frontend: bool,
        has_backend: bool,
        has_infra: bool,
        has_ml: bool,
    ) -> ProjectProfile:
        if has_ml:
            return ProjectProfile.AI_ML
        if has_frontend and has_backend:
            return ProjectProfile.FULLSTACK
        if has_frontend:
            return ProjectProfile.WEB_APP
        if has_infra and not has_backend:
            return ProjectProfile.DEVOPS
        if has_backend:
            return ProjectProfile.PYTHON_SERVICE
        return ProjectProfile.GENERIC

    def _build_ownership_hints(
        self,
        top_level_dirs: list[str],
        profile: ProjectProfile,
    ) -> dict[str, list[str]]:
        hints: dict[str, list[str]] = {}
        lower_dirs = {item.lower() for item in top_level_dirs}
        if lower_dirs & {"ui", "web", "frontend", "client"}:
            hints["frontend"] = ["ui/**", "web/**", "frontend/**", "client/**"]
        if lower_dirs & {"agent", "core", "backend", "server", "services"}:
            hints["backend"] = ["agent/**", "core/**", "backend/**", "server/**", "services/**"]
        if lower_dirs & {"tests", "scripts"}:
            hints["qa"] = ["tests/**", "scripts/**"]
        if lower_dirs & {"infra", "deploy", ".github", "docker"}:
            hints["devops"] = ["infra/**", "deploy/**", ".github/**", "docker/**", "Dockerfile*"]
        if profile == ProjectProfile.AI_ML:
            hints["ml"] = ["models/**", "notebooks/**", "pipelines/**"]
        return hints

    def _select_preset(self, goal: str, workspace: WorkspaceSummary) -> str:
        text = goal.lower()
        if any(token in text for token in {"incident", "outage", "hotfix", "sev", "rollback"}):
            return "incident-response"
        if any(token in text for token in {"docker", "ci", "deploy", "kubernetes", "terraform"}):
            if workspace.project_profile == ProjectProfile.FULLSTACK:
                return "fullstack"
            return "devops" if workspace.project_profile != ProjectProfile.PYTHON_SERVICE else "backend-platform"
        if any(token in text for token in {"rag", "ml", "model", "evaluation", "embedding"}):
            return "ai-ml"
        if workspace.project_profile == ProjectProfile.FULLSTACK:
            return "fullstack"
        if workspace.project_profile == ProjectProfile.WEB_APP:
            return "frontend-experience"
        if workspace.project_profile == ProjectProfile.DEVOPS:
            return "devops"
        return "backend-platform"

    def _select_worker_roles(
        self,
        goal: str,
        workspace: WorkspaceSummary,
        template_roles: list[str],
        team_size: int,
    ) -> list[str]:
        roles = list(template_roles)
        if workspace.has_frontend and "frontend" not in roles:
            roles.append("frontend")
        if workspace.has_tests and "qa" not in roles:
            roles.append("qa")
        if workspace.has_infra and "devops" not in roles and team_size >= 4:
            roles.append("devops")
        if workspace.has_ml and "ml" not in roles:
            roles.append("ml")
        if "security" in goal.lower() and "security" not in roles and team_size >= 4:
            roles.append("security")

        if team_size <= 1:
            return ["generalist"]

        trimmed = roles[: team_size]
        if not trimmed:
            trimmed = ["generalist"]
        return trimmed

    def _build_governance_agents(
        self,
        *,
        goal: str,
        workspace: WorkspaceSummary,
        ownership_mode: OwnershipMode,
        review_mode: VerificationMode,
        options: TeamSynthesisOptions,
    ) -> list[AgentSpec]:
        shared_scope = ScopeSpec(
            name="workspace-control",
            description="Governance agents may read workspace-wide metadata and shared artifacts.",
            include_patterns=["**/*"],
            writable_patterns=[".CasperCode/**"],
            shared_patterns=["**/*"],
        )
        return [
            AgentSpec(
                id="scheduler",
                type=AgentType.RATIONAL_SCHEDULER,
                role="scheduler",
                scope=shared_scope,
                capabilities=["dag_scheduling", "load_balancing", "replanning"],
                permissions=["read:any", "assign:tasks"],
                forbidden_actions=["write:workspace"],
                allowed_tools=["todo"],
                output_contract={"artifacts": ["task_graph", "decision_log"]},
                model_name=options.planner_model,
            ),
            AgentSpec(
                id="boundary",
                type=AgentType.BOUNDARY,
                role="boundary",
                scope=shared_scope,
                capabilities=["ownership_enforcement", "tool_policy", "risk_gating"],
                permissions=["read:any", "validate:patch", "validate:tool"],
                forbidden_actions=["apply:patch"],
                output_contract={"artifacts": ["review_report", "decision_log"]},
            ),
            AgentSpec(
                id="conflicts",
                type=AgentType.CONFLICT_DETECTOR,
                role="conflict",
                scope=shared_scope,
                capabilities=["file_conflict_detection", "semantic_conflict_detection"],
                permissions=["read:any", "validate:patch_bundle"],
                forbidden_actions=["apply:patch"],
                output_contract={"artifacts": ["review_report"]},
            ),
            AgentSpec(
                id="merge",
                type=AgentType.MERGE,
                role="merge",
                scope=shared_scope,
                capabilities=["patch_bundle_merge", "escalation"],
                permissions=["read:any", "merge:bundle"],
                forbidden_actions=["write:workspace"],
                output_contract={"artifacts": ["patch_bundle", "decision_log"]},
            ),
            AgentSpec(
                id="verification",
                type=AgentType.VERIFICATION,
                role="verification",
                scope=shared_scope,
                capabilities=["lint", "test", "build", "security_scan"],
                permissions=["read:any", "execute:verification"],
                forbidden_actions=["implement:business_logic"],
                allowed_tools=["shell", "read_file", "list_dir"],
                output_contract={"artifacts": ["review_report", "test_plan"]},
            ),
            AgentSpec(
                id="integrator",
                type=AgentType.INTEGRATOR,
                role="integrator",
                scope=shared_scope,
                capabilities=["commit_integration", "bundle_finalization"],
                permissions=["read:any", "apply:patch"],
                forbidden_actions=["plan:team"],
                output_contract={"artifacts": ["decision_log", "patch_bundle"]},
            ),
            AgentSpec(
                id="executor",
                type=AgentType.EXECUTION,
                role="execution",
                scope=shared_scope,
                capabilities=["tool_execution", "sandboxed_commands"],
                permissions=["execute:tools"],
                forbidden_actions=["plan:team"],
                allowed_tools=["shell", "read_file", "list_dir", "grep_search", "glob_search"],
                output_contract={"artifacts": ["decision_log"]},
            ),
        ]

    def _build_worker_agents(
        self,
        *,
        roles: list[str],
        workspace: WorkspaceSummary,
        options: TeamSynthesisOptions,
    ) -> list[AgentSpec]:
        agents: list[AgentSpec] = []
        seen_names: Counter[str] = Counter()
        for role in roles:
            seen_names[role] += 1
            suffix = f"-{seen_names[role]}" if seen_names[role] > 1 else ""
            scope = self._scope_for_role(role, workspace)
            agents.append(
                AgentSpec(
                    id=f"{role}{suffix}",
                    type=AgentType.LLM_WORKER,
                    role=role,
                    scope=scope,
                    capabilities=self._capabilities_for_role(role),
                    permissions=["read:owned", "write:owned", "propose:patch"],
                    forbidden_actions=self._forbidden_actions_for_role(role),
                    allowed_tools=self._tools_for_role(role),
                    output_contract={
                        "patches": True,
                        "artifacts": scope.artifact_requirements,
                    },
                    model_name=options.worker_model,
                    metadata={"workspace_profile": workspace.project_profile.value},
                )
            )
        return agents

    def _scope_for_role(self, role: str, workspace: WorkspaceSummary) -> ScopeSpec:
        hints = workspace.ownership_hints
        shared = ["README.md", "docs/**", ".CasperCode/**"]
        if role == "frontend":
            patterns = hints.get("frontend", ["ui/**", "web/**", "frontend/**", "templates/**"])
            return ScopeSpec(
                name="frontend",
                description="Owns UI, presentation, and client-side behavior.",
                include_patterns=patterns + shared,
                writable_patterns=patterns + ["docs/**"],
                exclude_patterns=["agent/**", "backend/**", "server/**"],
                artifact_requirements=["test_plan"],
                shared_patterns=shared,
            )
        if role == "backend":
            patterns = hints.get(
                "backend",
                ["agent/**", "core/**", "backend/**", "server/**", "services/**"],
            )
            return ScopeSpec(
                name="backend",
                description="Owns runtime, services, persistence, and server-side code.",
                include_patterns=patterns + shared,
                writable_patterns=patterns + ["tests/**", "docs/**"],
                exclude_patterns=["ui/**", "frontend/**", "web/**"],
                artifact_requirements=["api_contract"],
                shared_patterns=shared,
            )
        if role == "qa":
            patterns = hints.get("qa", ["tests/**", "scripts/**"])
            return ScopeSpec(
                name="qa",
                description="Owns automated verification, regression coverage, and review artifacts.",
                include_patterns=["**/*"],
                writable_patterns=patterns + ["docs/**"],
                read_only_patterns=["agent/**", "core/**", "ui/**", "web/**"],
                artifact_requirements=["test_plan", "review_report"],
                shared_patterns=shared,
            )
        if role == "devops":
            patterns = hints.get(
                "devops",
                ["infra/**", "deploy/**", ".github/**", "docker/**", "Dockerfile*"],
            )
            return ScopeSpec(
                name="devops",
                description="Owns CI/CD, deployment, infrastructure, and operational automation.",
                include_patterns=patterns + shared,
                writable_patterns=patterns + ["docs/**"],
                artifact_requirements=["dependency_impact_report"],
                shared_patterns=shared,
            )
        if role == "ml":
            patterns = hints.get("ml", ["models/**", "notebooks/**", "pipelines/**"])
            return ScopeSpec(
                name="ml",
                description="Owns model, evaluation, and data pipeline assets.",
                include_patterns=patterns + shared,
                writable_patterns=patterns + ["tests/**", "docs/**"],
                artifact_requirements=["schema_contract", "test_plan"],
                shared_patterns=shared,
            )
        if role == "security":
            return ScopeSpec(
                name="security",
                description="Owns auth, policy, secrets handling, and hardening changes.",
                include_patterns=["**/*"],
                writable_patterns=["safety/**", "config/**", "docs/**", "agent/**", "tests/**"],
                artifact_requirements=["review_report"],
                shared_patterns=shared,
            )
        if role == "planner":
            return ScopeSpec(
                name="planner",
                description="Owns architecture artifacts and task decomposition, not code mutation.",
                include_patterns=["**/*"],
                writable_patterns=["docs/**", ".CasperCode/**"],
                artifact_requirements=["architecture_spec", "decision_log"],
                shared_patterns=shared,
            )
        return ScopeSpec(
            name="generalist",
            description="Owns general implementation across the repo with lightweight boundaries.",
            include_patterns=["**/*"],
            writable_patterns=["**/*"],
            artifact_requirements=["test_plan"],
            shared_patterns=shared,
        )

    def _capabilities_for_role(self, role: str) -> list[str]:
        mapping = {
            "frontend": ["ui", "ux", "component", "routing"],
            "backend": ["api", "runtime", "storage", "jobs"],
            "qa": ["tests", "lint", "review", "regression"],
            "devops": ["ci", "deploy", "observability", "docker"],
            "ml": ["model", "evaluation", "pipeline", "dataset"],
            "security": ["auth", "policy", "audit", "hardening"],
            "planner": ["architecture", "planning", "decomposition"],
            "generalist": ["implementation", "refactor", "documentation"],
        }
        return mapping.get(role, ["implementation"])

    def _forbidden_actions_for_role(self, role: str) -> list[str]:
        mapping = {
            "frontend": ["write:backend_internals", "write:infra"],
            "backend": ["write:frontend_ui"],
            "qa": ["implement:business_logic"],
            "devops": ["write:app_business_logic"],
            "planner": ["apply:patch"],
        }
        return mapping.get(role, [])

    def _tools_for_role(self, role: str) -> list[str]:
        base = ["read_file", "list_dir", "grep_search", "glob_search"]
        if role in {"backend", "frontend", "devops", "ml", "security", "generalist"}:
            return [*base, "shell", "todo"]
        if role == "qa":
            return [*base, "shell"]
        return base

    def _validators_for_mode(
        self,
        mode: VerificationMode,
        workspace: WorkspaceSummary,
    ) -> list[str]:
        validators = ["changed_files", "boundary_consistency"]
        if mode in {VerificationMode.STRICT, VerificationMode.ENTERPRISE}:
            validators.append("tests")
        if workspace.project_profile in {
            ProjectProfile.PYTHON_SERVICE,
            ProjectProfile.FULLSTACK,
            ProjectProfile.AI_ML,
        }:
            validators.append("syntax")
        if mode == VerificationMode.ENTERPRISE:
            validators.extend(["lint", "security"])
        return validators
