from __future__ import annotations

from agent.team.models import OwnershipMode, TeamPresetBlueprint, VerificationMode


TEAM_PRESETS: dict[str, TeamPresetBlueprint] = {
    "solo": TeamPresetBlueprint(
        name="solo",
        description="A single implementation lane backed by governance agents.",
        worker_roles=["generalist"],
        default_verification_mode=VerificationMode.LIGHTWEIGHT,
        recommended_parallelism=1,
    ),
    "fullstack": TeamPresetBlueprint(
        name="fullstack",
        description="Balanced frontend, backend, and QA specialists.",
        worker_roles=["planner", "backend", "frontend", "qa"],
        default_verification_mode=VerificationMode.STRICT,
        recommended_parallelism=4,
    ),
    "backend-platform": TeamPresetBlueprint(
        name="backend-platform",
        description="Backend-heavy team for APIs, persistence, jobs, and infra.",
        worker_roles=["planner", "backend", "backend", "qa", "devops"],
        default_verification_mode=VerificationMode.STRICT,
        recommended_parallelism=4,
    ),
    "frontend-experience": TeamPresetBlueprint(
        name="frontend-experience",
        description="Frontend-heavy team focused on UX, app shell, and tests.",
        worker_roles=["planner", "frontend", "frontend", "qa"],
        default_verification_mode=VerificationMode.STRICT,
        recommended_parallelism=4,
    ),
    "ai-ml": TeamPresetBlueprint(
        name="ai-ml",
        description="Model, evaluation, API, and data pipeline specialists.",
        worker_roles=["planner", "ml", "backend", "qa"],
        default_verification_mode=VerificationMode.STRICT,
        recommended_parallelism=4,
    ),
    "devops": TeamPresetBlueprint(
        name="devops",
        description="Infrastructure, automation, reliability, and release focus.",
        worker_roles=["planner", "devops", "backend", "qa"],
        default_verification_mode=VerificationMode.STRICT,
        recommended_parallelism=3,
    ),
    "incident-response": TeamPresetBlueprint(
        name="incident-response",
        description="Triage, containment, remediation, and verification under pressure.",
        worker_roles=["planner", "backend", "qa", "security"],
        default_verification_mode=VerificationMode.STRICT,
        recommended_parallelism=3,
        strict_default=True,
    ),
    "enterprise-strict": TeamPresetBlueprint(
        name="enterprise-strict",
        description="High-governance delivery with stricter review and ownership rules.",
        worker_roles=["planner", "backend", "frontend", "qa", "devops", "security"],
        default_verification_mode=VerificationMode.ENTERPRISE,
        default_ownership_mode=OwnershipMode.STRICT,
        recommended_parallelism=4,
        strict_default=True,
    ),
    "startup-mvp": TeamPresetBlueprint(
        name="startup-mvp",
        description="Fast-moving delivery with fewer gates and a generalist bias.",
        worker_roles=["planner", "backend", "frontend", "qa"],
        default_verification_mode=VerificationMode.LIGHTWEIGHT,
        default_ownership_mode=OwnershipMode.FLEXIBLE,
        recommended_parallelism=4,
    ),
}


def get_team_preset(name: str) -> TeamPresetBlueprint:
    try:
        return TEAM_PRESETS[name]
    except KeyError as exc:
        available = ", ".join(sorted(TEAM_PRESETS))
        raise KeyError(f"Unknown team preset '{name}'. Available presets: {available}") from exc


def list_team_presets() -> list[str]:
    return sorted(TEAM_PRESETS)
