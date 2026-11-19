"""Real test of the recipe search: LM Studio with the chosen embedding model and the Qdrant of
Compose (docker compose up -d qdrant). Run with: pytest tests/test_rag_real.py -m real -v

Indexes recipes 85-95 of the real book in a test collection, deleted at the end."""

import os
import uuid
from dataclasses import replace
from pathlib import Path

import pytest

from rag.config import load_config
from rag.corpus import load_corpus
from rag.embedder import check_embedding_model, create_embedder
from rag.ingest import run_ingest
from rag.search import search
from rag.store import connect, count_points, drop_collection

pytestmark = pytest.mark.real

BOOK = Path("data/Ricettario.txt")


@pytest.fixture
def setup():
    missing = [name for name in ("LMSTUDIO_BASE_URL", "EMBEDDING_MODEL") if not os.environ.get(name)]
    if missing:
        pytest.skip(f"variabili non impostate: {', '.join(missing)}")
    if not BOOK.exists():
        pytest.skip("data/Ricettario.txt non presente")
    config = load_config(os.environ)
    config = replace(config, collection=f"recipes_test_{uuid.uuid4().hex[:8]}", corpus_file=str(BOOK))
    check_embedding_model(config.base_url, config.embedding_model)
    client = connect(config.qdrant_url)
    recipes = [r for r in load_corpus(BOOK) if 85 <= r.number <= 95]
    try:
        yield config, client, recipes
    finally:
        drop_collection(client, config.collection)
        client.close()


def test_ingestion_twice_then_search(setup):
    config, client, recipes = setup
    embedder = create_embedder(config)
    first = run_ingest(config, recipes, client, embedder)
    second = run_ingest(config, recipes, client, embedder)
    assert first.points_after == second.points_after == second.points_before == first.chunks
    assert second.removed == 0 and count_points(client, config.collection) == first.chunks

    results = search(client, embedder, config.collection, config.embedding_model,
                     "Quanta farina per gli gnocchi di patate?", k=5)
    assert 89 in [r.recipe_number for r in results]

    filtered = search(client, embedder, config.collection, config.embedding_model,
                      "Quanta farina per gli gnocchi di patate?", k=5,
                      chapter="Minestre asciutte e di magro")
    assert filtered and {r.chapter for r in filtered} == {"Minestre asciutte e di magro"}


def test_recreate_on_the_server_starts_empty(setup):
    config, client, recipes = setup
    embedder = create_embedder(config)
    run_ingest(config, recipes[:3], client, embedder)
    report = run_ingest(config, recipes[:3], client, embedder, recreate=True)
    assert report.points_before == 0 and report.points_after == report.chunks
