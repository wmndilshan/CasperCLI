# CasperCLI: Comprehensive Codebase Guide

## 1. Project Overview

**CasperCLI** (also called CasperCode) is an advanced terminal-based AI coding agent framework for local development workflows. It provides:

- **Multi-agent orchestration** with role-based specialist agents (Coordinator, Planner, Backend, Frontend, QA)
- **Tool ecosystem** with 12+ built-in tools and MCP (Model Context Protocol) integration
- **Durable workflow runtime** using Inngest for long-running, resumable tasks
- **Safety mechanisms** with approval policies and dangerous command detection
- **Context management** with automatic compaction and loop detection
- **Session persistence** with checkpoint recovery
- **Lifecycle hooks** for custom script execution at key points

### Tech Stack
- **Language**: Python 3.10+
- **LLM Provider**: OpenAI-compatible APIs (DeepSeek, OpenRouter, etc.)
- **UI**: Rich library for terminal formatting
- **Job Scheduler**: Inngest
- **MCP Support**: fastmcp for external tool integration
- **Config**: TOML/JSON with Pydantic validation

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI/Main Entry                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Agent (Main Agentic Loop)                │   │
│  │  - Conversation management                            │   │
│  │  - Turn-based execution                               │   │
│  │  - Event streaming                                    │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                   │
│        ┌──────────────────┼──────────────────┐               │
│        ▼                  ▼                  ▼               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Session    │  │    Multi-    │  │  Tool        │      │
│  │              │  │    Agent     │  │  Registry    │      │
│  │- Context Mgr│  │    System    │  │              │      │
│  │- LLM Client │  │              │  │- Built-in    │      │
│  │- Approval   │  │- Coordinator │  │- MCP Tools   │      │
│  │- Hooks      │  │- Roles       │  │- Subagents   │      │
│  └──────────────┘  │- A2A Comm   │  └──────────────┘      │
│                    └──────────────┘                          │
│                           │                                   │
│        ┌──────────────────┼──────────────────┐               │
│        ▼                  ▼                  ▼               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Context     │  │ Persistence  │  │  Safety &    │      │
│  │  Management  │  │              │  │  Approval    │      │
│  │              │  │- Snapshots   │  │              │      │
│  │- Compaction  │  │- Sessions    │  │- Policies    │      │
│  │- Loop Detect │  │- Checkpoints │  │- Dangerous   │      │
│  └──────────────┘  └──────────────┘  │  Detection   │      │
│                                       └──────────────┘      │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          Runtime & Durable Execution (Optional)       │   │
│  │  - SessionOrchestrator                                │   │
│  │  - Inngest scheduler/jobs                             │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Core Components

### 3.1 Agent (`agent/agent.py`)

The **Agent** class is the main orchestrator executing the agentic loop:

**Key Responsibilities:**
- Receives user messages and adds to context
- Runs the main loop: LLM call → tool execution → response handling
- Emits events for streaming responses
- Manages session lifecycle and context compression
- Detects and breaks infinite loops

**Agentic Loop Flow:**
```python
for turn_num in range(max_turns):
    1. Check if context needs compression
       - If yes, compact using ChatCompactor
    2. Get tool schemas from registry
    3. Call LLM with messages and tools
    4. Process streamed response events:
       - TEXT_DELTA: stream text to user
       - TOOL_CALL_COMPLETE: collect tool calls
       - MESSAGE_COMPLETE: get token usage
    5. Execute tool calls sequentially
    6. Add tool results to context
    7. Check for loops; break if detected
    8. Continue if more turns needed
```

**Key Methods:**
- `run(message: str)`: Main entry point, yields AgentEvent stream
- `_agentic_loop()`: Core loop implementation
- Event emission for streaming UI

---

### 3.2 Session (`agent/session.py`)

The **Session** class manages the lifecycle and state during a conversation:

**Components:**
- **LLMClient**: Manages API calls to LLM provider
- **ToolRegistry**: Registry of all available tools
- **ToolDiscoveryManager**: Dynamic tool discovery from filesystem
- **MCPManager**: Model Context Protocol server management
- **ContextManager**: Message history and context handling
- **ChatCompactor**: Compresses old conversation history
- **ApprovalManager**: Handles safety approvals
- **LoopDetector**: Detects infinite action loops
- **HookSystem**: Lifecycle hook execution
- **Session ID & Metadata**: Unique session tracking

**Initialization:**
```python
__init__()  # Create components
await initialize()  # Async setup: MCP, discovery, context manager
```

**State Tracking:**
- `turn_count`: Number of conversation turns
- `created_at` / `updated_at`: Timestamps
- `get_stats()`: Returns session statistics

---

### 3.3 ContextManager (`context/manager.py`)

Manages conversation history with automatic token counting and compression:

**Data Structure:**
```python
@dataclass
class MessageItem:
    role: str  # "user", "assistant", "tool", "system"
    content: str
    tool_call_id: str | None  # For tool result messages
    tool_calls: list[dict]     # For assistant messages with tools
    token_count: int | None
    pruned_at: datetime | None
```

**Key Methods:**
- `add_user_message(content: str)`: Add user input
- `add_assistant_message(content, tool_calls)`: Add LLM response
- `add_tool_result(tool_call_id, content)`: Add tool result
- `get_messages()`: Returns message list with system prompt
- `needs_compression()`: Check if context is growing too large
- `replace_with_summary(summary)`: Replace old messages with summary

**Token Management:**
- Tracks token usage for each message
- Computes total usage across session
- Protects last 40K tokens, keeps minimum 20K tokens

---

### 3.4 LLMClient (`client/llm_client.py`)

Handles streaming communication with LLM APIs:

**Configuration:**
- Uses OpenAI-compatible SDK (AsyncOpenAI)
- Supports custom base_url for different providers
- Configurable retry logic (max 3 attempts)

**Streaming Response Processing:**
- Parses tool calls from structured outputs
- Streams text deltas in real-time
- Extracts token usage statistics
- Handles errors and retries

**Response Events:**
```python
StreamEventType.TEXT_DELTA       # Text chunk
StreamEventType.TOOL_CALL_COMPLETE # Complete tool call
StreamEventType.MESSAGE_COMPLETE  # Done with message
StreamEventType.ERROR            # Error occurred
```

---

## 4. Tool System Architecture

### 4.1 Tool Base Class (`tools/base.py`)

All tools inherit from the abstract **Tool** class:

```python
class Tool(ABC):
    name: str                    # Unique identifier
    kind: ToolKind              # READ, WRITE, SHELL, NETWORK, MEMORY, MCP
    description: str             # Human-readable description
    schema: Type[BaseModel]      # Pydantic model for parameters
    
    @abstractmethod
    async def execute(invocation: ToolInvocation) -> ToolResult
    
    async def get_confirmation(invocation) -> ToolConfirmation | None
    
    def to_openai_schema() -> dict  # Convert to OpenAI format
```

**ToolInvocation:**
- `cwd`: Working directory for execution
- `params`: Parameter dict matching schema
- `confirmation`: User approval context

**ToolResult:**
- `success: bool`
- `output: str`: Main result text
- `error: str | None`: Error message if failed
- `metadata: dict`: Extra information (line count, paths, etc.)
- `diff: FileDiff | None`: For file modifications
- `exit_code: int | None`: For shell commands
- `truncated: bool`: If output was truncated

---

### 4.2 Built-in Tools (`tools/builtin/`)

**Core Tools (12 total):**

1. **read_file** - Read text file contents with line numbers
   - Params: `path`, `offset` (line start), `limit` (num lines)
   - Max file size: 10MB
   - Prevents binary file reads

2. **write_file** - Create new text files
   - Params: `path`, `content`
   - Fails if file exists (use edit_file for modifications)

3. **edit_file** - Find-and-replace text editing
   - Params: `path`, `old_string`, `new_string`
   - Returns unified diff of changes
   - Context preserved for accuracy

4. **shell** - Execute shell commands
   - Params: `command`, `timeout` (1-600 sec), `cwd`
   - Blocks dangerous patterns (rm -rf /, fork bomb, etc.)
   - Captures stdout/stderr/exit_code

5. **list_dir** - List directory contents
   - Params: `path`, `recursive` (bool)
   - Returns file and folder names

6. **glob_search** - Find files by glob pattern
   - Params: `pattern`
   - Example: `src/**/*.py`

7. **grep_search** - Search file contents by regex
   - Params: `query`, `isRegexp` (bool)
   - Supports `includePattern` and `maxResults`

8. **web_search** - Search the web
   - Uses ddgs (DuckDuckGo)
   - Params: `query`

9. **web_fetch** - Fetch URL contents
   - Params: `url`, `query` (optional content extraction)

10. **memory** - Persistent user notes/preferences
    - Params: `action` (create/view/update), `path`, `content`
    - Three scopes: user, session, repo
    - Persists across conversations

11. **todo** - Task list management
    - Params: `action` (create/list/update), `tasks`
    - Track: title, status, completion

12. **code_search** - Fast codebase exploration
    - Uses subagent for semantic search
    - Params: `query`, `thoroughness`

---

### 4.3 Tool Registry (`tools/registry.py`)

Central registry managing all available tools:

```python
class ToolRegistry:
    _tools: dict[str, Tool]      # Built-in tools
    _mcp_tools: dict[str, Tool]  # MCP-provided tools
    
    register(tool: Tool)         # Add built-in tool
    register_mcp_tool(tool)      # Add MCP tool
    get(name) -> Tool | None     # Retrieve by name
    get_tools() -> list[Tool]    # Get all tools
    get_schemas() -> list[dict]  # OpenAI schema format
    invoke() -> ToolResult       # Execute tool with safety
```

**Tool Invocation Pipeline:**
1. Resolve tool from registry
2. Validate parameters against schema
3. Check approval policies (get_confirmation)
4. Trigger before_tool hook
5. Execute tool
6. Trigger after_tool hook
7. Return ToolResult

---

### 4.4 Tool Discovery (`tools/discovery.py`)

Dynamic tool loading from filesystem:

```python
class ToolDiscoveryManager:
    discover_from_directory(path: Path)
        # Scans .ai-agent/tools/*.py for Tool subclasses
    discover_all()
        # Scans config dir and working directory
```

**Custom Tool Format:**
```python
# .ai-agent/tools/my_tool.py
from tools.base import Tool, ToolInvocation, ToolResult
from pydantic import BaseModel

class MyToolParams(BaseModel):
    param1: str

class MyTool(Tool):
    name = "my_tool"
    description = "What this does"
    schema = MyToolParams
    
    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        # Implementation
        return ToolResult.success_result("output")
```

---

### 4.5 MCP Integration (`tools/mcp/`)

Connects to external Model Context Protocol servers:

**MCPManager:**
- Manages connections to multiple MCP servers (stdio or HTTP/SSE)
- Auto-discovers tools from connected servers
- Registers MCP tools with automatic naming (e.g., `server_name__tool_name`)

**MCPTool:**
- Wraps MCP server tools as regular Tool objects
- Translates between internal and MCP protocols
- Inherits ToolKind.MCP

**Configuration:**
```python
mcp_servers:
  my_server:
    enabled: true
    command: "python -m my_mcp_server"  # stdio
    # OR
    url: "http://localhost:3000"  # HTTP/SSE
    startup_timeout_sec: 10
```

---

## 5. Multi-Agent System

### 5.1 Architecture (`agent/multi_agent/`)

The multi-agent system enables specialist agents to work together:

**Core Concepts:**
- **Roles**: Different agent types with specific capabilities
- **A2A Communication**: Agent-to-Agent messaging
- **Task Assignment**: Coordinator delegates to specialists
- **Capabilities**: Skills and keywords for agent matching

---

### 5.2 Agent Roles (`agent/multi_agent/models.py`)

```python
class AgentRole(str, Enum):
    COORDINATOR = "coordinator"  # Task graph, routing, recovery
    PLANNER = "planner"          # Long-horizon planning, architecture
    BACKEND = "backend"          # API, runtime, infrastructure
    FRONTEND = "frontend"        # UI, web, client-facing
    QA = "qa"                    # Testing, validation, regression

class AgentStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    RUNNING = "running"
    BLOCKED = "blocked"
    REVIEWING = "reviewing"

class AgentCapability(BaseModel):
    name: str                    # e.g., "task-routing"
    description: str
    keywords: list[str]          # For matching
```

**Default Team Composition:**
- **Coordinator**: Task graph ownership, planning loop, dependency ordering
- **Planner**: Long-horizon reasoning and architecture analysis
- **Backend**: API/runtime implementation
- **Frontend**: UI/client implementation
- **QA**: Testing and validation

---

### 5.3 MultiAgentCoordinator (`agent/multi_agent/coordinator.py`)

Orchestrates specialist agents:

```python
class MultiAgentCoordinator:
    ensure_team(session_id)       # Initialize team for session
    assign_task(state, step)       # Route task to capable agent
    record_outcome(state, step)    # Store task result
    record_job_update(state)       # Process job completion
```

**Task Routing:**
- Matches task requirements to agent capabilities
- Considers agent status and workload
- Routes supporting agents for complex tasks

---

### 5.4 Agent-to-Agent Communication (`agent/multi_agent/a2a.py`)

In-memory message bus for agent coordination:

```python
class A2AMessage:
    sender_agent_id: str         # From which agent
    recipient_agent_id: str      # To which agent
    task_id: str | None          # Associated task
    subject: str                 # Message topic
    body: str                    # Message content
    kind: str                    # "task_update", "status", etc.

class A2AThread:
    session_id: str
    topic: str
    participant_agent_ids: list[str]
    messages: list[A2AMessage]

class InMemoryA2ABus:
    create_thread()              # Start conversation thread
    send(message)                # Send A2A message
    threads_for_session()        # Retrieve session threads
```

---

## 6. Context Management & Intelligence

### 6.1 Context Compaction (`context/compaction.py`)

Automatically summarizes old conversation history to manage token limits:

**Trigger Conditions:**
- Context exceeds certain threshold
- Manual invocation

**Process:**
1. Collect all messages from session
2. Format into compression prompt
3. Use LLM to generate summary
4. Replace old messages with summary
5. Track token usage of compression

**Preserved Context:**
- Last 40K tokens always kept uncompressed
- Minimum 20K tokens preserved
- Tool calls and results summarized

---

### 6.2 Loop Detection (`context/loop_detector.py`)

Detects and breaks infinite execution loops:

**Detection Strategies:**
1. **Exact Repeats**: Same action repeated N times (default: 3)
   - Tracks action signatures (tool_name + args)
2. **Cycle Detection**: Repeating pattern of actions
   - Detects cycles up to length 3
   - Example: `[A, B, A, B]` detected

**Action Signatures:**
- Tool calls: `tool_name|arg1=val1|arg2=val2`
- Responses: `response|text_content`

**Breaking Loops:**
- Triggered on detection
- Invokes loop breaker prompt to change strategy
- Provides context to LLM about the loop

---

### 6.3 System Prompts (`prompts/system.py`)

Dynamic prompt generation based on configuration:

**Included Sections:**
1. **Identity**: Role as AI coding agent
2. **Environment**: Current date, OS, working directory, shell
3. **Tool Guidelines**: How to use available tools
4. **AGENTS.md Spec**: Repository agent instructions
5. **Security Guidelines**: Safe practices, approval policies
6. **Developer Instructions**: Custom from developer_instructions config
7. **User Instructions**: Custom from user_instructions config
8. **User Memory**: Persistent preferences and notes
9. **Operational Guidelines**: Best practices

---

## 7. Safety & Approval System

### 7.1 Approval Policies (`safety/approval.py`, `config/config.py`)

Control when tools require user confirmation:

```python
class ApprovalPolicy(str, Enum):
    ON_REQUEST = "on-request"    # Ask for every tool call
    ON_FAILURE = "on-failure"    # Only on tool errors
    AUTO = "auto"                # Always auto-approve
    AUTO_EDIT = "auto-edit"      # Auto-approve edits
    NEVER = "never"              # Never confirm
    YOLO = "yolo"                # Most permissive
```

---

### 7.2 Dangerous Command Detection

Blocks unsafe patterns:

**Dangerous Patterns:**
- File system destruction: `rm -rf /`, `mkfs`
- System control: `shutdown`, `reboot`, `halt`
- Permission escalation: `chmod 777 /`, `chown`
- Fork bomb: `:(){ :|:& };:`
- Network exposure: `nc -l`, `curl | bash`

**Safe Patterns (auto-approved):**
- Information: `ls`, `find`, `grep`, `cat`
- Version control: `git status`, `git log`
- Package managers: `npm list`, `pip list`
- System info: `uname`, `whoami`, `date`

---

### 7.3 ApprovalManager (`safety/approval.py`)

Manages approval workflows:

```python
class ApprovalContext:
    tool_name: str
    params: dict
    is_mutating: bool           # Creates/modifies files
    affected_paths: list[Path]
    command: str | None         # For shell tools
    is_dangerous: bool

class ApprovalManager:
    check_approval(context) -> ApprovalDecision
    confirmation_callback      # User confirmation function
```

**Decision Flow:**
1. Check if tool is dangerous
2. Check approval policy
3. Determine auto-approval eligibility
4. Request confirmation if needed
5. Return decision

---

## 8. Session Persistence & Checkpointing

### 8.1 PersistenceManager (`agent/persistence.py`)

Saves and restores session state:

```python
@dataclass
class SessionSnapshot:
    session_id: str
    created_at: datetime
    updated_at: datetime
    turn_count: int
    messages: list[dict]        # Full conversation
    total_usage: TokenUsage     # Token consumption
    
    def to_dict() -> dict       # Serialize
    @classmethod
    def from_dict(data) -> SessionSnapshot  # Deserialize
```

**Storage:**
- Sessions stored in: `~/.ai-agent/sessions/`
- Checkpoints in: `~/.ai-agent/checkpoints/`
- File permissions: 0o600 (read/write owner only)

**Operations:**
- `save_session()`: Persist session to disk
- `load_session(session_id)`: Restore from file
- `list_sessions()`: List all saved sessions
- `load_checkpoint()`: Load work checkpoint

---

## 9. Lifecycle Hooks System

### 9.1 HookSystem (`hooks/hook_system.py`)

Execute custom scripts at key lifecycle points:

**Hook Triggers:**
```python
class HookTrigger(str, Enum):
    BEFORE_AGENT = "before_agent"    # Before agent starts
    AFTER_AGENT = "after_agent"      # After agent completes
    BEFORE_TOOL = "before_tool"      # Before tool execution
    AFTER_TOOL = "after_tool"        # After tool execution
    ON_ERROR = "on_error"            # When error occurs
```

**Hook Configuration:**
```python
class HookConfig:
    name: str
    trigger: HookTrigger
    command: str | None              # Shell command to run
    script: str | None               # Inline bash script
    timeout_sec: float = 30
    enabled: bool = True
```

**Environment Variables:**
- `AI_AGENT_TRIGGER`: Which hook triggered
- `AI_AGENT_CWD`: Working directory
- `AI_AGENT_TOOL_NAME`: Tool name (before/after_tool)
- `AI_AGENT_USER_MESSAGE`: User input (before_agent)
- `AI_AGENT_ERROR`: Error message (on_error)

---

## 10. Durable Runtime & Jobs

### 10.1 SessionOrchestrator (`agent/runtime/orchestrator.py`)

Manages durable, resumable work sessions:

```python
@dataclass
class SessionOrchestrator:
    sessions: SessionStore           # Persists state
    planner: Planner                 # Plans next steps
    executor: ExecutionEngine        # Runs tasks
    memory: MemoryManager            # Caches context
    jobs: InngestScheduler           # Schedules work
    coordinator: MultiAgentCoordinator | None

    async def handle_goal(session_id, goal) -> SessionState
```

**Execution Flow:**
1. Load or create session state from SessionStore
2. Refresh workspace snapshot
3. Initialize multi-agent team
4. While goal not reached:
   - Planner: Determine next steps
   - Executor: Run ready tasks in parallel
   - MemoryManager: Update with outcomes
   - Jobs: Poll for completed background work
   - Coordinator: Record results and decide next step
5. Checkpoint final state

---

### 10.2 InngestScheduler (`jobs/inngest_scheduler.py`)

Priority job queue and scheduler:

```python
class InngestScheduler:
    async def enqueue(spec: JobSpec) -> str
    async def tick()                          # Process ready jobs
    async def poll_session_updates()          # Check completions

class PriorityJobQueue:
    async def push(spec: JobSpec)
    async def pop_ready_batch() -> list[JobSpec]

class JobSpec:
    job_id: str
    task_id: str
    agent_id: str
    priority: int                   # Higher = more urgent
```

---

### 10.3 Inngest Integration (`integrations/inngest_app.py`)

FastAPI app serving Inngest runtime:

```python
def create_inngest_app(config: Config) -> FastAPI
    # Creates FastAPI app for Inngest webhooks
    # Serves job queue and status endpoints
```

**Uses:**
- Background job execution
- Reliable retry logic
- Durable workflow storage

---

## 11. Configuration System

### 11.1 Config Structure (`config/config.py`)

Main configuration using Pydantic:

```python
class Config:
    # LLM Configuration
    api_key: str                     # LLM provider API key
    base_url: str                    # LLM provider base URL
    model_name: str                  # Model identifier
    planner_model_name: str          # For planner-specific tasks
    
    # Paths
    cwd: Path                        # Working directory
    
    # Agent Behavior
    max_turns: int                   # Max loop iterations
    
    # Approval & Safety
    approval: ApprovalPolicy         # When to request approval
    allowed_tools: list[str] | None  # Tool allowlist
    
    # MCP Servers
    mcp_servers: dict[str, MCPServerConfig]
    
    # Hooks
    hooks: list[HookConfig]
    hooks_enabled: bool
    
    # Custom Instructions
    developer_instructions: str | None
    user_instructions: str | None
    
    # Inngest
    inngest_app_id: str
    inngest_event_key: str
```

---

### 11.2 Configuration Loading (`config/loader.py`)

Load configuration from multiple sources:

**Priority (highest to lowest):**
1. Environment variables (e.g., `CASPER_API_KEY`)
2. `.env` file in current directory
3. `casper.toml` in config directory
4. Default values

**Data Directories:**
- Unix: `~/.config/casper-cli/`
- macOS: `~/Library/Application Support/casper-cli/`
- Windows: `%APPDATA%/casper-cli/`

---

## 12. Event System

### 12.1 Agent Events (`agent/events.py`)

Events emitted during agent execution:

```python
class AgentEventType(str, Enum):
    # Lifecycle
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    AGENT_ERROR = "agent_error"
    
    # Tools
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_COMPLETE = "tool_call_complete"
    
    # Text
    TEXT_DELTA = "text_delta"
    TEXT_COMPLETE = "text_complete"

@dataclass
class AgentEvent:
    type: AgentEventType
    data: dict[str, Any]
```

**Event Data Payloads:**
- `agent_start`: `{"message": user_input}`
- `text_delta`: `{"content": text_chunk}`
- `text_complete`: `{"content": full_response}`
- `tool_call_start`: `{"call_id", "name", "arguments"}`
- `tool_call_complete`: `{"call_id", "result"}`
- `agent_error`: `{"error": message}`
- `agent_end`: `{"response", "usage"}`

---

### 12.2 Streaming Response Events (`client/response.py`)

LLM streaming response events:

```python
class StreamEventType(str, Enum):
    TEXT_DELTA = "text_delta"
    TOOL_CALL_COMPLETE = "tool_call_complete"
    MESSAGE_COMPLETE = "message_complete"
    ERROR = "error"

@dataclass
class StreamEvent:
    type: StreamEventType
    text_delta: TextDelta | None
    tool_call: ToolCall | None
    usage: TokenUsage | None
    error: str | None
```

---

## 13. UI & Terminal Interface

### 13.1 TUI (`ui/tui.py`)

Terminal user interface using Rich library:

**Features:**
- Rich formatted output with colors
- Live markdown rendering
- Tool call visualization
- Interactive prompts
- Session info display

**Key Methods:**
- `print_welcome()`: Show startup info
- `handle_confirmation()`: Interactive approval prompts
- `display_event()`: Render agent events
- `show_stats()`: Session statistics display

---

## 14. Example Workflows

### 14.1 Single Command Execution

```python
async def run_single(message: str):
    async with Agent(config) as agent:
        # Single prompt execution
        async for event in agent.run(message):
            if event.type == AgentEventType.TEXT_DELTA:
                print(event.data["content"], end="", flush=True)
            elif event.type == AgentEventType.TOOL_CALL_START:
                print(f"→ Calling {event.data['name']}")
```

---

### 14.2 Interactive Multi-Turn Session

```python
async def run_interactive():
    async with Agent(config) as agent:
        while True:
            user_input = input("You: ")
            if user_input == "/exit":
                break
            
            async for event in agent.run(user_input):
                # Handle events
                tui.display_event(event)
        
        # Save session
        snapshot = SessionSnapshot(...)
        persistence_manager.save_session(snapshot)
```

---

### 14.3 Tool Execution Pipeline

```python
# When agent calls a tool:
1. Tool registry gets tool by name
2. Approval manager checks if approval needed
3. Before_tool hook runs
4. Tool executes with validated parameters
5. After_tool hook runs
6. ToolResult returned to agent
7. Agent adds tool result to context
8. Next turn processes result
```

---

### 14.4 Multi-Agent Task Execution

```python
# Coordinator flow:
1. User request received
2. Coordinator creates task graph
3. Planner analyzes requirements
4. Coordinator routes to specialist agents:
   - Backend agent: API implementation
   - Frontend agent: UI implementation
   - QA agent: Testing
5. A2A communication coordinates handoffs
6. Coordinator aggregates results
7. Response sent to user
```

---

## 15. Data Flow Diagrams

### 15.1 Complete Request-Response Flow

```
User Input
    ↓
Agent.run(message)
    ↓
Session.context_manager.add_user_message()
    ↓
Check: needs_compression? → Yes → ChatCompactor.compress()
    ↓
ToolRegistry.get_schemas()
    ↓
LLMClient.chat_completion(messages, tools)
    ↓
Stream Response Events
    ├→ TEXT_DELTA → emit TEXT_DELTA event
    ├→ TOOL_CALL_COMPLETE → add to tool_calls list
    └→ MESSAGE_COMPLETE → get token usage
    ↓
Add assistant message to context
    ↓
For each tool_call:
    ├→ ToolRegistry.get(tool_name)
    ├→ ToolConfirmation check
    ├→ HookSystem.trigger_before_tool()
    ├→ Tool.execute(invocation)
    ├→ HookSystem.trigger_after_tool()
    └→ Add tool result to context
    ↓
Check LoopDetector.check_for_loop()
    ↓
If loop detected → invoke loop_breaker_prompt
    ↓
Continue turn if max_turns not reached
    ↓
Agent.run() yields AGENT_END event
    ↓
PersistenceManager.save_session() [optional]
```

---

### 15.2 Tool Invocation Flow

```
ToolRegistry.invoke(name, params, cwd, ...)
    ↓
Get Tool from registry
    ↓
Create ToolInvocation(cwd, params, ...)
    ↓
Tool.get_confirmation(invocation)?
    ├→ No approval needed: continue
    ├→ Dangerous command: get user approval
    └→ Approval not granted: return error
    ↓
HookSystem.trigger_before_tool(tool_name)
    ↓
Tool.execute(invocation)
    ├→ Parse params with schema validation
    ├→ Apply safety checks (path validation, etc.)
    ├→ Execute core logic
    └→ Return ToolResult
    ↓
HookSystem.trigger_after_tool(tool_name, result)
    ↓
Return ToolResult to agent
```

---

## 16. Key Design Patterns

### 16.1 Async/Await Pattern
- All I/O operations are async (LLM, filesystem, network)
- Event streams use AsyncGenerator for streaming
- Concurrent execution with asyncio.gather()

### 16.2 Protocol/ABC Pattern
- Tool base class defines interface
- Multiple implementations (read_file, shell, web_fetch, etc.)
- MCP tools adapt to common interface

### 16.3 Configuration-Driven Design
- Most behavior controlled via Config class
- Pydantic validation ensures correctness
- Easy to extend with new options

### 16.4 Event-Driven Architecture
- Agent emits events for UI to consume
- Enables real-time streaming
- Loose coupling between agent and UI

### 16.5 Layered Architecture
- **Presentation**: TUI, event streaming
- **Application**: Agent, Session, Coordinator
- **Domain**: Tools, Context, Memory
- **Infrastructure**: LLMClient, Persistence, Hooks

---

## 17. Extension Points

### 17.1 Custom Tools
Create custom tools by:
1. Extend Tool class
2. Define Pydantic schema for parameters
3. Implement execute() method
4. Place in `.ai-agent/tools/` for auto-discovery

### 17.2 MCP Servers
Add MCP servers via configuration:
```toml
[mcp_servers.my_server]
enabled = true
command = "python -m my_mcp_server"
# or
url = "http://localhost:3000"
```

### 17.3 Lifecycle Hooks
Add custom execution at key points:
```toml
[[hooks]]
name = "my-hook"
trigger = "before_agent"
command = "echo 'Starting agent' > /tmp/log.txt"
enabled = true
```

### 17.4 Custom Agent Design
Use `/agents design` command to:
- Create new specialist agents
- Define custom capabilities
- Set role-specific system prompts
- Configure model overrides

### 17.5 Approval Policies
Control tool approval by:
- Setting approval_policy in config
- Defining custom dangerous patterns
- Implementing custom confirmation callbacks

---

## 18. Integration Architecture

### 18.1 With VS Code (via GitHub Copilot)
- Copilot Chat extension can invoke CasperCLI
- Send code snippets and prompts
- Receive streamed responses
- Tool results integrated into chat

### 18.2 With Inngest (Durable Runtime)
- Background job scheduling
- Long-running task management
- Automatic retries
- Resumable on failure

### 18.3 With MCP Servers
- Extend tool ecosystem
- Connect to external services
- Maintain common interface
- Easy server hot-plugging

---

## 19. Performance Considerations

### 19.1 Token Usage Management
- Count tokens for each message
- Trigger compression when threshold reached
- Compress to summary to preserve context
- Track total usage across session

### 19.2 Tool Performance
- File operations: Direct filesystem access
- Shell commands: Subprocess execution
- LLM calls: Async streaming
- Tool discovery: One-time on session init

### 19.3 Context Limits
- Protect last 40K tokens from compression
- Keep minimum 20K tokens uncompressed
- Trigger aggressive compression if needed
- Loop detection prevents wasted iterations

---

## 20. Testing & Debugging

### 20.1 Test Tool (`scripts/test_tool.py`)
- Isolated tool testing
- Parameter validation
- Output verification

### 20.2 Session Analysis
- `list_sessions()`: See all saved sessions
- `load_session()`: Inspect session state
- Event inspection: Review full event stream

### 20.3 Configuration Validation
- Pydantic automatic validation
- Config loader error reporting
- Schema checking on startup

---

## 21. Security Model

### 21.1 Path Validation
- Prevent escaping working directory
- Resolve paths relative to cwd
- Validate tool parameters

### 21.2 Command Blocking
- Dangerous pattern detection
- Explicit command blocklist
- Optional approval confirmation

### 21.3 File Permissions
- Session files: 0o600 (owner read/write only)
- Session directory: 0o700 (owner access only)
- Checkpoint directory: 0o700

### 21.4 Approval Flow
- Configurable policies per request
- User confirmation callbacks
- Dangerous command detection
- Safe command auto-approval

---

## 22. Troubleshooting Guide

### Issue: Context too large / Compression failing
**Solution:**
- Increase PRUNE_MINIMUM_TOKENS
- Check ChatCompactor prompt
- Verify LLM is generating summaries

### Issue: Tool not found
**Solution:**
- Verify tool in registry
- Check `.ai-agent/tools/` directory
- Run `ToolDiscoveryManager.discover_all()`

### Issue: Infinite loop detected
**Solution:**
- Loop breaker prompt triggered
- Agent should change strategy
- Check LoopDetector thresholds if needed

### Issue: Approval callback not working
**Solution:**
- Check ApprovalPolicy configuration
- Verify confirmation_callback is set
- Check dangerous pattern detection

---

## 23. API Reference

### Main Entry Points

**CLI:**
```python
from main import CLI
from config.loader import load_config

config = load_config()
cli = CLI(config)

# Single execution
result = await cli.run_single("your prompt")

# Interactive
await cli.run_interactive()
```

**Programmatic:**
```python
from agent.agent import Agent
from config.config import Config

config = Config(...)
async with Agent(config) as agent:
    async for event in agent.run("prompt"):
        handle_event(event)
```

---

## 24. Development Roadmap

### Planned Features
- [ ] More specialist agent roles
- [ ] Persistent A2A thread storage
- [ ] Multi-provider model selection
- [ ] Advanced context strategies (RAG)
- [ ] Custom event handlers
- [ ] Agent performance metrics
- [ ] Distributed execution
- [ ] Vision/image tool support

### Known Limitations
- Single-session concurrency only
- In-memory A2A threads (no persistence)
- No built-in authentication for MCP
- LLM token limits apply
- Tool output truncation at 25K tokens

---

## 25. Conclusion

CasperCLI is a sophisticated multi-agent framework that combines:

1. **Agentic Loop**: LLM reasoning with tool calling
2. **Tool Ecosystem**: Extensible plugin architecture
3. **Multi-Agent Coordination**: Specialist agents with A2A communication
4. **Safety First**: Approval policies, dangerous command detection
5. **Durability**: Session persistence, checkpoint recovery
6. **Context Intelligence**: Automatic compaction, loop detection
7. **Extensibility**: Custom tools, hooks, MCP servers

The architecture supports both simple single-agent scenarios and complex multi-agent orchestration with durable runtime execution.

