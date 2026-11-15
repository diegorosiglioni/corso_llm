import json
import logging
import re
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from assistant.api_client import AgentClient
from backend.api import OpenStream, _forward, create_app
from backend.db import Chat, ChatMessage, create_db_engine, init_db
from backend.store import AgentState, ChatStore
from conftest import (
    Clock,
    FakeModel,
    StreamingFakeModel,
    fake_service,
    lm_studio_error,
    sse,
    tool_call,
)

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


# --- sending a message ---

AGENT_URL = "http://agente.test:8000"
SAVED_HISTORY = [
    {"role": "user", "content": "Mi chiamo Paolo"}, {"role": "assistant", "content": "Piacere!"},
]


class RecordingAgent:
    """Passes each turn to `agent` and records (history, summary, message)."""

    def __init__(self, agent):
        self._agent = agent
        self.calls: list[tuple[list, str, str]] = []

    def chat(self, history, summary, *, message):
        self.calls.append((list(history), summary, message))
        return self._agent.chat(history, summary, message=message)


class ScriptedAgent:
    """Answers each turn with the next body (a function of nothing is called first)."""

    def __init__(self, *bodies):
        self._bodies = list(bodies)

    def chat(self, history, summary, *, message):
        body = self._bodies.pop(0)
        return body() if callable(body) else body


def service_agent(model) -> AgentClient:
    """Client of the agent of step 6 on a fake graph (no network)."""
    return AgentClient(AGENT_URL, http=fake_service(model))


def mock_agent(handler) -> AgentClient:
    return AgentClient(
        AGENT_URL, http=httpx.Client(transport=httpx.MockTransport(handler), base_url=AGENT_URL)
    )


def raising(exception):
    def handler(request):
        raise exception
    return handler


def app(store, agent) -> TestClient:
    return TestClient(create_app(store=store, agent=agent))


def agent_state(engine, chat_id: int) -> tuple[list, str]:
    with engine.connect() as connection:
        row = connection.execute(
            select(Chat.history, Chat.summary).where(Chat.id == chat_id)
        ).one()
    return list(row.history), row.summary


def contents(store, chat_id: int) -> list[tuple[str, str]]:
    return [(m.role, m.content) for m in store.get_chat(chat_id)[1]]


def test_send_saves_and_returns_question_and_answer(store, clock, engine):  # CA-73
    http = app(store, service_agent(FakeModel([tool_call(), AIMessage("A Tokyo sono le 00:47.")])))
    chat_id = http.post("/chats").json()["id"]

    response = http.post(f"/chats/{chat_id}/messages", json={"content": "Che ore sono a Tokyo?"})
    assert response.status_code == 201
    body = response.json()
    assert body["question"] == {
        "id": 1, "role": "user", "content": "Che ore sono a Tokyo?", "tools_used": [],
        "created_at": "2026-11-14T10:00:00Z",
    }
    answer = body["answer"]
    assert (answer["id"], answer["role"], answer["content"]) == (
        2, "assistant", "A Tokyo sono le 00:47."
    )
    assert [(t["name"], t["args"], t["ok"]) for t in answer["tools_used"]] == [
        ("get_current_time", {"timezone": "Asia/Tokyo"}, True)
    ]

    saved = http.get(f"/chats/{chat_id}").json()
    assert saved["title"] == "Che ore sono a Tokyo?"
    assert saved["messages"] == [body["question"], answer]
    history, summary = agent_state(engine, chat_id)
    assert [m["role"] for m in history] == ["user", "assistant", "tool", "assistant"]
    assert summary == ""


def test_second_message_uses_the_saved_history(store, engine):  # CA-73
    model = FakeModel([AIMessage("Piacere, Paolo!"), AIMessage("Ti chiami Paolo.")])
    agent = RecordingAgent(service_agent(model))
    http = app(store, agent)
    chat_id = http.post("/chats").json()["id"]
    http.post(f"/chats/{chat_id}/messages", json={"content": "Mi chiamo Paolo"})
    after_first = agent_state(engine, chat_id)

    response = http.post(f"/chats/{chat_id}/messages", json={"content": "Come mi chiamo?"})
    assert response.status_code == 201
    assert agent.calls[0] == ([], "", "Mi chiamo Paolo")
    assert agent.calls[1] == (after_first[0], "", "Come mi chiamo?")
    assert after_first[0] == [
        {"role": "user", "content": "Mi chiamo Paolo"},
        {"role": "assistant", "content": "Piacere, Paolo!"},
    ]
    assert "Mi chiamo Paolo" in [m.content for m in model.calls[-1]]
    assert len(agent_state(engine, chat_id)[0]) == 4


def test_summary_of_the_agent_is_saved_and_sent_back(store, engine):  # CA-73
    first = {"reply": "Uno", "tools_used": [], "history": SAVED_HISTORY, "summary": "riassunto 1"}
    second = {"reply": "Due", "tools_used": [], "history": [], "summary": "riassunto 2"}
    agent = RecordingAgent(ScriptedAgent(first, second))
    http = app(store, agent)
    chat_id = http.post("/chats").json()["id"]
    http.post(f"/chats/{chat_id}/messages", json={"content": "a"})
    assert agent_state(engine, chat_id) == (SAVED_HISTORY, "riassunto 1")
    http.post(f"/chats/{chat_id}/messages", json={"content": "b"})
    assert agent.calls == [([], "", "a"), (SAVED_HISTORY, "riassunto 1", "b")]
    assert agent_state(engine, chat_id) == ([], "riassunto 2")


def test_message_is_stripped_before_saving_and_sending(store):
    agent = RecordingAgent(ScriptedAgent(
        {"reply": "Ok", "tools_used": [], "history": [], "summary": ""}
    ))
    http = app(store, agent)
    chat_id = http.post("/chats").json()["id"]
    body = http.post(f"/chats/{chat_id}/messages", json={"content": "  Ciao \n"}).json()
    assert body["question"]["content"] == "Ciao"
    assert agent.calls == [([], "", "Ciao")]


def test_a_given_title_is_kept(store):
    http = app(store, ScriptedAgent({"reply": "Ok", "tools_used": [], "history": [], "summary": ""}))
    chat_id = http.post("/chats", json={"title": "Note"}).json()["id"]
    http.post(f"/chats/{chat_id}/messages", json={"content": "Ciao"})
    assert http.get(f"/chats/{chat_id}").json()["title"] == "Note"


@pytest.mark.parametrize("body", [
    {}, {"content": 3}, {"content": None}, {"content": "a", "role": "user"}, ["a"],
])
def test_send_body_outside_the_schema_is_422(http, store, body):  # CA-74
    chat_id = http.post("/chats").json()["id"]
    assert http.post(f"/chats/{chat_id}/messages", json=body).status_code == 422
    assert contents(store, chat_id) == []


def test_send_to_an_identifier_not_an_integer_is_422(http):  # CA-74
    assert http.post("/chats/abc/messages", json={"content": "a"}).status_code == 422


@pytest.mark.parametrize("content", ["", "   ", "\n\t"])
def test_empty_message_is_400_without_calling_the_agent(http, store, content):  # CA-74
    chat_id = http.post("/chats").json()["id"]
    response = http.post(f"/chats/{chat_id}/messages", json={"content": content})
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_request", "detail": "il messaggio è vuoto"}
    assert contents(store, chat_id) == []


def test_send_to_a_missing_chat_is_404_without_calling_the_agent(http):  # CA-74
    response = http.post("/chats/42/messages", json={"content": "Ciao"})
    assert response.status_code == 404
    assert response.json() == {"error": "chat_not_found", "detail": "chat 42 inesistente"}


AGENT_FAILURES = [
    pytest.param(
        lambda: AgentClient("http://127.0.0.1:1"), 503, "agent_unavailable",
        "agente non raggiungibile su http://127.0.0.1:1", id="closed-port",
    ),
    pytest.param(
        lambda: mock_agent(raising(httpx.ReadTimeout("lento"))), 504, "agent_timeout",
        "l'agente non ha risposto entro 600 s", id="timeout",
    ),
    pytest.param(
        lambda: service_agent(FakeModel([lm_studio_error()])), 502, "agent_error",
        "l'agente ha risposto con un errore (model_unavailable): LM Studio non raggiungibile: "
        "Connection error.", id="lm-studio-off",
    ),
    pytest.param(
        lambda: mock_agent(lambda request: httpx.Response(200, text="non json")), 502,
        "agent_error",
        "l'agente ha risposto con un errore (bad_response): risposta inattesa dell'agente "
        "(HTTP 200)", id="bad-response",
    ),
]


@pytest.mark.parametrize(("make_agent", "status", "code", "detail"), AGENT_FAILURES)
def test_agent_failure_keeps_the_question_and_the_agent_state(
    store, engine, caplog, make_agent, status, code, detail,
):  # CA-74, CA-76
    caplog.set_level(logging.INFO)
    chat_id = store.create_chat().id
    store.add_question(chat_id, "Mi chiamo Paolo")
    store.add_answer(chat_id, "Piacere!", [], AgentState(SAVED_HISTORY, "rias"))

    response = app(store, make_agent()).post(
        f"/chats/{chat_id}/messages", json={"content": "Quanto fa 2 + 2?"}
    )
    assert response.status_code == status
    assert response.json() == {"error": code, "detail": detail}
    assert contents(store, chat_id) == [
        ("user", "Mi chiamo Paolo"), ("assistant", "Piacere!"), ("user", "Quanto fa 2 + 2?"),
    ]
    assert agent_state(engine, chat_id) == (SAVED_HISTORY, "rias")
    escaped = detail.replace('"', '\\"')
    assert backend_lines(caplog)[-1] == (logging.WARNING, (
        f'backend response=send_message chat={chat_id} status={status} error={code} '
        f'detail="{escaped}" duration_ms=N'
    ))


def test_history_rejected_by_the_agent_is_502(store, engine):  # CA-74
    chat_id = store.create_chat().id
    store.add_question(chat_id, "Ciao")
    broken = [{"role": "tool", "content": "x", "tool_call_id": "c1"}]
    store.add_answer(chat_id, "Ciao!", [], AgentState(broken, ""))
    response = app(store, service_agent(FakeModel([]))).post(
        f"/chats/{chat_id}/messages", json={"content": "Di nuovo"}
    )
    assert response.status_code == 502
    assert response.json()["error"] == "agent_error"
    assert response.json()["detail"].startswith(
        "l'agente ha risposto con un errore (invalid_history): messaggio 1:"
    )
    assert agent_state(engine, chat_id) == (broken, "")


def test_chat_deleted_during_the_turn_is_404(store):
    def delete_then_answer():
        store.delete_chat(chat_id)
        return {"reply": "Ok", "tools_used": [], "history": [], "summary": ""}

    chat_id = store.create_chat().id
    response = app(store, ScriptedAgent(delete_then_answer)).post(
        f"/chats/{chat_id}/messages", json={"content": "Ciao"}
    )
    assert response.status_code == 404
    assert response.json() == {"error": "chat_not_found", "detail": f"chat {chat_id} inesistente"}
    assert store.list_chats() == []


def test_send_log_lines(store, caplog):  # CA-76
    caplog.set_level(logging.INFO)
    http = app(store, service_agent(FakeModel([
        tool_call(), AIMessage("A Tokyo sono le 00:47."), AIMessage("Prego!"),
    ])))
    chat_id = http.post("/chats").json()["id"]
    http.post(f"/chats/{chat_id}/messages", json={"content": "Che ore sono a Tokyo?"})
    http.post(f"/chats/{chat_id}/messages", json={"content": " Grazie "})
    http.post(f"/chats/{chat_id}/messages", json={"content": "  "})
    http.post("/chats/42/messages", json={"content": "Ciao"})
    assert backend_lines(caplog)[1:] == [
        (logging.INFO, f"backend request=send_message chat={chat_id} chars=21"),
        (logging.INFO, f"backend agent_call chat={chat_id} history=0 summary_chars=0"),
        (logging.INFO, (
            f"backend response=send_message chat={chat_id} status=201 tools=get_current_time "
            "reply_chars=22 duration_ms=N"
        )),
        (logging.INFO, f"backend request=send_message chat={chat_id} chars=8"),
        (logging.INFO, f"backend agent_call chat={chat_id} history=4 summary_chars=0"),
        (logging.INFO, (
            f"backend response=send_message chat={chat_id} status=201 tools= reply_chars=6 "
            "duration_ms=N"
        )),
        (logging.INFO, f"backend request=send_message chat={chat_id} chars=2"),
        (logging.INFO, (
            f"backend response=send_message chat={chat_id} status=400 error=invalid_request "
            'detail="il messaggio è vuoto" duration_ms=N'
        )),
        (logging.INFO, "backend request=send_message chat=42 chars=4"),
        (logging.INFO, (
            "backend response=send_message chat=42 status=404 error=chat_not_found "
            'detail="chat 42 inesistente" duration_ms=N'
        )),
    ]


def test_messages_do_not_enter_the_send_log(store, caplog):
    caplog.set_level(logging.DEBUG)
    http = app(store, ScriptedAgent(
        {"reply": "Risposta riservata", "tools_used": [], "history": [], "summary": "riservato"}
    ))
    chat_id = http.post("/chats").json()["id"]
    http.post(f"/chats/{chat_id}/messages", json={"content": "Domanda riservata"})
    assert "riservat" not in " ".join(message for _, message in backend_lines(caplog))


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
    send = paths["/chats/{chat_id}/messages"]["post"]
    assert set(paths["/chats/{chat_id}/messages"]) == {"post"}
    assert set(send["responses"]) == {"201", "400", "404", "422", "500", "502", "503", "504"}
    assert {"SendMessageRequest", "SendMessageResponse"} <= set(schemas)
    assert set(schemas["SendMessageRequest"]["properties"]) == {"content"}
    assert schemas["SendMessageRequest"]["additionalProperties"] is False
    assert set(schemas["SendMessageResponse"]["properties"]) == {"question", "answer"}
    error_ref = {"$ref": "#/components/schemas/ErrorBody"}
    assert create["responses"]["503"]["content"]["application/json"]["schema"] == error_ref
    for code in ("502", "503", "504"):
        assert send["responses"][code]["content"]["application/json"]["schema"] == error_ref
    for operation in (
        create, paths["/chats"]["get"], *paths["/chats/{chat_id}"].values(), send,
    ):
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


@pytest.mark.parametrize(("error", "status", "code", "detail", "level"), [
    (database_down(), 503, "database_unavailable", "database non disponibile; dettagli nel log",
     logging.WARNING),
    (RuntimeError("guasto"), 500, "internal_error",
     "errore interno del back-end; dettagli nel log", logging.ERROR),
])
def test_send_with_a_broken_archive(error, status, code, detail, level, caplog):  # CA-74, CA-76
    caplog.set_level(logging.INFO)
    http = TestClient(create_app(store=BrokenStore(error), agent=NoAgent()))
    response = http.post("/chats/3/messages", json={"content": "Ciao"})
    assert response.status_code == status
    assert response.json() == {"error": code, "detail": detail}
    lines = backend_lines(caplog)
    assert lines[0] == (logging.INFO, "backend request=send_message chat=3 chars=4")
    assert lines[1][0] == level
    assert lines[1][1].startswith(
        f'backend response=send_message chat=3 status={status} error={code} detail="{detail}"'
    )
    assert len(lines) == 2


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


# --- CORS (step 8) ---

PAGE = "http://127.0.0.1:8080"


@pytest.fixture
def cors_http(store):
    return TestClient(create_app(store=store, agent=NoAgent(), cors_origins=(PAGE,)))


@pytest.mark.parametrize(("method", "path"), [
    ("GET", "/chats"), ("POST", "/chats"), ("DELETE", "/chats/1"), ("POST", "/chats/1/messages"),
])
def test_preflight_from_an_allowed_origin(cors_http, method, path):  # CA-81
    response = cors_http.options(path, headers={
        "Origin": PAGE, "Access-Control-Request-Method": method,
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == PAGE
    assert method in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()
    assert "access-control-allow-credentials" not in response.headers


def test_answers_to_an_allowed_origin_carry_the_header(cors_http):  # CA-81
    created = cors_http.post("/chats", json={}, headers={"Origin": PAGE})
    assert created.status_code == 201
    assert created.headers["access-control-allow-origin"] == PAGE
    deleted = cors_http.delete(f"/chats/{created.json()['id']}", headers={"Origin": PAGE})
    assert deleted.status_code == 204
    assert deleted.headers["access-control-allow-origin"] == PAGE


@pytest.mark.parametrize(("method", "path", "status"), [
    ("GET", "/chats/99", 404), ("DELETE", "/chats/99", 404), ("GET", "/chats/abc", 422),
])
def test_error_answers_carry_the_header(cors_http, method, path, status):  # CA-81
    response = cors_http.request(method, path, headers={"Origin": PAGE})
    assert response.status_code == status
    assert response.headers["access-control-allow-origin"] == PAGE


def test_database_error_carries_the_header(store, monkeypatch):  # CA-81
    def broken():
        raise OperationalError("SELECT", {}, Exception("connessione rifiutata"))

    monkeypatch.setattr(store, "list_chats", broken)
    http = TestClient(create_app(store=store, agent=NoAgent(), cors_origins=(PAGE,)))
    response = http.get("/chats", headers={"Origin": PAGE})
    assert response.status_code == 503
    assert response.headers["access-control-allow-origin"] == PAGE


def test_no_header_for_another_origin(cors_http):  # CA-81
    response = cors_http.get("/chats", headers={"Origin": "http://altro:8080"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    preflight = cors_http.options("/chats", headers={
        "Origin": "http://altro:8080", "Access-Control-Request-Method": "POST",
    })
    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers


def test_no_cors_without_origins(http):  # CA-81
    response = http.get("/chats", headers={"Origin": PAGE})
    assert "access-control-allow-origin" not in response.headers


def test_cors_does_not_change_the_openapi(store, http, cors_http):
    assert cors_http.get("/openapi.json").json() == http.get("/openapi.json").json()


# --- POST /chats/{chat_id}/messages/stream (specification of the streaming, §6; CA-98) ---

STREAM_REPLIES = [
    AIMessage("Controllo.", tool_calls=[
        {"name": "get_current_time", "args": {"timezone": "Asia/Tokyo"}, "id": "c1"}
    ]),
    AIMessage("A Tokyo sono le 00:47."),
]


def send_stream(http: TestClient, chat_id: int, content: str) -> list[tuple[str, object]]:
    with http.stream(
        "POST", f"/chats/{chat_id}/messages/stream", json={"content": content}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        return sse(response.read().decode())


class ScriptedStreamAgent:
    """Answers each streamed turn with the next list of events (name, data); an exception in
    the list is raised when it is reached, a function of nothing is called first. Records
    (history, summary, message) and whether each stream was closed."""

    def __init__(self, *turns):
        self._turns = list(turns)
        self.calls: list[tuple[list, str, str]] = []
        self.closed: list[bool] = []

    def chat(self, *args, **kwargs):
        raise AssertionError("il flusso non deve usare /chat")

    def chat_stream(self, history, summary, *, message):
        self.calls.append((list(history), summary, message))
        events = self._turns.pop(0)
        index = len(self.closed)
        self.closed.append(False)

        def generate():
            try:
                for item in events:
                    if isinstance(item, BaseException):
                        raise item
                    yield item() if callable(item) else item
            finally:
                self.closed[index] = True

        return generate()


def done(reply="Ok", history=(), summary="") -> tuple[str, dict]:
    return "done", {"reply": reply, "tools_used": [], "history": list(history), "summary": summary}


def test_stream_forwards_the_events_and_saves_like_send(store, engine):  # CA-98
    http = app(store, service_agent(StreamingFakeModel(replies=list(STREAM_REPLIES))))
    chat_id = http.post("/chats").json()["id"]
    events = send_stream(http, chat_id, "Che ore sono a Tokyo?")

    assert [name for name, _ in events] == [
        "question", "text", "reset", "tool_start", "tool_end",
        "text", "text", "text", "text", "text", "done",
    ]
    question = {
        "id": 1, "role": "user", "content": "Che ore sono a Tokyo?", "tools_used": [],
        "created_at": "2026-11-14T10:00:00Z",
    }
    assert events[0] == ("question", question)
    assert events[1] == ("text", {"delta": "Controllo."})
    assert events[2] == ("reset", {"reason": "tools", "detail": ""})
    assert events[3] == ("tool_start", {
        "id": "c1", "name": "get_current_time", "args": {"timezone": "Asia/Tokyo"},
    })
    assert events[4][1]["id"] == "c1" and events[4][1]["ok"] is True
    assert "".join(data["delta"] for _, data in events[5:-1]) == "A Tokyo sono le 00:47."
    assert events[-1][1]["question"] == question

    # the same turn through POST /messages on another archive: same answer and agent state
    other_engine = create_db_engine("sqlite://")
    init_db(other_engine)
    reference = app(
        ChatStore(other_engine, now=Clock(START)),
        service_agent(StreamingFakeModel(replies=list(STREAM_REPLIES))),
    )
    other_id = reference.post("/chats").json()["id"]
    expected = reference.post(
        f"/chats/{other_id}/messages", json={"content": "Che ore sono a Tokyo?"}
    ).json()
    assert events[-1][1] == expected
    assert http.get(f"/chats/{chat_id}").json() == reference.get(f"/chats/{other_id}").json()
    assert agent_state(engine, chat_id) == agent_state(other_engine, other_id)
    other_engine.dispose()


def test_stream_sends_the_saved_history_and_summary(store, engine):  # CA-98
    agent = ScriptedStreamAgent(
        [done("Uno", history=SAVED_HISTORY, summary="riassunto 1")],
        [("text", {"delta": "Du"}), ("text", {"delta": "e"}), done("Due", summary="riassunto 2")],
    )
    http = app(store, agent)
    chat_id = http.post("/chats").json()["id"]
    first = send_stream(http, chat_id, "  a ")
    assert [name for name, _ in first] == ["question", "done"]
    assert agent_state(engine, chat_id) == (SAVED_HISTORY, "riassunto 1")
    second = send_stream(http, chat_id, "b")
    assert [name for name, _ in second] == ["question", "text", "text", "done"]
    assert agent.calls == [([], "", "a"), (SAVED_HISTORY, "riassunto 1", "b")]
    assert agent_state(engine, chat_id) == ([], "riassunto 2")
    assert contents(store, chat_id) == [
        ("user", "a"), ("assistant", "Uno"), ("user", "b"), ("assistant", "Due"),
    ]
    assert second[-1][1]["answer"]["content"] == "Due"
    assert agent.closed == [True, True]


@pytest.mark.parametrize("content", ["", "   "])
def test_stream_empty_message_is_400_in_json(http, store, content):  # CA-98
    chat_id = http.post("/chats").json()["id"]
    response = http.post(f"/chats/{chat_id}/messages/stream", json={"content": content})
    assert response.status_code == 400
    assert response.headers["content-type"] == "application/json; charset=utf-8"
    assert response.json() == {"error": "invalid_request", "detail": "il messaggio è vuoto"}
    assert contents(store, chat_id) == []


def test_stream_errors_of_the_request_are_json(http):  # CA-98
    missing = http.post("/chats/42/messages/stream", json={"content": "Ciao"})
    assert (missing.status_code, missing.json()) == (
        404, {"error": "chat_not_found", "detail": "chat 42 inesistente"}
    )
    assert http.post("/chats/1/messages/stream", json={"content": 3}).status_code == 422
    assert http.post("/chats/abc/messages/stream", json={"content": "a"}).status_code == 422


STREAM_OPEN_FAILURES = [
    pytest.param(
        lambda: AgentClient("http://127.0.0.1:1"), 503, "agent_unavailable",
        "agente non raggiungibile su http://127.0.0.1:1", id="closed-port",
    ),
    pytest.param(
        lambda: mock_agent(raising(httpx.ReadTimeout("lento"))), 504, "agent_timeout",
        "l'agente non ha risposto entro 60 s", id="timeout",
    ),
    pytest.param(
        lambda: mock_agent(lambda request: httpx.Response(
            400, json={"error": "invalid_history", "detail": "messaggio 1: ruolo sconosciuto"}
        )), 502, "agent_error",
        "l'agente ha risposto con un errore (invalid_history): messaggio 1: ruolo sconosciuto",
        id="error-answer",
    ),
]


@pytest.mark.parametrize(("make_agent", "status", "code", "detail"), STREAM_OPEN_FAILURES)
def test_stream_agent_failure_before_the_stream_is_json(
    store, engine, caplog, make_agent, status, code, detail,
):  # CA-98
    caplog.set_level(logging.INFO)
    chat_id = store.create_chat().id
    store.add_question(chat_id, "Mi chiamo Paolo")
    store.add_answer(chat_id, "Piacere!", [], AgentState(SAVED_HISTORY, "rias"))

    response = app(store, make_agent()).post(
        f"/chats/{chat_id}/messages/stream", json={"content": "Quanto fa 2 + 2?"}
    )
    assert response.status_code == status
    assert response.headers["content-type"] == "application/json; charset=utf-8"
    assert response.json() == {"error": code, "detail": detail}
    assert contents(store, chat_id)[-1] == ("user", "Quanto fa 2 + 2?")
    assert agent_state(engine, chat_id) == (SAVED_HISTORY, "rias")
    escaped = detail.replace('"', '\\"')
    assert backend_lines(caplog)[-1] == (logging.WARNING, (
        f'backend response=send_message_stream chat={chat_id} status={status} error={code} '
        f'detail="{escaped}" duration_ms=N'
    ))


@pytest.mark.parametrize(("error", "status", "code"), [
    (database_down(), 503, "database_unavailable"),
    (RuntimeError("guasto"), 500, "internal_error"),
])
def test_stream_with_a_broken_archive_is_json(error, status, code, caplog):  # CA-98
    caplog.set_level(logging.INFO)
    http = TestClient(create_app(store=BrokenStore(error), agent=NoAgent()))
    response = http.post("/chats/3/messages/stream", json={"content": "Ciao"})
    assert response.status_code == status
    assert response.json()["error"] == code
    lines = backend_lines(caplog)
    assert lines[0] == (logging.INFO, "backend request=send_message_stream chat=3 chars=4")
    assert lines[1][1].startswith(
        f"backend response=send_message_stream chat=3 status={status} error={code} "
    )
    assert len(lines) == 2


STREAM_FAILURES = [
    pytest.param(
        lambda: service_agent(StreamingFakeModel(replies=[STREAM_REPLIES[0], lm_studio_error()])),
        ["question", "text", "reset", "tool_start", "tool_end", "error"], "agent_error",
        "l'agente ha risposto con un errore (model_unavailable): LM Studio non raggiungibile: "
        "Connection error.", logging.WARNING, id="lm-studio-off",
    ),
    pytest.param(
        lambda: mock_agent(lambda request: httpx.Response(
            200, headers={"content-type": "text/event-stream"},
            content=b'event: text\ndata: {"delta": "a"}\n\n',
        )),
        ["question", "text", "error"], "agent_error",
        "l'agente ha risposto con un errore (bad_response): flusso dell'agente non valido: "
        "flusso interrotto prima della fine del turno", logging.WARNING, id="cut",
    ),
    pytest.param(
        lambda: ScriptedStreamAgent([("text", {"delta": "a"}), RuntimeError("guasto")]),
        ["question", "text", "error"], "internal_error",
        "errore interno del back-end; dettagli nel log", logging.ERROR, id="unexpected",
    ),
]


@pytest.mark.parametrize(("make_agent", "names", "code", "detail", "level"), STREAM_FAILURES)
def test_stream_error_during_the_turn_keeps_the_question_and_the_state(
    store, engine, caplog, make_agent, names, code, detail, level,
):  # CA-98
    caplog.set_level(logging.INFO)
    chat_id = store.create_chat().id
    store.add_question(chat_id, "Mi chiamo Paolo")
    store.add_answer(chat_id, "Piacere!", [], AgentState(SAVED_HISTORY, "rias"))

    events = send_stream(app(store, make_agent()), chat_id, "Che ore sono a Tokyo?")
    assert [name for name, _ in events] == names
    assert events[-1] == ("error", {"error": code, "detail": detail})
    assert contents(store, chat_id) == [
        ("user", "Mi chiamo Paolo"), ("assistant", "Piacere!"), ("user", "Che ore sono a Tokyo?"),
    ]
    assert agent_state(engine, chat_id) == (SAVED_HISTORY, "rias")
    escaped = detail.replace('"', '\\"')
    assert backend_lines(caplog)[-1] == (level, (
        f'backend response=send_message_stream chat={chat_id} status=200 outcome=error '
        f'error={code} detail="{escaped}" duration_ms=N'
    ))
    if level == logging.ERROR:
        assert "guasto" in caplog.text and "guasto" not in json.dumps(events)


def test_stream_chat_deleted_during_the_turn(store):  # CA-98
    def delete():
        store.delete_chat(chat_id)
        return "text", {"delta": "Ok"}

    chat_id = store.create_chat().id
    events = send_stream(app(store, ScriptedStreamAgent([delete, done()])), chat_id, "Ciao")
    assert events[-1] == (
        "error", {"error": "chat_not_found", "detail": f"chat {chat_id} inesistente"}
    )
    assert store.list_chats() == []


def test_stream_log_lines(store, caplog):  # CA-98
    caplog.set_level(logging.INFO)
    http = app(store, service_agent(StreamingFakeModel(replies=list(STREAM_REPLIES))))
    chat_id = http.post("/chats").json()["id"]
    send_stream(http, chat_id, "Che ore sono a Tokyo?")
    assert backend_lines(caplog)[1:] == [
        (logging.INFO, f"backend request=send_message_stream chat={chat_id} chars=21"),
        (logging.INFO, f"backend agent_call chat={chat_id} history=0 summary_chars=0 stream=true"),
        (logging.INFO, (
            f"backend response=send_message_stream chat={chat_id} status=200 outcome=done "
            "tools=get_current_time reply_chars=22 duration_ms=N"
        )),
    ]


def test_stream_messages_do_not_enter_the_log(store, caplog):
    caplog.set_level(logging.DEBUG)
    http = app(store, ScriptedStreamAgent([
        ("text", {"delta": "Risposta riservata"}), done("Risposta riservata", summary="riservato"),
    ]))
    chat_id = http.post("/chats").json()["id"]
    send_stream(http, chat_id, "Domanda riservata")
    assert "riservat" not in " ".join(message for _, message in backend_lines(caplog))


def test_client_gone_closes_the_stream_of_the_agent(store, engine, caplog):  # CA-98
    caplog.set_level(logging.INFO)
    chat_id = store.create_chat().id
    question, _ = store.add_question(chat_id, "Ciao")
    agent = ScriptedStreamAgent([("text", {"delta": "a"}), ("text", {"delta": "b"}), done()])
    stream = OpenStream(chat_id, question, agent.chat_stream([], "", message="Ciao"), 0.0)

    forwarded = _forward(store, stream)
    assert next(forwarded).event == "question"
    assert next(forwarded).event == "text"
    forwarded.close()
    assert agent.closed == [True]
    assert contents(store, chat_id) == [("user", "Ciao")]
    assert agent_state(engine, chat_id) == ([], "")
    assert backend_lines(caplog)[-1] == (logging.INFO, (
        f"backend response=send_message_stream chat={chat_id} status=200 outcome=client_gone "
        "duration_ms=N"
    ))


def test_openapi_describes_the_stream(http):  # CA-98
    document = http.get("/openapi.json").json()
    assert set(document["paths"]["/chats/{chat_id}/messages/stream"]) == {"post"}
    operation = document["paths"]["/chats/{chat_id}/messages/stream"]["post"]
    assert operation["summary"] and "`question`" in operation["description"]
    assert "text/event-stream" in operation["responses"]["200"]["content"]
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/SendMessageRequest"
    }
    error_ref = {"$ref": "#/components/schemas/ErrorBody"}
    assert set(operation["responses"]) == {"200", "400", "404", "422", "500", "502", "503", "504"}
    for code in ("400", "404", "500", "502", "503", "504"):
        assert operation["responses"][code]["content"] == {
            "application/json": {"schema": error_ref}
        }


def test_preflight_of_the_stream(cors_http):  # CA-98, CA-81
    response = cors_http.options("/chats/1/messages/stream", headers={
        "Origin": PAGE, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == PAGE


JSON_UTF8 = "application/json; charset=utf-8"


@pytest.mark.parametrize(("method", "path", "body", "status"), [
    ("GET", "/chats", None, 200),
    ("GET", "/chats/42", None, 404),
    ("POST", "/chats", {"title": "t", "altro": 1}, 422),
], ids=["list", "not-found", "422"])
def test_json_answers_declare_utf8(http, method, path, body, status):  # R-B7
    response = http.request(method, path, json=body)
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == JSON_UTF8


def test_stream_error_before_the_stream_declares_utf8(http):  # R-B7
    chat_id = http.post("/chats").json()["id"]
    response = http.post(f"/chats/{chat_id}/messages/stream", json={"content": ""})
    assert response.status_code == 400
    assert response.headers["content-type"] == JSON_UTF8


def test_streams_keep_their_media_type_and_cors(store):  # Review Focus 2
    agent = ScriptedStreamAgent([("text", {"delta": "Ok"}), done()])
    http = TestClient(create_app(store=store, agent=agent, cors_origins=(PAGE,)))
    chat_id = http.post("/chats").json()["id"]
    with http.stream("POST", f"/chats/{chat_id}/messages/stream", json={"content": "Ciao"},
                     headers={"Origin": PAGE}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["access-control-allow-origin"] == PAGE
        response.read()


def test_nul_in_the_title_is_400(http):  # R-C3, Review Focus 3
    response = http.post("/chats", json={"title": "a\x00b"})
    assert response.status_code == 400
    assert response.json() == {
        "error": "invalid_request", "detail": "il titolo contiene un carattere non ammesso (NUL)",
    }
    assert http.get("/chats").json() == []


@pytest.mark.parametrize("path", ["messages", "messages/stream"])
def test_nul_in_the_question_is_400_without_calling_the_agent(store, path, caplog):  # R-C3
    caplog.set_level(logging.DEBUG)
    http = app(store, ScriptedStreamAgent())  # any call of the agent fails
    chat_id = http.post("/chats").json()["id"]
    response = http.post(f"/chats/{chat_id}/{path}", json={"content": "segreto\x00"})
    assert response.status_code == 400
    assert response.headers["content-type"] == JSON_UTF8
    assert response.json() == {
        "error": "invalid_request", "detail": "il messaggio contiene un carattere non ammesso (NUL)",
    }
    assert contents(store, chat_id) == []
    assert "segreto" not in caplog.text
