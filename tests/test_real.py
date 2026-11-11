"""Tests with LM Studio running: run only on request with `pytest -m real`.

Each test opens a real MCP server (stdio) with the notes store in tmp_path.
"""

import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from assistant.catalog import DEFAULT_CATALOG_PATH
from assistant.config import ConfigError, load_config
from assistant.graph import build_graph
from assistant.mcp_client import McpClient, create_mcp_tools, server_command
from assistant.model import create_model, create_router_model
from assistant.session import Session
from assistant.tools import create_current_time_tool

pytestmark = pytest.mark.real


@pytest.fixture
def config():
    try:
        return load_config(os.environ)
    except ConfigError as error:
        pytest.fail(f"Prova reale: imposta LMSTUDIO_BASE_URL e LMSTUDIO_MODEL ({error})")


@contextmanager
def open_session(config, db):
    """Session with the eight tools on the notes store `db`; the MCP server closes on exit."""
    command, args, cwd = server_command(db, "WARNING")
    with McpClient(command, args, cwd=cwd) as client:
        tools = [create_current_time_tool(), *create_mcp_tools(client)]
        graph = build_graph(
            create_model(config, tools),
            tools,
            config.max_steps,
            router_model=create_router_model(config),
            scope=config.scope,
        )
        yield Session(graph), client


@pytest.fixture
def real(config, tmp_path):
    with open_session(config, tmp_path / "notes.sqlite3") as opened:
        yield opened


@pytest.fixture
def real_session(real):
    return real[0]


def tool_calls(messages) -> list[dict]:
    return [c for m in messages if isinstance(m, AIMessage) for c in m.tool_calls]


def calls(messages, name: str) -> list[dict]:
    """Arguments of the calls to tool `name`."""
    return [c["args"] for c in tool_calls(messages) if c["name"] == name]


def results(messages, name: str) -> list[dict]:
    """Results returned to the model by tool `name`."""
    return [json.loads(m.content) for m in messages if isinstance(m, ToolMessage) and m.name == name]


# --- CA-2…CA-4 (lesson 4) ---

def test_remembers_the_name_without_tools(real_session):  # CA-4
    real_session.send("Mi chiamo Paolo")
    reply = real_session.send("Come mi chiamo?")
    assert "Paolo" in reply, reply
    assert tool_calls(real_session.messages) == [], real_session.messages


def test_time_in_tokyo_then_in_rome(real_session):  # CA-2 and CA-3
    reply = real_session.send("Che ore sono a Tokyo?")
    messages = real_session.messages
    assert {"timezone": "Asia/Tokyo"} in [c["args"] for c in tool_calls(messages)], messages
    tokyo_time = datetime.fromisoformat(
        next(r["datetime"] for r in results(messages, "get_current_time")
             if r.get("timezone") == "Asia/Tokyo")
    )
    h, m = tokyo_time.hour, tokyo_time.minute
    assert f"{h:02d}:{m:02d}" in reply or f"{h}:{m:02d}" in reply, reply

    n = len(real_session.messages)
    rome_reply = real_session.send("E a Roma?")
    new_calls = tool_calls(real_session.messages[n:])
    assert {"timezone": "Europe/Rome"} in [c["args"] for c in new_calls], (rome_reply, new_calls)


# --- lesson 5 ---

def test_calculate_and_convert(real_session):  # CA-16
    reply = real_session.send("Quanto fa 17 * 23?")
    assert calls(real_session.messages, "calculate"), real_session.messages
    assert "391" in reply, reply

    n = len(real_session.messages)
    reply = real_session.send("Converti 10 km in miglia")
    new = real_session.messages[n:]
    conversions = calls(new, "convert_units")
    assert any(a.get("from_unit") == "km" and a.get("to_unit") == "mi" for a in conversions), new
    assert "6,21" in reply or "6.21" in reply, reply


def test_remember_creates_one_note(real_session):  # CA-17
    real_session.send("Ricordami di consegnare il report venerdì")
    assert len(calls(real_session.messages, "add_note")) == 1, real_session.messages


def test_delete_unknown_note(real):  # CA-18
    session, client = real
    client.call_tool("add_note", {"text": "Consegnare il report venerdì"})
    reply = session.send("Elimina la nota 99")
    messages = session.messages
    assert any(a.get("note_id") == 99 for a in calls(messages, "delete_note")), messages
    assert any("error" in r for r in results(messages, "delete_note")), (reply, messages)
    assert client.call_tool("list_notes", {})["total"] == 1


def test_notes_survive_restart(config, tmp_path):  # CA-19
    db = tmp_path / "notes.sqlite3"
    with open_session(config, db) as (_, client):
        client.call_tool("add_note", {"text": "Consegnare il report venerdì"})
    with open_session(config, db) as (session, _):
        reply = session.send("Quali note ho salvato?")
        assert calls(session.messages, "list_notes"), session.messages
        assert "report" in reply, reply


def test_catalog_search_then_detail(real_session):  # CA-20
    reply = real_session.send("Quante ore dura il corso di visione artificiale?")
    names = [c["name"] for c in tool_calls(real_session.messages)]
    assert "search_catalog" in names, real_session.messages
    first_search = names.index("search_catalog")
    details = [
        i for i, c in enumerate(tool_calls(real_session.messages))
        if c["name"] == "get_item" and str(c["args"].get("code", "")).strip().upper() == "DL-201"
    ]
    assert details and details[0] > first_search, real_session.messages
    assert "32" in reply, reply


def test_catalog_no_results(real_session):  # CA-20
    reply = real_session.send("Ci sono corsi di astrologia?")
    searches = results(real_session.messages, "search_catalog")
    assert searches and all(r.get("total") == 0 for r in searches), real_session.messages
    codes = [item["code"] for item in json.loads(DEFAULT_CATALOG_PATH.read_text(encoding="utf-8"))]
    assert not any(code in reply for code in codes), reply


def test_logs_correlate_call_ids(real_session, caplog):  # CA-21
    caplog.set_level(logging.INFO, logger="assistant.graph")
    real_session.send("Ricordami di comprare il latte")
    ids = [c["id"] for c in tool_calls(real_session.messages) if c["name"] == "add_note"]
    assert ids, real_session.messages
    call_id = ids[0]
    lines = [r.getMessage() for r in caplog.records]
    assert any(f"variant=mcp tool=add_note call_id={call_id}" in line for line in lines), lines
    assert any(f"execution=ok call_id={call_id}" in line for line in lines), lines
    assert f"tool_message.call_id={call_id} next_node=llm" in lines, lines


# --- lesson 6, step 1: router (CA-27) ---

def router_lines(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("node=router")]


def test_router_in_scope_reaches_the_agent(real_session, caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    real_session.send("Che ore sono a Tokyo?")
    assert any("category=conversation" in line for line in router_lines(caplog)), caplog.text
    assert "node=llm" in caplog.text


def test_router_refuses_out_of_scope(real_session, caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    reply = real_session.send("Chi ha vinto i Mondiali del 2006?")
    assert reply.startswith("Mi dispiace, questa domanda è fuori dal mio ambito"), reply
    assert "next_node=refusal" in caplog.text, caplog.text
    assert "node=llm" not in caplog.text
    assert tool_calls(real_session.messages) == []


def test_router_greeting_is_conversation(real_session, caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    real_session.send("Ciao!")
    assert any("category=conversation" in line for line in router_lines(caplog)), caplog.text
