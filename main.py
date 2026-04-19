import asyncio
from pathlib import Path
import shlex
import sys

import click
from dotenv import load_dotenv

from agent.agent import Agent
from agent.events import AgentEventType
from agent.multi_agent import AgentDesigner, MultiAgentCoordinator
from agent.persistence import PersistenceManager, SessionSnapshot
from agent.runtime.orchestrator import HybridOrchestrator, HybridRunRequest
from agent.session import Session
from config.config import ApprovalPolicy, Config
from config.loader import load_config
from agent.team import OwnershipMode, TeamSynthesisOptions, VerificationMode, list_team_presets
from ui.tui import TUI, get_console

console = get_console()


class CLI:
    def __init__(self, config: Config):
        self.agent: Agent | None = None
        self.config = config
        self.tui = TUI(config, console)
        self.multi_agent_coordinator = MultiAgentCoordinator(config)
        self.agent_designer = AgentDesigner(config)

    async def run_single(self, message: str) -> str | None:
        async with Agent(self.config) as agent:
            self.agent = agent
            self.multi_agent_coordinator.ensure_team(self._active_team_session_id())
            return await self._process_message(message)

    async def run_interactive(self) -> str | None:
        self.tui.print_welcome(
            "AI Agent",
            lines=[
                f"model: {self.config.model_name}",
                f"cwd: {self.config.cwd}",
                "commands: /help /config /approval /model /agents /exit",
            ],
        )

        async with Agent(
            self.config,
            confirmation_callback=self.tui.handle_confirmation,
        ) as agent:
            self.agent = agent
            self.multi_agent_coordinator.ensure_team(self._active_team_session_id())

            while True:
                try:
                    user_input = console.input("\n[user]>[/user] ").strip()
                    if not user_input:
                        continue

                    if user_input.startswith("/"):
                        should_continue = await self._handle_command(user_input)
                        if not should_continue:
                            break
                        continue

                    await self._process_message(user_input)
                except KeyboardInterrupt:
                    console.print("\n[dim]Use /exit to quit[/dim]")
                except EOFError:
                    break

        console.print("\n[dim]Goodbye![/dim]")
        return None

    def _get_tool_kind(self, tool_name: str) -> str | None:
        if not self.agent:
            return None
        tool = self.agent.session.tool_registry.get(tool_name)
        if not tool:
            return None
        return tool.kind.value

    async def _process_message(self, message: str) -> str | None:
        if not self.agent:
            return None

        assistant_streaming = False
        final_response: str | None = None

        async for event in self.agent.run(message):
            if event.type == AgentEventType.TEXT_DELTA:
                content = event.data.get("content", "")
                if not assistant_streaming:
                    self.tui.begin_assistant()
                    assistant_streaming = True
                self.tui.stream_assistant_delta(content)
            elif event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get("content")
                if assistant_streaming:
                    self.tui.end_assistant()
                    assistant_streaming = False
            elif event.type == AgentEventType.AGENT_ERROR:
                error = event.data.get("error", "Unknown error")
                console.print(f"\n[error]Error: {error}[/error]")
            elif event.type == AgentEventType.TOOL_CALL_START:
                tool_name = event.data.get("name", "unknown")
                tool_kind = self._get_tool_kind(tool_name)
                self.tui.tool_call_start(
                    event.data.get("call_id", ""),
                    tool_name,
                    tool_kind,
                    event.data.get("arguments", {}),
                )
            elif event.type == AgentEventType.TOOL_CALL_COMPLETE:
                tool_name = event.data.get("name", "unknown")
                tool_kind = self._get_tool_kind(tool_name)
                self.tui.tool_call_complete(
                    event.data.get("call_id", ""),
                    tool_name,
                    tool_kind,
                    event.data.get("success", False),
                    event.data.get("output", ""),
                    event.data.get("error"),
                    event.data.get("metadata"),
                    event.data.get("diff"),
                    event.data.get("truncated", False),
                    event.data.get("exit_code"),
                )

        return final_response

    async def _handle_command(self, command: str) -> bool:
        command = command.strip()
        parts = command.split(maxsplit=1)
        cmd_name = parts[0].lower()
        cmd_args = parts[1] if len(parts) > 1 else ""

        if cmd_name in {"/exit", "/quit"}:
            return False
        if cmd_name == "/help":
            self.tui.show_help()
        elif cmd_name == "/clear":
            self.agent.session.context_manager.clear()
            self.agent.session.loop_detector.clear()
            console.print("[success]Conversation cleared[/success]")
        elif cmd_name == "/config":
            console.print("\n[bold]Current Configuration[/bold]")
            console.print(f"  Model: {self.config.model_name}")
            console.print(f"  Planner Model: {self.config.planner_model_name}")
            console.print(f"  Executor Model: {self.config.executor_model_name}")
            console.print(f"  Temperature: {self.config.temperature}")
            console.print(f"  Approval: {self.config.approval.value}")
            console.print(f"  Working Dir: {self.config.cwd}")
            console.print(f"  Max Turns: {self.config.max_turns}")
            console.print(f"  Hooks Enabled: {self.config.hooks_enabled}")
            console.print(f"  Multi Agent: {self.config.multi_agent_enabled}")
        elif cmd_name == "/model":
            if cmd_args:
                self.config.model_name = cmd_args
                console.print(f"[success]Model changed to: {cmd_args}[/success]")
            else:
                console.print(f"Current model: {self.config.model_name}")
        elif cmd_name == "/approval":
            if cmd_args:
                try:
                    approval = ApprovalPolicy(cmd_args)
                    self.config.approval = approval
                    console.print(
                        f"[success]Approval policy changed to: {cmd_args}[/success]"
                    )
                except Exception:
                    console.print(
                        f"[error]Incorrect approval policy: {cmd_args}[/error]"
                    )
                    console.print(
                        f"Valid options: {', '.join(policy.value for policy in ApprovalPolicy)}"
                    )
            else:
                console.print(f"Current approval policy: {self.config.approval.value}")
        elif cmd_name == "/stats":
            stats = self.agent.session.get_stats()
            console.print("\n[bold]Session Statistics[/bold]")
            for key, value in stats.items():
                console.print(f"  {key}: {value}")
        elif cmd_name == "/agents":
            await self._handle_agents_command(cmd_args)
        elif cmd_name == "/tools":
            tools = self.agent.session.tool_registry.get_tools()
            console.print(f"\n[bold]Available tools ({len(tools)})[/bold]")
            for tool in tools:
                console.print(f"  - {tool.name}")
        elif cmd_name == "/mcp":
            mcp_servers = self.agent.session.mcp_manager.get_all_servers()
            console.print(f"\n[bold]MCP Servers ({len(mcp_servers)})[/bold]")
            for server in mcp_servers:
                status = server["status"]
                status_color = "green" if status == "connected" else "red"
                console.print(
                    f"  - {server['name']}: [{status_color}]{status}[/{status_color}] ({server['tools']} tools)"
                )
        elif cmd_name == "/save":
            persistence_manager = PersistenceManager()
            session_snapshot = SessionSnapshot(
                session_id=self.agent.session.session_id,
                created_at=self.agent.session.created_at,
                updated_at=self.agent.session.updated_at,
                turn_count=self.agent.session.turn_count,
                messages=self.agent.session.context_manager.get_messages(),
                total_usage=self.agent.session.context_manager.total_usage,
            )
            persistence_manager.save_session(session_snapshot)
            console.print(
                f"[success]Session saved: {self.agent.session.session_id}[/success]"
            )
        elif cmd_name == "/sessions":
            persistence_manager = PersistenceManager()
            sessions = persistence_manager.list_sessions()
            console.print("\n[bold]Saved Sessions[/bold]")
            for snapshot in sessions:
                console.print(
                    f"  - {snapshot['session_id']} (turns: {snapshot['turn_count']}, updated: {snapshot['updated_at']})"
                )
        elif cmd_name == "/resume":
            await self._resume_session(cmd_args)
        elif cmd_name == "/checkpoint":
            persistence_manager = PersistenceManager()
            session_snapshot = SessionSnapshot(
                session_id=self.agent.session.session_id,
                created_at=self.agent.session.created_at,
                updated_at=self.agent.session.updated_at,
                turn_count=self.agent.session.turn_count,
                messages=self.agent.session.context_manager.get_messages(),
                total_usage=self.agent.session.context_manager.total_usage,
            )
            checkpoint_id = persistence_manager.save_checkpoint(session_snapshot)
            console.print(f"[success]Checkpoint created: {checkpoint_id}[/success]")
        elif cmd_name == "/restore":
            await self._restore_checkpoint(cmd_args)
        else:
            console.print(f"[error]Unknown command: {cmd_name}[/error]")

        return True

    async def _resume_session(self, session_id: str) -> None:
        if not session_id:
            console.print("[error]Usage: /resume <session_id>[/error]")
            return

        persistence_manager = PersistenceManager()
        snapshot = persistence_manager.load_session(session_id)
        if not snapshot:
            console.print("[error]Session does not exist[/error]")
            return

        session = await self._hydrate_session(snapshot)
        self.agent.session = session
        self.multi_agent_coordinator.ensure_team(self._active_team_session_id())
        console.print(f"[success]Resumed session: {session.session_id}[/success]")

    async def _restore_checkpoint(self, checkpoint_id: str) -> None:
        if not checkpoint_id:
            console.print("[error]Usage: /restore <checkpoint_id>[/error]")
            return

        persistence_manager = PersistenceManager()
        snapshot = persistence_manager.load_checkpoint(checkpoint_id)
        if not snapshot:
            console.print("[error]Checkpoint does not exist[/error]")
            return

        session = await self._hydrate_session(snapshot)
        self.agent.session = session
        self.multi_agent_coordinator.ensure_team(self._active_team_session_id())
        console.print(
            f"[success]Restored session: {session.session_id}, checkpoint: {checkpoint_id}[/success]"
        )

    async def _hydrate_session(self, snapshot: SessionSnapshot) -> Session:
        session = Session(config=self.config)
        await session.initialize()
        session.session_id = snapshot.session_id
        session.created_at = snapshot.created_at
        session.updated_at = snapshot.updated_at
        session.turn_count = snapshot.turn_count
        session.context_manager.total_usage = snapshot.total_usage

        for message in snapshot.messages:
            role = message.get("role")
            if role == "system":
                continue
            if role == "user":
                session.context_manager.add_user_message(message.get("content", ""))
            elif role == "assistant":
                session.context_manager.add_assistant_message(
                    message.get("content", ""),
                    message.get("tool_calls"),
                )
            elif role == "tool":
                session.context_manager.add_tool_result(
                    message.get("tool_call_id", ""),
                    message.get("content", ""),
                )

        await self.agent.session.client.close()
        await self.agent.session.mcp_manager.shutdown()
        return session

    def _active_team_session_id(self) -> str:
        if self.agent:
            return self.agent.session.session_id
        return "preview"

    async def _handle_agents_command(self, cmd_args: str) -> None:
        parts = cmd_args.split(maxsplit=1) if cmd_args else []
        action = parts[0].lower() if parts else "list"
        remainder = parts[1] if len(parts) > 1 else ""
        session_id = self._active_team_session_id()

        if action in {"", "list"}:
            self.tui.show_agents(self._build_agent_status_rows())
            return

        if action in {"help", "-h", "--help"}:
            console.print("\n[bold]Agent Commands[/bold]")
            console.print("  /agents")
            console.print("  /agents add name=DataOps role=db color=bright_magenta powers=sql,json,jobs mission=\"Own database jobs\"")
            console.print("  /agents design build a database agent for migrations, query tuning, and JSON storage")
            console.print("  /agents show DataOps")
            console.print("  /agents threads")
            console.print("  /agents inbox DataOps")
            console.print("  /agents remove DataOps")
            return

        if action == "roles":
            console.print("\n[bold]Suggested roles[/bold]")
            console.print("  frontend, backend, qa, db, jobs, infra, security, docs, planner, coordinator")
            return

        if action in {"add", "create"}:
            options = self._parse_agent_kwargs(remainder)
            name = options.get("name")
            role = options.get("role")
            if not name or not role:
                console.print(
                    "[error]Usage: /agents add name=<name> role=<role> [color=<rich_color>] [model=<model>] [powers=a,b,c] [mission=\"text\"][/error]"
                )
                return

            powers = [item.strip() for item in options.get("powers", "").split(",") if item.strip()]
            mission = options.get("mission")
            agent = self.multi_agent_coordinator.add_custom_agent(
                session_id,
                name=name,
                role=role,
                model_name=options.get("model"),
                color=options.get("color"),
                powers=powers,
                mission=mission,
                source="custom",
            )
            console.print(
                f"[success]Added agent: {agent.name} ({agent.role}) with powers: {', '.join(agent.powers) or 'none'}[/success]"
            )
            self.tui.show_agent_profile(
                self.multi_agent_coordinator.agent_profile_row(session_id, agent.agent_id)
            )
            self.tui.show_agents(self._build_agent_status_rows())
            return

        if action in {"design", "generate"}:
            if not remainder.strip():
                console.print("[error]Usage: /agents design <free-form brief>[/error]")
                return

            draft = await self.agent_designer.design(
                remainder,
                self.multi_agent_coordinator.get_team(session_id),
            )
            agent = self.multi_agent_coordinator.add_custom_agent(
                session_id,
                name=draft.name,
                role=draft.role,
                model_name=draft.model_name,
                color=draft.color,
                powers=draft.powers,
                mission=draft.mission,
                system_prompt=draft.system_prompt,
                keywords=draft.keywords,
                source="generated",
            )
            console.print(
                f"[success]Designed agent via {draft.design_source}: {agent.name} ({agent.role})[/success]"
            )
            self.tui.show_agent_profile(
                self.multi_agent_coordinator.agent_profile_row(session_id, agent.agent_id)
            )
            self.tui.show_agents(self._build_agent_status_rows())
            return

        if action in {"show", "inspect"}:
            identifier = remainder.strip()
            if not identifier:
                console.print("[error]Usage: /agents show <agent_name_or_id>[/error]")
                return
            profile = self.multi_agent_coordinator.agent_profile_row(session_id, identifier)
            if profile is None:
                console.print(f"[error]Agent not found: {identifier}[/error]")
                return
            self.tui.show_agent_profile(profile)
            return

        if action == "threads":
            self.tui.show_agent_threads(self.multi_agent_coordinator.thread_rows(session_id))
            return

        if action in {"inbox", "messages"}:
            identifier = remainder.strip() or None
            title = "Agent Inbox" if identifier else "A2A Feed"
            if identifier and not self.multi_agent_coordinator.resolve_agent(session_id, identifier):
                console.print(f"[error]Agent not found: {identifier}[/error]")
                return
            self.tui.show_agent_messages(
                self.multi_agent_coordinator.message_rows(session_id, identifier),
                title=title,
            )
            return

        if action in {"remove", "delete"}:
            identifier = remainder.strip()
            if not identifier:
                console.print("[error]Usage: /agents remove <agent_name_or_id>[/error]")
                return

            deleted = self.multi_agent_coordinator.remove_custom_agent(session_id, identifier)
            if not deleted:
                console.print(f"[error]Custom agent not found: {identifier}[/error]")
                return

            console.print(f"[success]Removed custom agent: {identifier}[/success]")
            self.tui.show_agents(self._build_agent_status_rows())
            return

        console.print(f"[error]Unknown /agents action: {action}[/error]")

    def _parse_agent_kwargs(self, raw_args: str) -> dict[str, str]:
        result: dict[str, str] = {}
        try:
            parts = shlex.split(raw_args)
        except ValueError:
            parts = raw_args.split()

        for part in parts:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            normalized_key = key.lower()
            normalized_value = value.strip()
            if normalized_key in {"mission", "description"}:
                normalized_value = normalized_value.replace("_", " ")
            result[normalized_key] = normalized_value
        return result

    def _build_agent_status_rows(self) -> list[dict[str, str]]:
        rows = self.multi_agent_coordinator.roster_rows(self._active_team_session_id())
        mcp_count = 0
        if self.agent:
            mcp_count = len(self.agent.session.mcp_manager.get_all_servers())

        rows.append(
            {
                "name": "mcp-bridge",
                "role": "remote-tool-bridge",
                "model": "n/a",
                "status": "connected" if mcp_count else "idle",
                "task_id": "-",
                "color": "bright_cyan",
                "powers": f"{mcp_count} server(s), external tools",
                "source": "system",
            }
        )
        return rows


class HybridCLI:
    def __init__(self, config: Config):
        self.config = config
        self.tui = TUI(config, console)
        self.orchestrator = HybridOrchestrator(config.cwd, config=config)

    async def inspect_team(
        self,
        *,
        goal: str,
        team: str,
        team_size: int,
        strict: bool,
        verify: VerificationMode,
        planner_model: str | None,
        worker_model: str | None,
        ownership_mode: OwnershipMode,
    ) -> None:
        options = TeamSynthesisOptions(
            team=team,
            team_size=team_size,
            strict=strict,
            verification_mode=verify,
            planner_model=planner_model,
            worker_model=worker_model,
            ownership_mode=ownership_mode,
        )
        team_spec = self.orchestrator.inspect_team(goal, options)
        self.tui.show_team_spec(team_spec)

    async def run(
        self,
        *,
        goal: str,
        team: str,
        team_size: int,
        strict: bool,
        parallel: bool,
        max_parallel_agents: int,
        verify: VerificationMode,
        planner_model: str | None,
        worker_model: str | None,
        dry_run: bool,
        show_task_graph: bool,
        show_team: bool,
        apply_patches: bool,
        ownership_mode: OwnershipMode,
    ) -> None:
        request = HybridRunRequest(
            goal=goal,
            workspace_root=self.config.cwd,
            team=team,
            team_size=team_size,
            strict=strict,
            parallel=parallel,
            max_parallel_agents=max_parallel_agents,
            verify=verify,
            planner_model=planner_model,
            worker_model=worker_model,
            dry_run=dry_run,
            apply_patches=apply_patches,
            ownership_mode=ownership_mode,
        )
        result = await self.orchestrator.run(request)
        if show_team or self.config.hybrid.show_team:
            self.tui.show_team_spec(result.team_spec)
        if show_task_graph or self.config.hybrid.show_task_graph:
            self.tui.show_task_graph(result.task_graph)
        if result.commit_decision:
            self.tui.show_commit_decision(result.commit_decision)
        console.print(f"[success]Hybrid session: {result.session_id}[/success]")

    async def show_task_graph(self, session_id: str) -> None:
        task_graph = self.orchestrator.show_task_graph(session_id)
        self.tui.show_task_graph(task_graph)

    def show_locks(self) -> None:
        self.tui.show_locks(self.orchestrator.show_locks())

    async def apply_pending_patches(self, session_id: str) -> None:
        decision = await self.orchestrator.apply_pending_patches(session_id)
        self.tui.show_commit_decision(decision)


def _load_runtime_config(cwd: Path | None, *, require_api_key: bool) -> Config:
    load_dotenv(dotenv_path=(cwd or Path.cwd()) / ".env")
    config = load_config(cwd=cwd)
    errors = config.validate(require_api_key=require_api_key)
    if errors:
        for error in errors:
            console.print(f"[error]{error}[/error]")
        raise click.ClickException("Invalid configuration")
    return config


TEAM_CHOICES = ["auto", *list_team_presets()]
VERIFY_CHOICES = [mode.value for mode in VerificationMode]
OWNERSHIP_CHOICES = [mode.value for mode in OwnershipMode]
HYBRID_COMMANDS = {
    "chat",
    "run",
    "inspect-team",
    "show-task-graph",
    "show-locks",
    "apply-pending-patches",
    "--help",
    "-h",
}


def _run_legacy(prompt: str | None, cwd: Path | None) -> None:
    try:
        config = _load_runtime_config(cwd, require_api_key=True)
    except Exception as error:
        console.print(f"[error]Configuration Error: {error}[/error]")
        sys.exit(1)

    cli = CLI(config)
    if prompt:
        result = asyncio.run(cli.run_single(prompt))
        if result is None:
            sys.exit(1)
    else:
        asyncio.run(cli.run_interactive())


def _build_hybrid_cli(cwd: Path | None) -> HybridCLI:
    try:
        config = _load_runtime_config(cwd, require_api_key=False)
    except Exception as error:
        console.print(f"[error]Configuration Error: {error}[/error]")
        sys.exit(1)
    return HybridCLI(config)


def _resolve_hybrid_flag(current, fallback):
    return fallback if current is None else current


@click.command(name="chat")
@click.argument("prompt", required=False)
@click.option(
    "--cwd",
    "-c",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Current working directory",
)
def legacy_main(prompt: str | None, cwd: Path | None) -> None:
    _run_legacy(prompt, cwd)


@click.group()
def hybrid_main() -> None:
    """Hybrid multi-agent operating system commands."""


@hybrid_main.command("chat")
@click.argument("prompt", required=False)
@click.option(
    "--cwd",
    "-c",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Current working directory",
)
def chat_command(prompt: str | None, cwd: Path | None) -> None:
    _run_legacy(prompt, cwd)


@hybrid_main.command("run")
@click.argument("goal")
@click.option("--cwd", "-c", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--team", type=click.Choice(TEAM_CHOICES), default=None)
@click.option("--team-size", type=int, default=None)
@click.option("--strict/--no-strict", default=None)
@click.option("--parallel/--no-parallel", default=None)
@click.option("--max-parallel-agents", type=int, default=None)
@click.option("--verify", type=click.Choice(VERIFY_CHOICES), default=None)
@click.option("--planner-model", type=str, default=None)
@click.option("--worker-model", type=str, default=None)
@click.option("--dry-run/--no-dry-run", default=None)
@click.option("--show-task-graph/--no-show-task-graph", default=None)
@click.option("--show-team/--no-show-team", default=None)
@click.option("--apply-patches/--no-apply-patches", default=None)
@click.option("--ownership-mode", type=click.Choice(OWNERSHIP_CHOICES), default=None)
def run_command(
    goal: str,
    cwd: Path | None,
    team: str | None,
    team_size: int | None,
    strict: bool | None,
    parallel: bool | None,
    max_parallel_agents: int | None,
    verify: str | None,
    planner_model: str | None,
    worker_model: str | None,
    dry_run: bool | None,
    show_task_graph: bool | None,
    show_team: bool | None,
    apply_patches: bool | None,
    ownership_mode: str | None,
) -> None:
    hybrid = _build_hybrid_cli(cwd)
    config = hybrid.config.hybrid
    asyncio.run(
        hybrid.run(
            goal=goal,
            team=team or config.team,
            team_size=team_size or config.team_size,
            strict=_resolve_hybrid_flag(strict, config.strict),
            parallel=_resolve_hybrid_flag(parallel, config.parallel),
            max_parallel_agents=max_parallel_agents or config.max_parallel_agents,
            verify=VerificationMode(verify or config.verify.value),
            planner_model=planner_model or config.planner_model,
            worker_model=worker_model or config.worker_model,
            dry_run=_resolve_hybrid_flag(dry_run, config.dry_run),
            show_task_graph=_resolve_hybrid_flag(show_task_graph, config.show_task_graph),
            show_team=_resolve_hybrid_flag(show_team, config.show_team) or True,
            apply_patches=_resolve_hybrid_flag(apply_patches, config.apply_patches),
            ownership_mode=OwnershipMode(ownership_mode or config.ownership_mode.value),
        )
    )


@hybrid_main.command("inspect-team")
@click.option("--goal", required=True)
@click.option("--cwd", "-c", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--team", type=click.Choice(TEAM_CHOICES), default=None)
@click.option("--team-size", type=int, default=None)
@click.option("--strict/--no-strict", default=None)
@click.option("--verify", type=click.Choice(VERIFY_CHOICES), default=None)
@click.option("--planner-model", type=str, default=None)
@click.option("--worker-model", type=str, default=None)
@click.option("--ownership-mode", type=click.Choice(OWNERSHIP_CHOICES), default=None)
def inspect_team_command(
    goal: str,
    cwd: Path | None,
    team: str | None,
    team_size: int | None,
    strict: bool | None,
    verify: str | None,
    planner_model: str | None,
    worker_model: str | None,
    ownership_mode: str | None,
) -> None:
    hybrid = _build_hybrid_cli(cwd)
    config = hybrid.config.hybrid
    asyncio.run(
        hybrid.inspect_team(
            goal=goal,
            team=team or config.team,
            team_size=team_size or config.team_size,
            strict=_resolve_hybrid_flag(strict, config.strict),
            verify=VerificationMode(verify or config.verify.value),
            planner_model=planner_model or config.planner_model,
            worker_model=worker_model or config.worker_model,
            ownership_mode=OwnershipMode(ownership_mode or config.ownership_mode.value),
        )
    )


@hybrid_main.command("show-task-graph")
@click.option("--session", "session_id", required=True)
@click.option("--cwd", "-c", type=click.Path(exists=True, file_okay=False, path_type=Path))
def show_task_graph_command(session_id: str, cwd: Path | None) -> None:
    hybrid = _build_hybrid_cli(cwd)
    asyncio.run(hybrid.show_task_graph(session_id))


@hybrid_main.command("show-locks")
@click.option("--cwd", "-c", type=click.Path(exists=True, file_okay=False, path_type=Path))
def show_locks_command(cwd: Path | None) -> None:
    hybrid = _build_hybrid_cli(cwd)
    hybrid.show_locks()


@hybrid_main.command("apply-pending-patches")
@click.option("--session", "session_id", required=True)
@click.option("--cwd", "-c", type=click.Path(exists=True, file_okay=False, path_type=Path))
def apply_pending_patches_command(session_id: str, cwd: Path | None) -> None:
    hybrid = _build_hybrid_cli(cwd)
    asyncio.run(hybrid.apply_pending_patches(session_id))


def entrypoint() -> None:
    argv = sys.argv[1:]
    if argv and argv[0] in HYBRID_COMMANDS:
        hybrid_main(standalone_mode=True)
        return
    legacy_main(standalone_mode=True)


if __name__ == "__main__":
    entrypoint()
