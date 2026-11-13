"""Startup: configuration → logging → MCP client → models (agent, router, reviewer) → graph →
session → terminal."""

import logging
import os
import sys
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from assistant.config import ConfigError, load_config
from assistant.graph import build_graph
from assistant.mcp_client import (
    ALLOWED_MCP_TOOLS,
    McpClient,
    McpStartupError,
    create_mcp_tools,
    server_command,
)
from assistant.model import create_model, create_reviewer_model, create_router_model
from assistant.session import Session
from assistant.terminal import run
from assistant.tools import ToolUnavailableError, create_current_time_tool

log = logging.getLogger(__name__)

# Libraries whose INFO logs (HTTP requests, protocol details) are hidden unless LOG_LEVEL=DEBUG.
QUIET_LIBRARIES = ("httpx", "httpx2", "openai", "mcp", "fastmcp")  # openai 3.x uses httpx2


def main(env: Mapping[str, str] = os.environ) -> int:
    try:
        config = load_config(env)
    except ConfigError as error:
        print(f"Configurazione non valida: {error}", file=sys.stderr)
        return 1

    logging.basicConfig(
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=config.log_level,
    )
    if config.log_level != "DEBUG":
        for library in QUIET_LIBRARIES:
            logging.getLogger(library).setLevel(logging.WARNING)

    notes_db = Path(config.notes_db).resolve()
    notes_db.parent.mkdir(parents=True, exist_ok=True)
    command, args, cwd = server_command(notes_db, config.log_level)
    try:
        with McpClient(command, args, cwd=cwd) as client:
            return _converse(config, client)
    except McpStartupError as error:
        print(f"Server MCP non avviato: {error}", file=sys.stderr)
        return 1


def _converse(config, client) -> int:
    """Collects local and MCP tools, then runs the conversation while the session is open."""
    try:
        mcp_tools = create_mcp_tools(client, ALLOWED_MCP_TOOLS)
    except ToolUnavailableError as error:  # discovery failed after the handshake
        print(f"Server MCP non avviato: {error}", file=sys.stderr)
        return 1
    tools = [create_current_time_tool(), *mcp_tools]
    duplicates = [name for name, n in Counter(t.name for t in tools).items() if n > 1]
    if duplicates:
        names = ", ".join(f"'{name}'" for name in duplicates)
        print(f"Strumenti con lo stesso nome: {names}.", file=sys.stderr)
        return 1
    log.info(
        "tools=[%s]",
        ", ".join(f"{t.name} ({(t.metadata or {}).get('variant', 'local')})" for t in tools),
    )

    log.info("scope_file=%s max_reviews=%d", config.scope_file, config.max_reviews)

    model = create_model(config, tools)
    graph = build_graph(
        model,
        tools,
        config.max_steps,
        router_model=create_router_model(config),
        scope=config.scope,
        reviewer_model=create_reviewer_model(config),
        max_reviews=config.max_reviews,
    )
    session = Session(graph)
    print(
        f"Assistente del laboratorio — modello {config.model} su {config.base_url}. "
        "Scrivi 'esci' per uscire."
    )
    run(session)
    return 0


if __name__ == "__main__":
    sys.exit(main())
