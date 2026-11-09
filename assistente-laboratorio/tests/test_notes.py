from datetime import datetime, timezone

import pytest

from assistant.notes import NotesStore

NOTE_TIME = datetime(2026, 11, 9, 14, 2, 11, tzinfo=timezone.utc)


@pytest.fixture
def store(tmp_path):
    return NotesStore(tmp_path / "notes.sqlite3", now=lambda: NOTE_TIME)


def test_add_returns_id_and_date(store):
    assert store.add("  Consegnare il report venerdì  ") == {
        "id": 1, "text": "Consegnare il report venerdì", "created_at": "2026-11-09T14:02:11+00:00"
    }


def test_list_newest_first_with_limit_and_total(store):
    for t in ("a", "b", "c"):
        store.add(t)
    r = store.list(limit=2)
    assert [n["text"] for n in r["notes"]] == ["c", "b"] and r["total"] == 3


def test_list_empty(store):
    assert store.list() == {"notes": [], "total": 0}


def test_delete_returns_deleted_note(store):
    store.add("a")
    assert store.delete(1) == {
        "deleted": {"id": 1, "text": "a", "created_at": "2026-11-09T14:02:11+00:00"}
    }
    assert store.list()["total"] == 0


def test_delete_unknown_id_deletes_nothing(store):
    store.add("a")
    with pytest.raises(ValueError, match=r"^Nessuna nota con id 99: nessuna nota eliminata\.$"):
        store.delete(99)
    assert store.list()["total"] == 1


@pytest.mark.parametrize("text,message", [
    ("   ", r"^Il testo della nota è vuoto\.$"),
    ("x" * 501, r"^Il testo della nota è troppo lungo: massimo 500 caratteri\.$"),
])
def test_invalid_text(store, text, message):
    with pytest.raises(ValueError, match=message):
        store.add(text)


@pytest.mark.parametrize("limit", [0, 51])
def test_limit_out_of_range(store, limit):
    with pytest.raises(ValueError, match=rf"^limit deve essere tra 1 e 50, ricevuto {limit}\.$"):
        store.list(limit)


def test_notes_survive_reopening(tmp_path):
    NotesStore(tmp_path / "n.sqlite3").add("resta")
    assert NotesStore(tmp_path / "n.sqlite3").list()["notes"][0]["text"] == "resta"


def test_deleted_ids_are_not_reused(store):
    store.add("a")
    store.add("b")
    store.delete(2)
    assert store.add("c")["id"] == 3


def test_inaccessible_store(tmp_path):
    with pytest.raises(ValueError, match=r"^Archivio delle note non accessibile: "):
        NotesStore(tmp_path / "missing" / "n.sqlite3").add("a")


def test_real_clock_is_utc(tmp_path):
    assert NotesStore(tmp_path / "n.sqlite3").add("a")["created_at"].endswith("+00:00")
