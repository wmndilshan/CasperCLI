from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agent.artifacts.models import ArtifactKind
from agent.artifacts.store import ArtifactStore
from agent.runtime.patch_pipeline import PatchFragment, PatchOperation, PatchProposal
from agent.runtime.task_graph import TaskNode
from agent.team.models import AgentSpec, TeamSpec
from client.llm_client import LLMClient
from client.response import StreamEventType, TokenUsage, ToolCall
from config.config import ApprovalPolicy, Config
from context.manager import ContextManager
from hooks.hook_system import HookSystem
from tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from tools.registry import create_default_registry
from utils.paths import resolve_path


class ProposalFragmentInput(BaseModel):
    path: str
    operation: PatchOperation
    new_content: str | None = None
    rationale: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SubmitPatchProposalInput(BaseModel):
    title: str
    rationale: str
    fragments: list[ProposalFragmentInput]
    contract_changes: list[str] = Field(default_factory=list)
    required_artifacts: list[str] = Field(default_factory=list)
    affected_resources: list[str] = Field(default_factory=list)
    risk_metadata: dict[str, Any] = Field(default_factory=dict)


class PatchProposalCaptureTool(Tool):
    name = "submit_patch_proposal"
    description = (
        "Record a transactional patch proposal for the current hybrid worker task. "
        "This tool never writes to disk. For create/update fragments, provide the full "
        "final file content without line numbers."
    )
    kind = ToolKind.READ
    schema = SubmitPatchProposalInput

    def __init__(
        self,
        config: Config,
        *,
        workspace_root: Path,
        agent_spec: AgentSpec,
        task_id: str,
    ) -> None:
        super().__init__(config)
        self.workspace_root = workspace_root.resolve()
        self.agent_spec = agent_spec
        self.task_id = task_id
        self._proposals: list[PatchProposal] = []

    @property
    def proposals(self) -> list[PatchProposal]:
        return list(self._proposals)

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = SubmitPatchProposalInput(**invocation.params)
        fragments: list[PatchFragment] = []

        for fragment_input in params.fragments:
            try:
                relative_path = self._normalize_path(invocation.cwd, fragment_input.path)
            except ValueError as exc:
                return ToolResult.error_result(str(exc))

            file_path = self.workspace_root / relative_path
            exists = file_path.exists()

            if fragment_input.operation == PatchOperation.CREATE and exists:
                return ToolResult.error_result(
                    f"{relative_path} already exists; use update instead of create"
                )
            if fragment_input.operation in {PatchOperation.UPDATE, PatchOperation.DELETE} and not exists:
                return ToolResult.error_result(
                    f"{relative_path} does not exist; cannot {fragment_input.operation.value}"
                )
            if fragment_input.operation in {PatchOperation.CREATE, PatchOperation.UPDATE}:
                if fragment_input.new_content is None:
                    return ToolResult.error_result(
                        f"{relative_path} is missing new_content for {fragment_input.operation.value}"
                    )

            expected_old_content = None
            if exists and fragment_input.operation in {
                PatchOperation.UPDATE,
                PatchOperation.DELETE,
            }:
                expected_old_content = file_path.read_text(encoding="utf-8")

            fragments.append(
                PatchFragment(
                    path=relative_path,
                    operation=fragment_input.operation,
                    new_content=fragment_input.new_content,
                    expected_old_content=expected_old_content,
                    rationale=fragment_input.rationale,
                    metadata=fragment_input.metadata,
                )
            )

        proposal = PatchProposal(
            agent_id=self.agent_spec.id,
            task_id=self.task_id,
            title=params.title,
            fragments=fragments,
            rationale=params.rationale,
            contract_changes=params.contract_changes,
            required_artifacts=params.required_artifacts,
            affected_resources=params.affected_resources,
            risk_metadata=params.risk_metadata,
        )
        self._proposals.append(proposal)
        touched = ", ".join(proposal.touched_files()) or "no files"
        return ToolResult.success_result(
            f"Recorded {proposal.proposal_id} touching {touched}",
            metadata={
                "proposal_id": proposal.proposal_id,
                "fragment_count": len(fragments),
            },
        )

    def _normalize_path(self, cwd: Path, path: str) -> str:
        resolved = resolve_path(cwd, path).resolve()
        try:
            relative = resolved.relative_to(self.workspace_root)
        except ValueError as exc:
            raise ValueError(f"{path} is outside the workspace root") from exc
        return relative.as_posix()


@dataclass
class ProposalGenerationRequest:
    session_id: str
    goal: str
    workspace_root: Path
    team_spec: TeamSpec
    agent_spec: AgentSpec
    task: TaskNode
    artifact_store: ArtifactStore


@dataclass
class ProposalGenerationResult:
    proposals: list[PatchProposal] = field(default_factory=list)
    final_response: str | None = None
    usage: TokenUsage | None = None
    errors: list[str] = field(default_factory=list)
    skipped_reason: str | None = None


class LLMPatchProposalGenerator:
    """Generates patch proposals through the existing tool-calling runtime."""

    def __init__(
        self,
        base_config: Config,
        *,
        max_turns: int = 8,
    ) -> None:
        self.base_config = base_config
        self.max_turns = max_turns

    async def generate(
        self,
        request: ProposalGenerationRequest,
    ) -> ProposalGenerationResult:
        if not self.base_config.api_key:
            return ProposalGenerationResult(skipped_reason="missing-api-key")

        config = self._build_config(request)
        registry = create_default_registry(config)
        capture_tool = PatchProposalCaptureTool(
            config,
            workspace_root=request.workspace_root,
            agent_spec=request.agent_spec,
            task_id=request.task.id,
        )
        registry.register(capture_tool)

        hook_system = HookSystem(config)
        context = ContextManager(config=config, user_memory=None, tools=registry.get_tools())
        client = LLMClient(config=config)

        try:
            context.add_user_message(self._build_user_prompt(request))
            final_response: str | None = None
            last_usage: TokenUsage | None = None
            errors: list[str] = []

            for _ in range(config.max_turns):
                response_text = ""
                tool_calls: list[ToolCall] = []
                usage: TokenUsage | None = None

                async for event in client.chat_completion(
                    context.get_messages(),
                    tools=registry.get_schemas(),
                    stream=True,
                ):
                    if event.type == StreamEventType.TEXT_DELTA and event.text_delta:
                        response_text += event.text_delta.content
                    elif event.type == StreamEventType.TOOL_CALL_COMPLETE and event.tool_call:
                        tool_calls.append(event.tool_call)
                    elif event.type == StreamEventType.MESSAGE_COMPLETE:
                        usage = event.usage
                    elif event.type == StreamEventType.ERROR:
                        errors.append(event.error or "unknown-llm-error")

                context.add_assistant_message(
                    response_text or None,
                    tool_calls=[
                        {
                            "id": tool_call.call_id,
                            "type": "function",
                            "function": {
                                "name": tool_call.name,
                                "arguments": json.dumps(tool_call.arguments, sort_keys=True),
                            },
                        }
                        for tool_call in tool_calls
                    ]
                    or None,
                )
                if usage:
                    context.set_latest_usage(usage)
                    context.add_usage(usage)
                    last_usage = usage
                final_response = response_text or final_response

                if not tool_calls:
                    break

                for tool_call in tool_calls:
                    result = await registry.invoke(
                        tool_call.name or "",
                        tool_call.arguments,
                        config.cwd,
                        hook_system,
                    )
                    context.add_tool_result(tool_call.call_id, result.to_model_output())

                if capture_tool.proposals:
                    break

            return ProposalGenerationResult(
                proposals=capture_tool.proposals,
                final_response=final_response,
                usage=last_usage,
                errors=errors,
                skipped_reason=None if capture_tool.proposals or not errors else "generation-failed",
            )
        finally:
            await client.close()

    def _build_config(self, request: ProposalGenerationRequest) -> Config:
        config = self.base_config.model_copy(deep=True)
        config.cwd = request.workspace_root
        config.approval = ApprovalPolicy.NEVER
        config.allowed_tools = self._tool_names_for_agent(request.agent_spec)
        config.hooks_enabled = False
        config.max_turns = min(config.max_turns, self.max_turns)
        config.model_name = (
            request.agent_spec.model_name
            or self.base_config.executor_model_name
            or self.base_config.model_name
        )

        worker_instructions = self._build_worker_instructions(request)
        if config.developer_instructions:
            config.developer_instructions = (
                f"{config.developer_instructions}\n\n{worker_instructions}"
            )
        else:
            config.developer_instructions = worker_instructions
        return config

    def _tool_names_for_agent(self, agent_spec: AgentSpec) -> list[str]:
        allowed = {"read_file", "list_dir", "grep", "glob", "submit_patch_proposal"}
        normalized = []
        for tool_name in agent_spec.allowed_tools:
            canonical = {"grep_search": "grep", "glob_search": "glob"}.get(
                tool_name,
                tool_name,
            )
            if canonical in allowed and canonical not in normalized:
                normalized.append(canonical)
        for default in ("read_file", "list_dir", "grep", "glob", "submit_patch_proposal"):
            if default not in normalized and default in allowed:
                normalized.append(default)
        return normalized

    def _build_worker_instructions(self, request: ProposalGenerationRequest) -> str:
        scope = json.dumps(request.agent_spec.scope.model_dump(mode="json"), indent=2)
        ownership = json.dumps(request.team_spec.ownership_map, indent=2, sort_keys=True)
        architecture = self._artifact_content(
            request.artifact_store,
            ArtifactKind.ARCHITECTURE_SPEC,
            request.session_id,
        )
        return (
            f"You are the {request.agent_spec.role} worker ({request.agent_spec.id}) inside the "
            "hybrid multi-agent runtime.\n"
            "Your job is to inspect the repository and submit transactional patch proposals.\n"
            "Hard requirements:\n"
            "- Never attempt direct file edits or shell mutations.\n"
            "- Use only read-only tools and submit_patch_proposal.\n"
            "- Stay within writable scope. If the best fix crosses boundaries, do not propose it.\n"
            "- Prefer zero proposals over risky or speculative changes.\n"
            "- Each fragment must represent the complete final content of one file. Do not include line numbers.\n"
            "- If you update or create code, include nearby tests or docs when your scope allows it.\n"
            f"- Required artifacts for your role: {request.agent_spec.scope.artifact_requirements or ['none']}.\n\n"
            f"Worker scope:\n{scope}\n\n"
            f"Team ownership map:\n{ownership}\n\n"
            f"Architecture artifact:\n{architecture}\n"
        )

    def _build_user_prompt(self, request: ProposalGenerationRequest) -> str:
        workspace_summary = json.dumps(
            request.team_spec.metadata.get("workspace", {}),
            indent=2,
            sort_keys=True,
        )
        return (
            f"Goal: {request.goal}\n"
            f"Task ID: {request.task.id}\n"
            f"Task Title: {request.task.title}\n"
            f"Task Objective: {request.task.objective}\n"
            f"Agent Role: {request.agent_spec.role}\n"
            f"Capabilities: {', '.join(request.agent_spec.capabilities) or 'none'}\n\n"
            "Workspace summary:\n"
            f"{workspace_summary}\n\n"
            "Inspect the relevant files first. Then call submit_patch_proposal for each coherent change set.\n"
            "If no safe change is needed or your scope is not implicated, explain that briefly and submit no proposals."
        )

    def _artifact_content(
        self,
        store: ArtifactStore,
        kind: ArtifactKind,
        key: str,
    ) -> str:
        artifact = store.get_latest(kind, key)
        if not artifact:
            return "none"
        return json.dumps(artifact.content, indent=2, sort_keys=True)
