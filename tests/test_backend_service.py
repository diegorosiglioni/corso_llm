import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect

import backend.__main__ as service
from backend.__main__ import main
from backend.db import create_db_engine

URL = "postgresql://lab:segreta@db.example:5432/assistente"
VALID = {"DATABASE_URL": URL}


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
def engines(monkeypatch) -> list:
    """The database is SQLite in memory: records the URL received by create_db_engine."""
    created = []

    def create(url):
        engine = create_db_engine("sqlite://")
        created.append((url, engine))
        return engine

    monkeypatch.setattr(service, "create_db_engine", create)
    return created


@pytest.fixture
def server(monkeypatch) -> FakeUvicorn:
    fake = FakeUvicorn()
    monkeypatch.setattr(service.uvicorn, "run", fake)
    return fake


def test_startup_with_the_default_address(engines, server, caplog):  # CA-75
    caplog.set_level(logging.INFO)
    assert main(VALID) == 0
    [(app, kwargs)] = server.runs
    assert isinstance(app, FastAPI)
    assert kwargs == {"host": "127.0.0.1", "port": 8001, "access_log": False, "log_config": None}
    [(url, _)] = engines
    assert url == "postgresql+psycopg://lab:segreta@db.example:5432/assistente"
    assert (
        "backend listening=http://127.0.0.1:8001 docs=/docs agent_url=http://127.0.0.1:8000 "
        "database=postgresql+psycopg://lab:***@db.example:5432/assistente "
        "cors_origins=http://127.0.0.1:8080,http://localhost:8080"
    ) in [r.getMessage() for r in caplog.records if r.name == "backend.service"]


def test_password_never_in_the_log(engines, server, caplog):  # CA-75
    caplog.set_level(logging.DEBUG)
    assert main({**VALID, "LOG_LEVEL": "DEBUG"}) == 0
    assert "segreta" not in caplog.text


def test_address_and_agent_from_the_environment(engines, server, caplog):  # CA-75
    caplog.set_level(logging.INFO)
    env = {**VALID, "BACKEND_HOST": "0.0.0.0", "BACKEND_PORT": "9001",
           "AGENT_URL": "http://agent:8000"}
    assert main(env) == 0
    [(_, kwargs)] = server.runs
    assert (kwargs["host"], kwargs["port"]) == ("0.0.0.0", 9001)
    assert "agent_url=http://agent:8000 " in caplog.text


def test_tables_are_created_before_serving(engines, monkeypatch):  # RF-61
    tables = []

    def during(app):  # the in-memory database disappears with engine.dispose() after the run
        [(_, engine)] = engines
        tables.extend(inspect(engine).get_table_names())

    monkeypatch.setattr(service.uvicorn, "run", FakeUvicorn(during))
    assert main(VALID) == 0
    assert set(tables) == {"chats", "chat_messages"}


@pytest.mark.parametrize(("env", "message"), [
    ({}, "Manca DATABASE_URL."),
    ({"DATABASE_URL": "sqlite:///chat.sqlite3"}, "ricevuto lo schema 'sqlite'"),
    ({**VALID, "BACKEND_PORT": "0"}, "BACKEND_PORT deve essere un intero tra 1 e 65535"),
    ({**VALID, "AGENT_URL": "http://[::1"}, "AGENT_URL non è un indirizzo valido"),
])
def test_invalid_config_exits_1(env, message, engines, server, capsys):  # CA-75
    assert main(env) == 1
    err = capsys.readouterr().err
    assert err.startswith("Configurazione non valida: ") and message in err
    assert engines == [] and server.runs == []


def test_unreachable_database_exits_1(server, capsys, monkeypatch):  # CA-75
    """Real psycopg on a closed port, with the shortest timeout: depending on the system the
    connection is refused at once or times out."""
    monkeypatch.setattr(
        service, "create_db_engine", lambda url: create_db_engine(url, connect_timeout=1)
    )
    assert main({"DATABASE_URL": "postgresql://lab:segreta@127.0.0.1:1/assistente"}) == 1
    err = capsys.readouterr().err
    assert err.startswith("Database non raggiungibile: ") and len(err.strip()) > 28
    assert "segreta" not in err
    assert server.runs == []


def test_postgresql_engine_has_a_connect_timeout(monkeypatch):
    received = {}
    monkeypatch.setattr(
        "backend.db.create_engine", lambda url, **options: received.update(options) or "engine"
    )
    assert create_db_engine("postgresql+psycopg://lab:segreta@db/assistente") == "engine"
    assert received == {
        "pool_pre_ping": True, "hide_parameters": True, "connect_args": {"connect_timeout": 10}
    }


def test_agent_is_not_contacted_at_startup(engines, server, monkeypatch):
    def must_not_call(*args, **kwargs):
        raise AssertionError("non deve essere chiamato")

    monkeypatch.setattr(service.AgentClient, "chat", must_not_call)
    monkeypatch.setattr(service.AgentClient, "status", must_not_call, raising=False)
    assert main({**VALID, "AGENT_URL": "http://127.0.0.1:1"}) == 0  # agent switched off


def test_served_app_uses_the_database(engines, monkeypatch):
    answers = {}

    def during(app):
        http = TestClient(app)
        answers["created"] = http.post("/chats", json={"title": "Prova"})
        answers["listed"] = http.get("/chats")

    monkeypatch.setattr(service.uvicorn, "run", FakeUvicorn(during))
    assert main(VALID) == 0
    assert answers["created"].status_code == 201
    assert [chat["title"] for chat in answers["listed"].json()] == ["Prova"]


def test_library_http_logs_hidden_at_info(engines, server):
    main(VALID)
    assert logging.getLogger("httpx").getEffectiveLevel() == logging.WARNING


def test_served_app_allows_the_configured_origins(engines, monkeypatch):  # CA-81
    answers = {}

    def during(app):
        http = TestClient(app)
        for origin in ("http://pagina:9000", "http://127.0.0.1:8080"):
            answers[origin] = http.get("/chats", headers={"Origin": origin})

    monkeypatch.setattr(service.uvicorn, "run", FakeUvicorn(during))
    assert main({**VALID, "CORS_ORIGINS": "http://pagina:9000"}) == 0
    allowed = answers["http://pagina:9000"].headers.get("access-control-allow-origin")
    assert allowed == "http://pagina:9000"
    assert "access-control-allow-origin" not in answers["http://127.0.0.1:8080"].headers
