"""Tests with LM Studio running: run only on request with `pytest -m real`."""

import json
import os
from datetime import datetime

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from assistant.config import ConfigError, load_config
from assistant.graph import build_graph
from assistant.model import create_model
from assistant.session import Session
from assistant.tools import create_current_time_tool

pytestmark = pytest.mark.real


@pytest.fixture
def real_session():
    try:
        config = load_config(os.environ)
    except ConfigError as error:
        pytest.fail(f"Prova reale: imposta LMSTUDIO_BASE_URL e LMSTUDIO_MODEL ({error})")
    tools = [create_current_time_tool()]
    return Session(build_graph(create_model(config, tools), tools, config.max_steps))


def tool_calls(messages) -> list[dict]:
    return [c for m in messages if isinstance(m, AIMessage) for c in m.tool_calls]


def test_remembers_the_name_without_tools(real_session):  # CA-4
    real_session.send("Mi chiamo Paolo")
    reply = real_session.send("Come mi chiamo?")
    assert "Paolo" in reply, reply
    assert tool_calls(real_session.messages) == [], real_session.messages


def test_time_in_tokyo_then_in_rome(real_session):  # CA-2 and CA-3
    reply = real_session.send("Che ore sono a Tokyo?")
    messages = real_session.messages
    assert {"timezone": "Asia/Tokyo"} in [c["args"] for c in tool_calls(messages)], messages
    results = [json.loads(m.content) for m in messages if isinstance(m, ToolMessage)]
    tokyo_time = datetime.fromisoformat(
        next(r["datetime"] for r in results if r.get("timezone") == "Asia/Tokyo")
    )
    h, m = tokyo_time.hour, tokyo_time.minute
    assert f"{h:02d}:{m:02d}" in reply or f"{h}:{m:02d}" in reply, reply

    n = len(real_session.messages)
    rome_reply = real_session.send("E a Roma?")
    new_calls = tool_calls(real_session.messages[n:])
    assert {"timezone": "Europe/Rome"} in [c["args"] for c in new_calls], (rome_reply, new_calls)
