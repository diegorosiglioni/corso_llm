import logging
import re
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from backend.api import create_app
from backend.db import ChatMessage, create_db_engine, init_db
from backend.store import AgentState, ChatStore
from conftest import Clock

START = datetime(2026, 11, 14, 10, 0, 0, tzinfo=UTC)
TOOL = {"name": "calculate", "args": {"expression": "17 * 23"}, "result": {"result": 391}, "ok": True}


class NoAgent:
    """The chat operations never call the agent."""

    def chat(self, *args, **kwargs):
        raise AssertionError("l'agente non deve essere chiamato")


@pytest.fixture
def engine():
    engine = create_db_engine("sqlite://")
    init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def clock():
    return Clock(START)


@pytest.fixture
def store(engine, clock):
    return ChatStore(engine, now=clock)


@pytest.fixture
def http(store):
    return TestClient(create_app(store=store, agent=NoAgent()))


def backend_lines(caplog) -> list[tuple[int, str]]:
    """(level, message) of the back-end lines, with the duration replaced by N."""
    return [
        (r.levelno, re.sub(r"duration_ms=\d+", "duration_ms=N", r.getMessage()))
        for r in caplog.records if r.name == "backend.api"
    ]


def answered_turn(store, clock, chat_id: int, question: str, reply: str, tools=()) -> None:
    """A question and its answer saved directly in the archive."""
    store.add_question(chat_id, question)
    clock.advance(5)
    store.add_answer(chat_id, reply, list(tools), AgentState([], ""))


# --- creation ---

def test_create_without_body(http):  # CA-72
    response = http.post("/chats")
    assert response.status_code == 201
    assert response.json() == {
        "id": 1, "title": "Nuova chat", "created_at": "2026-11-14T10:00:00Z",
        "last_message_at": None,
    }


@pytest.mark.parametrize(("body", "title"), [
    ({}, "Nuova chat"),
    ({"title": None}, "Nuova chat"),
    ({"title": "   "}, "Nuova chat"),
    ({"title": "  Conversioni di unità  "}, "Conversioni di unità"),
    ({"title": "x" * 200}, "x" * 200),
])
def test_create_with_optional_title(http, body, title):  # CA-72
    response = http.post("/chats", json=body)
    assert response.status_code == 201
    assert response.json()["title"] == title


def test_identifiers_grow(http):
    assert [http.post("/chats").json()["id"] for _ in range(3)] == [1, 2, 3]


def test_title_too_long_is_400(http, store):  # CA-74
    response = http.post("/chats", json={"title": "x" * 201})
    assert response.status_code == 400
    assert response.json() == {
        "error": "invalid_request", "detail": "il titolo supera 200 caratteri",
    }
    assert store.list_chats() == []


@pytest.mark.parametrize("body", [
    {"title": 3}, {"title": "a", "colore": "blu"}, ["titolo"],
])
def test_body_outside_the_schema_is_422(http, store, body):  # CA-74
    assert http.post("/chats", json=body).status_code == 422
    assert store.list_chats() == []


# --- list ---

def test_empty_list(http):  # CA-72
    response = http.get("/chats")
    assert (response.status_code, response.json()) == (200, [])


def test_list_with_title_last_message_and_order(http, store, clock):  # CA-72
    first = http.post("/chats").json()["id"]
    clock.advance(10)
    second = http.post("/chats", json={"title": "Note"}).json()["id"]
    clock.advance(10)
    answered_turn(store, clock, first, "Quanto fa 17 * 23?", "17 * 23 fa 391.", [TOOL])

    response = http.get("/chats")
    assert response.status_code == 200
    assert response.json() == [
        {"id": first, "title": "Quanto fa 17 * 23?", "created_at": "2026-11-14T10:00:00Z",
         "last_message_at": "2026-11-14T10:00:25Z"},
        {"id": second, "title": "Note", "created_at": "2026-11-14T10:00:10Z",
         "last_message_at": None},
    ]


# --- read ---

def test_read_a_chat_with_its_messages_in_order(http, store, clock):  # CA-72
    chat_id = http.post("/chats").json()["id"]
    answered_turn(store, clock, chat_id, "Quanto fa 17 * 23?", "17 * 23 fa 391.", [TOOL])
    clock.advance(5)
    answered_turn(store, clock, chat_id, "E 2 + 2?", "2 + 2 fa 4.")

    response = http.get(f"/chats/{chat_id}")
    assert response.status_code == 200
    body = response.json()
    assert {key: body[key] for key in ("id", "title", "created_at", "last_message_at")} == {
        "id": chat_id, "title": "Quanto fa 17 * 23?", "created_at": "2026-11-14T10:00:00Z",
        "last_message_at": "2026-11-14T10:00:15Z",
    }
    assert body["messages"] == [
        {"id": 1, "role": "user", "content": "Quanto fa 17 * 23?", "tools_used": [],
         "created_at": "2026-11-14T10:00:00Z"},
        {"id": 2, "role": "assistant", "content": "17 * 23 fa 391.", "tools_used": [TOOL],
         "created_at": "2026-11-14T10:00:05Z"},
        {"id": 3, "role": "user", "content": "E 2 + 2?", "tools_used": [],
         "created_at": "2026-11-14T10:00:10Z"},
        {"id": 4, "role": "assistant", "content": "2 + 2 fa 4.", "tools_used": [],
         "created_at": "2026-11-14T10:00:15Z"},
    ]


def test_read_an_empty_chat(http):
    chat_id = http.post("/chats", json={"title": "Vuota"}).json()["id"]
    assert http.get(f"/chats/{chat_id}").json() == {
        "id": chat_id, "title": "Vuota", "created_at": "2026-11-14T10:00:00Z",
        "last_message_at": None, "messages": [],
    }


def test_agent_state_is_not_exposed(http, store, clock):
    chat_id = http.post("/chats").json()["id"]
    store.add_question(chat_id, "Ciao")
    store.add_answer(chat_id, "Ciao!", [], AgentState([{"role": "user", "content": "x"}], "rias"))
    body = http.get(f"/chats/{chat_id}").json()
    assert "history" not in body and "summary" not in body


@pytest.mark.parametrize("method", ["get", "delete"])
def test_missing_chat_is_404(http, method):  # CA-74
    response = getattr(http, method)("/chats/42")
    assert response.status_code == 404
    assert response.json() == {"error": "chat_not_found", "detail": "chat 42 inesistente"}


@pytest.mark.parametrize("method", ["get", "delete"])
def test_identifier_not_an_integer_is_422(http, method):  # CA-74
    assert getattr(http, method)("/chats/abc").status_code == 422


# --- deletion ---

def test_delete_removes_the_chat_and_its_messages(http, store, clock, engine):  # CA-72
    chat_id = http.post("/chats").json()["id"]
    kept = http.post("/chats").json()["id"]
    answered_turn(store, clock, chat_id, "Ciao", "Ciao!")
    answered_turn(store, clock, kept, "Salve", "Salve!")

    response = http.delete(f"/chats/{chat_id}")
    assert (response.status_code, response.content) == (204, b"")
    assert http.get(f"/chats/{chat_id}").status_code == 404
    assert [chat["id"] for chat in http.get("/chats").json()] == [kept]
    with engine.connect() as connection:
        remaining = connection.execute(select(func.count()).select_from(ChatMessage)).scalar_one()
    assert remaining == 2  # only the messages of the other chat


# --- OpenAPI ---

def test_openapi_describes_the_operations_and_schemas(http):  # CA-72
    document = http.get("/openapi.json").json()
    assert document["info"]["title"] == "Assistente del laboratorio — back-end"
    paths = document["paths"]
    assert set(paths["/chats"]) == {"get", "post"}
    assert set(paths["/chats/{chat_id}"]) == {"get", "delete"}
    schemas = document["components"]["schemas"]
    assert {"CreateChatRequest", "ChatInfo", "ChatDetail", "ChatMessageInfo", "ErrorBody"} <= set(
        schemas
    )
    assert set(schemas["ChatDetail"]["properties"]) == {
        "id", "title", "created_at", "last_message_at", "messages",
    }
    assert set(schemas["ChatMessageInfo"]["properties"]) == {
        "id", "role", "content", "tools_used", "created_at",
    }
    assert schemas["CreateChatRequest"]["additionalProperties"] is False

    create = paths["/chats"]["post"]
    assert set(create["responses"]) == {"201", "400", "422", "500", "503"}
    assert set(paths["/chats/{chat_id}"]["get"]["responses"]) == {"200", "404", "422", "500", "503"}
    assert set(paths["/chats/{chat_id}"]["delete"]["responses"]) == {
        "204", "404", "422", "500", "503",
    }
    error_ref = {"$ref": "#/components/schemas/ErrorBody"}
    assert create["responses"]["503"]["content"]["application/json"]["schema"] == error_ref
    for operation in (create, paths["/chats"]["get"], *paths["/chats/{chat_id}"].values()):
        assert operation["summary"] and operation["description"]


def test_docs_page(http):
    assert http.get("/docs").status_code == 200


# --- database and unexpected errors ---

class BrokenStore:
    """Archive whose every operation raises `error`."""

    def __init__(self, error: Exception):
        self._error = error

    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise self._error
        return fail


def database_down() -> OperationalError:
    driver = Exception('connection to server at "db" (10.0.0.5), port 5432 failed: refused\n')
    return OperationalError("SELECT 1", {}, driver)


REQUESTS = [
    ("post", "/chats", "backend response=create_chat"),
    ("get", "/chats", "backend response=list_chats"),
    ("get", "/chats/3", "backend response=get_chat chat=3"),
    ("delete", "/chats/3", "backend response=delete_chat chat=3"),
]


@pytest.mark.parametrize(("method", "path", "prefix"), REQUESTS)
def test_database_unavailable_is_503(method, path, prefix, caplog):  # CA-74, CA-76
    caplog.set_level(logging.INFO)
    http = TestClient(create_app(store=BrokenStore(database_down()), agent=NoAgent()))
    response = getattr(http, method)(path)
    assert response.status_code == 503
    assert response.json() == {
        "error": "database_unavailable", "detail": "database non disponibile; dettagli nel log",
    }
    assert backend_lines(caplog) == [(logging.WARNING, (
        f'{prefix} status=503 error=database_unavailable '
        'detail="database non disponibile; dettagli nel log" duration_ms=N '
        'cause="connection to server at \\"db\\" (10.0.0.5), port 5432 failed: refused"'
    ))]


@pytest.mark.parametrize(("method", "path", "prefix"), REQUESTS)
def test_unexpected_error_is_500_with_the_traceback_in_the_log(method, path, prefix, caplog):
    caplog.set_level(logging.INFO)  # CA-74, CA-76
    http = TestClient(create_app(store=BrokenStore(RuntimeError("guasto")), agent=NoAgent()))
    response = getattr(http, method)(path)
    assert response.status_code == 500
    assert response.json() == {
        "error": "internal_error", "detail": "errore interno del back-end; dettagli nel log",
    }
    assert backend_lines(caplog) == [(logging.ERROR, (
        f'{prefix} status=500 error=internal_error '
        'detail="errore interno del back-end; dettagli nel log" duration_ms=N'
    ))]
    [record] = [r for r in caplog.records if r.name == "backend.api"]
    assert record.exc_info is not None and "guasto" in caplog.text
    assert "guasto" not in response.text


# --- log lines ---

def test_log_lines_of_the_chat_operations(http, store, clock, caplog):  # CA-76
    caplog.set_level(logging.INFO)
    chat_id = http.post("/chats").json()["id"]
    answered_turn(store, clock, chat_id, "Ciao", "Ciao!")
    http.get("/chats")
    http.get(f"/chats/{chat_id}")
    http.delete(f"/chats/{chat_id}")
    assert backend_lines(caplog) == [
        (logging.INFO, "backend response=create_chat status=201 chat=1 duration_ms=N"),
        (logging.INFO, "backend response=list_chats status=200 count=1 duration_ms=N"),
        (logging.INFO, "backend response=get_chat chat=1 status=200 messages=2 duration_ms=N"),
        (logging.INFO, "backend response=delete_chat chat=1 status=204 duration_ms=N"),
    ]


def test_log_lines_of_the_request_errors(http, caplog):  # CA-76: 4xx at INFO
    caplog.set_level(logging.INFO)
    http.post("/chats", json={"title": "x" * 201})
    http.get("/chats/42")
    http.delete("/chats/42")
    assert backend_lines(caplog) == [
        (logging.INFO, (
            "backend response=create_chat status=400 error=invalid_request "
            'detail="il titolo supera 200 caratteri" duration_ms=N'
        )),
        (logging.INFO, (
            "backend response=get_chat chat=42 status=404 error=chat_not_found "
            'detail="chat 42 inesistente" duration_ms=N'
        )),
        (logging.INFO, (
            "backend response=delete_chat chat=42 status=404 error=chat_not_found "
            'detail="chat 42 inesistente" duration_ms=N'
        )),
    ]


def test_titles_and_messages_do_not_enter_the_log(http, store, clock, caplog):
    caplog.set_level(logging.DEBUG)
    chat_id = http.post("/chats", json={"title": "Titolo riservato"}).json()["id"]
    answered_turn(store, clock, chat_id, "Domanda riservata", "Risposta riservata")
    http.get(f"/chats/{chat_id}")
    assert "riservat" not in " ".join(message for _, message in backend_lines(caplog))
