"""Configuration of the front-end service, read from environment variables.

BACKEND_URL is the address of the back-end as the browser sees it: the page calls it directly.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from assistant.config import ConfigError, read_log_level

DEFAULT_BACKEND_URL = "http://127.0.0.1:8001"
DEFAULT_FRONTEND_HOST = "127.0.0.1"  # not reachable from other computers
DEFAULT_FRONTEND_PORT = 8080  # the agent uses 8000, the back-end 8001


@dataclass(frozen=True)
class FrontendConfig:
    backend_url: str = DEFAULT_BACKEND_URL  # BACKEND_URL (without the final "/")
    host: str = DEFAULT_FRONTEND_HOST  # FRONTEND_HOST
    port: int = DEFAULT_FRONTEND_PORT  # FRONTEND_PORT (integer 1…65535)
    log_level: str = "INFO"  # LOG_LEVEL


def load_frontend_config(env: Mapping[str, str]) -> FrontendConfig:
    """Reads and validates the configuration; every problem ends up in one message."""
    problems: list[str] = []

    def read(name: str) -> str:
        return env.get(name, "").strip()

    backend_url = read("BACKEND_URL") or DEFAULT_BACKEND_URL
    if not backend_url.startswith(("http://", "https://")):
        problems.append(
            f"BACKEND_URL deve iniziare con http:// o https://, ricevuto '{backend_url}'."
        )

    host = read("FRONTEND_HOST") or DEFAULT_FRONTEND_HOST

    port = DEFAULT_FRONTEND_PORT
    port_text = read("FRONTEND_PORT")
    if port_text:
        try:
            port = int(port_text)
        except ValueError:
            port = 0
        if not 1 <= port <= 65535:
            problems.append(
                f"FRONTEND_PORT deve essere un intero tra 1 e 65535, ricevuto '{port_text}'."
            )

    log_level = read_log_level(env, problems)

    if problems:
        raise ConfigError(" ".join(problems))
    return FrontendConfig(backend_url.rstrip("/"), host, port, log_level)
