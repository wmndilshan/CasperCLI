# CasperCode 👻

> A terminal-based AI coding agent for local development workflows with multi-agent orchestration, durable workflow runtime, and rich CLI experience.

## Overview

CasperCode is a powerful AI agent framework designed for software development tasks. It combines a conversational interface with tool-calling capabilities, multi-agent coordination, and durable workflow execution to help you build, refactor, and manage codebases efficiently.

## Core Features

### 🤖 AI Agent Capabilities
- **Interactive Chat & One-shot Execution** - Have conversations or run single prompts
- **Streaming Responses** - Real-time text generation with Rich-powered formatting
- **Tool Calling** - 12+ built-in tools for file operations, search, shell commands, web access, memory, and task management
- **Session Persistence** - Save, resume, and checkpoint conversations
- **Context Management** - Automatic context compaction and loop detection for long-running work

### 🏢 Multi-Agent System
- **Coordinator + Specialist Agents** - Role-based agent separation with explicit responsibilities:
  - `coordinator`: Task graph ownership, planning loop, dependency ordering, risk gates
  - `frontend agent`: UI/web/client-facing implementation tasks
  - `backend agent`: API/runtime/data/indexing/infrastructure tasks
  - `qa agent`: Validation, regression detection, test strategy execution
- **Custom Agent Design** - AI-powered agent creation with `/agents design`
- **A2A Communication** - Agent-to-Agent messaging for task assignment, status updates, and handoffs
- **Team Management** - Add, remove, inspect agents dynamically
- **Hybrid Multi-Agent OS** - Structured team synthesis, DAG scheduling, lock-aware execution, transactional patches, conflict detection, and verification-gated integration

### 🔧 Tool Ecosystem

#### Built-in Tools (12)
| Tool | Purpose |
|------|---------|
| `read_file` | Read file contents with line numbers |
| `write_file` | Create new files with content |
| `edit_file` | Find-and-replace text edits |
| `shell` | Execute shell commands with safety checks |
| `list_dir` | List directory contents |
| `grep_search` | Pattern matching across files |
| `glob_search` | Find files by glob patterns |
| `web_search` | Search the web for information |
| `web_fetch` | Fetch content from URLs |
| `memory` | Store and retrieve persistent information |
| `todo` | Manage task lists |
| `code_search` | Fast codebase exploration subagent |

#### MCP Integration
- Connect to external MCP servers over **stdio** or **HTTP/SSE**
- Extend tool capabilities without code changes
- Auto-discovery of remote tools

### ⚡ Durable Workflow Runtime (Inngest)
- **Concurrent Background Jobs** - Parallel task execution
- **Long-running Tasks** - Survivable across restarts
- **Retries & Resumability** - Automatic failure recovery
- **Validation Pipelines** - Structured validation workflows
- **Autonomous Continuation** - Self-healing execution

### 🛡️ Safety & Control
- **Approval Policies**: `on-request`, `on-failure`, `auto`, `auto-edit`, `never`, `yolo`
- **Dangerous Command Detection** - Automatic blocking of risky shell commands
- **Path Validation** - Prevents escaping working directory
- **Confirmation Callbacks** - User approval for mutating operations
- **Tool Allowlisting** - Restrict available tools per session

### 🪝 Lifecycle Hooks
Execute custom scripts at key points:
- `before_agent` - Before agent starts
- `after_agent` - After agent completes
- `before_tool` - Before tool execution
- `after_tool` - After tool execution
- `on_error` - When errors occur

## Quick Start

### Prerequisites
- Python 3.10+
- DeepSeek API key (or compatible OpenAI-compatible provider)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd CasperCode

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API_KEY and BASE_URL
```

### Configuration (.env)

```env
# Required: LLM Provider
API_KEY=your_deepseek_api_key_here
BASE_URL=https://api.deepseek.com

# Optional: Model Selection
PLANNER_MODEL=deepseek-reasoner
EXECUTOR_MODEL=deepseek-coder

# Optional: Multi-Agent
MULTI_AGENT_ENABLED=1

# Optional: Inngest Workflow Runtime
INNGEST_APP_ID=caspercode
INNGEST_DEV=1
INNGEST_EVENT_KEY=your_event_key
INNGEST_SIGNING_KEY=your_signing_key

# Optional: Development
DEBUG=0
```

### Running CasperCode

```bash
# Create a local virtual environment with uv
uv venv .venv
UV_CACHE_DIR=/tmp/uv-cache uv pip install --python .venv/bin/python -r requirements.txt

# Interactive mode
.venv/bin/python main.py

# Single prompt mode
.venv/bin/python main.py "Refactor the auth module to use JWT tokens"

# Specify working directory
.venv/bin/python main.py --cwd /path/to/project "Analyze this codebase"

# Hybrid runtime mode
.venv/bin/python main.py run "add JWT auth, admin dashboard, tests, docker" --team auto --team-size 6 --strict --parallel --verify strict --show-team --show-task-graph
.venv/bin/python main.py inspect-team --goal "build RAG API with evaluation" --team-size 5
```

## CLI Commands

### Hybrid Runtime
| Command | Description |
|---------|-------------|
| `run "<goal>" --team <preset|auto>` | Execute the hybrid DAG runtime |
| `inspect-team --goal "<goal>"` | Preview synthesized team topology |
| `show-task-graph --session <id>` | Inspect a persisted hybrid session DAG |
| `show-locks` | Show active runtime locks |
| `apply-pending-patches --session <id>` | Apply staged proposals from a hybrid session |

### Session Management
| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/config` | Display current configuration |
| `/clear` | Clear conversation context |
| `/exit` or `/quit` | Exit the application |

### Model & Settings
| Command | Description |
|---------|-------------|
| `/model <name>` | Change LLM model |
| `/approval <policy>` | Set approval policy (`on-request`, `auto`, `yolo`, etc.) |
| `/stats` | Show session statistics |

### Persistence
| Command | Description |
|---------|-------------|
| `/save` | Save current session |
| `/sessions` | List saved sessions |
| `/resume <session_id>` | Resume a saved session |
| `/checkpoint` | Create a checkpoint |
| `/restore <checkpoint_id>` | Restore from checkpoint |

### Tools & Integrations
| Command | Description |
|---------|-------------|
| `/tools` | List available tools |
| `/mcp` | Show MCP server status |

### Multi-Agent (New!)
| Command | Description |
|---------|-------------|
| `/agents` | List all agents in the team |
| `/agents add name=<n> role=<r>` | Add a custom agent |
| `/agents design <brief>` | AI-design a new agent |
| `/agents show <name>` | Show agent profile |
| `/agents threads` | View agent threads |
| `/agents inbox <name>` | View agent messages |
| `/agents remove <name>` | Remove custom agent |
| `/agents roles` | Show suggested roles |

## Configuration File

Create `.ai-agent/config.toml` in your working directory:

```toml
[model]
name = "deepseek-chat"
temperature = 1
context_window = 256000

cwd = "."
approval = "on-request"
max_turns = 100
hooks_enabled = false

allowed_tools = ["read_file", "write_file", "edit_file", "grep_search"]

[mcp_servers.filesystem]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"]
startup_timeout_sec = 10

[mcp_servers.fetch]
url = "https://your-mcp-server.com/sse"

[shell_environment]
ignore_default_excludes = false

[shell_environment.set_vars]
CUSTOM_VAR = "value"

[hybrid]
team = "auto"
team_size = 4
strict = true
parallel = true
max_parallel_agents = 4
verify = "strict"
show_team = true
show_task_graph = true
ownership_mode = "strict"
```

## Architecture

```
CasperCode/
├── main.py              # CLI entry point with Click
├── agent/               # Core agent implementation
│   ├── agent.py         # Agent lifecycle and execution loop
│   ├── events.py        # Event system (TEXT_DELTA, TOOL_CALL, etc.)
│   ├── session.py       # Session state management
│   ├── persistence.py   # Save/resume/checkpoint logic
│   ├── runtime/         # Inngest workflow runtime
│   ├── sessions/        # Task graph state models
│   └── multi_agent/     # Coordinator, designer, A2A messaging
├── client/              # LLM client & response handling
├── config/              # Configuration models & loader
├── context/             # Context compaction & loop detection
├── tools/               # Tool framework
│   ├── base.py          # Base tool class
│   ├── registry.py      # Tool registration
│   ├── discovery.py     # Tool discovery for LLM
│   ├── builtin/         # 12 built-in tools
│   ├── mcp/             # MCP client & tool adapter
│   └── subagents.py     # Subagent tools
├── ui/                  # Terminal UI (Rich-based)
├── hooks/               # Lifecycle hook system
├── safety/              # Approval & safety checks
└── utils/               # Utilities & errors
```

## Multi-Agent Deep Dive

### Agent-to-Agent Communication

Agents communicate via structured envelopes:

```python
{
  "session_id": "sess_abc123",
  "task_id": "task_refactor_auth",
  "agent_role": "backend",
  "message_type": "task_assignment",  # or status_update, handoff, validation
  "payload": {...}
}
```

### Creating Custom Agents

**Manual creation:**
```
/agents add name=DataOps role=db color=bright_magenta powers=sql,json,jobs mission="Own database jobs and migrations"
```

**AI-designed:**
```
/agents design build a database agent that handles migrations, query tuning, and JSON storage with power to run SQL and schedule jobs
```

### Coordinator Runtime

The coordinator maintains a task graph and assigns work:
1. Decomposes user goals into task nodes
2. Assigns nodes to specialist agents based on role
3. Tracks progress through Inngest-backed runtime
4. Handles replanning on failures/blocks

## Development

### Running Tests

```bash
pytest
```

### Project Structure for Contributors

- All tool implementations go in `tools/builtin/`
- Add new tools to `tools/builtin/__init__.py`
- Agent logic in `agent/agent.py`
- UI components in `ui/tui.py`
- Configuration models in `config/config.py`

### Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `API_KEY` | Yes | LLM API key |
| `BASE_URL` | Yes | LLM base URL |
| `PLANNER_MODEL` | No | Model for planning tasks |
| `EXECUTOR_MODEL` | No | Model for execution tasks |
| `MULTI_AGENT_ENABLED` | No | Enable multi-agent mode (default: 1) |
| `INNGEST_APP_ID` | No | Inngest application ID |
| `INNGEST_DEV` | No | Run Inngest in dev mode |
| `INNGEST_EVENT_KEY` | No | Inngest event key |
| `INNGEST_SIGNING_KEY` | No | Inngest signing key |
| `DEBUG` | No | Enable debug logging |

## Safety Notes

- `.env` is gitignored by default - never commit API keys
- Shell commands are validated against dangerous patterns
- Path operations are sandboxed to the working directory
- Approval policies provide defense-in-depth

## License

[Your License Here]

## Acknowledgments

- Built with [Rich](https://github.com/Textualize/rich) for beautiful terminal UI
- Uses [Inngest](https://www.inngest.com/) for durable workflows
- Compatible with DeepSeek, OpenAI, and other OpenAI-compatible providers
