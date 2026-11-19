"""python -m rag.search "domanda" [--chapter NOME] [--k N] [--doses]: the k chunks nearest to a
question, with their source (recipe, title, chapter, chunk position) and whether they hold a dose list.

The question is embedded as it is, with the same method as the chunks; the chapter filter and the
--doses filter (has_doses = true) are applied by Qdrant during the search. With --doses, a collection
where some points lack has_doses is refused: they would be left out without saying so."""

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from rag.config import ConfigError, configure_logging, load_config
from rag.corpus import CHAPTERS
from rag.embedder import Embedder, EmbeddingError, check_embedding_model, create_embedder
from rag.store import StoreError, check_collection, connect, count_missing, query

DEFAULT_TOP_K = 5
MAX_TOP_K = 20
MISSING_DOSES = "Alcuni punti non hanno has_doses: eseguire python -m rag.update_payload"


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
    has_doses: bool = False


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
    doses: bool = False,
) -> list[SearchResult]:
    chapter_name = validate(question, k, chapter)
    vector = embedder.embed([question])[0]
    check_collection(client, collection, len(vector), model)
    if doses and count_missing(client, collection, "has_doses") > 0:
        raise StoreError(MISSING_DOSES)
    return [
        SearchResult(
            rank=rank,
            score=score,
            recipe_number=payload["recipe_number"],
            title=payload["title"],
            chapter=payload["chapter"],
            chunk_index=payload["chunk_index"],
            text=payload["text"],
            has_doses=payload.get("has_doses", False),
        )
        for rank, (score, payload) in enumerate(
            query(client, collection, vector, k, chapter_name, doses), start=1
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
            + (" · dosi" if result.has_doses else "")
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
    parser.add_argument(
        "--doses", action="store_true", help="solo i chunk con un elenco di ingredienti",
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
                args.question, args.k, args.chapter, args.doses,
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
