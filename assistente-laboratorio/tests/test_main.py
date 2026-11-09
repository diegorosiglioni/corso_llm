import logging

import assistant.__main__ as entry
from assistant.__main__ import main
from assistant.session import Session

VALID = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "google/gemma-4-e2b"}


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
    for library in ("httpx", "httpx2", "openai"):
        assert logging.getLogger(library).getEffectiveLevel() == logging.WARNING, library


def test_clock_tool_reaches_the_model(monkeypatch):
    received = []
    monkeypatch.setattr(entry, "create_model", lambda config, tools: received.append(tools))
    monkeypatch.setattr(entry, "run", lambda session: None)
    assert main(VALID) == 0
    assert [t.name for t in received[0]] == ["get_current_time"]
