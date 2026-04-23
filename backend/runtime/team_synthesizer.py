from __future__ import annotations

import uuid
from pathlib import Path

from models.schemas import AgentKind, AgentSpec, AgentStatus, OwnershipRules, TeamSpec


class TeamSynthesizer:
    """
    Produces a structured team from goal + workspace context.
    Always includes the nine agent archetypes; adds extra LLM workers to reach team_size.
    """

    def synthesize(
        self,
        *,
        project_root: Path,
        goal: str,
        team_size: int,
        strict: bool,
        project_context: str = "",
    ) -> TeamSpec:
        team_id = f"team_{uuid.uuid4().hex[:10]}"
        root = project_root.resolve()
        scope = [str(root), str(root / "backend"), str(root / "frontend")]

        control_plane: list[AgentSpec] = [
            AgentSpec(
                id=f"agent_scheduler_{uuid.uuid4().hex[:6]}",
                kind=AgentKind.SCHEDULER,
                role="scheduler",
                scope_paths=scope,
                permissions=["graph:edit", "task:assign"],
                forbidden_actions=["filesystem:write"],
            ),
            AgentSpec(
                id=f"agent_boundary_{uuid.uuid4().hex[:6]}",
                kind=AgentKind.BOUNDARY,
                role="boundary",
                scope_paths=scope,
                permissions=["policy:validate"],
                forbidden_actions=["shell:run"],
            ),
            AgentSpec(
                id=f"agent_rule_{uuid.uuid4().hex[:6]}",
                kind=AgentKind.RULE_BASED,
                role="rules",
                scope_paths=scope,
                permissions=["lint:fix"],
                forbidden_actions=["deps:bump"],
            ),
            AgentSpec(
                id=f"agent_exec_{uuid.uuid4().hex[:6]}",
                kind=AgentKind.EXECUTION,
                role="execution",
                scope_paths=scope,
                permissions=["code:write"],
                forbidden_actions=["infra:destroy"],
            ),
            AgentSpec(
                id=f"agent_conflict_{uuid.uuid4().hex[:6]}",
                kind=AgentKind.CONFLICT_DETECTION,
                role="conflict",
                scope_paths=scope,
                permissions=["patch:analyze"],
                forbidden_actions=["patch:apply"],
            ),
            AgentSpec(
                id=f"agent_merge_{uuid.uuid4().hex[:6]}",
                kind=AgentKind.MERGE,
                role="merge",
                scope_paths=scope,
                permissions=["patch:merge"],
                forbidden_actions=["force:push"],
            ),
            AgentSpec(
                id=f"agent_verify_{uuid.uuid4().hex[:6]}",
                kind=AgentKind.VERIFICATION,
                role="verification",
                scope_paths=scope,
                permissions=["ci:trigger"],
                forbidden_actions=["prod:deploy"],
            ),
            AgentSpec(
                id=f"agent_integrator_{uuid.uuid4().hex[:6]}",
                kind=AgentKind.INTEGRATOR,
                role="integrator",
                scope_paths=scope,
                permissions=["workspace:coordinate"],
                forbidden_actions=[],
            ),
        ]

        llm_count = max(1, team_size - len(control_plane))
        llm_workers = [
            AgentSpec(
                id=f"agent_llm_{i}_{uuid.uuid4().hex[:4]}",
                kind=AgentKind.LLM_WORKER,
                role="llm_worker",
                scope_paths=scope,
                permissions=["code:assist", "search:repo"],
                forbidden_actions=["secrets:read"],
                metadata={"worker_index": i},
            )
            for i in range(llm_count)
        ]

        agents = control_plane + llm_workers
        if len(llm_workers) >= 2:
            path_owners = {"backend/": llm_workers[0].id, "frontend/": llm_workers[-1].id}
        elif llm_workers:
            path_owners = {"backend/": llm_workers[0].id}
        else:
            path_owners = {}

        ownership = OwnershipRules(
            strict=strict,
            default_owner=llm_workers[0].id if llm_workers else None,
            path_prefix_owners=path_owners,
        )

        notes = [
            f"goal={goal[:120]}",
            f"context_hint={project_context[:120]}" if project_context else "context_hint=none",
            f"parallel_workers={llm_count}",
        ]

        return TeamSpec(
            team_id=team_id,
            project_root=str(root),
            goal=goal,
            agents=agents,
            ownership=ownership,
            synthesis_notes=notes,
        )
