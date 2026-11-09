"""Persistent notes in SQLite: one connection per operation, each change in a transaction."""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

MAX_TEXT_LENGTH = 500
MAX_LIST_LIMIT = 50

ADD_NOTE_DESCRIPTION = (
    "Salva una nuova nota persistente. Usalo una sola volta per ogni richiesta di ricordare "
    "qualcosa."
)
LIST_NOTES_DESCRIPTION = "Elenca le note salvate, dalla più recente."
DELETE_NOTE_DESCRIPTION = (
    "Elimina una sola nota dato il suo id numerico esatto. Non usarlo senza un id indicato "
    "dall'utente o letto con list_notes."
)

# AUTOINCREMENT keeps the id of a deleted note from being reused.
_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS notes ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, created_at TEXT NOT NULL)"
)


def _note(row: tuple) -> dict:
    return {"id": row[0], "text": row[1], "created_at": row[2]}


class NotesStore:
    def __init__(
        self,
        path: str | Path,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._path = Path(path)
        self._now = now

    def _run(self, operation: Callable[[sqlite3.Connection], dict]) -> dict:
        """Runs `operation` in a transaction on a fresh connection, closed right after."""
        try:
            with closing(sqlite3.connect(self._path)) as connection:
                with connection:  # commit on success, rollback on error
                    connection.execute(_SCHEMA)
                    return operation(connection)
        except sqlite3.Error as error:
            raise ValueError(f"Archivio delle note non accessibile: {error}.") from None

    def add(self, text: str) -> dict:
        text = text.strip()
        if not text:
            raise ValueError("Il testo della nota è vuoto.")
        if len(text) > MAX_TEXT_LENGTH:
            raise ValueError(
                f"Il testo della nota è troppo lungo: massimo {MAX_TEXT_LENGTH} caratteri."
            )
        created_at = self._now().astimezone(timezone.utc).isoformat(timespec="seconds")

        def insert(connection: sqlite3.Connection) -> dict:
            cursor = connection.execute(
                "INSERT INTO notes (text, created_at) VALUES (?, ?)", (text, created_at)
            )
            return {"id": cursor.lastrowid, "text": text, "created_at": created_at}

        return self._run(insert)

    def list(self, limit: int = 10) -> dict:
        if not 1 <= limit <= MAX_LIST_LIMIT:
            raise ValueError(f"limit deve essere tra 1 e {MAX_LIST_LIMIT}, ricevuto {limit}.")

        def select(connection: sqlite3.Connection) -> dict:
            rows = connection.execute(
                "SELECT id, text, created_at FROM notes ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            total = connection.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
            return {"notes": [_note(row) for row in rows], "total": total}

        return self._run(select)

    def delete(self, note_id: int) -> dict:
        def remove(connection: sqlite3.Connection) -> dict:
            row = connection.execute(
                "SELECT id, text, created_at FROM notes WHERE id = ?", (note_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Nessuna nota con id {note_id}: nessuna nota eliminata.")
            connection.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            return {"deleted": _note(row)}

        return self._run(remove)
