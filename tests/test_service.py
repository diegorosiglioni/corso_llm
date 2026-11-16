import json
import logging
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

import assistant.service as service
from assistant.config import DEFAULT_PREFERENCES_FILE, DEFAULT_SCOPE_FILE, load_config
from assistant.mcp_client import (
    ALLOWED_MCP_TOOLS,
    PromptArgument,
    PromptMessage,
    PromptSpec,
    ToolSpec,
)
from assistant.preferences import (
    DEFAULT_PREFERENCES,
    PREFERENCES_URI,
    parse_preferences,
    preferences_prompt,
)
from assistant.service import main
from assistant.tools import ToolUnavailableError
from conftest import MCP_SPECS, ApprovingReviewer, ConversationRouter, FakeMcpClient, FakeModel

VALID = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "google/gemma-4-e2b"}
NEW_YORK = {"language": "italiano", "timezone": "America/New_York", "style": "sintetico"}


class FakeUvicorn:
    """Stands in for uvicorn.run: records the arguments and runs `during(app)` if given."""

    def __init__(self, during=None):
        self.runs: list[tuple[FastAPI, dict]] = []
        self._during = during

    def __call__(self, app, **kwargs) -> None:
        self.runs.append((app, kwargs))
        if self._during is not None:
            self._during(app)


@pytest.fixture
def mcp(monkeypatch, tmp_path) -> FakeMcpClient:
    """Fake MCP client with the preferences resource; notes folder in tmp_path, not in the repo."""
    client = FakeMcpClient(MCP_SPECS, resources={PREFERENCES_URI: json.dumps(NEW_YORK)})
    monkeypatch.setattr(service, "McpClient", lambda *a, **k: client)
    monkeypatch.chdir(tmp_path)
    return client


@pytest.fixture
def server(monkeypatch) -> FakeUvicorn:
    fake = FakeUvicorn()
    monkeypatch.setattr(service.uvicorn, "run", fake)
    return fake


def _must_not_call(*args, **kwargs):
    raise AssertionError("non deve essere chiamato")


def test_startup_serves_the_app_with_the_default_address(mcp, server, caplog):  # CA-65
    caplog.set_level(logging.INFO)
    assert main(VALID) == 0
    [(app, kwargs)] = server.runs
    assert isinstance(app, FastAPI)
    assert kwargs == {"host": "127.0.0.1", "port": 8000, "access_log": False, "log_config": None}
    assert (
        "api listening=http://127.0.0.1:8000 docs=/docs model=google/gemma-4-e2b "
        "base_url=http://localhost:1234/v1"
    ) in [r.getMessage() for r in caplog.records]


def test_address_from_the_environment(mcp, server):  # CA-65
    assert main({**VALID, "AGENT_HOST": "0.0.0.0", "AGENT_PORT": "8080"}) == 0
    [(_, kwargs)] = server.runs
    assert (kwargs["host"], kwargs["port"]) == ("0.0.0.0", 8080)


@pytest.mark.parametrize(("env", "message"), [
    ({"LMSTUDIO_BASE_URL": "http://localhost:1234/v1"}, "Manca LMSTUDIO_MODEL."),
    ({**VALID, "AGENT_PORT": "0"}, "AGENT_PORT deve essere un intero tra 1 e 65535"),
])
def test_invalid_config_exits_1(env, message, mcp, server, capsys):  # CA-65
    assert main(env) == 1
    assert message in capsys.readouterr().err
    assert server.runs == []


def test_mcp_startup_failure_exits_1(monkeypatch, server, capsys, tmp_path):  # CA-65
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        service, "McpClient", lambda *a, **k: FakeMcpClient(MCP_SPECS, fail_on_enter=True)
    )
    assert main(VALID) == 1
    assert "Server MCP non avviato: comando non trovato" in capsys.readouterr().err
    assert server.runs == []


class DiscoveryFails(FakeMcpClient):
    def list_tools(self, timeout=None):
        raise ToolUnavailableError("nessuna risposta entro 30 s")


def test_discovery_failure_exits_1(monkeypatch, server, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(service, "McpClient", lambda *a, **k: DiscoveryFails(MCP_SPECS))
    assert main(VALID) == 1
    assert "Server MCP non avviato: nessuna risposta entro 30 s" in capsys.readouterr().err
    assert server.runs == []


def test_name_collision_exits_1(monkeypatch, server, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    clash = ToolSpec("get_current_time", "doppione", {"type": "object", "properties": {}})
    monkeypatch.setattr(service, "ALLOWED_MCP_TOOLS", (*ALLOWED_MCP_TOOLS, "get_current_time"))
    monkeypatch.setattr(service, "McpClient", lambda *a, **k: FakeMcpClient(MCP_SPECS + [clash]))
    assert main(VALID) == 1
    assert "Strumenti con lo stesso nome: 'get_current_time'." in capsys.readouterr().err
    assert server.runs == []


def test_server_command_gets_absolute_paths(monkeypatch, server, tmp_path):
    received = []

    def client(command, args, cwd=None):
        received.append(args)
        return FakeMcpClient(MCP_SPECS)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(service, "McpClient", client)
    assert main({**VALID, "NOTES_DB": "sub/n.sqlite3", "PREFERENCES_FILE": "p.json"}) == 0
    [args] = received
    assert args[args.index("--notes-db") + 1] == str(tmp_path / "sub" / "n.sqlite3")
    assert args[args.index("--preferences-file") + 1] == str(tmp_path / "p.json")
    assert (tmp_path / "sub").is_dir()


def test_library_http_logs_hidden_at_info(mcp, server, caplog):
    caplog.set_level(logging.INFO)
    main(VALID)
    for library in ("httpx", "httpx2", "openai", "mcp", "fastmcp"):
        assert logging.getLogger(library).getEffectiveLevel() == logging.WARNING, library


def test_lm_studio_is_not_contacted_at_startup(mcp, server, monkeypatch):
    monkeypatch.setattr(service, "check_model", _must_not_call)
    assert main(VALID) == 0  # LM Studio switched off does not stop the startup


def test_served_app_uses_graph_mcp_and_model_check(mcp, monkeypatch):
    """The app given to uvicorn answers /status, /prompts and /chat with the open MCP session."""
    agent = FakeModel([AIMessage("Ciao!"), AIMessage("Ancora ciao!")])
    checked = []
    monkeypatch.setattr(service, "create_model", lambda config, tools: agent)
    monkeypatch.setattr(service, "create_router_model", lambda config: ConversationRouter())
    monkeypatch.setattr(service, "create_reviewer_model", lambda config: ApprovingReviewer())
    monkeypatch.setattr(
        service, "check_model", lambda config: checked.append(config) or (True, "")
    )
    answers = {}

    def during(app):
        http = TestClient(app)
        answers["status"] = http.get("/status")
        answers["prompts"] = http.get("/prompts")
        answers["chat"] = [http.post("/chat", json={"message": "ciao"}) for _ in range(2)]

    monkeypatch.setattr(service.uvicorn, "run", FakeUvicorn(during))
    assert main(VALID) == 0

    status = answers["status"]
    assert status.status_code == 200
    assert status.json()["mcp"] == {"status": "ok", "detail": "7 strumenti"}
    assert status.json()["model"]["id"] == "google/gemma-4-e2b"
    assert checked == [load_config(VALID)]
    assert (answers["prompts"].status_code, answers["prompts"].json()) == (200, [])
    assert [r.json()["reply"] for r in answers["chat"]] == ["Ciao!", "Ancora ciao!"]
    # preferences: read once at startup, at the top of the agent's prompt in every turn
    assert mcp.resource_reads == [PREFERENCES_URI]
    expected = preferences_prompt(parse_preferences(json.dumps(NEW_YORK))[0])
    assert all(call[0].content.startswith(expected) for call in agent.calls)


# --- graph wiring (from test_main.py, when the CLI became a client: step 6, point 5) ---

def graph_options(monkeypatch, env=VALID) -> dict:
    """Keyword arguments given by main() to build_graph."""
    received = []
    monkeypatch.setattr(
        service, "build_graph", lambda *args, **kwargs: received.append(kwargs) or "graph"
    )
    assert main(env) == 0
    return received[0]


def test_all_tools_reach_the_model(mcp, server, monkeypatch):  # RF-41: not the resource
    received = []
    monkeypatch.setattr(service, "create_model", lambda config, tools: received.append(tools))
    assert main(VALID) == 0
    assert [t.name for t in received[0]] == ["get_current_time", *ALLOWED_MCP_TOOLS]


def test_router_model_and_scope_reach_the_graph(mcp, server, monkeypatch):
    router = object()
    monkeypatch.setattr(service, "create_router_model", lambda config: router)
    options = graph_options(monkeypatch)
    assert options["router_model"] is router
    assert options["scope"] == load_config(VALID).scope


@pytest.mark.parametrize(("env", "expected"), [({}, 2), ({"MAX_REVIEWS": "3"}, 3)])
def test_reviewer_model_and_max_reviews_reach_the_graph(mcp, server, monkeypatch, env, expected):
    reviewer = object()
    monkeypatch.setattr(service, "create_reviewer_model", lambda config: reviewer)
    options = graph_options(monkeypatch, {**VALID, **env})
    assert options["reviewer_model"] is reviewer
    assert options["max_reviews"] == expected


@pytest.mark.parametrize(("env", "maximum", "keep"), [
    ({}, 20, 6),
    ({"SUMMARY_MAX_MESSAGES": "8", "SUMMARY_KEEP_MESSAGES": "3"}, 8, 3),
])
def test_summary_model_and_thresholds_reach_the_graph(mcp, server, monkeypatch, env, maximum, keep):
    summarizer = object()
    monkeypatch.setattr(service, "create_summary_model", lambda config: summarizer)
    options = graph_options(monkeypatch, {**VALID, **env})
    assert options["summary_model"] is summarizer
    assert options["summary_max_messages"] == maximum
    assert options["summary_keep_messages"] == keep


def test_preferences_text_reaches_the_graph(mcp, server, monkeypatch):
    assert graph_options(monkeypatch)["preferences"] == preferences_prompt(
        parse_preferences(json.dumps(NEW_YORK))[0]
    )


def test_unavailable_resource_starts_with_the_defaults(server, monkeypatch, tmp_path, caplog):
    caplog.set_level(logging.INFO)  # RF-42
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(service, "McpClient", lambda *a, **k: FakeMcpClient(MCP_SPECS))
    monkeypatch.setattr(service, "build_graph", lambda *args, **kwargs: "graph")
    assert main(VALID) == 0
    assert len(server.runs) == 1  # the service starts anyway
    warnings = [
        r.getMessage() for r in caplog.records
        if r.levelno == logging.WARNING and r.name == "assistant.preferences"
    ]
    assert len(warnings) == 1 and "status=unavailable" in warnings[0]


def test_unavailable_resource_gives_the_default_preferences(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(service, "McpClient", lambda *a, **k: FakeMcpClient(MCP_SPECS))
    monkeypatch.setattr(service.uvicorn, "run", FakeUvicorn())
    assert graph_options(monkeypatch)["preferences"] == preferences_prompt(DEFAULT_PREFERENCES)


def test_configuration_is_logged(mcp, server, caplog):
    caplog.set_level(logging.INFO)
    main(VALID)
    assert (
        f"scope_file={DEFAULT_SCOPE_FILE} max_reviews=2 "
        "summary_max_messages=20 summary_keep_messages=6 "
        f"preferences_file={Path(DEFAULT_PREFERENCES_FILE).resolve()}"
    ) in caplog.text


def node_names(lines: list[str]) -> list[str]:
    """The node of each line of the graph ("step=1/5 node=llm" has it in second position)."""
    return [line.split()[0] if line.startswith("node=") else line.split()[1] for line in lines]


def served_chat(monkeypatch, agent: FakeModel, body: dict) -> dict:
    """POST /chat to the app served by main(), with fake models that route and approve."""
    monkeypatch.setattr(service, "create_model", lambda config, tools: agent)
    monkeypatch.setattr(service, "create_router_model", lambda config: ConversationRouter())
    monkeypatch.setattr(service, "create_reviewer_model", lambda config: ApprovingReviewer())
    monkeypatch.setattr(service, "create_summary_model", lambda config: FakeModel([]))
    answers = []
    monkeypatch.setattr(service.uvicorn, "run", FakeUvicorn(
        lambda app: answers.append(TestClient(app).post("/chat", json=body))
    ))
    assert main(VALID) == 0
    assert answers[0].status_code == 200, answers[0].json()
    return answers[0].json()


def test_turn_goes_through_summary_router_agent_and_reviewer(mcp, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    body = served_chat(monkeypatch, FakeModel([AIMessage("Ciao!")]), {"message": "Ciao"})
    assert body["reply"] == "Ciao!"
    lines = [r.getMessage() for r in caplog.records if r.name == "assistant.graph"]
    assert lines[0] == "node=summary messages=1/20 skipped=below_threshold next_node=router"
    assert node_names(lines) == ["node=summary", "node=router", "node=llm", "node=reviewer"]


def test_prompt_goes_through_the_graph(monkeypatch, tmp_path, caplog):  # CA-57, RF-49
    caplog.set_level(logging.INFO)
    monkeypatch.chdir(tmp_path)
    text = "Spiegami Model Context Protocol a livello base: con parole semplici."
    spec = PromptSpec("spiega", "Spiega un argomento al livello scelto.", (
        PromptArgument("argomento", "", True), PromptArgument("livello", "", False),
    ))
    client = FakeMcpClient(
        MCP_SPECS, prompts={"spiega": (spec, lambda a: [PromptMessage("user", text)])}
    )
    monkeypatch.setattr(service, "McpClient", lambda *a, **k: client)
    agent = FakeModel([AIMessage("MCP è un protocollo aperto.")])
    body = served_chat(monkeypatch, agent, {"prompt": {
        "name": "spiega", "arguments": {"argomento": "Model Context Protocol", "livello": "base"},
    }})
    assert body["reply"] == "MCP è un protocollo aperto."
    assert [m["content"] for m in body["history"]] == [text, "MCP è un protocollo aperto."]
    assert agent.calls[0][-1].content == text
    lines = [
        r.getMessage() for r in caplog.records
        if r.name in ("assistant.commands", "assistant.graph")
    ]
    start = lines.index("prompts/list count=1 names=spiega")
    assert lines[start + 1] == (
        'prompts/get name=spiega arguments={"argomento": "Model Context Protocol", '
        '"livello": "base"} status=ok messages=1'
    )
    assert lines[start + 2].startswith("prompts/get name=spiega message=1/1 role=user text=")
    assert node_names(lines[start + 3:]) == [
        "node=summary", "node=router", "node=llm", "node=reviewer"
    ]
