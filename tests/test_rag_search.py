"""Top-k search with chapter filter, on recipes indexed in memory with the fake embedder."""

import pytest
from qdrant_client import QdrantClient, models

from conftest import FakeEmbedder
from rag import search as search_module
from rag.config import load_config
from rag.corpus import Recipe
from rag.ingest import run_ingest
from rag.search import (
    DEFAULT_TOP_K, MAX_TOP_K, SearchError, SearchResult, format_results, resolve_chapter, search,
)
from rag.store import StoreError

VALID = {"LMSTUDIO_BASE_URL": "http://127.0.0.1:1234/v1", "EMBEDDING_MODEL": "modello-scelto"}
DOSES = "\n\nOlio, grammi 100.\nSale, quanto basta."   # a dose list: has_doses true
RECIPES = [
    Recipe(1, "Pollo fritto", "Fritti", "Pollo fritto dorato nell'olio." + DOSES),
    Recipe(2, "Fritto misto", "Fritti", "Fritto misto di pollo e verdure." + DOSES),
    Recipe(3, "Carciofi fritti", "Fritti", "Carciofi fritti in pastella."),
    Recipe(4, "Frittelle", "Fritti", "Frittelle di riso con zucchero."),
    Recipe(5, "Cervello fritto", "Fritti", "Cervello fritto con limone."),
    Recipe(6, "Pollo lesso", "Lesso", "Pollo lesso con il brodo." + DOSES),
    Recipe(7, "Arrosto", "Arrosti", "Arrosto di vitella al forno."),
]


@pytest.fixture
def indexed(qdrant):
    run_ingest(load_config(VALID), RECIPES, qdrant, FakeEmbedder())
    return qdrant


def run(client, question="pollo", **kwargs):
    return search(client, FakeEmbedder(), "recipes", "modello-scelto", question, **kwargs)


def test_constants():
    assert (DEFAULT_TOP_K, MAX_TOP_K) == (5, 20)


def test_results_carry_the_source(indexed):
    results = run(indexed, "pollo lesso con il brodo", k=2)
    assert results[0] == SearchResult(
        rank=1, score=results[0].score, recipe_number=6, title="Pollo lesso", chapter="Lesso",
        chunk_index=0, text="Pollo lesso con il brodo." + DOSES, has_doses=True)
    assert len(results) == 2 and results[0].score >= results[1].score


def test_default_k(indexed):
    assert len(run(indexed)) == DEFAULT_TOP_K


def test_chapter_filter_returns_only_that_chapter(indexed):
    results = run(indexed, "pollo fritto", k=3, chapter="fritti")
    assert len(results) == 3 and {r.chapter for r in results} == {"Fritti"}
    assert [r.rank for r in results] == [1, 2, 3]


def test_chapter_filter_keeps_k_when_the_best_points_are_elsewhere(indexed):
    results = run(indexed, "pollo lesso con il brodo", k=5, chapter="Fritti")
    assert len(results) == 5 and 6 not in {r.recipe_number for r in results}


def test_chapter_with_fewer_points_than_k(indexed):
    results = run(indexed, "pollo", k=5, chapter="LESSO")
    assert [r.chapter for r in results] == ["Lesso"]


@pytest.mark.parametrize("k", [0, 21])
def test_k_out_of_range(indexed, k):
    with pytest.raises(SearchError, match="20"):
        run(indexed, k=k)


@pytest.mark.parametrize("question", ["", "   "])
def test_blank_question(indexed, question):
    with pytest.raises(SearchError, match="domanda"):
        run(indexed, question)


def test_doses_filter_returns_only_dose_chunks(indexed):
    results = run(indexed, "pollo", k=5, doses=True)
    assert sorted(r.recipe_number for r in results) == [1, 2, 6]
    assert all(r.has_doses for r in results)


def test_without_doses_the_flag_is_reported(indexed):
    results = run(indexed, "pollo", k=7)
    assert {r.recipe_number for r in results if r.has_doses} == {1, 2, 6}
    assert len(results) == 7


def test_doses_with_chapter(indexed):
    assert [r.recipe_number for r in run(indexed, "pollo", doses=True, chapter="Lesso")] == [6]


def test_doses_in_a_chapter_without_doses(indexed):
    assert run(indexed, "arrosto", doses=True, chapter="Arrosti") == []


def test_doses_on_points_without_the_field(indexed):
    indexed.delete_payload("recipes", keys=["has_doses"], points=models.Filter(), wait=True)
    with pytest.raises(StoreError) as error:
        run(indexed, doses=True)
    assert str(error.value) == "Alcuni punti non hanno has_doses: eseguire python -m rag.update_payload"
    assert len(run(indexed)) == DEFAULT_TOP_K


def test_other_model_is_blocked(indexed):
    with pytest.raises(StoreError, match="--recreate"):
        search(indexed, FakeEmbedder(), "recipes", "altro", "pollo")


def test_resolve_chapter_by_name_or_heading():
    assert resolve_chapter("minestre ASCIUTTE e di magro") == "Minestre asciutte e di magro"
    assert resolve_chapter(" BRODI, GELATINA E SUGHI ") == "Brodi, gelatina e sughi"


def test_unknown_chapter_lists_the_chapters():
    with pytest.raises(SearchError, match="'Frittate'.*Fritti.*Cose diverse"):
        resolve_chapter("Frittate")


def test_result_line():
    text = format_results([
        SearchResult(1, 0.7771, 89, "Gnocchi di patate", "Minestre asciutte e di magro", 0, "Testo\nseconda riga", True),
        SearchResult(2, 0.7, 90, "Gnocchi di farina gialla", "Minestre asciutte e di magro", 1, "Altro"),
    ])
    assert text.splitlines() == [
        "1. 0,777 · ricetta 89 «Gnocchi di patate» · Minestre asciutte e di magro · chunk 0 · dosi",
        "  Testo",
        "  seconda riga",
        "",
        "2. 0,700 · ricetta 90 «Gnocchi di farina gialla» · Minestre asciutte e di magro · chunk 1",
        "  Altro",
    ]


def test_no_results():
    assert format_results([]) == "Nessun risultato."


@pytest.fixture
def offline(monkeypatch, qdrant):
    monkeypatch.setattr(qdrant, "close", lambda: None)
    monkeypatch.setattr(search_module, "check_embedding_model", lambda *a, **k: None)
    monkeypatch.setattr(search_module, "connect", lambda url: qdrant)
    monkeypatch.setattr(search_module, "create_embedder", lambda config: FakeEmbedder())
    return qdrant


def test_main_without_ingestion(capsys, offline):
    assert search_module.main(["pollo"], VALID) == 1
    assert "rag.ingest" in capsys.readouterr().err


def test_main_prints_the_results(capsys, offline):
    run_ingest(load_config(VALID), RECIPES, offline, FakeEmbedder())
    assert search_module.main(["pollo lesso", "--chapter", "Lesso", "--k", "3", "--doses"], VALID) == 0
    assert capsys.readouterr().out.splitlines()[0].endswith("· ricetta 6 «Pollo lesso» · Lesso · chunk 0 · dosi")


@pytest.mark.parametrize("argv, message", [
    (["pollo", "--k", "21"], "20"),
    (["pollo", "--chapter", "Frittate"], "Cose diverse"),
    (["  "], "domanda"),
])
def test_main_rejects_before_calling_the_services(capsys, monkeypatch, argv, message):
    def unexpected(*args, **kwargs):
        raise AssertionError("servizio contattato")

    monkeypatch.setattr(search_module, "check_embedding_model", unexpected)
    monkeypatch.setattr(search_module, "connect", unexpected)
    assert search_module.main(argv, VALID) == 1
    assert message in capsys.readouterr().err
