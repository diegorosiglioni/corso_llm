"""python -m rag.update_payload with Qdrant in memory: `has_doses` on the points of exercise 1,
vectors and other fields unchanged, repeatable, recovery after an interrupted run."""

import pytest
from qdrant_client import QdrantClient

from conftest import FakeEmbedder
from rag import update_payload
from rag.store import ChunkPoint, StoreError, count_missing, count_points, ensure_collection, point_id, upsert_points
from rag.update_payload import UpdateReport, format_report, run_update

VALID = {"LMSTUDIO_BASE_URL": "http://127.0.0.1:1234/v1", "EMBEDDING_MODEL": "m"}
TEXTS = [
    "Brodo di carne con sedano e carota.",
    "Patate, grammi 400.\nFarina, grammi 150.\n\nCuocete le patate.",
    "Se il maiale volasse\nNon ci saria danar che lo pagasse,",
]


def exercise_one_points(name="recipes"):
    """Points as the ingestion of exercise 1 wrote them: no `has_doses`, no chunking fields."""
    fake = FakeEmbedder()
    vectors = fake.embed(TEXTS)
    return [
        ChunkPoint(point_id("Ricettario.txt", n, 0), vector, {
            "source": "Ricettario.txt", "recipe_number": n, "title": f"R{n}", "chapter": "Zuppe",
            "chunk_index": 0, "text": text, "embedding_model": "m",
        })
        for n, (text, vector) in enumerate(zip(TEXTS, vectors), start=1)
    ]


@pytest.fixture
def indexed(qdrant):
    ensure_collection(qdrant, "recipes", FakeEmbedder.DIMENSION, "m")
    upsert_points(qdrant, "recipes", exercise_one_points())
    return qdrant


def stored(client):
    ids = [p.id for p in exercise_one_points()]
    return {p.id: p for p in client.retrieve("recipes", ids, with_payload=True, with_vectors=True)}


def test_every_point_gets_the_field(indexed):
    assert run_update(indexed, "recipes") == UpdateReport(3, 3, 1, 0)
    assert count_missing(indexed, "recipes", "has_doses") == 0
    assert [stored(indexed)[p.id].payload["has_doses"] for p in exercise_one_points()] == [False, True, False]


def test_vectors_and_other_fields_unchanged(indexed):
    before = stored(indexed)
    run_update(indexed, "recipes")
    after = stored(indexed)
    for point_id_, point in before.items():
        assert after[point_id_].vector == point.vector
        assert {k: v for k, v in after[point_id_].payload.items() if k != "has_doses"} == point.payload


def test_rerun_gives_the_same_report(indexed):
    assert run_update(indexed, "recipes") == run_update(indexed, "recipes")
    assert count_points(indexed, "recipes") == 3


def test_interrupted_update_then_rerun(indexed, monkeypatch):
    real_set_field = update_payload.set_field
    calls = []

    def fail_on_second(*args, **kwargs):
        calls.append(args)
        if len(calls) == 2:
            raise StoreError("Errore di Qdrant durante l'aggiornamento: connessione chiusa")
        real_set_field(*args, **kwargs)

    monkeypatch.setattr(update_payload, "set_field", fail_on_second)
    with pytest.raises(StoreError):
        run_update(indexed, "recipes")
    assert 0 < count_missing(indexed, "recipes", "has_doses") < 3
    monkeypatch.setattr(update_payload, "set_field", real_set_field)
    assert run_update(indexed, "recipes").missing == 0


def test_creates_the_index(indexed, monkeypatch):
    # The local client does not keep payload indexes: record the calls (as in test_rag_store).
    created = []
    monkeypatch.setattr(indexed, "create_payload_index",
                        lambda name, field, field_schema: created.append(field))
    run_update(indexed, "recipes")
    assert "has_doses" in created


def test_missing_or_empty_collection(qdrant):
    with pytest.raises(StoreError, match="rag.ingest"):
        run_update(qdrant, "recipes")
    ensure_collection(qdrant, "recipes", FakeEmbedder.DIMENSION, "m")
    with pytest.raises(StoreError, match="rag.ingest"):
        run_update(qdrant, "recipes")


def test_report_line():
    assert format_report(UpdateReport(1143, 1143, 400, 0)) == (
        "Punti: 1143 · aggiornati: 1143 · con dosi: 400 · senza campo: 0")


@pytest.fixture
def offline(monkeypatch):
    """main() with Qdrant in memory; close() does nothing so the test can read the points."""
    client = QdrantClient(":memory:")
    monkeypatch.setattr(client, "close", lambda: None)
    monkeypatch.setattr(update_payload, "connect", lambda url: client)
    yield client
    QdrantClient.close(client)


def test_main_success_and_missing_collection(offline, capsys):
    assert update_payload.main([], VALID) == 1
    captured = capsys.readouterr()
    assert "rag.ingest" in captured.err and captured.out == ""
    ensure_collection(offline, "recipes", FakeEmbedder.DIMENSION, "m")
    upsert_points(offline, "recipes", exercise_one_points())
    assert update_payload.main([], VALID) == 0
    assert capsys.readouterr().out == "Punti: 3 · aggiornati: 3 · con dosi: 1 · senza campo: 0\n"


def test_main_fails_when_points_stay_without_the_field(offline, capsys, monkeypatch):
    ensure_collection(offline, "recipes", FakeEmbedder.DIMENSION, "m")
    upsert_points(offline, "recipes", exercise_one_points())
    monkeypatch.setattr(update_payload, "count_missing", lambda client, name, field: 2)
    assert update_payload.main([], VALID) == 1
    captured = capsys.readouterr()
    assert "senza campo: 2" in captured.out
    assert "2 punti senza has_doses dopo l'aggiornamento: rieseguire python -m rag.update_payload" in captured.err


def test_main_invalid_configuration_is_a_message(capsys):
    assert update_payload.main([], {"EMBEDDING_MODEL": "m"}) == 1
    assert "LMSTUDIO_BASE_URL" in capsys.readouterr().err


def test_main_does_not_call_lm_studio():
    assert not hasattr(update_payload, "create_embedder")
    assert not hasattr(update_payload, "check_embedding_model")
