import logging

import pytest

import assistant.__main__ as entry
from assistant.__main__ import main
from assistant.mcp_client import ALLOWED_MCP_TOOLS, ToolSpec
from assistant.session import Session
from conftest import MCP_SPECS, FakeMcpClient

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
    monkeypatch.setattr(entry, "run", received.append)
    assert main(VALID) == 0
    assert len(received) == 1 and isinstance(received[0], Session)
    assert (
        "Assistente del laboratorio — modello google/gemma-4-e2b su http://localhost:1234/v1. "
        "Scrivi 'esci' per uscire."
    ) in capsys.readouterr().out


def test_library_http_logs_hidden_at_info(monkeypatch, caplog):
    caplog.set_level(logging.INFO)  # as in the app, where the root is at INFO
    monkeypatch.setattr(entry, "run", lambda session: None)
    main(VALID)
    for library in ("httpx", "httpx2", "openai", "mcp", "fastmcp"):
        assert logging.getLogger(library).getEffectiveLevel() == logging.WARNING, library


def test_all_tools_reach_the_model(monkeypatch):
    received = []
    monkeypatch.setattr(entry, "create_model", lambda config, tools: received.append(tools))
    monkeypatch.setattr(entry, "run", lambda session: None)
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


def test_name_collision_exits_1(capsys, monkeypatch):
    clash = ToolSpec("get_current_time", "doppione", {"type": "object", "properties": {}})
    monkeypatch.setattr(entry, "ALLOWED_MCP_TOOLS", (*ALLOWED_MCP_TOOLS, "get_current_time"))
    monkeypatch.setattr(entry, "McpClient", lambda *a, **k: FakeMcpClient(MCP_SPECS + [clash]))
    monkeypatch.setattr(entry, "create_model", _must_not_call)
    monkeypatch.setattr(entry, "run", _must_not_call)
    assert main(VALID) == 1
    assert "Strumenti con lo stesso nome: 'get_current_time'." in capsys.readouterr().err


def test_notes_folder_is_created(tmp_path, monkeypatch):
    monkeypatch.setattr(entry, "run", lambda session: None)
    main({**VALID, "NOTES_DB": str(tmp_path / "sub" / "n.sqlite3")})
    assert (tmp_path / "sub").is_dir()
