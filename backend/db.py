"""Database schema of the chats and engine creation (PostgreSQL in use, SQLite in the tests)."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Engine,
    ForeignKey,
    String,
    Text,
    create_engine,
    event,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class Chat(Base):
    """A chat: title, creation time and the agent state (Step 6 history and summary)."""

    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    summary: Mapped[str] = mapped_column(Text, default="", server_default="")
    history: Mapped[list] = mapped_column(JSON, default=list, server_default=text("'[]'"))

    # passive_deletes: the database deletes the messages (ON DELETE CASCADE), not the ORM.
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan", passive_deletes=True
    )


class ChatMessage(Base):
    """A message the user sees: a question ('user') or an answer ('assistant') with its tools."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    tools_used: Mapped[list] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    chat: Mapped[Chat] = relationship(back_populates="messages")


def _enable_sqlite_foreign_keys(connection, _record) -> None:
    connection.execute("PRAGMA foreign_keys=ON")


def create_db_engine(url: str) -> Engine:
    """Engine for `url`. SQLite (tests only) gets foreign keys on and, in memory, one shared
    connection; PostgreSQL checks pooled connections before use, so a database restart is
    not seen as an error by the first request after it."""
    if url.startswith("sqlite"):
        options = {}
        if url in ("sqlite://", "sqlite:///:memory:"):
            options = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
        engine = create_engine(url, **options)
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
        return engine
    return create_engine(url, pool_pre_ping=True)


def init_db(engine: Engine) -> None:
    """Creates the missing tables; existing tables and their data are left as they are."""
    Base.metadata.create_all(engine)
