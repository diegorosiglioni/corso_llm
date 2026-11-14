"""Configuration of the back-end, read from environment variables.

DATABASE_URL carries the database credentials: it is never written whole in messages or logs
(`display_url` hides the password, the configuration errors show only the scheme). AGENT_URL and
LOG_LEVEL follow the same rules as the CLI.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from assistant.config import ConfigError, load_client_config

DEFAULT_BACKEND_HOST = "127.0.0.1"  # not reachable from other computers
DEFAULT_BACKEND_PORT = 8001  # the agent uses 8000
DRIVER_SCHEME = "postgresql+psycopg"
ACCEPTED_SCHEMES = ("postgresql", DRIVER_SCHEME)


@dataclass(frozen=True)
class BackendConfig:
    database_url: str  # DATABASE_URL (required, PostgreSQL, always with the psycopg driver)
    agent_url: str  # AGENT_URL   (address of the agent service)
    host: str = DEFAULT_BACKEND_HOST  # BACKEND_HOST
    port: int = DEFAULT_BACKEND_PORT  # BACKEND_PORT (integer 1…65535)
    log_level: str = "INFO"  # LOG_LEVEL


def display_url(url: str) -> str:
    """The database URL with the password replaced by ***, for logs and messages."""
    return make_url(url).render_as_string(hide_password=True)


def _database_url(text: str, problems: list[str]) -> str:
    """DATABASE_URL with the psycopg driver; problems never quote the URL (it has a password)."""
    if not text:
        problems.append("Manca DATABASE_URL.")
        return ""
    scheme = text.split("://", 1)[0] if "://" in text else ""
    if scheme not in ACCEPTED_SCHEMES:
        received = f", ricevuto lo schema '{scheme}'" if scheme else ""
        problems.append(
            f"DATABASE_URL deve iniziare con postgresql:// o postgresql+psycopg://{received}."
        )
        return ""
    url = DRIVER_SCHEME + text[len(scheme):]
    try:
        make_url(url)
    except (ArgumentError, ValueError):
        problems.append("DATABASE_URL non interpretabile (non mostrata: può contenere la password).")
        return ""
    return url


def load_backend_config(env: Mapping[str, str]) -> BackendConfig:
    """Reads and validates the configuration; every problem ends up in one message."""
    problems: list[str] = []

    def read(name: str) -> str:
        return env.get(name, "").strip()

    database_url = _database_url(read("DATABASE_URL"), problems)

    client = None
    try:
        client = load_client_config(env)
    except ConfigError as error:
        problems.append(str(error))

    host = read("BACKEND_HOST") or DEFAULT_BACKEND_HOST

    port = DEFAULT_BACKEND_PORT
    port_text = read("BACKEND_PORT")
    if port_text:
        try:
            port = int(port_text)
        except ValueError:
            port = 0
        if not 1 <= port <= 65535:
            problems.append(
                f"BACKEND_PORT deve essere un intero tra 1 e 65535, ricevuto '{port_text}'."
            )

    if problems:
        raise ConfigError(" ".join(problems))
    return BackendConfig(database_url, client.agent_url, host, port, client.log_level)
