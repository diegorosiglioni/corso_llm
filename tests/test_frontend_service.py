import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import frontend.__main__ as service
from frontend.__main__ import main


class FakeUvicorn:
    """Stands in for uvicorn.run: records the arguments."""

    def __init__(self):
        self.runs: list[tuple[FastAPI, dict]] = []

    def __call__(self, app, **kwargs) -> None:
        self.runs.append((app, kwargs))


@pytest.fixture
def server(monkeypatch) -> FakeUvicorn:
    fake = FakeUvicorn()
    monkeypatch.setattr(service.uvicorn, "run", fake)
    return fake


def test_startup_with_the_default_address(server, caplog):  # CA-80
    caplog.set_level(logging.INFO)
    assert main({}) == 0
    [(app, kwargs)] = server.runs
    assert isinstance(app, FastAPI)
    assert kwargs == {"host": "127.0.0.1", "port": 8080, "access_log": False, "log_config": None}
    assert [r.getMessage() for r in caplog.records if r.name == "frontend.service"] == [
        "frontend listening=http://127.0.0.1:8080 backend_url=http://127.0.0.1:8001"
    ]


def test_address_and_backend_from_the_environment(server, caplog):  # CA-80
    caplog.set_level(logging.INFO)
    env = {"FRONTEND_HOST": "0.0.0.0", "FRONTEND_PORT": "9080",
           "BACKEND_URL": "http://localhost:9001/"}
    assert main(env) == 0
    [(app, kwargs)] = server.runs
    assert (kwargs["host"], kwargs["port"]) == ("0.0.0.0", 9080)
    assert "backend_url=http://localhost:9001" in caplog.text
    assert "http://localhost:9001" in TestClient(app).get("/config.js").text


@pytest.mark.parametrize(("env", "message"), [
    ({"BACKEND_URL": "backend:8001"}, "BACKEND_URL deve iniziare con http:// o https://"),
    ({"FRONTEND_PORT": "0"}, "FRONTEND_PORT deve essere un intero tra 1 e 65535"),
    ({"LOG_LEVEL": "tanto"}, "LOG_LEVEL deve essere uno tra"),
])
def test_invalid_config_exits_1(env, message, server, capsys):  # CA-80
    assert main(env) == 1
    err = capsys.readouterr().err
    assert err.startswith("Configurazione non valida: ") and message in err
    assert server.runs == []
