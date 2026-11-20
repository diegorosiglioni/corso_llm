"""Configuration of the recipe pipeline, read from environment variables, and the logging setup."""

import logging
import sys
from collections.abc import Mapping
from dataclasses import dataclass

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
CHUNK_STRATEGIES = ("paragraph", "window")
CHUNK_HEADERS = ("title_chapter", "none")  # what precedes each chunk in the embedded text
MIN_CHUNK_SIZE = 100
# Libraries whose INFO logs (HTTP requests) are hidden unless LOG_LEVEL=DEBUG.
QUIET_LIBRARIES = ("httpx", "httpx2", "openai", "qdrant_client")  # openai 3.x uses httpx2


@dataclass(frozen=True)
class RagConfig:
    base_url: str  # LMSTUDIO_BASE_URL (required)
    embedding_model: str  # EMBEDDING_MODEL (required, chosen by the user: no default)
    qdrant_url: str = "http://127.0.0.1:6333"  # QDRANT_URL
    collection: str = "recipes"  # QDRANT_COLLECTION
    corpus_file: str = "data/Ricettario.txt"  # CORPUS_FILE
    chunk_strategy: str = "paragraph"  # CHUNK_STRATEGY (paragraph or window)
    chunk_size: int = 1200  # CHUNK_SIZE (characters, >= 100)
    chunk_overlap: int = 200  # CHUNK_OVERLAP (characters, 0 .. CHUNK_SIZE // 2)
    chunk_header: str = "title_chapter"  # CHUNK_HEADER (title_chapter or none)
    batch_size: int = 32  # EMBEDDING_BATCH_SIZE (>= 1)
    log_level: str = "INFO"  # LOG_LEVEL


class ConfigError(Exception):
    """Invalid configuration; the message lists every problem, one per line."""


def load_config(env: Mapping[str, str]) -> RagConfig:
    """Reads and validates the configuration; empty or blank values count as missing."""
    defaults = RagConfig(base_url="", embedding_model="")
    problems: list[str] = []

    def read(name: str) -> str:
        return env.get(name, "").strip()

    def read_url(name: str, default: str | None) -> str:
        url = read(name) or default or ""
        if not url:
            problems.append(f"Manca {name}.")
        elif not url.startswith(("http://", "https://")):
            problems.append(f"{name} deve iniziare con http:// o https://, ricevuto '{url}'.")
        return url

    def read_int(name: str, default: int, minimum: int, maximum: int | None = None) -> int:
        text = read(name)
        if not text:
            return default
        try:
            value = int(text)
        except ValueError:
            value = None
        if value is None or value < minimum or (maximum is not None and value > maximum):
            limits = f"tra {minimum} e {maximum}" if maximum is not None else f"≥ {minimum}"
            problems.append(f"{name} deve essere un intero {limits}, ricevuto '{text}'.")
            return default
        return value

    base_url = read_url("LMSTUDIO_BASE_URL", None)
    embedding_model = read("EMBEDDING_MODEL")
    if not embedding_model:
        problems.append(
            "Manca EMBEDDING_MODEL: l'identificativo del modello di embedding restituito da "
            "GET /v1/models di LM Studio."
        )
    qdrant_url = read_url("QDRANT_URL", defaults.qdrant_url)
    collection = read("QDRANT_COLLECTION") or defaults.collection
    corpus_file = read("CORPUS_FILE") or defaults.corpus_file

    strategy = read("CHUNK_STRATEGY").lower() or defaults.chunk_strategy
    if strategy not in CHUNK_STRATEGIES:
        problems.append(
            f"CHUNK_STRATEGY deve essere uno tra {', '.join(CHUNK_STRATEGIES)}, ricevuto '{strategy}'."
        )
    size = read_int("CHUNK_SIZE", defaults.chunk_size, MIN_CHUNK_SIZE)
    overlap = read_int("CHUNK_OVERLAP", defaults.chunk_overlap, 0, size // 2)
    header = read("CHUNK_HEADER").lower() or defaults.chunk_header
    if header not in CHUNK_HEADERS:
        problems.append(
            f"CHUNK_HEADER deve essere uno tra {', '.join(CHUNK_HEADERS)}, ricevuto '{header}'."
        )
    batch_size = read_int("EMBEDDING_BATCH_SIZE", defaults.batch_size, 1)

    log_level = read("LOG_LEVEL").upper() or defaults.log_level
    if log_level not in LOG_LEVELS:
        problems.append(
            f"LOG_LEVEL deve essere uno tra {', '.join(LOG_LEVELS)}, ricevuto '{read('LOG_LEVEL')}'."
        )

    if problems:
        raise ConfigError("\n".join(problems))
    return RagConfig(
        base_url=base_url, embedding_model=embedding_model, qdrant_url=qdrant_url,
        collection=collection, corpus_file=corpus_file, chunk_strategy=strategy,
        chunk_size=size, chunk_overlap=overlap, chunk_header=header, batch_size=batch_size,
        log_level=log_level,
    )


def configure_logging(log_level: str) -> None:
    """Logs on stderr (results are on stdout); libraries quiet unless DEBUG."""
    logging.basicConfig(
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=log_level,
    )
    if log_level != "DEBUG":
        for library in QUIET_LIBRARIES:
            logging.getLogger(library).setLevel(logging.WARNING)
