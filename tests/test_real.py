"""Tests with LM Studio running: run only on request with `pytest -m real`.

Each test opens a real MCP server (stdio) with the notes store in tmp_path.
"""

import dataclasses
import json
import logging
import os
import re
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from langchain_core.messages import AIMessage, ToolMessage

from assistant.catalog import DEFAULT_CATALOG_PATH
from assistant.commands import PromptCommands, resolve_prompt
from assistant.config import DEFAULT_PREFERENCES_FILE, ConfigError, load_config
from assistant.graph import build_graph
from assistant.mcp_client import McpClient, create_mcp_tools, server_command
from assistant.model import (
    create_model,
    create_reviewer_model,
    create_router_model,
    create_summary_model,
)
from assistant.preferences import DEFAULT_PREFERENCES, load_preferences, preferences_prompt
from assistant.reviewer import is_feedback
from assistant.session import Session
from assistant.summary import is_user_question
from assistant.tools import create_current_time_tool
from conftest import postgres_schema

pytestmark = pytest.mark.real

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def config():
    try:
        return load_config(os.environ)
    except ConfigError as error:
        pytest.fail(f"Prova reale: imposta LMSTUDIO_BASE_URL e LMSTUDIO_MODEL ({error})")


@contextmanager
def open_session(config, db, wrap_agent=None, preferences_file=DEFAULT_PREFERENCES_FILE):
    """Session with the eight tools on the notes store `db`; the MCP server closes on exit.

    `wrap_agent`, if given, wraps the agent's model; router and reviewer stay real.
    The preferences are read from `preferences_file` through the resource, as in `__main__`.
    """
    command, args, cwd = server_command(db, "WARNING", preferences_file)
    with McpClient(command, args, cwd=cwd) as client:
        tools = [create_current_time_tool(), *create_mcp_tools(client)]
        model = create_model(config, tools)
        graph = build_graph(
            wrap_agent(model) if wrap_agent else model,
            tools,
            config.max_steps,
            router_model=create_router_model(config),
            scope=config.scope,
            reviewer_model=create_reviewer_model(config),
            max_reviews=config.max_reviews,
            summary_model=create_summary_model(config),
            summary_max_messages=config.summary_max_messages,
            summary_keep_messages=config.summary_keep_messages,
            preferences=preferences_prompt(load_preferences(client)),
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
    # "next_node=llm" in the router's own line also contains "node=llm": look for the agent's line.
    assert re.search(r"step=\d+/\d+ node=llm", caplog.text), caplog.text


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


# --- lesson 6, step 2: reviewer (CA-36) ---

TWO_PARTS = "Che ore sono a Tokyo e quanto fa 17 * 23?"
PARTIAL = "A Tokyo sono le 10:00."  # answers only the first part; the time is not checked


class PartialFirstAnswer:
    """The agent's first call returns a fixed partial answer; later calls use the real model."""

    def __init__(self, model, text: str):
        self._model = model
        self._text = text
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        if self.calls == 1:
            return AIMessage(self._text)
        return self._model.invoke(messages)


def reviewer_lines(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("node=reviewer")]


def tool_times(messages, timezone: str) -> list[str]:
    """Times returned by get_current_time for `timezone`, as HH:MM and H:MM."""
    times = []
    for r in results(messages, "get_current_time"):
        if r.get("timezone") == timezone:
            t = datetime.fromisoformat(r["datetime"])
            times += [f"{t.hour:02d}:{t.minute:02d}", f"{t.hour}:{t.minute:02d}"]
    return times


def tokyo_times(messages) -> list[str]:
    return tool_times(messages, "Asia/Tokyo")


def test_reviewer_rejects_an_imposed_partial_answer(config, tmp_path, caplog):
    # The agent's FIRST answer is imposed (PartialFirstAnswer); reviewer and rewrite are real.
    caplog.set_level(logging.INFO, logger="assistant.graph")
    wrap = lambda model: PartialFirstAnswer(model, PARTIAL)  # noqa: E731
    with open_session(config, tmp_path / "notes.sqlite3", wrap_agent=wrap) as (session, _):
        reply = session.send(TWO_PARTS)
        messages = session.messages
    lines = reviewer_lines(caplog)
    assert lines and "coherent=false" in lines[0] and 'reason=""' not in lines[0], lines
    assert any("coherent=true" in line for line in lines[1:]), lines
    assert len(lines) <= config.max_reviews, lines
    assert any(is_feedback(m) for m in messages), messages
    assert re.search(r"step=2/\d+ node=llm", caplog.text), caplog.text  # the real agent rewrote
    assert "391" in reply, reply


def test_two_part_question_fully_real(config, real_session, caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    reply = real_session.send(TWO_PARTS)
    messages = real_session.messages
    assert "391" in reply, (reply, messages)
    assert any(t in reply for t in tokyo_times(messages)), (reply, messages)
    assert 1 <= len(reviewer_lines(caplog)) <= config.max_reviews, caplog.text


# --- lesson 6, step 3: summary (CA-43) ---

COMPRESSION = re.compile(
    r"node=summary messages_before=(\d+) messages_after=(\d+) removed=\d+ next_node=router"
)


def summary_lines(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("node=summary")]


def test_first_turn_information_survives_compression(config, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    small = dataclasses.replace(config, summary_max_messages=4, summary_keep_messages=2)
    with open_session(small, tmp_path / "notes.sqlite3") as (session, _):
        session.send("Mi chiamo Paolo")
        first = summary_lines(caplog)
        session.send("Che ore sono a Tokyo?")
        reply = session.send("Come mi chiamo?")
        messages, summary = session.messages, session.summary
    lines = summary_lines(caplog)
    assert first == ["node=summary messages=1/4 skipped=below_threshold next_node=router"], first
    sizes = [tuple(map(int, m.groups())) for m in map(COMPRESSION.fullmatch, lines) if m]
    assert sizes and all(before > after for before, after in sizes), lines
    last = max(i for i, m in enumerate(messages) if is_user_question(m))
    # the name can reach the agent only through the summary
    assert not any("Paolo" in m.text for m in messages[:last]), messages
    assert "Paolo" in summary, (summary, lines)
    assert "Paolo" in reply, (reply, summary, lines)


# --- lesson 6, step 4: preferences resource (CA-50, CA-51) ---

def write_preferences(path, **fields):
    """A preferences file with the defaults changed by `fields`."""
    data = {**dataclasses.asdict(DEFAULT_PREFERENCES), **fields}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def preferences_lines(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("resources/read")]


def test_default_timezone_from_preferences(config, tmp_path, caplog):  # CA-50
    caplog.set_level(logging.INFO, logger="assistant.preferences")
    prefs = write_preferences(tmp_path / "preferenze.json", timezone="America/New_York")
    with open_session(config, tmp_path / "notes.sqlite3", preferences_file=prefs) as (session, _):
        reply = session.send("Che ore sono?")
        messages = session.messages
    assert any("status=ok" in line and "timezone=America/New_York" in line
               for line in preferences_lines(caplog)), caplog.text
    # answered in the first turn with the default timezone, without asking for it
    assert {"timezone": "America/New_York"} in calls(messages, "get_current_time"), messages
    assert any(t in reply for t in tool_times(messages, "America/New_York")), (reply, messages)


ITALIAN_WORDS = {"il", "lo", "la", "di", "che", "e", "è", "per", "posso", "con", "un", "una",
                 "del", "della", "ti", "le", "sono", "ora", "corsi", "ciao"}
ENGLISH_WORDS = {"the", "and", "you", "i", "can", "to", "of", "for", "with", "your", "is",
                 "help", "time", "courses", "notes", "hello", "hi"}


def language_counts(text: str) -> tuple[int, int]:
    """Common Italian and English words in `text` (fixed lists, see the specification §7)."""
    words = re.findall(r"[a-zàèéìòù]+", text.lower())
    return sum(w in ITALIAN_WORDS for w in words), sum(w in ENGLISH_WORDS for w in words)


def test_language_from_preferences(config, tmp_path, caplog):  # CA-51
    caplog.set_level(logging.INFO, logger="assistant.preferences")
    question = "Ciao, che cosa sai fare?"
    with open_session(config, tmp_path / "notes.sqlite3") as (session, _):
        italian = session.send(question)
    prefs = write_preferences(tmp_path / "preferenze.json", language="inglese")
    with open_session(config, tmp_path / "notes.sqlite3", preferences_file=prefs) as (session, _):
        english = session.send(question)
    lines = preferences_lines(caplog)
    assert any('language="inglese"' in line for line in lines), lines
    it, en = language_counts(italian)
    assert it > en, (italian, it, en)
    it, en = language_counts(english)
    assert en > it, (english, it, en)


# --- lesson 6, step 5: MCP prompts (CA-58, CA-59) ---

REFUSAL = "Mi dispiace, questa domanda è fuori dal mio ambito"


def send_prompt(session, client, text: str) -> str:
    """A /prompt command as CLI and service run it: syntax in the CLI, host check and
    prompts/get in the service, then the messages go to the graph as a turn."""
    result = PromptCommands(None).handle(text)  # /prompt never calls the agent client
    assert result.prompt, result.output
    return session.send_messages(resolve_prompt(client, *result.prompt))


def prompt_get_lines(caplog, name: str) -> list[str]:
    return [r.getMessage() for r in caplog.records
            if r.getMessage().startswith(f"prompts/get name={name} arguments=")]


def test_explain_prompt(real, caplog):  # CA-58
    caplog.set_level(logging.INFO, logger="assistant")
    session, client = real
    reply = send_prompt(
        session, client, '/prompt spiega argomento="Model Context Protocol" livello=base'
    )
    assert any("status=ok" in line for line in prompt_get_lines(caplog, "spiega")), caplog.text
    assert any("category=conversation" in line for line in router_lines(caplog)), caplog.text
    assert reviewer_lines(caplog), caplog.text
    assert reply.strip() and not reply.startswith(REFUSAL), reply
    assert "protocol" in reply.lower() or "mcp" in reply.lower(), reply


def test_summary_prompt(real, caplog):  # CA-59
    caplog.set_level(logging.INFO, logger="assistant")
    session, client = real
    session.send("Mi chiamo Paolo")
    session.send("Quanto fa 17 * 23?")
    n = len(router_lines(caplog))
    reply = send_prompt(session, client, "/prompt riassumi_conversazione stile=sintetico")
    assert any("status=ok" in line
               for line in prompt_get_lines(caplog, "riassumi_conversazione")), caplog.text
    assert any("category=conversation" in line for line in router_lines(caplog)[n:]), caplog.text
    assert "Paolo" in reply and "391" in reply, (reply, session.messages)


# --- lesson 6, step 6: the agent as an HTTP service (CA-67…CA-69) ---

QUESTION = "Quanto fa 17 * 23?"
SERVICE_START_TIMEOUT = 60.0  # seconds: MCP server, discovery and preferences before uvicorn


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextmanager
def start_service(tmp_path, **overrides):
    """`python -m assistant.service` as a subprocess on a free port, notes in tmp_path and log in
    a file; yields (base_url, read_log). The process is stopped on exit."""
    port = free_port()
    env = {
        "AGENT_HOST": "127.0.0.1",
        "AGENT_PORT": str(port),
        "NOTES_DB": str(tmp_path / "notes.sqlite3"),
        **overrides,
    }
    with start_process("assistant.service", tmp_path, port, env) as started:
        yield started


@contextmanager
def start_process(module: str, tmp_path, port: int, env: dict):
    """`python -m <module>` as a subprocess listening on `port`, with `env` added to the
    environment and its log in a new file of tmp_path; yields (base_url, read_log) once
    /openapi.json answers. The process is stopped on exit."""
    env = {**os.environ, "LOG_LEVEL": "INFO", "PYTHONIOENCODING": "utf-8", **env}
    log_path = tmp_path / f"{module}-{port}-{time.monotonic_ns()}.log"
    base_url = f"http://127.0.0.1:{port}"
    with open(log_path, "wb") as log_file:
        process = subprocess.Popen(
            [sys.executable, "-m", module],
            cwd=REPO_ROOT, env=env, stdout=log_file, stderr=subprocess.STDOUT,
        )
        try:
            wait_for_service(base_url, process, log_path)
            yield base_url, lambda: log_path.read_text(encoding="utf-8", errors="replace")
        finally:
            process.terminate()
            process.wait(timeout=30)


def wait_for_service(base_url, process, log_path) -> None:
    deadline = time.monotonic() + SERVICE_START_TIMEOUT
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail(f"Servizio terminato: {log_path.read_text(encoding='utf-8')}")
        try:
            httpx.get(f"{base_url}/openapi.json", timeout=2.0)
            return
        except httpx.TransportError:
            time.sleep(0.5)
    pytest.fail(f"Servizio non pronto: {log_path.read_text(encoding='utf-8')}")


def post_chat(base_url, message: str, history=(), summary: str = "") -> httpx.Response:
    return httpx.post(
        f"{base_url}/chat",
        json={"message": message, "history": list(history), "summary": summary},
        timeout=600.0,
    )


def cli_replies(stdout: str) -> list[str]:
    """Replies printed by the CLI: text after 'Assistente> ' up to the next prompt."""
    return [part.split("Tu> ")[0].replace("Arrivederci!", "").strip()
            for part in stdout.split("Assistente> ")[1:]]


def chat_response_lines(log: str) -> list[str]:
    return [line for line in log.splitlines() if "api response=chat" in line]


def test_http_chat_with_a_tool(tmp_path):  # CA-67
    with start_service(tmp_path) as (base_url, read_log):
        response = post_chat(base_url, QUESTION)
        log = read_log()
    assert response.status_code == 200, response.text
    body = response.json()
    assert [t["name"] for t in body["tools_used"]] == ["calculate"], body
    assert body["tools_used"][0]["ok"] is True, body
    assert "391" in body["reply"], body
    assert body["history"][0]["role"] == "user", body
    assert body["history"][0]["content"] == QUESTION, body
    assert "api request=chat kind=message history=0" in log, log
    assert any("status=200 tools=calculate " in line
               for line in chat_response_lines(log)), log
    assert re.search(r"variant=\S+ tool=calculate call_id=", log), log


def test_same_answer_from_cli_and_api(tmp_path):  # CA-68
    with start_service(tmp_path) as (base_url, read_log):
        api = post_chat(base_url, QUESTION)
        cli = subprocess.run(
            [sys.executable, "-m", "assistant"],
            cwd=REPO_ROOT, input=f"{QUESTION}\nesci\n", capture_output=True,
            encoding="utf-8", errors="replace", timeout=900,
            env={**os.environ, "AGENT_URL": base_url, "LOG_LEVEL": "INFO",
                 "PYTHONIOENCODING": "utf-8"},
        )
        log = read_log()
    assert api.status_code == 200, api.text
    assert cli.returncode == 0, (cli.stdout, cli.stderr)
    api_reply = api.json()["reply"]
    (cli_reply,) = cli_replies(cli.stdout)
    lines = chat_response_lines(log)
    assert len(lines) == 2, log
    assert all("status=200 tools=calculate " in line for line in lines), lines
    assert "391" in api_reply and "391" in cli_reply, (api_reply, cli_reply)
    print(f"API: {api_reply!r}\nCLI: {cli_reply!r}\nuguali: {api_reply == cli_reply}")


def test_openapi_and_status(tmp_path):  # CA-69
    with start_service(tmp_path) as (base_url, _):
        openapi = httpx.get(f"{base_url}/openapi.json", timeout=10.0)
        docs = httpx.get(f"{base_url}/docs", timeout=10.0)
        status = httpx.get(f"{base_url}/status", timeout=30.0)
    assert openapi.status_code == 200, openapi.text
    assert {"/chat", "/prompts", "/status"} <= set(openapi.json()["paths"]), openapi.json()
    assert docs.status_code == 200, docs.text
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["status"] == "ok", body
    assert body["mcp"]["status"] == "ok" and body["model"]["status"] == "ok", body


def test_service_without_lm_studio(tmp_path):  # CA-69
    with start_service(tmp_path, LMSTUDIO_BASE_URL="http://127.0.0.1:1/v1") as (base_url, read_log):
        status = httpx.get(f"{base_url}/status", timeout=30.0)
        chat = post_chat(base_url, QUESTION)
        log = read_log()
    assert status.status_code == 503, status.text
    assert status.json()["mcp"]["status"] == "ok", status.json()
    assert status.json()["model"]["status"] == "unavailable", status.json()
    assert chat.status_code == 503, chat.text
    assert chat.json()["error"] == "model_unavailable", chat.json()
    assert "api response=chat status=503 error=model_unavailable" in log, log


# --- lesson 6, step 7: back-end with PostgreSQL and the agent (CA-78) ---

FOLLOW_UP = "Moltiplica per 2 il risultato di prima."


@contextmanager
def start_backend(tmp_path, port: int, agent_url: str, database: tuple[str, str]):
    """`python -m backend` on `port` with the database in the temporary schema `database`
    (url, schema); PGOPTIONS (read by libpq) sets the search_path of every connection."""
    url, schema = database
    env = {
        "BACKEND_HOST": "127.0.0.1",
        "BACKEND_PORT": str(port),
        "AGENT_URL": agent_url,
        "DATABASE_URL": url,
        "PGOPTIONS": f"-csearch_path={schema}",
    }
    with start_process("backend", tmp_path, port, env) as started:
        yield started


def send_message(base_url, chat_id: int, content: str) -> httpx.Response:
    return httpx.post(
        f"{base_url}/chats/{chat_id}/messages", json={"content": content}, timeout=900.0
    )


def agent_call_histories(log: str) -> list[int]:
    return [int(n) for n in re.findall(r"backend agent_call chat=\d+ history=(\d+)", log)]


def test_backend_keeps_chats_across_restarts(tmp_path):  # CA-78
    backend_port = free_port()
    with postgres_schema("backend") as database:
        with start_service(tmp_path) as (agent_url, read_agent_log):
            with start_backend(tmp_path, backend_port, agent_url, database) as (base_url, read_log):
                created = httpx.post(f"{base_url}/chats", timeout=30.0)
                chat_id = created.json()["id"]
                first = send_message(base_url, chat_id, QUESTION)
                first_log = read_log()
            # back-end stopped and started again on the same database
            with start_backend(tmp_path, backend_port, agent_url, database) as (base_url, read_log):
                listed = httpx.get(f"{base_url}/chats", timeout=30.0)
                restored = httpx.get(f"{base_url}/chats/{chat_id}", timeout=30.0)
                second = send_message(base_url, chat_id, FOLLOW_UP)
                second_log = read_log()
            agent_log = read_agent_log()
        # agent stopped
        with start_backend(tmp_path, backend_port, agent_url, database) as (base_url, read_log):
            failed = send_message(base_url, chat_id, "Quanto fa 2 + 2?")
            final = httpx.get(f"{base_url}/chats/{chat_id}", timeout=30.0)
            failed_log = read_log()

    assert created.status_code == 201, created.text
    assert first.status_code == 201, first.text
    answer = first.json()["answer"]
    assert [t["name"] for t in answer["tools_used"]] == ["calculate"], answer
    assert "391" in answer["content"], answer
    assert agent_call_histories(first_log) == [0], first_log
    assert "status=201 tools=calculate " in first_log, first_log

    assert listed.status_code == 200, listed.text
    assert [(c["id"], c["title"]) for c in listed.json()] == [(chat_id, QUESTION)], listed.json()
    messages = restored.json()["messages"]
    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", QUESTION), ("assistant", answer["content"]),
    ], messages
    assert messages[1]["tools_used"] == answer["tools_used"], messages

    assert second.status_code == 201, second.text
    (history,) = agent_call_histories(second_log)
    assert history > 0, second_log  # the saved history reached the agent
    assert f"api request=chat kind=message history={history}" in agent_log, agent_log
    assert "782" in second.json()["answer"]["content"], second.json()

    assert failed.status_code == 503, failed.text
    assert failed.json()["error"] == "agent_unavailable", failed.json()
    assert "status=503 error=agent_unavailable" in failed_log, failed_log
    contents = [m["content"] for m in final.json()["messages"]]
    assert len(contents) == 5 and contents[-1] == "Quanto fa 2 + 2?", contents
    print(f"risposte: {answer['content']!r} / {second.json()['answer']['content']!r}")
