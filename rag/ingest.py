"""python -m rag.ingest [--recreate]: indexes the recipes of the book in Qdrant.

Repeatable: stable IDs and upsert, then the points of the same source not written in this run are
removed, so the number of points is always the number of current chunks. --recreate deletes the
collection first (to change the embedding model).

Every point records, besides source, recipe, chapter, text and model, whether the chunk holds a dose
list (`has_doses`, rule in rag/doses.py) and the chunking parameters used (`chunk_strategy`,
`chunk_size`, `chunk_overlap`, `chunk_header`), which the evaluation reads back from the index.

The vector is computed from the text preceded by title and chapter of the recipe (CHUNK_HEADER,
rag.chunking.indexed_text); the payload keeps the original text. Changing CHUNK_HEADER and running
again rewrites every point with the same IDs."""

import argparse
import logging
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from rag.chunking import indexed_text, split_recipe
from rag.config import ConfigError, RagConfig, configure_logging, load_config
from rag.corpus import CorpusError, Recipe, load_corpus
from rag.doses import has_doses
from rag.embedder import Embedder, EmbeddingError, check_embedding_model, create_embedder
from rag.store import (
    ChunkPoint, StoreError, connect, count_points, drop_collection, ensure_collection, point_id,
    remove_stale, upsert_points,
)

logger = logging.getLogger(__name__)
PROBE_TEXT = "prova"  # embedded once to learn the vector size of the model


@dataclass(frozen=True)
class IngestReport:
    recipes: int
    chunks: int
    points_before: int
    points_after: int
    removed: int


def run_ingest(
    config: RagConfig,
    recipes: Sequence[Recipe],
    client,
    embedder: Embedder,
    recreate: bool = False,
) -> IngestReport:
    """Chunks, embeds (in batches of config.batch_size) and upserts every recipe, batch by batch;
    stale points are removed only after the last batch."""
    source = Path(config.corpus_file).name
    dimension = len(embedder.embed([PROBE_TEXT])[0])
    if recreate:
        drop_collection(client, config.collection)
    ensure_collection(client, config.collection, dimension, config.embedding_model)
    points_before = count_points(client, config.collection)

    payloads = [
        {
            "source": source,
            "recipe_number": recipe.number,
            "title": recipe.title,
            "chapter": recipe.chapter,
            "chunk_index": chunk.chunk_index,
            "text": chunk.text,
            "embedding_model": config.embedding_model,
            "has_doses": has_doses(chunk.text),
            "chunk_strategy": config.chunk_strategy,
            "chunk_size": config.chunk_size,
            "chunk_overlap": config.chunk_overlap,
            "chunk_header": config.chunk_header,
        }
        for recipe in recipes
        for chunk in split_recipe(
            recipe.text, config.chunk_strategy, config.chunk_size, config.chunk_overlap
        )
    ]
    written: set[str] = set()
    batches = range(0, len(payloads), config.batch_size)
    for number, start in enumerate(batches, start=1):
        batch = payloads[start:start + config.batch_size]
        vectors = embedder.embed([
            indexed_text(p["title"], p["chapter"], p["text"], p["chunk_header"]) for p in batch
        ])
        points = [
            ChunkPoint(point_id(source, p["recipe_number"], p["chunk_index"]), vector, p)
            for p, vector in zip(batch, vectors, strict=True)
        ]
        upsert_points(client, config.collection, points)
        written.update(point.id for point in points)
        logger.info("Lotto %d di %d: %d chunk scritti.", number, len(batches), len(written))

    removed = remove_stale(client, config.collection, source, written)
    return IngestReport(
        recipes=len(recipes),
        chunks=len(payloads),
        points_before=points_before,
        points_after=count_points(client, config.collection),
        removed=removed,
    )


def format_report(report: IngestReport) -> str:
    return (
        f"Ricette: {report.recipes} · chunk: {report.chunks} · punti prima: "
        f"{report.points_before} · punti dopo: {report.points_after} · rimossi: {report.removed}"
    )


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] = os.environ) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rag.ingest",
        description="Indicizza le ricette del libro in Qdrant (ripetibile, senza duplicati).",
    )
    parser.add_argument(
        "--recreate", action="store_true",
        help="cancella la collezione prima di cominciare (per cambiare modello di embedding)",
    )
    args = parser.parse_args(argv)
    try:
        config = load_config(env)
        configure_logging(config.log_level)
        recipes = load_corpus(config.corpus_file)  # first: needs no service
        check_embedding_model(config.base_url, config.embedding_model)
        client = connect(config.qdrant_url)
        try:
            report = run_ingest(config, recipes, client, create_embedder(config), args.recreate)
        finally:
            client.close()
    except (ConfigError, CorpusError, EmbeddingError, StoreError) as error:
        print(error, file=sys.stderr)
        return 1
    print(format_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
