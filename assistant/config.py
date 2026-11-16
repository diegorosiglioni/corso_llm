"""Configuration read from environment variables and from the scope file they point to, and the
logging setup shared by the service and the CLI.

The preferences file is only located here: the MCP server reads it."""

import logging
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
# Libraries whose INFO logs (HTTP requests, protocol details) are hidden unless LOG_LEVEL=DEBUG.
QUIET_LIBRARIES = ("httpx", "httpx2", "openai", "mcp", "fastmcp")  # openai 3.x uses httpx2
DEFAULT_NOTES_DB = "data/notes.sqlite3"
DEFAULT_SCOPE_FILE = str(Path(__file__).parent / "data" / "scope.txt")
DEFAULT_PREFERENCES_FILE = str(Path(__file__).parent / "data" / "preferenze.json")
DEFAULT_AGENT_HOST = "127.0.0.1"  # not reachable from other computers
DEFAULT_AGENT_PORT = 8000
DEFAULT_AGENT_URL = f"http://{DEFAULT_AGENT_HOST}:{DEFAULT_AGENT_PORT}"  # used by the CLI


@dataclass(frozen=True)
class Config:
    base_url: str  # LMSTUDIO_BASE_URL  (required)
    model: str  # LMSTUDIO_MODEL     (required)
    max_steps: int = 5  # MAX_STEPS   (integer >= 1)
    log_level: str = "INFO"  # LOG_LEVEL   (DEBUG, INFO, WARNING, ERROR)
    notes_db: str = DEFAULT_NOTES_DB  # NOTES_DB    (path of the SQLite file)
    scope_file: str = DEFAULT_SCOPE_FILE  # SCOPE_FILE  (text file with the scope)
    scope: str = ""  # text read from scope_file
    max_reviews: int = 2  # MAX_REVIEWS (integer >= 1): reviewer calls per turn
    summary_max_messages: int = 20  # SUMMARY_MAX_MESSAGES (integer >= 1)
    summary_keep_messages: int = 6  # SUMMARY_KEEP_MESSAGES (integer >= 1, < max)
    # PREFERENCES_FILE: not read here, a missing file must not stop the startup (the MCP
    # server reads it, the host falls back to the defaults).
    preferences_file: str = DEFAULT_PREFERENCES_FILE
    agent_host: str = DEFAULT_AGENT_HOST  # AGENT_HOST  (address of the HTTP service)
    agent_port: int = DEFAULT_AGENT_PORT  # AGENT_PORT  (integer 1…65535)


class ConfigError(Exception):
    """Missing or invalid configuration; the message lists every problem."""


def load_config(env: Mapping[str, str]) -> Config:
    """Reads and validates the configuration; empty or blank values count as missing."""
    problems = []

    def read(name: str) -> str:
        return env.get(name, "").strip()

    base_url = read("LMSTUDIO_BASE_URL")
    if not base_url:
        problems.append("Manca LMSTUDIO_BASE_URL.")
    elif not base_url.startswith(("http://", "https://")):
        problems.append(
            f"LMSTUDIO_BASE_URL deve iniziare con http:// o https://, ricevuto '{base_url}'."
        )

    model = read("LMSTUDIO_MODEL")
    if not model:
        problems.append("Manca LMSTUDIO_MODEL.")

    max_steps = 5
    steps_text = read("MAX_STEPS")
    if steps_text:
        try:
            max_steps = int(steps_text)
        except ValueError:
            max_steps = 0
        if max_steps < 1:
            problems.append(f"MAX_STEPS deve essere un intero ≥ 1, ricevuto '{steps_text}'.")

    max_reviews = 2
    reviews_text = read("MAX_REVIEWS")
    if reviews_text:
        try:
            max_reviews = int(reviews_text)
        except ValueError:
            max_reviews = 0
        if max_reviews < 1:
            problems.append(f"MAX_REVIEWS deve essere un intero ≥ 1, ricevuto '{reviews_text}'.")

    def read_positive(name: str, default: int) -> int | None:
        """Integer >= 1 from `name`, `default` if unset; None (and a problem) if invalid."""
        text = read(name)
        if not text:
            return default
        try:
            value = int(text)
        except ValueError:
            value = 0
        if value < 1:
            problems.append(f"{name} deve essere un intero ≥ 1, ricevuto '{text}'.")
            return None
        return value

    summary_max_messages = read_positive("SUMMARY_MAX_MESSAGES", 20)
    summary_keep_messages = read_positive("SUMMARY_KEEP_MESSAGES", 6)
    if (
        summary_max_messages is not None
        and summary_keep_messages is not None
        and summary_keep_messages >= summary_max_messages
    ):
        problems.append(
            "SUMMARY_KEEP_MESSAGES deve essere minore di SUMMARY_MAX_MESSAGES, "
            f"ricevuti '{summary_keep_messages}' e '{summary_max_messages}'."
        )

    log_level = read_log_level(env, problems)

    notes_db = read("NOTES_DB") or DEFAULT_NOTES_DB

    scope_file = read("SCOPE_FILE") or DEFAULT_SCOPE_FILE
    scope = ""
    try:
        scope = Path(scope_file).read_text(encoding="utf-8-sig").strip()
    except (OSError, UnicodeDecodeError) as error:
        reason = getattr(error, "strerror", None) or str(error)
        problems.append(f"SCOPE_FILE non leggibile: '{scope_file}' ({reason}).")
    else:
        if not scope:
            problems.append(f"SCOPE_FILE vuoto: '{scope_file}'.")

    agent_port = DEFAULT_AGENT_PORT
    port_text = read("AGENT_PORT")
    if port_text:
        try:
            agent_port = int(port_text)
        except ValueError:
            agent_port = 0
        if not 1 <= agent_port <= 65535:
            problems.append(
                f"AGENT_PORT deve essere un intero tra 1 e 65535, ricevuto '{port_text}'."
            )

    if problems:
        raise ConfigError(" ".join(problems))
    return Config(
        base_url, model, max_steps, log_level, notes_db, scope_file, scope, max_reviews,
        summary_max_messages, summary_keep_messages,
        read("PREFERENCES_FILE") or DEFAULT_PREFERENCES_FILE,
        read("AGENT_HOST") or DEFAULT_AGENT_HOST,
        agent_port,
    )


def read_log_level(env: Mapping[str, str], problems: list[str]) -> str:
    """LOG_LEVEL in upper case (default INFO); an invalid value is added to `problems`."""
    text = env.get("LOG_LEVEL", "").strip()
    log_level = text.upper() or "INFO"
    if log_level not in LOG_LEVELS:
        problems.append(
            f"LOG_LEVEL deve essere uno tra {', '.join(LOG_LEVELS)}, ricevuto '{text}'."
        )
    return log_level


@dataclass(frozen=True)
class ClientConfig:
    """Configuration of the CLI, a client of the HTTP service: it needs no LM Studio variables."""

    agent_url: str = DEFAULT_AGENT_URL  # AGENT_URL (address of the agent service)
    log_level: str = "INFO"  # LOG_LEVEL


def _is_valid_url(url: str) -> bool:
    """A host name and, if present, a port in 0…65535 (R-B9: no InvalidURL at the first request)."""
    try:
        parts = urlsplit(url)
        parts.port  # raises ValueError for a port that is not a number or out of range
    except ValueError:
        return False
    return bool(parts.hostname)


def load_client_config(env: Mapping[str, str]) -> ClientConfig:
    """Reads and validates the configuration of the CLI; the URL loses its final "/"."""
    problems = []
    agent_url = env.get("AGENT_URL", "").strip() or DEFAULT_AGENT_URL
    if not agent_url.startswith(("http://", "https://")):
        problems.append(f"AGENT_URL deve iniziare con http:// o https://, ricevuto '{agent_url}'.")
    elif not _is_valid_url(agent_url):
        problems.append(f"AGENT_URL non è un indirizzo valido, ricevuto '{agent_url}'.")
    log_level = read_log_level(env, problems)
    if problems:
        raise ConfigError(" ".join(problems))
    return ClientConfig(agent_url.rstrip("/"), log_level)


def configure_logging(log_level: str) -> None:
    """Logs on stderr (the conversation of the CLI is on stdout); libraries quiet unless DEBUG."""
    logging.basicConfig(
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=log_level,
    )
    if log_level != "DEBUG":
        for library in QUIET_LIBRARIES:
            logging.getLogger(library).setLevel(logging.WARNING)
