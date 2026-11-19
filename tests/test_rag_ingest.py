"""Repeatable ingestion with Qdrant in memory and the fake embedder: no duplicates, stale points
removed, interrupted runs, --recreate, and the command's messages."""

from dataclasses import replace

import pytest
from qdrant_client import QdrantClient

from conftest import FakeEmbedder
from rag import ingest
from rag.config import load_config
from rag.corpus import Recipe
from rag.embedder import EmbeddingError
from rag.ingest import IngestReport, format_report, run_ingest
from rag.store import StoreError, count_points, query

VALID = {"LMSTUDIO_BASE_URL": "http://127.0.0.1:1234/v1", "EMBEDDING_MODEL": "modello-scelto"}
config = load_config({**VALID, "CHUNK_SIZE": "100", "CHUNK_OVERLAP": "20", "EMBEDDING_BATCH_SIZE": "2"})

LONG_TEXT = " ".join(f"parola{i:02d}" for i in range(18))   # 161 characters: two chunks of at most 100
RECIPES = [
    Recipe(1, "Brodo", "Brodi, gelatina e sughi", "Brodo di carne con sedano e carota."),
    Recipe(2, "Minestra lunga", "Minestre in brodo", LONG_TEXT),
    Recipe(3, "Torta", "Torte e dolci al cucchiaio", "Torta di mandorle con zucchero."),
]


class FailingEmbedder(FakeEmbedder):
    """FakeEmbedder that raises EmbeddingError at call number `fail_on_call`."""

    def __init__(self, fail_on_call: int) -> None:
        super().__init__()
        self.fail_on_call = fail_on_call

    def embed(self, texts):
        if len(self.calls) + 1 == self.fail_on_call:
            self.calls.append(list(texts))
            raise EmbeddingError("LM Studio non raggiungibile su http://127.0.0.1:1234/v1.")
        return super().embed(texts)


def test_first_run_writes_one_point_per_chunk(qdrant):
    embedder = FakeEmbedder()
    report = run_ingest(config, RECIPES, qdrant, embedder)
    assert report == IngestReport(recipes=3, chunks=4, points_before=0, points_after=4, removed=0)
    assert embedder.calls[0] == ["prova"] and [len(c) for c in embedder.calls[1:]] == [2, 2]


def test_two_runs_same_points(qdrant):
    first = run_ingest(config, RECIPES, qdrant, FakeEmbedder())
    second = run_ingest(config, RECIPES, qdrant, FakeEmbedder())
    assert first.points_after == second.points_after == second.points_before == first.chunks
    assert second.removed == 0


def test_shorter_recipe_removes_its_old_chunks(qdrant):
    run_ingest(config, RECIPES, qdrant, FakeEmbedder())
    shorter = [replace(r, text=r.text[:50]) for r in RECIPES]
    report = run_ingest(config, shorter, qdrant, FakeEmbedder())
    assert report.points_after == report.chunks == 3 and report.removed == 1


def test_interrupted_run_then_rerun_has_no_duplicates(qdrant):
    with pytest.raises(EmbeddingError):
        run_ingest(config, RECIPES, qdrant, FailingEmbedder(fail_on_call=3))  # probe + 1 batch, then error
    assert count_points(qdrant, "recipes") == 2
    report = run_ingest(config, RECIPES, qdrant, FakeEmbedder())
    assert (report.points_before, report.points_after, report.removed) == (2, report.chunks, 0)


def test_payload_of_a_point(qdrant):
    run_ingest(config, RECIPES, qdrant, FakeEmbedder())
    (_, payload), = query(qdrant, "recipes", FakeEmbedder().embed([RECIPES[0].text])[0], 1, None)
    assert payload == {
        "source": "Ricettario.txt", "recipe_number": 1, "title": "Brodo",
        "chapter": "Brodi, gelatina e sughi", "chunk_index": 0,
        "text": "Brodo di carne con sedano e carota.", "embedding_model": "modello-scelto",
        "has_doses": False, "chunk_strategy": "paragraph", "chunk_size": 100, "chunk_overlap": 20,
    }


def test_payload_marks_the_dose_list(qdrant):
    text = "Farina, grammi 200.\nUova, N. 2.\n\nImpastate."
    run_ingest(config, [*RECIPES, Recipe(4, "Pasta", "Paste", text)], qdrant, FakeEmbedder())
    (_, payload), = query(qdrant, "recipes", FakeEmbedder().embed([text])[0], 1, None)
    assert payload["recipe_number"] == 4 and payload["has_doses"] is True


def test_other_model_needs_recreate(qdrant):
    run_ingest(config, RECIPES, qdrant, FakeEmbedder())
    with pytest.raises(StoreError, match="--recreate"):
        run_ingest(replace(config, embedding_model="altro"), RECIPES, qdrant, FakeEmbedder())


def test_recreate_starts_from_an_empty_collection(qdrant):
    run_ingest(config, RECIPES, qdrant, FakeEmbedder())
    report = run_ingest(replace(config, embedding_model="altro"), RECIPES, qdrant, FakeEmbedder(), recreate=True)
    assert report.points_before == 0 and report.points_after == report.chunks


def test_report_line():
    assert format_report(IngestReport(790, 2950, 0, 2950, 0)) == (
        "Ricette: 790 · chunk: 2950 · punti prima: 0 · punti dopo: 2950 · rimossi: 0")


@pytest.fixture
def offline(monkeypatch):
    """main() with LM Studio and Qdrant replaced: the model check passes, Qdrant is in memory.
    main closes its client: here close() does nothing, so every run sees the same points (the
    local on-disk mode is not usable: it brings points back after delete_collection)."""
    client = QdrantClient(":memory:")
    monkeypatch.setattr(client, "close", lambda: None)
    monkeypatch.setattr(ingest, "check_embedding_model", lambda *a, **k: None)
    monkeypatch.setattr(ingest, "connect", lambda url: client)
    monkeypatch.setattr(ingest, "create_embedder", lambda config: FakeEmbedder())
    yield client
    QdrantClient.close(client)


def test_main_missing_corpus_is_a_message(tmp_path, capsys, offline):
    code = ingest.main([], {**VALID, "CORPUS_FILE": str(tmp_path / "manca.txt")})
    captured = capsys.readouterr()
    assert code == 1 and "manca.txt" in captured.err and "Traceback" not in captured.err


def test_main_invalid_configuration_is_a_message(capsys):
    assert ingest.main([], {"EMBEDDING_MODEL": "m"}) == 1
    assert "LMSTUDIO_BASE_URL" in capsys.readouterr().err


def test_main_lm_studio_off_is_a_message(capsys, monkeypatch):
    monkeypatch.setattr(ingest, "load_corpus", lambda path: RECIPES)

    def refuse(*args, **kwargs):
        raise EmbeddingError("LM Studio non raggiungibile su http://127.0.0.1:1234/v1.")

    monkeypatch.setattr(ingest, "check_embedding_model", refuse)
    assert ingest.main([], VALID) == 1
    assert "LM Studio non raggiungibile" in capsys.readouterr().err


def test_main_success_prints_the_counts(capsys, monkeypatch, offline):
    monkeypatch.setattr(ingest, "load_corpus", lambda path: RECIPES)
    env = {**VALID, "CHUNK_SIZE": "100", "CHUNK_OVERLAP": "20"}
    assert ingest.main([], env) == 0
    assert ingest.main([], env) == 0
    assert ingest.main(["--recreate"], env) == 0
    assert capsys.readouterr().out.splitlines() == [
        "Ricette: 3 · chunk: 4 · punti prima: 0 · punti dopo: 4 · rimossi: 0",
        "Ricette: 3 · chunk: 4 · punti prima: 4 · punti dopo: 4 · rimossi: 0",
        "Ricette: 3 · chunk: 4 · punti prima: 0 · punti dopo: 4 · rimossi: 0",
    ]
