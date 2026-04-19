from __future__ import annotations

from pathlib import Path
import unittest

from agent.agent import Agent
from client.response import StreamEvent, StreamEventType, TokenUsage, ToolCall
from config.config import Config
from context.loop_detector import LoopDetector
from tools.base import ToolResult


class _FakeContextManager:
    def __init__(self) -> None:
        self.user_messages: list[str] = []
        self.assistant_messages: list[dict[str, object]] = []
        self.tool_results: list[tuple[str, str]] = []
        self.total_usage = TokenUsage()

    def add_user_message(self, content: str) -> None:
        self.user_messages.append(content)

    def add_assistant_message(self, content: str, tool_calls=None) -> None:
        self.assistant_messages.append(
            {
                "content": content,
                "tool_calls": tool_calls or [],
            }
        )

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        self.tool_results.append((tool_call_id, content))

    def get_messages(self):
        return []

    def needs_compression(self) -> bool:
        return False

    def set_latest_usage(self, usage: TokenUsage) -> None:
        return None

    def add_usage(self, usage: TokenUsage) -> None:
        self.total_usage += usage

    def prune_tool_outputs(self) -> int:
        return 0


class _FakeToolRegistry:
    def __init__(self) -> None:
        self.invocations: list[tuple[str | None, dict[str, object]]] = []

    def get_schemas(self):
        return [
            {
                "name": "read_file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                    },
                    "required": ["path"],
                },
            }
        ]

    async def invoke(self, name, params, cwd, hook_system, approval_manager):
        self.invocations.append((name, params))
        return ToolResult.error_result(
            "Invalid parameters: Parameter 'path': Field required",
            metadata={
                "tool_name": name,
                "validation_errors": ["Parameter 'path': Field required"],
            },
        )


class _FakeClient:
    def __init__(self) -> None:
        self.turn = 0

    async def chat_completion(self, messages, tools=None, stream=True):
        if self.turn == 0:
            self.turn += 1
            yield StreamEvent(
                type=StreamEventType.TOOL_CALL_COMPLETE,
                tool_call=ToolCall(call_id="call-1", name="read_file", arguments={}),
            )
            yield StreamEvent(
                type=StreamEventType.TOOL_CALL_COMPLETE,
                tool_call=ToolCall(call_id="call-2", name="read_file", arguments={}),
            )
            yield StreamEvent(
                type=StreamEventType.MESSAGE_COMPLETE,
                usage=TokenUsage(total_tokens=1),
            )
            return

        self.turn += 1
        yield StreamEvent(
            type=StreamEventType.TEXT_DELTA,
            text_delta=None,
        )
        yield StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            usage=TokenUsage(total_tokens=1),
        )


class _FakeHookSystem:
    async def trigger_before_agent(self, message: str) -> None:
        return None

    async def trigger_after_agent(self, message: str, response: str | None) -> None:
        return None


class _FakeSession:
    def __init__(self) -> None:
        self.context_manager = _FakeContextManager()
        self.tool_registry = _FakeToolRegistry()
        self.client = _FakeClient()
        self.loop_detector = LoopDetector()
        self.hook_system = _FakeHookSystem()
        self.approval_manager = None
        self.turn_count = 0
        self.chat_compactor = None

    def increment_turn(self) -> int:
        self.turn_count += 1
        return self.turn_count


class AgentLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_duplicate_tool_calls_are_deduped_and_prompted(self) -> None:
        agent = Agent(Config(cwd=Path.cwd(), max_turns=3))
        fake_session = _FakeSession()
        agent.session = fake_session

        events = [event async for event in agent._agentic_loop()]

        self.assertEqual(len(fake_session.tool_registry.invocations), 1)
        self.assertTrue(
            any("Invalid Tool Call" in message for message in fake_session.context_manager.user_messages)
        )
        assistant_tool_calls = fake_session.context_manager.assistant_messages[0]["tool_calls"]
        self.assertEqual(assistant_tool_calls[0]["function"]["arguments"], "{}")
        tool_complete_events = [event for event in events if event.type.value == "tool_call_complete"]
        self.assertEqual(len(tool_complete_events), 2)
        self.assertEqual(
            tool_complete_events[1].data["error"],
            "Duplicate tool call in same turn skipped",
        )
