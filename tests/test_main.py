import json
import logging
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, SystemMessage

import assistant.__main__ as entry
from assistant.__main__ import main
from assistant.commands import PromptCommands
from assistant.config import DEFAULT_PREFERENCES_FILE, DEFAULT_SCOPE_FILE, load_config
from assistant.graph import SYSTEM_PROMPT
from assistant.mcp_client import ALLOWED_MCP_TOOLS, PromptSpec, ToolSpec
from assistant.preferences import (
    DEFAULT_PREFERENCES,
    PREFERENCES_URI,
    Preferences,
    preferences_prompt,
    with_preferences,
)
from assistant.session import Session
from assistant.tools import ToolUnavailableError

from conftest import MCP_SPECS, ApprovingReviewer, ConversationRouter, FakeMcpClient, FakeModel

VALID = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "google/gemma-4-e2b"}


@pytest.fixture(autouse=True)
def fake_mcp(monkeypatch, tmp_path):
    """No real MCP server, and the default notes folder lands in tmp_path, not in the repo."""
    monkeypatch.setattr(entry, "McpClient", lambda *a, **k: FakeMcpClient(MCP_SPECS))
    monkeypatch.chdir(tmp_path)


def _must_not_call(*args, **kwargs):
    raise AssertionError("LM Studio non deve essere contattato")


def test_missing_config_exits_with_1(capsys, monkeypatch):
    monkeypatch.setattr(entry, "create_model", _must_not_call)
    monkeypatch.setattr(entry, "run", _must_not_call)
    assert main({"LMSTUDIO_BASE_URL": "http://localhost:1234/v1"}) == 1
    assert "Manca LMSTUDIO_MODEL." in capsys.readouterr().err


def test_startup_wires_the_modules(capsys, monkeypatch):
    received = []
    monkeypatch.setattr(entry, "run", lambda session, **kw: received.append((session, kw)))
    assert main(VALID) == 0
    assert len(received) == 1 and isinstance(received[0][0], Session)
    assert isinstance(received[0][1]["commands"], PromptCommands)
    assert (
        "Assistente del laboratorio — modello google/gemma-4-e2b su http://localhost:1234/v1. "
        "Scrivi /prompts per i prompt disponibili, 'esci' per uscire."
    ) in capsys.readouterr().out


def test_library_http_logs_hidden_at_info(monkeypatch, caplog):
    caplog.set_level(logging.INFO)  # as in the app, where the root is at INFO
    monkeypatch.setattr(entry, "run", lambda session, **kw: None)
    main(VALID)
    for library in ("httpx", "httpx2", "openai", "mcp", "fastmcp"):
        assert logging.getLogger(library).getEffectiveLevel() == logging.WARNING, library


def test_all_tools_reach_the_model(monkeypatch):
    received = []
    monkeypatch.setattr(entry, "create_model", lambda config, tools: received.append(tools))
    monkeypatch.setattr(entry, "run", lambda session, **kw: None)
    assert main(VALID) == 0
    assert [t.name for t in received[0]] == ["get_current_time", *ALLOWED_MCP_TOOLS]


def test_mcp_startup_failure_exits_1(capsys, monkeypatch):
    monkeypatch.setattr(
        entry, "McpClient", lambda *a, **k: FakeMcpClient(MCP_SPECS, fail_on_enter=True)
    )
    monkeypatch.setattr(entry, "create_model", _must_not_call)
    monkeypatch.setattr(entry, "run", _must_not_call)
    assert main(VALID) == 1
    assert "Server MCP non avviato: comando non trovato" in capsys.readouterr().err


class DiscoveryFails(FakeMcpClient):
    def list_tools(self):
        raise ToolUnavailableError("nessuna risposta entro 30 s")


def test_discovery_failure_exits_1(capsys, monkeypatch):
    monkeypatch.setattr(entry, "McpClient", lambda *a, **k: DiscoveryFails(MCP_SPECS))
    monkeypatch.setattr(entry, "create_model", _must_not_call)
    monkeypatch.setattr(entry, "run", _must_not_call)
    assert main(VALID) == 1
    assert "Server MCP non avviato: nessuna risposta entro 30 s" in capsys.readouterr().err


def test_name_collision_exits_1(capsys, monkeypatch):
    clash = ToolSpec("get_current_time", "doppione", {"type": "object", "properties": {}})
    monkeypatch.setattr(entry, "ALLOWED_MCP_TOOLS", (*ALLOWED_MCP_TOOLS, "get_current_time"))
    monkeypatch.setattr(entry, "McpClient", lambda *a, **k: FakeMcpClient(MCP_SPECS + [clash]))
    monkeypatch.setattr(entry, "create_model", _must_not_call)
    monkeypatch.setattr(entry, "run", _must_not_call)
    assert main(VALID) == 1
    assert "Strumenti con lo stesso nome: 'get_current_time'." in capsys.readouterr().err


def test_notes_folder_is_created(tmp_path, monkeypatch):
    monkeypatch.setattr(entry, "run", lambda session, **kw: None)
    main({**VALID, "NOTES_DB": str(tmp_path / "sub" / "n.sqlite3")})
    assert (tmp_path / "sub").is_dir()


# --- router (lesson 6, step 1) ---

def test_router_model_and_scope_reach_the_graph(monkeypatch):
    router = object()
    received = []
    monkeypatch.setattr(entry, "create_router_model", lambda config: router)
    monkeypatch.setattr(
        entry, "build_graph", lambda *args, **kwargs: received.append(kwargs) or "graph"
    )
    monkeypatch.setattr(entry, "run", lambda session, **kw: None)
    assert main(VALID) == 0
    assert received[0]["router_model"] is router
    assert received[0]["scope"] == load_config(VALID).scope


def test_scope_file_is_logged(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(entry, "run", lambda session, **kw: None)
    main(VALID)
    assert f"scope_file={DEFAULT_SCOPE_FILE}" in caplog.text


def test_missing_scope_file_exits_1(capsys, monkeypatch, tmp_path):
    monkeypatch.setattr(entry, "create_model", _must_not_call)
    monkeypatch.setattr(entry, "create_router_model", _must_not_call)
    monkeypatch.setattr(entry, "create_reviewer_model", _must_not_call)
    monkeypatch.setattr(entry, "create_summary_model", _must_not_call)
    monkeypatch.setattr(entry, "run", _must_not_call)
    assert main({**VALID, "SCOPE_FILE": str(tmp_path / "manca.txt")}) == 1
    assert "Configurazione non valida: SCOPE_FILE non leggibile:" in capsys.readouterr().err


# --- reviewer (lesson 6, step 2) ---

@pytest.mark.parametrize(("env", "expected"), [({}, 2), ({"MAX_REVIEWS": "3"}, 3)])
def test_reviewer_model_and_max_reviews_reach_the_graph(monkeypatch, env, expected):
    reviewer = object()
    received = []
    monkeypatch.setattr(entry, "create_reviewer_model", lambda config: reviewer)
    monkeypatch.setattr(
        entry, "build_graph", lambda *args, **kwargs: received.append(kwargs) or "graph"
    )
    monkeypatch.setattr(entry, "run", lambda session, **kw: None)
    assert main({**VALID, **env}) == 0
    assert received[0]["reviewer_model"] is reviewer
    assert received[0]["max_reviews"] == expected


def test_graph_built_by_main_goes_through_the_reviewer(monkeypatch):
    reviewer, replies = ApprovingReviewer(), []
    monkeypatch.setattr(
        entry, "create_model", lambda config, tools: FakeModel([AIMessage("Ciao!")])
    )
    monkeypatch.setattr(entry, "create_router_model", lambda config: ConversationRouter())
    monkeypatch.setattr(entry, "create_reviewer_model", lambda config: reviewer)
    monkeypatch.setattr(entry, "run", lambda session, **kw: replies.append(session.send("Ciao")))
    assert main(VALID) == 0
    assert replies == ["Ciao!"]
    assert len(reviewer.calls) == 1


def test_max_reviews_is_logged(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(entry, "run", lambda session, **kw: None)
    main(VALID)
    assert f"scope_file={DEFAULT_SCOPE_FILE} max_reviews=2" in caplog.text


# --- summary (lesson 6, step 3) ---

@pytest.mark.parametrize(("env", "maximum", "keep"), [
    ({}, 20, 6),
    ({"SUMMARY_MAX_MESSAGES": "8", "SUMMARY_KEEP_MESSAGES": "3"}, 8, 3),
])
def test_summary_model_and_thresholds_reach_the_graph(monkeypatch, env, maximum, keep):
    summarizer = object()
    received = []
    monkeypatch.setattr(entry, "create_summary_model", lambda config: summarizer)
    monkeypatch.setattr(
        entry, "build_graph", lambda *args, **kwargs: received.append(kwargs) or "graph"
    )
    monkeypatch.setattr(entry, "run", lambda session, **kw: None)
    assert main({**VALID, **env}) == 0
    assert received[0]["summary_model"] is summarizer
    assert received[0]["summary_max_messages"] == maximum
    assert received[0]["summary_keep_messages"] == keep


def test_graph_built_by_main_goes_through_the_summary_node(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    replies = []
    monkeypatch.setattr(
        entry, "create_model", lambda config, tools: FakeModel([AIMessage("Ciao!")])
    )
    monkeypatch.setattr(entry, "create_router_model", lambda config: ConversationRouter())
    monkeypatch.setattr(entry, "create_reviewer_model", lambda config: ApprovingReviewer())
    monkeypatch.setattr(entry, "create_summary_model", lambda config: FakeModel([]))
    monkeypatch.setattr(entry, "run", lambda session, **kw: replies.append(session.send("Ciao")))
    assert main(VALID) == 0
    assert replies == ["Ciao!"]
    assert "node=summary messages=1/20 skipped=below_threshold next_node=router" in caplog.text


def test_summary_thresholds_are_logged(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(entry, "run", lambda session, **kw: None)
    main(VALID)
    assert (
        f"scope_file={DEFAULT_SCOPE_FILE} max_reviews=2 "
        "summary_max_messages=20 summary_keep_messages=6"
    ) in caplog.text


# --- preferences (lesson 6, step 4) ---

def _server_args(monkeypatch, env) -> list[str]:
    """Arguments given to McpClient by main()."""
    received = []

    def fake_client(command, args, **kwargs):
        received.append(args)
        return FakeMcpClient(MCP_SPECS)

    monkeypatch.setattr(entry, "McpClient", fake_client)
    monkeypatch.setattr(entry, "run", lambda session, **kw: None)
    assert main(env) == 0
    return received[0]


def test_server_gets_the_default_preferences_file(monkeypatch):
    args = _server_args(monkeypatch, VALID)
    assert args[args.index("--preferences-file") + 1] == str(Path(DEFAULT_PREFERENCES_FILE))


def test_server_gets_an_absolute_preferences_file(monkeypatch, tmp_path):
    args = _server_args(monkeypatch, {**VALID, "PREFERENCES_FILE": "p.json"})  # cwd is tmp_path
    assert args[args.index("--preferences-file") + 1] == str((tmp_path / "p.json").resolve())


NEW_YORK = json.dumps({"language": "inglese", "timezone": "America/New_York", "style": "sintetico"})


def _with_resource(monkeypatch, text=NEW_YORK) -> FakeMcpClient:
    """main() gets a fake client that publishes the preferences; returned to inspect the reads."""
    client = FakeMcpClient(MCP_SPECS, resources={PREFERENCES_URI: text})
    monkeypatch.setattr(entry, "McpClient", lambda *a, **k: client)
    return client


def test_resource_is_read_once_in_a_session_of_many_turns(monkeypatch):  # CA-49
    client = _with_resource(monkeypatch)
    model = FakeModel([AIMessage("Hi!"), AIMessage("Bye!")])
    monkeypatch.setattr(entry, "create_model", lambda config, tools: model)
    monkeypatch.setattr(entry, "create_router_model", lambda config: ConversationRouter())
    monkeypatch.setattr(entry, "create_reviewer_model", lambda config: ApprovingReviewer())
    replies = []
    monkeypatch.setattr(
        entry, "run", lambda session, **kw: replies.extend([session.send("Ciao"), session.send("Ciao")])
    )
    assert main(VALID) == 0
    assert replies == ["Hi!", "Bye!"]
    assert client.resource_reads == [PREFERENCES_URI]
    expected = with_preferences(SYSTEM_PROMPT, preferences_prompt(
        Preferences("inglese", "America/New_York", "sintetico")
    ))
    assert [call[0] for call in model.calls] == [SystemMessage(expected)] * 2


def test_resource_is_read_before_the_first_question(monkeypatch):
    client = _with_resource(monkeypatch)
    reads_at_start = []
    monkeypatch.setattr(
        entry, "run", lambda session, **kw: reads_at_start.append(list(client.resource_reads))
    )
    assert main(VALID) == 0
    assert reads_at_start == [[PREFERENCES_URI]]


def test_resource_does_not_reach_bind_tools(monkeypatch):  # RF-41
    _with_resource(monkeypatch)
    received = []
    monkeypatch.setattr(entry, "create_model", lambda config, tools: received.append(tools))
    monkeypatch.setattr(entry, "run", lambda session, **kw: None)
    assert main(VALID) == 0
    assert [t.name for t in received[0]] == ["get_current_time", *ALLOWED_MCP_TOOLS]


def test_preferences_text_reaches_the_graph(monkeypatch):
    _with_resource(monkeypatch)
    received = []
    monkeypatch.setattr(
        entry, "build_graph", lambda *args, **kwargs: received.append(kwargs) or "graph"
    )
    monkeypatch.setattr(entry, "run", lambda session, **kw: None)
    assert main(VALID) == 0
    assert received[0]["preferences"] == preferences_prompt(
        Preferences("inglese", "America/New_York", "sintetico")
    )


def test_unavailable_resource_starts_with_the_defaults(monkeypatch, caplog):  # RF-42
    caplog.set_level(logging.INFO)
    received = []
    monkeypatch.setattr(  # the autouse fake client has no resources
        entry, "build_graph", lambda *args, **kwargs: received.append(kwargs) or "graph"
    )
    started = []
    monkeypatch.setattr(entry, "run", lambda session, **kw: started.append(session))
    assert main(VALID) == 0
    assert len(started) == 1  # the session starts anyway
    assert received[0]["preferences"] == preferences_prompt(DEFAULT_PREFERENCES)
    warnings = [
        r.getMessage() for r in caplog.records
        if r.levelno == logging.WARNING and r.name == "assistant.preferences"
    ]
    assert len(warnings) == 1 and "status=unavailable" in warnings[0]


def test_preferences_file_is_logged(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(entry, "run", lambda session, **kw: None)
    main(VALID)
    assert (
        "summary_max_messages=20 summary_keep_messages=6 "
        f"preferences_file={Path(DEFAULT_PREFERENCES_FILE).resolve()}"
    ) in caplog.text


# --- prompt commands (lesson 6, step 5) ---

def test_prompts_command_uses_the_session_client(monkeypatch, caplog):  # CA-56
    caplog.set_level(logging.INFO)
    spec = PromptSpec("spiega", "Spiega un argomento al livello scelto.", ())
    client = FakeMcpClient(MCP_SPECS, prompts={"spiega": (spec, lambda arguments: [])})
    monkeypatch.setattr(entry, "McpClient", lambda *a, **k: client)
    monkeypatch.setattr(entry, "create_model", lambda config, tools: FakeModel([]))
    lists_at_start, outputs = [], []

    def fake_run(session, commands):
        lists_at_start.append(client.prompt_lists)
        outputs.append(commands.handle("/prompts").output)

    monkeypatch.setattr(entry, "run", fake_run)
    assert main(VALID) == 0
    assert lists_at_start == [0]  # prompts/list only when the user asks for it
    assert client.prompt_lists == 1 and client.prompt_gets == []
    assert outputs[0].startswith(
        "Prompt disponibili:\n- spiega: Spiega un argomento al livello scelto."
    )
    assert "prompts/list count=1 names=spiega" in caplog.text
