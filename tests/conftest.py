from collections.abc import Callable
from datetime import datetime, timezone

import httpx2
import openai
from langchain_core.messages import AIMessage, BaseMessage

from assistant.graph import build_graph
from assistant.mcp_client import (
    McpStartupError,
    PromptMessage,
    PromptSpec,
    PromptUnavailableError,
    ResourceUnavailableError,
    ToolSpec,
)
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
    model, tools=None, max_steps=5, router=None, scope=TEST_SCOPE, reviewer=None, max_reviews=2,
    summary_model=None, summary_max_messages=20, summary_keep_messages=6, preferences="",
):
    """Graph with fake models; the default summary model fails if it is ever called.

    `preferences=""` keeps the agent's system prompt equal to SYSTEM_PROMPT.
    """
    if tools is None:
        tools = [create_current_time_tool(lambda: FIXED_NOW)]
    if router is None:
        router = ConversationRouter()
    if reviewer is None:
        reviewer = ApprovingReviewer()
    return build_graph(
        model, list(tools), max_steps,
        router_model=router, scope=scope, reviewer_model=reviewer, max_reviews=max_reviews,
        summary_model=FakeModel([]) if summary_model is None else summary_model,
        summary_max_messages=summary_max_messages, summary_keep_messages=summary_keep_messages,
        preferences=preferences,
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
    """Stands in for McpClient: publishes `specs`, records calls and answers {"ok": True}.

    `resources` maps URI → text; any other URI is unavailable. Reads go to `resource_reads`.
    `prompts` maps name → (PromptSpec, function arguments → list[PromptMessage]); an unknown
    name or a ValueError of the function is unavailable. Calls go to `prompt_lists` (a count)
    and `prompt_gets`, failed ones included.
    """

    def __init__(
        self, specs: list[ToolSpec], fail_on_enter: bool = False,
        resources: dict[str, str] | None = None,
        prompts: dict[str, tuple[PromptSpec, Callable[[dict], list[PromptMessage]]]] | None = None,
    ):
        self._specs = list(specs)
        self._fail_on_enter = fail_on_enter
        self._resources = dict(resources or {})
        self._prompts = dict(prompts or {})
        self.calls: list[tuple[str, dict]] = []
        self.resource_reads: list[str] = []
        self.prompt_lists = 0
        self.prompt_gets: list[tuple[str, dict]] = []

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

    def read_resource(self, uri: str) -> str:
        self.resource_reads.append(uri)
        if uri not in self._resources:
            raise ResourceUnavailableError(f"Resource not found: {uri!r}")
        return self._resources[uri]

    def list_prompts(self) -> list[PromptSpec]:
        self.prompt_lists += 1
        return [spec for spec, _ in self._prompts.values()]

    def get_prompt(self, name: str, arguments: dict) -> list[PromptMessage]:
        self.prompt_gets.append((name, dict(arguments)))
        if name not in self._prompts:
            raise PromptUnavailableError(f"Unknown prompt: '{name}'")
        try:
            return self._prompts[name][1](dict(arguments))
        except ValueError as error:
            raise PromptUnavailableError(str(error)) from error


class PromptListFails(FakeMcpClient):
    """FakeMcpClient whose prompts/list fails as with a closed MCP session."""

    def list_prompts(self):
        self.prompt_lists += 1
        raise PromptUnavailableError("sessione MCP chiusa")


def lm_studio_error() -> openai.APIConnectionError:
    return openai.APIConnectionError(
        request=httpx2.Request("POST", "http://localhost:1234/v1/chat/completions")
    )
