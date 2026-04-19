"""Team synthesis package with lazy compiler loading to avoid import cycles."""

from importlib import import_module

from agent.team.models import (
    AgentSpec,
    AgentType,
    CoordinationPolicy,
    OwnershipMode,
    ProjectProfile,
    ResourcePolicy,
    ReviewPolicy,
    ScopeSpec,
    TeamPresetBlueprint,
    TeamSpec,
    TeamSynthesisOptions,
    VerificationMode,
    WorkspaceSummary,
)
from agent.team.presets import TEAM_PRESETS, get_team_preset, list_team_presets
from agent.team.synthesizer import TeamSynthesizer

__all__ = [
    "AgentSpec",
    "AgentType",
    "CoordinationPolicy",
    "OwnershipMode",
    "ProjectProfile",
    "ResourcePolicy",
    "ReviewPolicy",
    "ScopeSpec",
    "TEAM_PRESETS",
    "TeamCompiler",
    "TeamPresetBlueprint",
    "TeamSpec",
    "TeamSynthesizer",
    "TeamSynthesisOptions",
    "VerificationMode",
    "WorkspaceSummary",
    "get_team_preset",
    "list_team_presets",
]


def __getattr__(name: str):
    if name != "TeamCompiler":
        raise AttributeError(name)
    module = import_module("agent.team.compiler")
    value = getattr(module, name)
    globals()[name] = value
    return value
