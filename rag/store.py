"""Qdrant collection of the recipe chunks: creation, model and dimension checks, upsert with stable
IDs, removal of stale points, count and search filtered by chapter.

Every function receives the client: in use QdrantClient(url=...), in the tests QdrantClient(":memory:").
The embedding model is registered in the payload of every point (works with any Qdrant version and
in memory); the vector size comes from the collection configuration."""

import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass

import httpx
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

CONNECT_TIMEOUT = 5  # seconds, also for the following calls
SCROLL_PAGE = 256
DELETE_BATCH = 256
INDEXES = {
    "chapter": models.PayloadSchemaType.KEYWORD,
    "recipe_number": models.PayloadSchemaType.INTEGER,
    "source": models.PayloadSchemaType.KEYWORD,
}
REINDEX = "per reindicizzare eseguire python -m rag.ingest --recreate"


class StoreError(Exception):
    """Qdrant unreachable, or a collection that cannot be used as it is."""


@dataclass(frozen=True)
class ChunkPoint:
    id: str
    vector: list[float]
    payload: dict


def point_id(source: str, recipe_number: int, chunk_index: int) -> str:
    """Same chunk, same ID: UUID version 5 of source, recipe number and chunk position."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source}#{recipe_number}#{chunk_index}"))


@contextmanager
def _qdrant_errors(action: str) -> Iterator[None]:
    try:
        yield
    except (ResponseHandlingException, UnexpectedResponse, httpx.HTTPError) as error:
        raise StoreError(f"Errore di Qdrant durante {action}: {error}") from None


def connect(url: str) -> QdrantClient:
    """Client for the Qdrant server at `url`, checked with a first request."""
    # Versions of client and image are pinned together (requirements.txt, compose.yaml): the
    # compatibility check would only add a warning when the server is down.
    client = QdrantClient(url=url, timeout=CONNECT_TIMEOUT, check_compatibility=False)
    try:
        client.get_collections()
    except (ResponseHandlingException, UnexpectedResponse, httpx.HTTPError, OSError):
        client.close()
        raise StoreError(
            f"Qdrant non raggiungibile su {url}: avviarlo con docker compose up -d qdrant"
        ) from None
    return client


def ensure_collection(client: QdrantClient, name: str, dimension: int, model: str) -> None:
    """Creates the collection (cosine, payload indexes) if missing; otherwise checks that its
    vectors have `dimension` and its points come from `model`."""
    with _qdrant_errors(f"la preparazione della collezione '{name}'"):
        if client.collection_exists(name):
            _check_model_and_dimension(client, name, dimension, model)
            return
        client.create_collection(
            name, vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE)
        )
        for field, schema in INDEXES.items():
            client.create_payload_index(name, field, field_schema=schema)


def check_collection(client: QdrantClient, name: str, dimension: int, model: str) -> None:
    """For search and evaluation: the collection exists, has points, and matches model and dimension."""
    if count_points(client, name) == 0:
        raise StoreError(
            f"La collezione '{name}' non esiste o è vuota: eseguire prima python -m rag.ingest"
        )
    with _qdrant_errors(f"il controllo della collezione '{name}'"):
        _check_model_and_dimension(client, name, dimension, model)


def _check_model_and_dimension(client: QdrantClient, name: str, dimension: int, model: str) -> None:
    stored_dimension = client.get_collection(name).config.params.vectors.size
    if stored_dimension != dimension:
        raise StoreError(
            f"La collezione '{name}' ha vettori di dimensione {stored_dimension}, il modello "
            f"'{model}' ne produce {dimension}: {REINDEX}"
        )
    found, _ = client.scroll(name, limit=1, with_payload=["embedding_model"], with_vectors=False)
    if found:
        stored_model = (found[0].payload or {}).get("embedding_model")
        if stored_model != model:
            raise StoreError(
                f"La collezione '{name}' contiene embedding di '{stored_model}', la configurazione "
                f"usa '{model}': {REINDEX}"
            )


def drop_collection(client: QdrantClient, name: str) -> None:
    with _qdrant_errors(f"la cancellazione della collezione '{name}'"):
        if client.collection_exists(name):
            client.delete_collection(name)


def count_points(client: QdrantClient, name: str) -> int:
    """Exact number of points; 0 if the collection is missing."""
    with _qdrant_errors(f"il conteggio dei punti di '{name}'"):
        if not client.collection_exists(name):
            return 0
        return client.count(name, exact=True).count


def upsert_points(client: QdrantClient, name: str, points: Sequence[ChunkPoint]) -> None:
    with _qdrant_errors(f"la scrittura dei punti in '{name}'"):
        client.upsert(
            name,
            points=[models.PointStruct(id=p.id, vector=p.vector, payload=p.payload) for p in points],
            wait=True,
        )


def remove_stale(client: QdrantClient, name: str, source: str, keep: set[str]) -> int:
    """Deletes the points of `source` whose ID is not in `keep`; returns how many."""
    source_filter = models.Filter(
        must=[models.FieldCondition(key="source", match=models.MatchValue(value=source))]
    )
    stale: list[str] = []
    with _qdrant_errors(f"la rimozione dei punti superati da '{name}'"):
        offset = None
        while True:
            page, offset = client.scroll(
                name, scroll_filter=source_filter, limit=SCROLL_PAGE, offset=offset,
                with_payload=False, with_vectors=False,
            )
            stale.extend(str(point.id) for point in page if str(point.id) not in keep)
            if offset is None:
                break
        for start in range(0, len(stale), DELETE_BATCH):
            client.delete(
                name,
                points_selector=models.PointIdsList(points=stale[start:start + DELETE_BATCH]),
                wait=True,
            )
    return len(stale)


def query(
    client: QdrantClient, name: str, vector: list[float], limit: int, chapter: str | None,
) -> list[tuple[float, dict]]:
    """The `limit` nearest points as (score, payload), best first; the chapter filter is applied
    by Qdrant during the search, not afterwards."""
    query_filter = None
    if chapter is not None:
        query_filter = models.Filter(
            must=[models.FieldCondition(key="chapter", match=models.MatchValue(value=chapter))]
        )
    with _qdrant_errors(f"la ricerca in '{name}'"):
        answer = client.query_points(
            name, query=vector, query_filter=query_filter, limit=limit,
            with_payload=True, with_vectors=False,
        )
    return [(point.score, point.payload or {}) for point in answer.points]
