"""Startup of the HTTP service of the agent: configuration → logging → MCP client → tools →
preferences → models → graph → FastAPI app served by uvicorn while the MCP session is open.

Start with `python -m assistant.service`; address from AGENT_HOST and AGENT_PORT. LM Studio
switched off does not stop the startup: GET /status reports it.
"""

import logging
import os
import sys
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

import uvicorn

from assistant.api import create_app
from assistant.config import ConfigError, load_config
from assistant.graph import build_graph
from assistant.mcp_client import (
    ALLOWED_MCP_TOOLS,
    McpClient,
    McpStartupError,
    create_mcp_tools,
    server_command,
)
from assistant.model import (
    check_model,
    create_model,
    create_reviewer_model,
    create_router_model,
    create_summary_model,
)
from assistant.preferences import load_preferences, preferences_prompt
from assistant.tools import ToolUnavailableError, create_current_time_tool

log = logging.getLogger("assistant.service")  # not "__main__" with python -m

# Libraries whose INFO logs (HTTP requests, protocol details) are hidden unless LOG_LEVEL=DEBUG.
QUIET_LIBRARIES = ("httpx", "httpx2", "openai", "mcp", "fastmcp")  # openai 3.x uses httpx2


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=log_level,
    )
    if log_level != "DEBUG":
        for library in QUIET_LIBRARIES:
            logging.getLogger(library).setLevel(logging.WARNING)


def main(env: Mapping[str, str] = os.environ) -> int:
    try:
        config = load_config(env)
    except ConfigError as error:
        print(f"Configurazione non valida: {error}", file=sys.stderr)
        return 1
    configure_logging(config.log_level)

    notes_db = Path(config.notes_db).resolve()
    notes_db.parent.mkdir(parents=True, exist_ok=True)
    command, args, cwd = server_command(
        notes_db, config.log_level, Path(config.preferences_file).resolve()
    )
    try:
        with McpClient(command, args, cwd=cwd) as client:
            return _serve(config, client)
    except McpStartupError as error:
        print(f"Server MCP non avviato: {error}", file=sys.stderr)
        return 1


def _tools(client) -> list:
    """Local and MCP tools; ValueError with the Italian message if they cannot be used."""
    try:
        mcp_tools = create_mcp_tools(client, ALLOWED_MCP_TOOLS)
    except ToolUnavailableError as error:  # discovery failed after the handshake
        raise ValueError(f"Server MCP non avviato: {error}") from error
    tools = [create_current_time_tool(), *mcp_tools]
    duplicates = [name for name, n in Counter(t.name for t in tools).items() if n > 1]
    if duplicates:
        names = ", ".join(f"'{name}'" for name in duplicates)
        raise ValueError(f"Strumenti con lo stesso nome: {names}.")
    log.info(
        "tools=[%s]",
        ", ".join(f"{t.name} ({(t.metadata or {}).get('variant', 'local')})" for t in tools),
    )
    return tools


def _serve(config, client) -> int:
    """Builds the graph on the open MCP session and serves the app until uvicorn stops."""
    try:
        tools = _tools(client)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    log.info(
        "scope_file=%s max_reviews=%d summary_max_messages=%d summary_keep_messages=%d "
        "preferences_file=%s",
        config.scope_file, config.max_reviews,
        config.summary_max_messages, config.summary_keep_messages,
        Path(config.preferences_file).resolve(),
    )
    preferences = load_preferences(client)  # once per service: valid for every conversation
    graph = build_graph(
        create_model(config, tools),
        tools,
        config.max_steps,
        router_model=create_router_model(config),
        scope=config.scope,
        reviewer_model=create_reviewer_model(config),
        max_reviews=config.max_reviews,
        summary_model=create_summary_model(config),
        summary_max_messages=config.summary_max_messages,
        summary_keep_messages=config.summary_keep_messages,
        preferences=preferences_prompt(preferences),
    )
    app = create_app(
        graph=graph, client=client, model_id=config.model,
        model_status=lambda: check_model(config),
    )
    log.info(
        "api listening=http://%s:%d docs=/docs model=%s base_url=%s",
        config.agent_host, config.agent_port, config.model, config.base_url,
    )
    uvicorn.run(
        app, host=config.agent_host, port=config.agent_port, access_log=False, log_config=None
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
