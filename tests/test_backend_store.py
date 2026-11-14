from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from backend.db import ChatMessage, create_db_engine, init_db
from backend.store import (
    MAX_TITLE_LENGTH,
    TITLE_LENGTH,
    AgentState,
    ChatNotFoundError,
    ChatStore,
    InvalidInputError,
    title_from_question,
)

START = datetime(2026, 11, 14, 10, 0, 0, tzinfo=UTC)
TOOL = {"name": "calculate", "args": {"expression": "17 * 23"}, "result": {"result": 391}, "ok": True}
HISTORY = [
    {"type": "human", "content": "Quanto fa 17 * 23?"},
    {"type": "ai", "content": "17 * 23 fa 391."},
]


class Clock:
    """Fixed clock that moves only when the test says so."""

    def __init__(self, start: datetime = START):
        self.current = start

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: int) -> None:
        self.current += timedelta(seconds=seconds)


@pytest.fixture
def engine():
    engine = create_db_engine("sqlite://")
    init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def store(engine, clock):
    return ChatStore(engine, now=clock)


def count_messages(engine) -> int:
    with engine.connect() as connection:
        return connection.execute(select(func.count()).select_from(ChatMessage)).scalar_one()


def complete_turn(store, chat_id, question="Quanto fa 17 * 23?", reply="17 * 23 fa 391."):
    store.add_question(chat_id, question)
    return store.add_answer(chat_id, reply, [TOOL], AgentState(HISTORY, ""))


# --- schema ------------------------------------------------------------------------------------


def test_init_db_creates_both_tables_with_the_columns_of_the_spec(engine):
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == {"chats", "chat_messages"}
    assert {c["name"] for c in inspector.get_columns("chats")} == {
        "id", "title", "created_at", "summary", "history",
    }
    assert {c["name"] for c in inspector.get_columns("chat_messages")} == {
        "id", "chat_id", "role", "content", "tools_used", "created_at",
    }


def test_messages_reference_chats_with_on_delete_cascade(engine):
    (foreign_key,) = inspect(engine).get_foreign_keys("chat_messages")
    assert foreign_key["referred_table"] == "chats"
    assert foreign_key["constrained_columns"] == ["chat_id"]
    assert foreign_key["options"].get("ondelete") == "CASCADE"


def test_init_db_keeps_existing_data(engine, store):
    chat = store.create_chat("Prima chat")
    init_db(engine)
    assert [c.id for c in store.list_chats()] == [chat.id]


def test_sqlite_engine_enforces_foreign_keys(engine):
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1


# --- creation ----------------------------------------------------------------------------------


def test_create_chat_with_a_title(store):
    chat = store.create_chat("Calcoli")
    assert chat.id >= 1
    assert chat.title == "Calcoli"
    assert chat.created_at == START
    assert chat.last_message_at is None


def test_create_chat_without_a_title(store):
    chat = store.create_chat()
    assert chat.title is None


def test_create_chat_strips_the_title_and_treats_blank_as_missing(store):
    assert store.create_chat("  Calcoli \n").title == "Calcoli"
    assert store.create_chat("   ").title is None


def test_create_chat_accepts_the_longest_title(store):
    title = "a" * MAX_TITLE_LENGTH
    assert store.create_chat(title).title == title


def test_create_chat_rejects_a_title_that_is_too_long(store):
    with pytest.raises(InvalidInputError, match=f"il titolo supera {MAX_TITLE_LENGTH} caratteri"):
        store.create_chat("a" * (MAX_TITLE_LENGTH + 1))
    assert store.list_chats() == []


def test_chat_ids_are_distinct_and_growing(store):
    first = store.create_chat()
    second = store.create_chat()
    assert second.id > first.id


# --- listing -----------------------------------------------------------------------------------


def test_list_chats_is_empty_at_first(store):
    assert store.list_chats() == []


def test_list_chats_reports_title_and_last_message_time(store, clock):
    chat = store.create_chat("Calcoli")
    clock.advance(5)
    store.add_question(chat.id, "Quanto fa 17 * 23?")
    clock.advance(3)
    store.add_answer(chat.id, "17 * 23 fa 391.", [TOOL], AgentState(HISTORY, ""))

    (listed,) = store.list_chats()
    assert listed.title == "Calcoli"
    assert listed.created_at == START
    assert listed.last_message_at == START + timedelta(seconds=8)


def test_list_chats_puts_the_most_recent_activity_first(store, clock):
    old = store.create_chat("vecchia")
    clock.advance(10)
    new = store.create_chat("nuova")
    clock.advance(10)
    empty = store.create_chat("vuota, creata per ultima")
    assert [c.id for c in store.list_chats()] == [empty.id, new.id, old.id]

    clock.advance(10)
    store.add_question(old.id, "ciao")
    assert [c.id for c in store.list_chats()] == [old.id, empty.id, new.id]


def test_list_chats_breaks_ties_with_the_newest_id(store):
    first = store.create_chat()
    second = store.create_chat()
    assert [c.id for c in store.list_chats()] == [second.id, first.id]


def test_times_come_back_in_utc_even_from_another_timezone(engine):
    rome = datetime(2026, 11, 14, 11, 0, 0, tzinfo=timezone(timedelta(hours=1)))
    store = ChatStore(engine, now=lambda: rome)
    chat = store.create_chat()
    assert chat.created_at.tzinfo is not None
    assert chat.created_at.utcoffset() == timedelta(0)
    assert chat.created_at == rome
    assert store.list_chats()[0].created_at == rome


# --- reading -----------------------------------------------------------------------------------


def test_get_chat_returns_the_messages_in_chronological_order(store, clock):
    chat = store.create_chat()
    complete_turn(store, chat.id, "Quanto fa 17 * 23?", "17 * 23 fa 391.")
    clock.advance(60)
    complete_turn(store, chat.id, "E 2 + 2?", "Fa 4.")

    record, messages = store.get_chat(chat.id)
    assert record.id == chat.id
    assert [(m.role, m.content) for m in messages] == [
        ("user", "Quanto fa 17 * 23?"),
        ("assistant", "17 * 23 fa 391."),
        ("user", "E 2 + 2?"),
        ("assistant", "Fa 4."),
    ]
    assert [m.id for m in messages] == sorted(m.id for m in messages)
    assert record.last_message_at == START + timedelta(seconds=60)


def test_get_chat_orders_by_id_when_times_are_equal(store):
    chat = store.create_chat()
    complete_turn(store, chat.id)  # fixed clock: question and answer share created_at
    _, messages = store.get_chat(chat.id)
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[0].created_at == messages[1].created_at


def test_get_chat_of_an_empty_chat(store):
    chat = store.create_chat("vuota")
    record, messages = store.get_chat(chat.id)
    assert record == chat
    assert messages == []


def test_get_chat_keeps_the_messages_of_each_chat_apart(store):
    first = store.create_chat()
    second = store.create_chat()
    store.add_question(first.id, "nella prima")
    store.add_question(second.id, "nella seconda")
    assert [m.content for m in store.get_chat(first.id)[1]] == ["nella prima"]
    assert [m.content for m in store.get_chat(second.id)[1]] == ["nella seconda"]


def test_get_chat_of_a_missing_chat(store):
    with pytest.raises(ChatNotFoundError, match="^chat 42 inesistente$"):
        store.get_chat(42)


# --- deletion ----------------------------------------------------------------------------------


def test_delete_chat_removes_the_chat_and_its_messages(store, engine):
    chat = store.create_chat()
    other = store.create_chat()
    complete_turn(store, chat.id)
    store.add_question(other.id, "resta")
    assert count_messages(engine) == 3

    store.delete_chat(chat.id)

    assert [c.id for c in store.list_chats()] == [other.id]
    assert count_messages(engine) == 1
    with pytest.raises(ChatNotFoundError):
        store.get_chat(chat.id)


def test_database_cascade_removes_messages_without_the_orm(store, engine):
    chat = store.create_chat()
    complete_turn(store, chat.id)
    with engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM chats WHERE id = ?", (chat.id,))
    assert count_messages(engine) == 0


def test_delete_chat_of_a_missing_chat(store):
    with pytest.raises(ChatNotFoundError, match="^chat 7 inesistente$"):
        store.delete_chat(7)


def test_new_chat_does_not_inherit_the_messages_of_a_deleted_one(store):
    chat = store.create_chat()
    complete_turn(store, chat.id)
    store.delete_chat(chat.id)
    new = store.create_chat()  # SQLite may give it the id of the deleted chat
    assert store.get_chat(new.id)[1] == []
    _, state = store.add_question(new.id, "ciao")
    assert state == AgentState([], "")


# --- title from the first question -------------------------------------------------------------


def test_title_from_question_keeps_a_short_first_line():
    assert title_from_question("Quanto fa 17 * 23?") == "Quanto fa 17 * 23?"


def test_title_from_question_uses_only_the_first_line():
    assert title_from_question("Prima riga  \nseconda riga") == "Prima riga"


def test_title_from_question_keeps_exactly_the_maximum_length():
    text = "a" * TITLE_LENGTH
    assert title_from_question(text) == text


def test_title_from_question_cuts_long_lines_with_an_ellipsis():
    title = title_from_question("a" * (TITLE_LENGTH + 10))
    assert title == "a" * (TITLE_LENGTH - 1) + "…"
    assert len(title) == TITLE_LENGTH


def test_title_from_question_drops_spaces_before_the_ellipsis():
    text = "a" * (TITLE_LENGTH - 2) + "   coda lunga"
    assert title_from_question(text) == "a" * (TITLE_LENGTH - 2) + "…"


def test_first_question_gives_the_title_to_a_chat_without_one(store):
    chat = store.create_chat()
    store.add_question(chat.id, "  Quanto fa 17 * 23?\nGrazie  ")
    assert store.get_chat(chat.id)[0].title == "Quanto fa 17 * 23?"


def test_later_questions_do_not_change_the_title(store):
    chat = store.create_chat()
    complete_turn(store, chat.id, "Prima domanda")
    store.add_question(chat.id, "Seconda domanda")
    assert store.get_chat(chat.id)[0].title == "Prima domanda"


def test_first_question_keeps_a_title_given_at_creation(store):
    chat = store.create_chat("Titolo scelto")
    store.add_question(chat.id, "Quanto fa 17 * 23?")
    assert store.get_chat(chat.id)[0].title == "Titolo scelto"


def test_first_question_cuts_a_long_title(store):
    chat = store.create_chat()
    store.add_question(chat.id, "parola " * 20)
    title = store.get_chat(chat.id)[0].title
    assert len(title) <= TITLE_LENGTH
    assert title.endswith("…")


# --- question, answer and agent state ----------------------------------------------------------


def test_new_chat_has_an_empty_agent_state(store):
    chat = store.create_chat()
    _, state = store.add_question(chat.id, "ciao")
    assert state == AgentState(history=[], summary="")


def test_add_question_saves_the_stripped_question(store):
    chat = store.create_chat()
    question, _ = store.add_question(chat.id, "  Quanto fa 17 * 23?  ")
    assert question.role == "user"
    assert question.content == "Quanto fa 17 * 23?"
    assert question.tools_used == []
    assert question.created_at == START
    assert store.get_chat(chat.id)[1] == [question]


def test_add_question_rejects_an_empty_message(store, engine):
    chat = store.create_chat()
    with pytest.raises(InvalidInputError, match="^il messaggio è vuoto$"):
        store.add_question(chat.id, " \n ")
    assert count_messages(engine) == 0
    assert store.get_chat(chat.id)[0].title is None


def test_add_question_of_a_missing_chat(store, engine):
    with pytest.raises(ChatNotFoundError, match="^chat 5 inesistente$"):
        store.add_question(5, "ciao")
    assert count_messages(engine) == 0


def test_add_answer_saves_reply_and_tools(store, clock):
    chat = store.create_chat()
    store.add_question(chat.id, "Quanto fa 17 * 23?")
    clock.advance(5)
    answer = store.add_answer(chat.id, "17 * 23 fa 391.", [TOOL], AgentState(HISTORY, ""))
    assert answer.role == "assistant"
    assert answer.content == "17 * 23 fa 391."
    assert answer.tools_used == [TOOL]
    assert answer.created_at == START + timedelta(seconds=5)
    assert store.get_chat(chat.id)[1][-1] == answer


def test_add_answer_replaces_the_agent_state(store):
    chat = store.create_chat()
    complete_turn(store, chat.id)
    _, state = store.add_question(chat.id, "E 2 + 2?")
    assert state == AgentState(HISTORY, "")

    longer = HISTORY + [{"type": "human", "content": "E 2 + 2?"}, {"type": "ai", "content": "4"}]
    store.add_answer(chat.id, "4", [], AgentState(longer, "L'utente fa calcoli."))
    _, state = store.add_question(chat.id, "Grazie")
    assert state == AgentState(longer, "L'utente fa calcoli.")


def test_agent_state_does_not_change_with_only_a_question(store):
    chat = store.create_chat()
    complete_turn(store, chat.id)
    store.add_question(chat.id, "domanda senza risposta (agente spento)")
    _, state = store.add_question(chat.id, "di nuovo")
    assert state == AgentState(HISTORY, "")


def test_agent_state_is_kept_per_chat(store):
    first = store.create_chat()
    second = store.create_chat()
    complete_turn(store, first.id)
    _, state = store.add_question(second.id, "ciao")
    assert state == AgentState([], "")


def test_add_answer_of_a_chat_deleted_during_the_turn(store, engine):
    chat = store.create_chat()
    store.add_question(chat.id, "Quanto fa 17 * 23?")
    store.delete_chat(chat.id)  # deleted while the agent was answering
    with pytest.raises(ChatNotFoundError, match=f"^chat {chat.id} inesistente$"):
        store.add_answer(chat.id, "17 * 23 fa 391.", [TOOL], AgentState(HISTORY, ""))
    assert count_messages(engine) == 0


def test_agent_state_saved_is_a_copy(store):
    chat = store.create_chat()
    history = list(HISTORY)
    store.add_question(chat.id, "Quanto fa 17 * 23?")
    store.add_answer(chat.id, "391", [], AgentState(history, ""))
    history.append({"type": "human", "content": "modificata dopo"})
    _, state = store.add_question(chat.id, "ancora")
    assert state.history == HISTORY


# --- database errors ---------------------------------------------------------------------------


def test_database_errors_reach_the_caller():
    engine = create_db_engine("sqlite://")  # tables never created
    store = ChatStore(engine)
    with pytest.raises(SQLAlchemyError):
        store.list_chats()
    with pytest.raises(OperationalError):
        store.create_chat()
    engine.dispose()
