"""python -m rag.search "domanda" [--chapter NOME] [--k N]: the k chunks nearest to a question,
with their source (recipe, title, chapter, chunk position).

The question is embedded as it is, with the same method as the chunks; the chapter filter is
applied by Qdrant during the search."""

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from rag.config import ConfigError, configure_logging, load_config
from rag.corpus import CHAPTERS
from rag.embedder import Embedder, EmbeddingError, check_embedding_model, create_embedder
from rag.store import StoreError, check_collection, connect, query

DEFAULT_TOP_K = 5
MAX_TOP_K = 20


class SearchError(Exception):
    """Invalid question, k or chapter."""


@dataclass(frozen=True)
class SearchResult:
    rank: int
    score: float
    recipe_number: int
    title: str
    chapter: str
    chunk_index: int
    text: str


def resolve_chapter(name: str) -> str:
    """The saved name of one of the 23 chapters, ignoring case; SearchError listing them otherwise."""
    wanted = name.strip().casefold()
    for chapter in CHAPTERS:
        if wanted in (chapter.name.casefold(), chapter.heading.casefold()):
            return chapter.name
    names = ", ".join(chapter.name for chapter in CHAPTERS)
    raise SearchError(f"Capitolo sconosciuto: '{name.strip()}'. Capitoli: {names}.")


def validate(question: str, k: int, chapter: str | None) -> str | None:
    """Checks question and k; returns the saved chapter name (None: no filter)."""
    if not question.strip():
        raise SearchError("La domanda è vuota.")
    if not 1 <= k <= MAX_TOP_K:
        raise SearchError(f"k deve essere un intero da 1 a {MAX_TOP_K}, ricevuto {k}.")
    return None if chapter is None else resolve_chapter(chapter)


def search(
    client,
    embedder: Embedder,
    collection: str,
    model: str,
    question: str,
    k: int = DEFAULT_TOP_K,
    chapter: str | None = None,
) -> list[SearchResult]:
    chapter_name = validate(question, k, chapter)
    vector = embedder.embed([question])[0]
    check_collection(client, collection, len(vector), model)
    return [
        SearchResult(
            rank=rank,
            score=score,
            recipe_number=payload["recipe_number"],
            title=payload["title"],
            chapter=payload["chapter"],
            chunk_index=payload["chunk_index"],
            text=payload["text"],
        )
        for rank, (score, payload) in enumerate(
            query(client, collection, vector, k, chapter_name), start=1
        )
    ]


def format_score(score: float) -> str:
    """Three decimals with the decimal comma: 0.7771 → 0,777."""
    return f"{score:.3f}".replace(".", ",")


def format_results(results: Sequence[SearchResult]) -> str:
    if not results:
        return "Nessun risultato."
    blocks = []
    for result in results:
        header = (
            f"{result.rank}. {format_score(result.score)} · ricetta {result.recipe_number} "
            f"«{result.title}» · {result.chapter} · chunk {result.chunk_index}"
        )
        body = "\n".join(f"  {line}" if line else "" for line in result.text.splitlines())
        blocks.append(f"{header}\n{body}")
    return "\n\n".join(blocks)


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] = os.environ) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rag.search",
        description="Cerca nelle ricette indicizzate i passaggi più vicini a una domanda.",
    )
    parser.add_argument("question", help="la domanda, tra virgolette")
    parser.add_argument("--chapter", help="solo i risultati di questo capitolo (es. Fritti)")
    parser.add_argument(
        "--k", type=int, default=DEFAULT_TOP_K,
        help=f"numero di risultati, da 1 a {MAX_TOP_K} (predefinito {DEFAULT_TOP_K})",
    )
    args = parser.parse_args(argv)
    try:
        config = load_config(env)
        configure_logging(config.log_level)
        validate(args.question, args.k, args.chapter)  # before contacting the services
        check_embedding_model(config.base_url, config.embedding_model)
        client = connect(config.qdrant_url)
        try:
            results = search(
                client, create_embedder(config), config.collection, config.embedding_model,
                args.question, args.k, args.chapter,
            )
        finally:
            client.close()
    except (ConfigError, SearchError, EmbeddingError, StoreError) as error:
        print(error, file=sys.stderr)
        return 1
    print(format_results(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
