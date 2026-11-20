"""Qdrant collection of the recipes, with the real client in memory: stable IDs, registered model,
removal of stale points, search filtered by chapter and by `has_doses`, payload updates."""

import pytest

from conftest import FakeEmbedder
from rag.store import (
    ChunkPoint, StoreError, check_collection, connect, count_missing, count_points, drop_collection,
    ensure_collection, iter_texts, point_id, query, remove_stale, set_field, stored_chunking,
    stored_header, upsert_points,
)
from rag import store
from qdrant_client import models


def payload(n, i, chapter="Zuppe", model="m", source="libro.txt", has_doses=None):
    fields = {"source": source, "recipe_number": n, "title": f"R{n}", "chapter": chapter,
              "chunk_index": i, "text": f"testo {n} {i}", "embedding_model": model}
    if has_doses is not None:
        fields["has_doses"] = has_doses
    return fields


def points(fake, specs, model="m", source="libro.txt", doses=None):
    """`doses`: None leaves `has_doses` out (payload of exercise 1); otherwise the set of recipe
    numbers whose chunks have it true, the others false."""
    items = [payload(n, i, c, model, source, None if doses is None else n in doses)
             for n, i, c in specs]
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


def test_indexes_are_added_to_an_existing_collection(qdrant, monkeypatch):
    # The local client does not keep payload indexes (payload_schema stays empty): record the calls.
    qdrant.create_collection(
        "c", vectors_config=models.VectorParams(size=FakeEmbedder.DIMENSION, distance=models.Distance.COSINE)
    )
    upsert_points(qdrant, "c", points(FakeEmbedder(), [(1, 0, "Zuppe")]))
    created = {}
    monkeypatch.setattr(qdrant, "create_payload_index",
                        lambda name, field, field_schema: created.setdefault(field, field_schema))
    ensure_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
    assert created["has_doses"] == models.PayloadSchemaType.BOOL
    assert set(created) == {"chapter", "recipe_number", "source", "has_doses"}


def test_indexes_already_present_are_not_created_again(qdrant, monkeypatch):
    ensure_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
    present = {field: models.PayloadIndexInfo(data_type=schema, points=0)
               for field, schema in store.INDEXES.items()}
    info = qdrant.get_collection("c").model_copy(update={"payload_schema": present})
    monkeypatch.setattr(qdrant, "get_collection", lambda name: info)
    monkeypatch.setattr(qdrant, "create_payload_index",
                        lambda *a, **k: pytest.fail("index created again"))
    store.ensure_indexes(qdrant, "c")


def dose_collection(qdrant, specs, doses):
    fake = FakeEmbedder()
    ensure_collection(qdrant, "c", fake.DIMENSION, "m")
    upsert_points(qdrant, "c", points(fake, specs, doses=doses))
    return fake


def test_query_with_doses_returns_only_true(qdrant):
    fake = dose_collection(qdrant, [(n, 0, "Zuppe") for n in range(1, 7)], doses={2, 5})
    results = query(qdrant, "c", fake.embed(["testo 1 0"])[0], 5, None, doses=True)
    assert sorted(p["recipe_number"] for _, p in results) == [2, 5]
    assert all(p["has_doses"] is True for _, p in results)


def test_query_with_doses_and_chapter(qdrant):
    specs = [(1, 0, "Zuppe"), (2, 0, "Zuppe"), (3, 0, "Dolci"), (4, 0, "Dolci")]
    fake = dose_collection(qdrant, specs, doses={1, 3, 4})
    results = query(qdrant, "c", fake.embed(["testo 1 0"])[0], 5, "Dolci", doses=True)
    assert sorted(p["recipe_number"] for _, p in results) == [3, 4]


def test_query_without_doses_keeps_false_points(qdrant):
    fake = dose_collection(qdrant, [(n, 0, "Zuppe") for n in range(1, 4)], doses={2})
    assert len(query(qdrant, "c", fake.embed(["testo 1 0"])[0], 5, None)) == 3


def test_count_missing(qdrant):
    fake = FakeEmbedder()
    ensure_collection(qdrant, "c", fake.DIMENSION, "m")
    upsert_points(qdrant, "c", points(fake, [(1, 0, "Zuppe"), (2, 0, "Zuppe")]))
    upsert_points(qdrant, "c", points(fake, [(3, 0, "Zuppe")], doses=set()))   # has_doses false
    assert count_missing(qdrant, "c", "has_doses") == 2


def test_iter_texts_past_one_page(qdrant, monkeypatch):
    monkeypatch.setattr(store, "SCROLL_PAGE", 2)
    fake = FakeEmbedder()
    ensure_collection(qdrant, "c", fake.DIMENSION, "m")
    batch = points(fake, [(n, 0, "Zuppe") for n in range(1, 4)])
    upsert_points(qdrant, "c", batch)
    assert dict(iter_texts(qdrant, "c")) == {p.id: p.payload["text"] for p in batch}


def test_set_field_keeps_vector_and_other_fields(qdrant):
    fake = FakeEmbedder()
    ensure_collection(qdrant, "c", fake.DIMENSION, "m")
    batch = points(fake, [(1, 0, "Zuppe"), (2, 0, "Zuppe")])
    upsert_points(qdrant, "c", batch)
    ids = [p.id for p in batch]
    before = {p.id: p for p in qdrant.retrieve("c", ids, with_payload=True, with_vectors=True)}
    set_field(qdrant, "c", "has_doses", True, [ids[0]])
    after = {p.id: p for p in qdrant.retrieve("c", ids, with_payload=True, with_vectors=True)}
    assert after[ids[0]].vector == before[ids[0]].vector
    assert after[ids[0]].payload == {**before[ids[0]].payload, "has_doses": True}
    assert after[ids[1]].payload == before[ids[1]].payload


def test_set_field_in_batches(qdrant, monkeypatch):
    monkeypatch.setattr(store, "DELETE_BATCH", 2)
    fake = FakeEmbedder()
    ensure_collection(qdrant, "c", fake.DIMENSION, "m")
    batch = points(fake, [(n, 0, "Zuppe") for n in range(1, 6)])
    upsert_points(qdrant, "c", batch)
    calls = []
    original = qdrant.set_payload
    monkeypatch.setattr(qdrant, "set_payload", lambda *a, **k: calls.append(k) or original(*a, **k))
    set_field(qdrant, "c", "has_doses", False, [p.id for p in batch])
    assert len(calls) == 3 and count_missing(qdrant, "c", "has_doses") == 0


def test_stored_chunking(qdrant):
    fake = FakeEmbedder()
    ensure_collection(qdrant, "c", fake.DIMENSION, "m")
    assert stored_chunking(qdrant, "c") is None                       # no points
    upsert_points(qdrant, "c", points(fake, [(1, 0, "Zuppe")]))
    assert stored_chunking(qdrant, "c") is None                       # payload of exercise 1
    point = points(fake, [(2, 0, "Zuppe")])[0]
    point.payload.update(chunk_strategy="paragraph", chunk_size=1200, chunk_overlap=200)
    qdrant.delete_collection("c")
    ensure_collection(qdrant, "c", fake.DIMENSION, "m")
    upsert_points(qdrant, "c", [point])
    assert stored_chunking(qdrant, "c") == ("paragraph", 1200, 200)


def test_stored_header(qdrant):
    fake = FakeEmbedder()
    ensure_collection(qdrant, "c", fake.DIMENSION, "m")
    assert stored_header(qdrant, "c") is None                         # no points
    upsert_points(qdrant, "c", points(fake, [(1, 0, "Zuppe")]))
    assert stored_header(qdrant, "c") is None                         # payload before modification B
    point = points(fake, [(2, 0, "Zuppe")])[0]
    point.payload.update(chunk_header="none")
    qdrant.delete_collection("c")
    ensure_collection(qdrant, "c", fake.DIMENSION, "m")
    upsert_points(qdrant, "c", [point])
    assert stored_header(qdrant, "c") == "none"
