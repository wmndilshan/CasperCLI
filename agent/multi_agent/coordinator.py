from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re
from uuid import uuid4

from agent.multi_agent.a2a import A2AMessage, A2AThread, InMemoryA2ABus
from agent.multi_agent.models import (
    AgentCapability,
    AgentProfile,
    AgentRole,
    AgentStatus,
    TaskAssignment,
)
from agent.multi_agent.store import AgentProfileStore
from agent.sessions.task_graph import SessionState, TaskNode
from config.config import Config
from jobs.job_models import JobResult


ROLE_COLORS = {
    AgentRole.COORDINATOR.value: "bright_magenta",
    AgentRole.PLANNER.value: "bright_cyan",
    AgentRole.BACKEND.value: "bright_green",
    AgentRole.FRONTEND.value: "bright_blue",
    AgentRole.QA.value: "yellow",
    "db": "bright_magenta",
    "jobs": "bright_red",
    "infra": "cyan",
    "security": "bright_yellow",
    "docs": "white",
}


def _capability(name: str, description: str, *keywords: str) -> AgentCapability:
    return AgentCapability(name=name, description=description, keywords=list(keywords))


def build_default_team(config: Config) -> list[AgentProfile]:
    return [
        AgentProfile(
            agent_id="agent-coordinator",
            role=AgentRole.COORDINATOR.value,
            name="Coordinator",
            model_name=config.planner_model_name,
            color=ROLE_COLORS[AgentRole.COORDINATOR.value],
            powers=["task_graph", "routing", "recovery", "a2a"],
            capabilities=[
                _capability(
                    "task-routing",
                    "Routes work across specialist agents and keeps the plan coherent.",
                    "plan",
                    "route",
                    "coordinate",
                    "dependency",
                )
            ],
            system_prompt="Coordinate specialist agents, keep the task graph coherent, and unblock execution.",
        ),
        AgentProfile(
            agent_id="agent-planner",
            role=AgentRole.PLANNER.value,
            name="Planner",
            model_name=config.planner_model_name,
            color=ROLE_COLORS[AgentRole.PLANNER.value],
            powers=["planning", "analysis", "architecture", "refactor"],
            capabilities=[
                _capability(
                    "reasoning",
                    "Performs long-horizon planning and repo understanding.",
                    "architecture",
                    "reason",
                    "analyze",
                    "refactor",
                )
            ],
            system_prompt="Build plans, analyze repositories, and prepare work for specialist executors.",
        ),
        AgentProfile(
            agent_id="agent-backend",
            role=AgentRole.BACKEND.value,
            name="Backend",
            model_name=config.executor_model_name,
            color=ROLE_COLORS[AgentRole.BACKEND.value],
            powers=["api", "runtime", "storage", "jobs", "database"],
            capabilities=[
                _capability(
                    "services",
                    "Implements APIs, data flows, storage, and runtime logic.",
                    "api",
                    "backend",
                    "database",
                    "storage",
                    "server",
                )
            ],
            system_prompt="Own backend implementation, storage, runtime jobs, and service logic.",
        ),
        AgentProfile(
            agent_id="agent-frontend",
            role=AgentRole.FRONTEND.value,
            name="Frontend",
            model_name=config.executor_model_name,
            color=ROLE_COLORS[AgentRole.FRONTEND.value],
            powers=["ui", "web", "components", "design"],
            capabilities=[
                _capability(
                    "interface",
                    "Builds UI, interactions, and presentation logic.",
                    "ui",
                    "frontend",
                    "style",
                    "component",
                    "page",
                )
            ],
            system_prompt="Own UI, interaction design, and developer-facing experience.",
        ),
        AgentProfile(
            agent_id="agent-qa",
            role=AgentRole.QA.value,
            name="QA",
            model_name=config.executor_model_name,
            color=ROLE_COLORS[AgentRole.QA.value],
            powers=["tests", "lint", "regression", "validation"],
            capabilities=[
                _capability(
                    "verification",
                    "Owns tests, review, and validation loops.",
                    "test",
                    "qa",
                    "verify",
                    "regression",
                    "review",
                )
            ],
            system_prompt="Own validation, regression detection, and quality gates.",
        ),
    ]


@dataclass
class MultiAgentCoordinator:
    config: Config
    bus: InMemoryA2ABus = field(default_factory=InMemoryA2ABus)
    store: AgentProfileStore = field(default_factory=AgentProfileStore)
    _teams: dict[str, list[AgentProfile]] = field(default_factory=dict)
    _assignments: dict[str, TaskAssignment] = field(default_factory=dict)
    _threads_by_task: dict[tuple[str, str], A2AThread] = field(default_factory=dict)

    def ensure_team(self, session_id: str) -> list[AgentProfile]:
        if session_id not in self._teams:
            self._teams[session_id] = [
                *build_default_team(self.config),
                *self.store.load(),
            ]
        return self._teams[session_id]

    def get_team(self, session_id: str) -> list[AgentProfile]:
        return self.ensure_team(session_id)

    def resolve_agent(self, session_id: str, identifier: str) -> AgentProfile | None:
        probe = identifier.strip().lower()
        for agent in self.ensure_team(session_id):
            if agent.agent_id.lower() == probe:
                return agent
            if agent.name.lower() == probe:
                return agent
            if agent.role.lower() == probe:
                return agent
        return None

    def add_custom_agent(
        self,
        session_id: str,
        *,
        name: str,
        role: str,
        model_name: str | None = None,
        color: str | None = None,
        powers: list[str] | None = None,
        mission: str | None = None,
        system_prompt: str | None = None,
        keywords: list[str] | None = None,
        source: str = "custom",
    ) -> AgentProfile:
        normalized_role = self._normalize_term(role)
        normalized_powers = self._normalize_terms(powers or [])
        capability_keywords = self._normalize_terms([normalized_role, *normalized_powers, *(keywords or [])])
        mission_text = mission or f"Own {normalized_role} work and collaborate with the rest of the agent team."
        agent = AgentProfile(
            agent_id=f"agent-{self._slugify(name)}-{str(uuid4())[:6]}",
            role=normalized_role,
            name=name.strip() or "Custom Agent",
            model_name=model_name or self._default_model_for_role(normalized_role),
            color=color or ROLE_COLORS.get(normalized_role, "bright_white"),
            powers=normalized_powers,
            system_prompt=system_prompt or self._build_system_prompt(name, normalized_role, normalized_powers, mission_text),
            source=source,
            capabilities=[
                AgentCapability(
                    name=f"{normalized_role}-specialist",
                    description=mission_text,
                    keywords=capability_keywords,
                )
            ],
        )
        self.store.upsert(agent)

        for key, team in self._teams.items():
            self._teams[key] = [
                existing
                for existing in team
                if existing.name.lower() != agent.name.lower() and existing.agent_id != agent.agent_id
            ]
            self._teams[key].append(agent)

        self.ensure_team(session_id)
        self._seed_onboarding_thread(session_id, agent, mission_text)
        return agent

    def remove_custom_agent(self, session_id: str, identifier: str) -> bool:
        deleted = self.store.delete(identifier)
        if not deleted:
            return False

        for key, team in self._teams.items():
            self._teams[key] = [
                agent
                for agent in team
                if not (
                    agent.source in {"custom", "generated"}
                    and (agent.agent_id == identifier or agent.name.lower() == identifier.lower())
                )
            ]

        self.ensure_team(session_id)
        return True

    def get_assignment(self, session_id: str, task_id: str) -> TaskAssignment | None:
        return self._assignments.get(f"{session_id}:{task_id}")

    def assign_task(self, state: SessionState, task: TaskNode) -> TaskAssignment:
        team = self.ensure_team(state.session_id)
        primary = self._select_primary_agent(team, task)
        supporting = [
            agent.agent_id
            for agent in team
            if agent.role == AgentRole.QA.value and agent.agent_id != primary.agent_id
        ]

        assignment = TaskAssignment(
            task_id=task.id,
            primary_agent_id=primary.agent_id,
            supporting_agent_ids=supporting,
            reason=self._assignment_reason(primary, task),
        )
        self._assignments[f"{state.session_id}:{task.id}"] = assignment

        primary.status = AgentStatus.RUNNING
        primary.current_task_id = task.id

        thread = self._ensure_task_thread(state, task, assignment)
        self.bus.send(
            A2AMessage(
                session_id=state.session_id,
                thread_id=thread.thread_id,
                task_id=task.id,
                sender_agent_id="agent-coordinator",
                recipient_agent_id=primary.agent_id,
                subject=f"Assigned: {task.title}",
                body=task.objective,
                kind="task_assignment",
            )
        )

        for agent_id in supporting:
            self.bus.send(
                A2AMessage(
                    session_id=state.session_id,
                    thread_id=thread.thread_id,
                    task_id=task.id,
                    sender_agent_id="agent-coordinator",
                    recipient_agent_id=agent_id,
                    subject=f"Support requested: {task.title}",
                    body="Track this task for verification and regression coverage.",
                    kind="support_request",
                )
            )

        state.task_assignments[task.id] = primary.role
        return assignment

    def record_outcome(self, state: SessionState, task: TaskNode, outcome: object) -> None:
        assignment = self.get_assignment(state.session_id, task.id)
        if assignment is None:
            return

        thread = self._ensure_task_thread(state, task, assignment)
        qa_agent = self._find_agent(self.ensure_team(state.session_id), AgentRole.QA.value)
        recipient = qa_agent.agent_id if qa_agent else assignment.primary_agent_id
        self.bus.send(
            A2AMessage(
                session_id=state.session_id,
                thread_id=thread.thread_id,
                task_id=task.id,
                sender_agent_id=assignment.primary_agent_id,
                recipient_agent_id=recipient,
                subject=f"Implementation update: {task.title}",
                body=str(outcome),
                kind="implementation_update",
            )
        )

        for agent in self.ensure_team(state.session_id):
            if agent.current_task_id == task.id:
                agent.status = AgentStatus.REVIEWING

    def record_job_update(self, state: SessionState, result: JobResult) -> None:
        task_id = result.metadata.get("task_id") if result.metadata else None
        if not task_id:
            return

        assignment = self.get_assignment(state.session_id, task_id)
        if assignment is None:
            return

        thread = self._threads_by_task.get((state.session_id, task_id))
        if thread is None:
            return

        self.bus.send(
            A2AMessage(
                session_id=state.session_id,
                thread_id=thread.thread_id,
                task_id=task_id,
                sender_agent_id="agent-coordinator",
                recipient_agent_id=assignment.primary_agent_id,
                subject=f"Job update: {result.status}",
                body=result.output or (result.error or "No output"),
                kind="job_update",
            )
        )

    def roster_rows(self, session_id: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for agent in self.ensure_team(session_id):
            rows.append(
                {
                    "agent_id": agent.agent_id,
                    "name": agent.name,
                    "role": agent.role,
                    "model": agent.model_name,
                    "status": agent.status.value,
                    "task_id": agent.current_task_id or "-",
                    "color": agent.color,
                    "powers": ", ".join(agent.powers) or "-",
                    "source": agent.source,
                }
            )
        return rows

    def agent_profile_row(self, session_id: str, identifier: str) -> dict[str, str] | None:
        agent = self.resolve_agent(session_id, identifier)
        if agent is None:
            return None

        mission = agent.capabilities[0].description if agent.capabilities else "-"
        return {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "role": agent.role,
            "model": agent.model_name,
            "status": agent.status.value,
            "color": agent.color,
            "powers": ", ".join(agent.powers) or "-",
            "source": agent.source,
            "mission": mission,
            "system_prompt": agent.system_prompt or "-",
            "keywords": ", ".join(agent.capabilities[0].keywords) if agent.capabilities else "-",
        }

    def thread_rows(self, session_id: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        threads = sorted(
            self.bus.threads_for_session(session_id),
            key=lambda thread: thread.messages[-1].created_at if thread.messages else datetime.min,
            reverse=True,
        )
        for thread in threads:
            participant_names = ", ".join(self._agent_label(session_id, agent_id) for agent_id in thread.participant_agent_ids)
            rows.append(
                {
                    "thread_id": thread.thread_id,
                    "topic": thread.topic,
                    "participants": participant_names or "-",
                    "messages": str(len(thread.messages)),
                    "last_subject": thread.messages[-1].subject if thread.messages else "-",
                }
            )
        return rows

    def message_rows(
        self,
        session_id: str,
        identifier: str | None = None,
        *,
        limit: int = 20,
    ) -> list[dict[str, str]]:
        filter_agent = self.resolve_agent(session_id, identifier) if identifier else None
        rows: list[tuple[datetime, dict[str, str]]] = []
        for thread in self.bus.threads_for_session(session_id):
            for message in thread.messages:
                if filter_agent and filter_agent.agent_id not in {
                    message.sender_agent_id,
                    message.recipient_agent_id,
                }:
                    continue
                rows.append(
                    (
                        message.created_at,
                        {
                            "time": message.created_at.strftime("%H:%M:%S"),
                            "thread": thread.topic,
                            "kind": message.kind,
                            "from": self._agent_label(session_id, message.sender_agent_id),
                            "to": self._agent_label(session_id, message.recipient_agent_id),
                            "subject": message.subject,
                            "body": message.body,
                            "sender_color": self._agent_color(session_id, message.sender_agent_id),
                            "recipient_color": self._agent_color(session_id, message.recipient_agent_id),
                        },
                    )
                )
        rows.sort(key=lambda item: item[0], reverse=True)
        return [payload for _, payload in rows[:limit]]

    def _select_primary_agent(
        self,
        team: list[AgentProfile],
        task: TaskNode,
    ) -> AgentProfile:
        text = f"{task.title} {task.objective}".lower()
        candidates = [
            agent for agent in team if agent.role not in {AgentRole.COORDINATOR.value}
        ]

        scored = [(self._score_agent(agent, text), agent) for agent in candidates]
        scored.sort(key=lambda item: item[0], reverse=True)
        if scored and scored[0][0] > 0:
            return scored[0][1]

        if any(token in text for token in ["ui", "frontend", "design", "page"]):
            return self._find_agent(team, AgentRole.FRONTEND.value) or candidates[0]
        if any(
            token in text
            for token in ["test", "qa", "verify", "lint", "type-check", "review"]
        ):
            return self._find_agent(team, AgentRole.QA.value) or candidates[0]
        if any(token in text for token in ["plan", "reason", "analyze", "architecture"]):
            return self._find_agent(team, AgentRole.PLANNER.value) or candidates[0]

        return self._find_agent(team, AgentRole.BACKEND.value) or candidates[0]

    def _find_agent(self, team: list[AgentProfile], role: str) -> AgentProfile | None:
        for agent in team:
            if agent.role == role:
                return agent
        return None

    def _score_agent(self, agent: AgentProfile, text: str) -> int:
        score = 0
        terms = {agent.role.lower(), agent.name.lower()}
        terms.update(power.lower() for power in agent.powers)
        for capability in agent.capabilities:
            terms.add(capability.name.lower())
            terms.update(keyword.lower() for keyword in capability.keywords)

        for term in terms:
            if term and term in text:
                score += 3 if term == agent.role.lower() else 1
        return score

    def _ensure_task_thread(
        self,
        state: SessionState,
        task: TaskNode,
        assignment: TaskAssignment,
    ) -> A2AThread:
        key = (state.session_id, task.id)
        thread = self._threads_by_task.get(key)
        if thread is None:
            participants = [assignment.primary_agent_id, *assignment.supporting_agent_ids]
            thread = self.bus.create_thread(
                session_id=state.session_id,
                topic=task.title,
                participant_agent_ids=["agent-coordinator", *participants],
            )
            self._threads_by_task[key] = thread
        return thread

    def _seed_onboarding_thread(self, session_id: str, agent: AgentProfile, mission: str) -> None:
        thread = self.bus.create_thread(
            session_id=session_id,
            topic=f"Agent onboarding: {agent.name}",
            participant_agent_ids=["agent-coordinator", agent.agent_id],
        )
        powers = ", ".join(agent.powers) or "general implementation"
        self.bus.send(
            A2AMessage(
                session_id=session_id,
                thread_id=thread.thread_id,
                sender_agent_id="agent-coordinator",
                recipient_agent_id=agent.agent_id,
                subject="Welcome to the team",
                body=(
                    f"You now own the {agent.role} lane. "
                    f"Mission: {mission} Powers: {powers}."
                ),
                kind="onboarding",
            )
        )
        self.bus.send(
            A2AMessage(
                session_id=session_id,
                thread_id=thread.thread_id,
                sender_agent_id=agent.agent_id,
                recipient_agent_id="agent-coordinator",
                subject="Capabilities acknowledged",
                body=f"Ready for {agent.role} work with powers: {powers}.",
                kind="ack",
            )
        )

    def _assignment_reason(self, agent: AgentProfile, task: TaskNode) -> str:
        return (
            f"Task '{task.title}' matched agent '{agent.name}' because its role is '{agent.role}' "
            f"and its powers are {', '.join(agent.powers) or 'general implementation'}"
        )

    def _default_model_for_role(self, role: str) -> str:
        if role in {AgentRole.COORDINATOR.value, AgentRole.PLANNER.value}:
            return self.config.planner_model_name
        return self.config.executor_model_name

    def _build_system_prompt(
        self,
        name: str,
        role: str,
        powers: list[str],
        mission: str | None,
    ) -> str:
        power_text = ", ".join(powers) if powers else "general software delivery"
        mission_text = mission or f"Own {role} work and collaborate with the rest of the agent team."
        return (
            f"You are {name}, a specialist {role} agent. "
            f"Your powers are: {power_text}. "
            f"Mission: {mission_text}"
        )

    def _agent_label(self, session_id: str, agent_id: str) -> str:
        for agent in self.ensure_team(session_id):
            if agent.agent_id == agent_id:
                return agent.name
        if agent_id == "agent-coordinator":
            return "Coordinator"
        return agent_id

    def _agent_color(self, session_id: str, agent_id: str) -> str:
        for agent in self.ensure_team(session_id):
            if agent.agent_id == agent_id:
                return agent.color
        if agent_id == "agent-coordinator":
            return ROLE_COLORS[AgentRole.COORDINATOR.value]
        return "white"

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "custom-agent"

    def _normalize_terms(self, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            term = self._normalize_term(value)
            if not term or term in seen:
                continue
            seen.add(term)
            result.append(term)
        return result

    def _normalize_term(self, value: str) -> str:
        value = value.strip().lower().replace("_", "-")
        value = re.sub(r"[^a-z0-9-]+", "-", value)
        value = re.sub(r"-+", "-", value).strip("-")
        return value
