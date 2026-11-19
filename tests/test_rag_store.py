"""Qdrant collection of the recipes, with the real client in memory: stable IDs, registered model,
removal of stale points, search filtered by chapter."""

import pytest

from conftest import FakeEmbedder
from rag.store import (
    ChunkPoint, StoreError, check_collection, connect, count_points, drop_collection,
    ensure_collection, point_id, query, remove_stale, upsert_points,
)


def payload(n, i, chapter="Zuppe", model="m", source="libro.txt"):
    return {"source": source, "recipe_number": n, "title": f"R{n}", "chapter": chapter,
            "chunk_index": i, "text": f"testo {n} {i}", "embedding_model": model}


def points(fake, specs, model="m", source="libro.txt"):
    items = [payload(n, i, c, model, source) for n, i, c in specs]
    vectors = fake.embed([p["text"] for p in items])
    return [ChunkPoint(point_id(source, p["recipe_number"], p["chunk_index"]), v, p)
            for p, v in zip(items, vectors)]


def test_point_id_is_stable_and_distinct():
    assert point_id("libro.txt", 89, 0) == point_id("libro.txt", 89, 0) != point_id("libro.txt", 89, 1)
    assert point_id("libro.txt", 89, 0) != point_id("altro.txt", 89, 0)
    assert point_id("libro.txt", 1, 10) != point_id("libro.txt", 11, 0)


def test_new_collection_is_empty(qdrant):
    assert count_points(qdrant, "c") == 0
    ensure_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
    assert count_points(qdrant, "c") == 0


def test_upsert_twice_keeps_the_count(qdrant):
    batch = points(FakeEmbedder(), [(1, 0, "Zuppe"), (1, 1, "Zuppe"), (2, 0, "Dolci")])
    for _ in range(2):
        ensure_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
        upsert_points(qdrant, "c", batch)
    assert count_points(qdrant, "c") == 3


def test_remove_stale_points(qdrant):
    ensure_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
    batch = points(FakeEmbedder(), [(1, 0, "Zuppe"), (1, 1, "Zuppe")])
    upsert_points(qdrant, "c", batch)
    assert remove_stale(qdrant, "c", "libro.txt", {batch[0].id}) == 1
    assert count_points(qdrant, "c") == 1


def test_remove_stale_only_touches_its_source(qdrant):
    ensure_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
    mine = points(FakeEmbedder(), [(n, 0, "Zuppe") for n in range(1, 4)])
    other = points(FakeEmbedder(), [(1, 0, "Zuppe")], source="altro.txt")
    upsert_points(qdrant, "c", mine + other)
    assert remove_stale(qdrant, "c", "libro.txt", set()) == 3
    assert count_points(qdrant, "c") == 1


def test_remove_stale_scrolls_past_one_page(qdrant):
    ensure_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
    batch = points(FakeEmbedder(), [(n, 0, "Zuppe") for n in range(1, 301)])
    upsert_points(qdrant, "c", batch)
    keep = {p.id for p in batch[:10]}
    assert remove_stale(qdrant, "c", "libro.txt", keep) == 290
    assert count_points(qdrant, "c") == 10


def test_other_model_is_blocked(qdrant):
    ensure_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
    upsert_points(qdrant, "c", points(FakeEmbedder(), [(1, 0, "Zuppe")]))
    for check in (ensure_collection, check_collection):
        with pytest.raises(StoreError, match="'m'.*'altro'.*--recreate"):
            check(qdrant, "c", FakeEmbedder.DIMENSION, "altro")


def test_other_dimension_is_blocked(qdrant):
    ensure_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
    upsert_points(qdrant, "c", points(FakeEmbedder(), [(1, 0, "Zuppe")]))
    for check in (ensure_collection, check_collection):
        with pytest.raises(StoreError, match="64.*32.*--recreate"):
            check(qdrant, "c", 32, "m")


def test_same_model_and_dimension_pass(qdrant):
    ensure_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
    upsert_points(qdrant, "c", points(FakeEmbedder(), [(1, 0, "Zuppe")]))
    ensure_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
    check_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")


def test_missing_or_empty_collection_for_search(qdrant):
    with pytest.raises(StoreError, match="rag.ingest"):
        check_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
    ensure_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
    with pytest.raises(StoreError, match="rag.ingest"):
        check_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")


def test_drop_collection(qdrant):
    drop_collection(qdrant, "c")                     # no error if missing
    ensure_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
    upsert_points(qdrant, "c", points(FakeEmbedder(), [(1, 0, "Zuppe")]))
    drop_collection(qdrant, "c")
    assert count_points(qdrant, "c") == 0


def test_query_filters_during_the_search(qdrant):
    fake = FakeEmbedder()
    ensure_collection(qdrant, "c", fake.DIMENSION, "m")
    upsert_points(qdrant, "c", points(fake, [(n, 0, "Zuppe") for n in range(1, 9)] + [(9, 0, "Dolci"), (10, 0, "Dolci")]))
    results = query(qdrant, "c", fake.embed(["testo 1 0"])[0], 2, "Dolci")
    assert len(results) == 2 and {p["chapter"] for _, p in results} == {"Dolci"}
    assert results[0][0] >= results[1][0]


def test_query_without_filter_is_ordered_by_score(qdrant):
    fake = FakeEmbedder()
    ensure_collection(qdrant, "c", fake.DIMENSION, "m")
    upsert_points(qdrant, "c", points(fake, [(n, 0, "Zuppe") for n in range(1, 9)]))
    results = query(qdrant, "c", fake.embed(["testo 3 0"])[0], 3, None)
    assert len(results) == 3 and results[0][1]["recipe_number"] == 3
    assert [score for score, _ in results] == sorted((score for score, _ in results), reverse=True)


def test_connect_refused():
    with pytest.raises(StoreError, match="127.0.0.1:9.*docker compose up -d qdrant"):
        connect("http://127.0.0.1:9")
