"""Configuration read from environment variables and from the scope file they point to."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
DEFAULT_NOTES_DB = "data/notes.sqlite3"
DEFAULT_SCOPE_FILE = str(Path(__file__).parent / "data" / "scope.txt")


@dataclass(frozen=True)
class Config:
    base_url: str  # LMSTUDIO_BASE_URL  (required)
    model: str  # LMSTUDIO_MODEL     (required)
    max_steps: int = 5  # MAX_STEPS   (integer >= 1)
    log_level: str = "INFO"  # LOG_LEVEL   (DEBUG, INFO, WARNING, ERROR)
    notes_db: str = DEFAULT_NOTES_DB  # NOTES_DB    (path of the SQLite file)
    scope_file: str = DEFAULT_SCOPE_FILE  # SCOPE_FILE  (text file with the scope)
    scope: str = ""  # text read from scope_file


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

    log_level = read("LOG_LEVEL").upper() or "INFO"
    if log_level not in LOG_LEVELS:
        problems.append(
            f"LOG_LEVEL deve essere uno tra {', '.join(LOG_LEVELS)}, "
            f"ricevuto '{read('LOG_LEVEL')}'."
        )

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

    if problems:
        raise ConfigError(" ".join(problems))
    return Config(base_url, model, max_steps, log_level, notes_db, scope_file, scope)
