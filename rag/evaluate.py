"""python -m rag.evaluate [--k N] [--questions FILE] [--doses]: for every question with an expected
source, where the first chunk of an expected recipe appears among the k results. Markdown table on
stdout, identical for the same index, questions and options. --doses searches only the chunks with
a dose list, for every question.

Strategy, size and overlap in the header are read from the payload of the index (saved by the
ingestion); for an index built before they were saved, they come from the current configuration,
marked «(dalla configurazione)». The chunk header (title and chapter in the embedded text) is
read the same way; an index without it predates modification B, so it is «none»."""

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from rag.config import ConfigError, configure_logging, load_config
from rag.corpus import EXPECTED_RECIPES
from rag.embedder import EmbeddingError, check_embedding_model, create_embedder
from rag.search import DEFAULT_TOP_K, SearchError, SearchResult, format_score, search, validate
from rag.store import StoreError, connect, count_points, stored_chunking, stored_header

DEFAULT_QUESTIONS = Path(__file__).parent / "data" / "questions.json"
DASH = "—"
FROM_CONFIGURATION = " (dalla configurazione)"
# Before modification B no vector had the header: a missing field means none, not a guess.
BEFORE_MODIFICATION_B = "none (indice precedente alla modifica B)"


@dataclass(frozen=True)
class Question:
    question: str
    expected: tuple[int, ...]  # recipe numbers; empty: the book has no answer


@dataclass(frozen=True)
class Outcome:
    question: Question
    position: int | None  # rank of the first chunk of an expected recipe; None if absent
    source_score: float | None
    best_score: float | None


def load_questions(path: Path) -> list[Question]:
    """Reads the questions file; ValueError naming the file and the question's position."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"Impossibile leggere le domande '{path}': {error.strerror or error}.") from None
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Il file delle domande '{path}' non è un JSON valido: {error}.") from None
    if not isinstance(data, list) or not data:
        raise ValueError(f"Il file delle domande '{path}' deve contenere un elenco non vuoto.")
    questions = []
    for position, item in enumerate(data, start=1):
        where = f"'{path}', domanda {position}"
        if not isinstance(item, dict) or "question" not in item or "expected" not in item:
            raise ValueError(f"{where}: servono i campi 'question' ed 'expected'.")
        text, expected = item["question"], item["expected"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{where}: la domanda è vuota.")
        if not isinstance(expected, list) or not all(
            isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= EXPECTED_RECIPES
            for n in expected
        ):
            raise ValueError(
                f"{where}: 'expected' deve essere un elenco di numeri di ricetta da 1 a "
                f"{EXPECTED_RECIPES} (vuoto se il libro non ha la risposta)."
            )
        questions.append(Question(text.strip(), tuple(expected)))
    return questions


def evaluate_question(question: Question, results: Sequence[SearchResult]) -> Outcome:
    best = results[0].score if results else None
    for result in results:
        if result.recipe_number in question.expected:
            return Outcome(question, result.rank, result.score, best)
    return Outcome(question, None, None, best)


def _score(score: float | None) -> str:
    return DASH if score is None else format_score(score)


def format_report(header: Mapping[str, str], outcomes: Sequence[Outcome]) -> str:
    lines = [f"- **{key}:** {value}" for key, value in header.items()]
    lines += [
        "",
        "| Domanda | Fonte attesa | Posizione | Score fonte | Score migliore |",
        "|---|---|---|---|---|",
    ]
    for outcome in outcomes:
        expected = outcome.question.expected
        if not expected:
            position = DASH
        else:
            position = str(outcome.position) if outcome.position is not None else "assente"
        cells = [
            outcome.question.question.replace("|", "\\|"),
            ", ".join(str(n) for n in expected) if expected else DASH,
            position,
            _score(outcome.source_score),
            _score(outcome.best_score),
        ]
        lines.append(f"| {' | '.join(cells)} |")
    with_source = [o for o in outcomes if o.question.expected]
    found = sum(o.position is not None for o in with_source)
    lines += ["", f"Fonte attesa trovata in {found} casi su {len(with_source)}."]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] = os.environ) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rag.evaluate",
        description="Valuta la ricerca sulle domande con fonte attesa (tabella Markdown).",
    )
    parser.add_argument(
        "--k", type=int, default=DEFAULT_TOP_K,
        help=f"risultati per domanda (predefinito {DEFAULT_TOP_K})",
    )
    parser.add_argument(
        "--questions", type=Path, default=DEFAULT_QUESTIONS,
        help="file JSON delle domande (predefinito rag/data/questions.json)",
    )
    parser.add_argument(
        "--doses", action="store_true",
        help="cerca solo tra i chunk con un elenco di ingredienti, per ogni domanda",
    )
    args = parser.parse_args(argv)
    try:
        config = load_config(env)
        configure_logging(config.log_level)
        validate("domanda", args.k, None)  # k checked before contacting the services
        questions = load_questions(args.questions)
        check_embedding_model(config.base_url, config.embedding_model)
        client = connect(config.qdrant_url)
        try:
            embedder = create_embedder(config)
            outcomes = [
                evaluate_question(question, search(
                    client, embedder, config.collection, config.embedding_model,
                    question.question, args.k, doses=args.doses,
                ))
                for question in questions
            ]
            points = count_points(client, config.collection)
            chunking = stored_chunking(client, config.collection)
            chunk_header = stored_header(client, config.collection) or BEFORE_MODIFICATION_B
        finally:
            client.close()
    except (ConfigError, SearchError, ValueError, EmbeddingError, StoreError) as error:
        print(error, file=sys.stderr)
        return 1
    if chunking is None:
        strategy, size, overlap = (
            f"{value}{FROM_CONFIGURATION}"
            for value in (config.chunk_strategy, config.chunk_size, config.chunk_overlap)
        )
    else:
        strategy, size, overlap = (str(value) for value in chunking)
    header = {
        "modello": config.embedding_model,
        "collezione": config.collection,
        "punti": str(points),
        "strategia": strategy,
        "dimensione": size,
        "overlap": overlap,
        "intestazione dei chunk": chunk_header,
        "k": str(args.k),
        "filtro dosi": "sì" if args.doses else "no",
    }
    print(format_report(header, outcomes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
