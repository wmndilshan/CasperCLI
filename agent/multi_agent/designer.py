from __future__ import annotations

import asyncio
import json
import re
from typing import Iterable

from agent.multi_agent.models import AgentDesignDraft, AgentProfile
from client.llm_client import LLMClient
from client.response import StreamEventType
from config.config import Config


ROLE_COLOR_MAP = {
    "coordinator": "bright_magenta",
    "planner": "bright_cyan",
    "backend": "bright_green",
    "frontend": "bright_blue",
    "qa": "yellow",
    "db": "bright_magenta",
    "database": "bright_magenta",
    "jobs": "bright_red",
    "worker": "bright_red",
    "infra": "cyan",
    "security": "bright_yellow",
    "docs": "white",
}

ROLE_POWER_MAP = {
    "frontend": ["ui", "web", "components", "design"],
    "backend": ["api", "runtime", "storage", "jobs", "database"],
    "qa": ["tests", "lint", "regression", "validation"],
    "planner": ["planning", "analysis", "architecture", "refactor"],
    "coordinator": ["task-graph", "routing", "recovery", "a2a"],
    "db": ["sql", "migrations", "schema", "query-tuning", "json"],
    "database": ["sql", "migrations", "schema", "query-tuning", "json"],
    "jobs": ["queues", "workers", "scheduling", "retries", "monitoring"],
    "worker": ["queues", "workers", "scheduling", "retries", "monitoring"],
    "infra": ["docker", "ci", "deploy", "observability"],
    "security": ["auth", "audit", "secrets", "hardening"],
    "docs": ["documentation", "examples", "guides"],
}

ROLE_NAME_MAP = {
    "frontend": "Frontend Forge",
    "backend": "Backend Ops",
    "qa": "Quality Gate",
    "planner": "Strategy Planner",
    "coordinator": "Mission Control",
    "db": "DataOps",
    "database": "DataOps",
    "jobs": "JobRunner",
    "worker": "JobRunner",
    "infra": "Platform Ops",
    "security": "Security Sentinel",
    "docs": "Docs Pilot",
}

KEYWORD_ROLE_MAP = {
    "ui": "frontend",
    "frontend": "frontend",
    "web": "frontend",
    "component": "frontend",
    "page": "frontend",
    "style": "frontend",
    "api": "backend",
    "server": "backend",
    "runtime": "backend",
    "storage": "backend",
    "database": "db",
    "db": "db",
    "sql": "db",
    "migration": "db",
    "query": "db",
    "job": "jobs",
    "queue": "jobs",
    "worker": "jobs",
    "schedule": "jobs",
    "background": "jobs",
    "test": "qa",
    "qa": "qa",
    "verify": "qa",
    "regression": "qa",
    "review": "qa",
    "plan": "planner",
    "architecture": "planner",
    "reason": "planner",
    "orchestrate": "coordinator",
    "route": "coordinator",
    "coordinate": "coordinator",
    "infra": "infra",
    "deploy": "infra",
    "docker": "infra",
    "security": "security",
    "auth": "security",
    "audit": "security",
    "docs": "docs",
    "documentation": "docs",
}


class AgentDesigner:
    def __init__(self, config: Config) -> None:
        self.config = config

    async def design(
        self,
        brief: str,
        existing_agents: list[AgentProfile] | None = None,
    ) -> AgentDesignDraft:
        existing_agents = existing_agents or []
        llm_response = await self._generate_with_llm(brief, existing_agents)
        if llm_response:
            parsed = self._parse_llm_response(llm_response)
            if parsed is not None:
                return self._normalize_draft(parsed, brief, design_source="llm")

        return self._fallback_design(brief, existing_agents)

    async def _generate_with_llm(
        self,
        brief: str,
        existing_agents: list[AgentProfile],
    ) -> str | None:
        if not self.config.api_key:
            return None

        design_config = self.config.model_copy(deep=True)
        design_config.model.name = self.config.planner_model_name
        design_config.model.temperature = 0.2
        client = LLMClient(design_config)

        existing_summary = [
            {
                "name": agent.name,
                "role": agent.role,
                "powers": agent.powers,
            }
            for agent in existing_agents
        ]

        messages = [
            {
                "role": "system",
                "content": (
                    "You design specialist agents for a terminal AI coding system. "
                    "Return exactly one JSON object and no markdown. "
                    "Keys: name, role, color, powers, mission, system_prompt, keywords, model_name. "
                    "Use short role names such as frontend, backend, qa, db, jobs, infra, docs, security, planner, coordinator. "
                    "Use deepseek-reasoner only for coordinator/planner roles and deepseek-coder for all implementation roles."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "brief": brief,
                        "existing_agents": existing_summary,
                        "color_palette": sorted(set(ROLE_COLOR_MAP.values())),
                    }
                ),
            },
        ]

        try:
            async with asyncio.timeout(12):
                async for event in client.chat_completion(messages, tools=None, stream=False):
                    if event.type == StreamEventType.ERROR:
                        return None
                    if event.type == StreamEventType.MESSAGE_COMPLETE and event.text_delta:
                        return event.text_delta.content
        except TimeoutError:
            return None
        except Exception:
            return None
        finally:
            await client.close()

        return None

    def _parse_llm_response(self, content: str) -> AgentDesignDraft | None:
        payload = self._extract_json_object(content)
        if payload is None:
            return None

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None

        if isinstance(data.get("powers"), str):
            data["powers"] = [item.strip() for item in data["powers"].split(",") if item.strip()]
        if isinstance(data.get("keywords"), str):
            data["keywords"] = [item.strip() for item in data["keywords"].split(",") if item.strip()]

        try:
            return AgentDesignDraft(**data)
        except Exception:
            return None

    def _extract_json_object(self, content: str) -> str | None:
        content = content.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL)
        if fenced:
            return fenced.group(1)

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return match.group(0)
        return None

    def _normalize_draft(
        self,
        draft: AgentDesignDraft,
        brief: str,
        *,
        design_source: str,
    ) -> AgentDesignDraft:
        role = self._normalize_role(draft.role or self._infer_role(brief))
        powers = self._unique_terms([*draft.powers, *self._infer_powers(brief, role)])
        keywords = self._unique_terms([*draft.keywords, role, *powers])
        color = draft.color or self._infer_color(role, powers)
        model_name = draft.model_name or self._default_model_for_role(role)
        mission = self._clean_sentence(draft.mission or brief)
        name = self._clean_name(draft.name or self._infer_name(brief, role))
        system_prompt = draft.system_prompt or self._build_system_prompt(name, role, powers, mission)

        return AgentDesignDraft(
            name=name,
            role=role,
            color=color,
            powers=powers,
            mission=mission,
            system_prompt=system_prompt,
            keywords=keywords,
            model_name=model_name,
            design_source=design_source,
        )

    def _fallback_design(
        self,
        brief: str,
        existing_agents: list[AgentProfile],
    ) -> AgentDesignDraft:
        role = self._infer_role(brief)
        powers = self._infer_powers(brief, role)
        keywords = self._unique_terms([role, *powers])
        name = self._infer_name(brief, role, existing_agents)
        mission = self._clean_sentence(brief)
        color = self._infer_color(role, powers)
        model_name = self._default_model_for_role(role)
        system_prompt = self._build_system_prompt(name, role, powers, mission)
        return AgentDesignDraft(
            name=name,
            role=role,
            color=color,
            powers=powers,
            mission=mission,
            system_prompt=system_prompt,
            keywords=keywords,
            model_name=model_name,
            design_source="heuristic",
        )

    def _infer_role(self, brief: str) -> str:
        text = brief.lower()
        scores: dict[str, int] = {}
        for keyword, role in KEYWORD_ROLE_MAP.items():
            if keyword in text:
                scores[role] = scores.get(role, 0) + 1

        if scores:
            return max(scores.items(), key=lambda item: item[1])[0]
        return "backend"

    def _infer_powers(self, brief: str, role: str) -> list[str]:
        text = brief.lower()
        powers = list(ROLE_POWER_MAP.get(role, []))
        keyword_powers = {
            "json": "json",
            "sql": "sql",
            "migration": "migrations",
            "queue": "queues",
            "retry": "retries",
            "monitor": "monitoring",
            "cache": "cache",
            "auth": "auth",
            "secret": "secrets",
            "docs": "documentation",
            "search": "search",
            "index": "indexing",
            "worker": "workers",
        }
        for keyword, power in keyword_powers.items():
            if keyword in text:
                powers.append(power)
        return self._unique_terms(powers)

    def _infer_name(
        self,
        brief: str,
        role: str,
        existing_agents: list[AgentProfile] | None = None,
    ) -> str:
        named_match = re.search(r"(?:named|called)\s+([A-Za-z][A-Za-z0-9_-]{1,30})", brief)
        if named_match:
            base_name = named_match.group(1)
        else:
            base_name = ROLE_NAME_MAP.get(role, f"{role.title()} Agent")

        existing_names = {agent.name.lower() for agent in (existing_agents or [])}
        if base_name.lower() not in existing_names:
            return base_name

        suffix = 2
        while f"{base_name} {suffix}".lower() in existing_names:
            suffix += 1
        return f"{base_name} {suffix}"

    def _infer_color(self, role: str, powers: Iterable[str]) -> str:
        if role in ROLE_COLOR_MAP:
            return ROLE_COLOR_MAP[role]
        for power in powers:
            if power in ROLE_COLOR_MAP:
                return ROLE_COLOR_MAP[power]
        return "bright_white"

    def _default_model_for_role(self, role: str) -> str:
        if role in {"coordinator", "planner"}:
            return self.config.planner_model_name
        return self.config.executor_model_name

    def _build_system_prompt(
        self,
        name: str,
        role: str,
        powers: list[str],
        mission: str,
    ) -> str:
        power_text = ", ".join(powers) if powers else "general software delivery"
        return (
            f"You are {name}, a specialist {role} agent inside CasperCode. "
            f"Your powers are {power_text}. "
            f"Mission: {mission}. "
            "Collaborate through structured A2A handoffs, keep updates concise, and focus on your ownership area."
        )

    def _normalize_role(self, role: str) -> str:
        role = role.strip().lower().replace("_", "-")
        role = re.sub(r"[^a-z0-9-]+", "-", role)
        role = re.sub(r"-+", "-", role).strip("-")
        return role or "backend"

    def _clean_name(self, name: str) -> str:
        name = re.sub(r"\s+", " ", name.strip())
        return name or "Custom Agent"

    def _clean_sentence(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text.strip())
        return text.rstrip(".") + "." if text else "Own this specialist role for the team."

    def _unique_terms(self, items: Iterable[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for item in items:
            term = item.strip().lower().replace(" ", "-")
            term = re.sub(r"[^a-z0-9-]+", "-", term)
            term = re.sub(r"-+", "-", term).strip("-")
            if not term or term in seen:
                continue
            seen.add(term)
            result.append(term)
        return result

