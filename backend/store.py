"""Chat archive: chats, visible messages and the agent state, one transaction per operation.

No transaction stays open while the agent answers: `add_question` and `add_answer` are two
separate operations. SQLAlchemy errors reach the caller unchanged.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from backend.db import Chat, ChatMessage

MAX_TITLE_LENGTH = 200
TITLE_LENGTH = 60  # title taken from the first question
NUL = "\x00"  # rejected in titles and messages: PostgreSQL text cannot hold it


class ChatNotFoundError(Exception):
    def __init__(self, chat_id: int):
        super().__init__(f"chat {chat_id} inesistente")
        self.chat_id = chat_id


class InvalidInputError(Exception):
    """Title or message the archive does not accept (the API answers 400)."""


@dataclass(frozen=True)
class MessageRecord:
    id: int
    role: str
    content: str
    tools_used: list
    created_at: datetime


@dataclass(frozen=True)
class ChatRecord:
    id: int
    title: str | None
    created_at: datetime
    last_message_at: datetime | None


@dataclass(frozen=True)
class AgentState:
    history: list[dict]
    summary: str


def title_from_question(text: str) -> str:
    """First line of the question, at most TITLE_LENGTH characters ending with «…» if cut."""
    line = text.strip().splitlines()[0].strip()
    if len(line) <= TITLE_LENGTH:
        return line
    return line[: TITLE_LENGTH - 1].rstrip() + "…"


def _utc(moment: datetime | None) -> datetime | None:
    """SQLite gives back times without a timezone: they were saved in UTC."""
    if moment is None:
        return None
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def _message(row: ChatMessage) -> MessageRecord:
    return MessageRecord(
        id=row.id,
        role=row.role,
        content=row.content,
        tools_used=list(row.tools_used),
        created_at=_utc(row.created_at),
    )


def _chat(row: Chat, last_message_at: datetime | None) -> ChatRecord:
    return ChatRecord(
        id=row.id,
        title=row.title,
        created_at=_utc(row.created_at),
        last_message_at=_utc(last_message_at),
    )


class ChatStore:
    def __init__(self, engine: Engine, now: Callable[[], datetime] = lambda: datetime.now(UTC)):
        self._sessions = sessionmaker(engine, expire_on_commit=False)
        self._now = now

    def _timestamp(self) -> datetime:
        return self._now().astimezone(UTC)

    @staticmethod
    def _find(session: Session, chat_id: int) -> Chat:
        chat = session.get(Chat, chat_id)
        if chat is None:
            raise ChatNotFoundError(chat_id)
        return chat

    def create_chat(self, title: str | None = None) -> ChatRecord:
        title = (title or "").strip() or None
        if title is not None and len(title) > MAX_TITLE_LENGTH:
            raise InvalidInputError(f"il titolo supera {MAX_TITLE_LENGTH} caratteri")
        if title is not None and NUL in title:
            raise InvalidInputError("il titolo contiene un carattere non ammesso (NUL)")
        with self._sessions.begin() as session:
            chat = Chat(title=title, created_at=self._timestamp(), summary="", history=[])
            session.add(chat)
            session.flush()
            return _chat(chat, None)

    def list_chats(self) -> list[ChatRecord]:
        """Chats with the most recent activity (last message, or creation) first."""
        last = func.max(ChatMessage.created_at)
        query = (
            select(Chat, last)
            .outerjoin(ChatMessage, ChatMessage.chat_id == Chat.id)
            .group_by(Chat.id)
            .order_by(func.coalesce(last, Chat.created_at).desc(), Chat.id.desc())
        )
        with self._sessions() as session:
            return [_chat(chat, last_at) for chat, last_at in session.execute(query)]

    def get_chat(self, chat_id: int) -> tuple[ChatRecord, list[MessageRecord]]:
        """The chat and its messages in insertion order (id grows with each message)."""
        with self._sessions() as session:
            chat = self._find(session, chat_id)
            rows = session.scalars(
                select(ChatMessage).where(ChatMessage.chat_id == chat_id).order_by(ChatMessage.id)
            ).all()
            last_at = max((row.created_at for row in rows), default=None)
            return _chat(chat, last_at), [_message(row) for row in rows]

    def delete_chat(self, chat_id: int) -> None:
        with self._sessions.begin() as session:
            session.delete(self._find(session, chat_id))

    def add_question(self, chat_id: int, text: str) -> tuple[MessageRecord, AgentState]:
        """Saves the question (giving the chat its title if it has none) and returns the agent
        state to send along with it."""
        text = text.strip()
        if not text:
            raise InvalidInputError("il messaggio è vuoto")
        if NUL in text:
            raise InvalidInputError("il messaggio contiene un carattere non ammesso (NUL)")
        with self._sessions.begin() as session:
            chat = self._find(session, chat_id)
            if chat.title is None:
                chat.title = title_from_question(text)
            question = self._add_message(session, chat_id, "user", text, [])
            return question, AgentState(history=list(chat.history), summary=chat.summary)

    def add_answer(
        self, chat_id: int, reply: str, tools_used: list, state: AgentState
    ) -> MessageRecord:
        """Saves the answer and replaces the agent state of the chat, in one transaction."""
        with self._sessions.begin() as session:
            chat = self._find(session, chat_id)
            chat.history = list(state.history)
            chat.summary = state.summary
            return self._add_message(session, chat_id, "assistant", reply, list(tools_used))

    def _add_message(
        self, session: Session, chat_id: int, role: str, content: str, tools_used: list
    ) -> MessageRecord:
        row = ChatMessage(
            chat_id=chat_id,
            role=role,
            content=content,
            tools_used=tools_used,
            created_at=self._timestamp(),
        )
        session.add(row)
        session.flush()
        return _message(row)
