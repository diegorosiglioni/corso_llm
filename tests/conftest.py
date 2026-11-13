from datetime import datetime, timezone

import httpx2
import openai
from langchain_core.messages import AIMessage, BaseMessage

from assistant.graph import build_graph
from assistant.mcp_client import McpStartupError, ToolSpec
from assistant.reviewer import ReviewDecision
from assistant.router import RouteDecision
from assistant.tools import create_current_time_tool

FIXED_NOW = datetime(2026, 10, 26, 15, 47, 12, 345678, tzinfo=timezone.utc)


class FakeModel:
    """Model with scripted replies: returns them in order and raises those that are exceptions."""

    def __init__(self, replies: list[AIMessage | BaseException]):
        self._replies = list(replies)
        self.calls: list[list[BaseMessage]] = []

    def invoke(self, messages) -> AIMessage:
        self.calls.append(list(messages))
        reply = self._replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply


TEST_SCOPE = "Ambito di prova: ora e calcoli."


class ConversationRouter:
    """Router that always sends the turn to the agent; records the messages it receives."""

    def __init__(self):
        self.calls: list[list[BaseMessage]] = []

    def invoke(self, messages) -> RouteDecision:
        self.calls.append(list(messages))
        return RouteDecision(category="conversation", reason="test")


class ApprovingReviewer:
    """Reviewer that always approves the answer; records the messages it receives."""

    def __init__(self):
        self.calls: list[list[BaseMessage]] = []

    def invoke(self, messages) -> ReviewDecision:
        self.calls.append(list(messages))
        return ReviewDecision(reason="test", coherent=True)


def fake_graph(
    model, tools=None, max_steps=5, router=None, scope=TEST_SCOPE, reviewer=None, max_reviews=2
):
    if tools is None:
        tools = [create_current_time_tool(lambda: FIXED_NOW)]
    if router is None:
        router = ConversationRouter()
    if reviewer is None:
        reviewer = ApprovingReviewer()
    return build_graph(
        model, list(tools), max_steps,
        router_model=router, scope=scope, reviewer_model=reviewer, max_reviews=max_reviews,
    )


def tool_call(
    timezone: str | None = "Asia/Tokyo", id: str = "c1", name: str = "get_current_time"
) -> AIMessage:
    """Model reply that requests a tool; timezone=None → empty arguments."""
    args = {} if timezone is None else {"timezone": timezone}
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": id}])


MCP_SPECS = [
    ToolSpec(name, f"Descrizione di {name}", {"type": "object", "properties": {}})
    for name in (
        "convert_units", "calculate", "search_catalog", "get_item",
        "add_note", "list_notes", "delete_note",
    )
]


class FakeMcpClient:
    """Stands in for McpClient: publishes `specs`, records calls and answers {"ok": True}."""

    def __init__(self, specs: list[ToolSpec], fail_on_enter: bool = False):
        self._specs = list(specs)
        self._fail_on_enter = fail_on_enter
        self.calls: list[tuple[str, dict]] = []

    def __enter__(self):
        if self._fail_on_enter:
            raise McpStartupError("comando non trovato")
        return self

    def __exit__(self, *exc) -> None:
        pass

    def list_tools(self) -> list[ToolSpec]:
        return list(self._specs)

    def call_tool(self, name: str, arguments: dict) -> dict:
        self.calls.append((name, arguments))
        return {"ok": True}


def lm_studio_error() -> openai.APIConnectionError:
    return openai.APIConnectionError(
        request=httpx2.Request("POST", "http://localhost:1234/v1/chat/completions")
    )
