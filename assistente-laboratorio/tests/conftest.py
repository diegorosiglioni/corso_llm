from datetime import datetime, timezone

import httpx2
import openai
from langchain_core.messages import AIMessage, BaseMessage

from assistant.graph import build_graph
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


def fake_graph(model, tools=None, max_steps=5):
    if tools is None:
        tools = [create_current_time_tool(lambda: FIXED_NOW)]
    return build_graph(model, list(tools), max_steps)


def tool_call(
    timezone: str | None = "Asia/Tokyo", id: str = "c1", name: str = "get_current_time"
) -> AIMessage:
    """Model reply that requests a tool; timezone=None → empty arguments."""
    args = {} if timezone is None else {"timezone": timezone}
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": id}])


def lm_studio_error() -> openai.APIConnectionError:
    return openai.APIConnectionError(
        request=httpx2.Request("POST", "http://localhost:1234/v1/chat/completions")
    )
