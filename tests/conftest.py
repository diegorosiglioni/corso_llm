import json
import os
import re
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx2
import openai
import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field
from sqlalchemy import Engine, event
from sqlalchemy.exc import OperationalError

from assistant.api import create_app
from assistant.config import ConfigError
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
from backend.config import load_backend_config
from backend.db import create_db_engine

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


class StreamingFakeModel(BaseChatModel):
    """Chat model of LangChain with scripted replies (AIMessage or exceptions to raise).

    With graph.invoke it returns each reply whole; with graph.stream(stream_mode="messages") it
    streams it: one piece per word of the text (spaces included), then one piece per call, with
    the arguments as JSON text (the received text for the invalid calls).
    """

    replies: list[Any]
    calls: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "streaming-fake"

    def _next(self, messages) -> AIMessage:
        self.calls.append(list(messages))
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next(messages))])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        reply = self._next(messages)
        for piece in re.findall(r"\s*\S+\s*", reply.content):
            yield ChatGenerationChunk(message=AIMessageChunk(content=piece))
        calls = [(c["id"], c["name"], json.dumps(c["args"])) for c in reply.tool_calls]
        calls += [(c["id"], c["name"], c["args"]) for c in reply.invalid_tool_calls]
        for index, (call_id, name, args) in enumerate(calls):
            yield ChatGenerationChunk(message=AIMessageChunk(content="", tool_call_chunks=[
                {"id": call_id, "name": name, "args": args, "index": index}
            ]))


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
        self.list_timeouts: list[float | None] = []
        self.resource_reads: list[str] = []
        self.prompt_lists = 0
        self.prompt_gets: list[tuple[str, dict]] = []

    def __enter__(self):
        if self._fail_on_enter:
            raise McpStartupError("comando non trovato")
        return self

    def __exit__(self, *exc) -> None:
        pass

    def list_tools(self, timeout: float | None = None) -> list[ToolSpec]:
        self.list_timeouts.append(timeout)
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


MODEL_ID = "google/gemma-4-e2b"


def model_ok() -> tuple[bool, str]:
    return True, ""


def fake_service(model=None, client=None, model_status=model_ok, **graph_options) -> TestClient:
    """The real app of the agent service on a fake graph and a fake MCP client, without a
    network; the default model fails if it is ever called."""
    graph = fake_graph(FakeModel([]) if model is None else model, **graph_options)
    return TestClient(create_app(
        graph=graph, client=client or FakeMcpClient(MCP_SPECS), model_id=MODEL_ID,
        model_status=model_status,
    ))


def sse(text: str) -> list[tuple[str, object]]:
    """(event, decoded data) of a text/event-stream body written by FastAPI."""
    events = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        fields = dict(
            line.split(": ", 1) for line in block.split("\n") if line and not line.startswith(":")
        )
        if fields:
            events.append((fields["event"], json.loads(fields["data"])))
    return events


class Clock:
    """Fixed clock that moves only when the test says so (archive of the back-end)."""

    def __init__(self, start: datetime):
        self.current = start

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)


@contextmanager
def postgres_schema(prefix: str) -> Iterator[tuple[str, str]]:
    """New empty schema in the PostgreSQL of TEST_DATABASE_URL (real tests only); yields
    (database URL with the psycopg driver, schema name) and drops the schema, with its tables,
    at the end. The tables of the other schemas are never touched."""
    try:
        url = load_backend_config(
            {"DATABASE_URL": os.environ.get("TEST_DATABASE_URL", "")}
        ).database_url
    except ConfigError as error:
        pytest.fail(f"Prova reale: imposta TEST_DATABASE_URL con un database PostgreSQL ({error})")
    schema = f"{prefix}_{uuid.uuid4().hex[:12]}"
    admin = create_db_engine(url)
    try:
        try:
            with admin.begin() as connection:
                connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        except OperationalError as error:
            pytest.fail(f"PostgreSQL non raggiungibile: {str(error.orig).strip()}")
        try:
            yield url, schema
        finally:
            with admin.begin() as connection:
                connection.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
    finally:
        admin.dispose()


def engine_on_schema(url: str, schema: str) -> Engine:
    """`create_db_engine(url)` whose connections use only `schema` (search_path)."""
    engine = create_db_engine(url)

    @event.listens_for(engine, "connect", insert=True)  # before SQLAlchemy reads the schema
    def use_schema(dbapi_connection, _record) -> None:
        autocommit = dbapi_connection.autocommit
        dbapi_connection.autocommit = True
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f'SET search_path TO "{schema}"')
        dbapi_connection.autocommit = autocommit

    return engine
