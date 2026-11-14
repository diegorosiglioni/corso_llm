import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

import assistant.service as service
from assistant.config import load_config
from assistant.mcp_client import ALLOWED_MCP_TOOLS, ToolSpec
from assistant.preferences import PREFERENCES_URI, parse_preferences, preferences_prompt
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
    def list_tools(self):
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
