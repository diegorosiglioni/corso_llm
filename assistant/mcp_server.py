"""Local MCP server (FastMCP, stdio) exposing unit converter, calculator, catalog and notes as
tools, the user preferences as the resource utente://preferenze, and the prompts spiega and
riassumi_conversazione.

Run as a subprocess by the client:
python -m assistant.mcp_server --notes-db PATH --preferences-file PATH [--log-level L]
stdout is reserved for the protocol: logs go to stderr.
"""

import argparse
import logging
import sys
from collections.abc import Callable
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import PromptError, ResourceError, ToolError
from pydantic import Field

from assistant.calculator import CALCULATOR_DESCRIPTION, calculate
from assistant.catalog import GET_ITEM_DESCRIPTION, SEARCH_DESCRIPTION, Catalog
from assistant.config import LOG_LEVELS
from assistant.notes import (
    ADD_NOTE_DESCRIPTION,
    DELETE_NOTE_DESCRIPTION,
    LIST_NOTES_DESCRIPTION,
    NotesStore,
)
from assistant.preferences import PREFERENCES_URI, read_preferences_file
from assistant.prompts import (
    EXPLAIN_DESCRIPTION,
    LEVEL_DESCRIPTION,
    STYLE_DESCRIPTION,
    SUMMARY_DESCRIPTION,
    TOPIC_DESCRIPTION,
    explain_prompt,
    summary_prompt,
)
from assistant.units import UNITS_DESCRIPTION, convert_units

# Explicit name: run with "python -m", __name__ would be "__main__".
log = logging.getLogger("assistant.mcp_server")

# Minimum level of the library loggers unless --log-level DEBUG. fastmcp logs every tool error
# and every invalid argument at WARNING/ERROR: the client graph already reports them
# (execution=tool_error), so only fastmcp's real failures (ERROR) are kept.
LIBRARY_LEVELS = {"mcp": logging.WARNING, "fastmcp": logging.ERROR}

SERVER_NAME = "Strumenti del laboratorio"
PREFERENCES_DESCRIPTION = (
    "Preferenze dell'utente: lingua delle risposte, fuso orario predefinito e stile."
)


def _run(function: Callable[..., dict], *args) -> dict:
    """Calls the pure logic; an invalid input becomes an MCP tool error (isError)."""
    try:
        return function(*args)
    except ValueError as error:
        # An expected input error, not a server failure: logged by fastmcp only at INFO.
        raise ToolError(str(error), log_level=logging.INFO) from None


def _prompt(name: str, function: Callable[..., str], *args) -> str:
    """Calls the pure logic of a prompt; an invalid value becomes an MCP prompt error."""
    try:
        text = function(*args)
    except ValueError as error:
        # An expected input error, not a server failure: logged by fastmcp only at INFO.
        raise PromptError(str(error), log_level=logging.INFO) from None
    log.info("event=prompt_get name=%s", name)
    return text


def _configure_library_logging(level: str) -> None:
    """Routes fastmcp's records through the standard handler (no Rich output) and quiets them."""
    fastmcp_logger = logging.getLogger("fastmcp")
    for handler in fastmcp_logger.handlers[:]:
        fastmcp_logger.removeHandler(handler)
    fastmcp_logger.propagate = True
    if level != "DEBUG":
        for name, minimum in LIBRARY_LEVELS.items():
            logging.getLogger(name).setLevel(max(minimum, logging.getLevelName(level)))


def build_server(notes: NotesStore, catalog: Catalog, preferences_file: str | Path) -> FastMCP:
    """Returns a FastMCP server with the seven tools bound to `notes` and `catalog`, the
    preferences resource read from `preferences_file` and the two prompts."""
    server = FastMCP(SERVER_NAME)

    @server.resource(
        PREFERENCES_URI,
        name="preferenze",
        mime_type="application/json",
        description=PREFERENCES_DESCRIPTION,
    )
    def preferences() -> str:
        try:
            text = read_preferences_file(preferences_file)  # at every read: no cache
        except ValueError as error:
            # Expected (missing or wrong file): the host logs the WARNING and uses the defaults.
            raise ResourceError(str(error), log_level=logging.INFO) from None
        log.info("event=resource_read uri=%s", PREFERENCES_URI)
        return text

    # Parameter names are the published argument names, hence Italian. Field as the default
    # value (not Annotated): fastmcp 4.1.6 would add an English note to the description.
    @server.prompt(name="spiega", description=EXPLAIN_DESCRIPTION)
    def explain(
        argomento: str = Field(description=TOPIC_DESCRIPTION),
        livello: str = Field("base", description=LEVEL_DESCRIPTION),
    ) -> str:
        return _prompt("spiega", explain_prompt, argomento, livello)

    @server.prompt(name="riassumi_conversazione", description=SUMMARY_DESCRIPTION)
    def summarize(stile: str = Field(description=STYLE_DESCRIPTION)) -> str:
        return _prompt("riassumi_conversazione", summary_prompt, stile)

    @server.tool(name="convert_units", description=UNITS_DESCRIPTION)
    def convert_units_tool(value: float, from_unit: str, to_unit: str) -> dict:
        return _run(convert_units, value, from_unit, to_unit)

    @server.tool(name="calculate", description=CALCULATOR_DESCRIPTION)
    def calculate_tool(expression: str) -> dict:
        return _run(calculate, expression)

    @server.tool(name="search_catalog", description=SEARCH_DESCRIPTION)
    def search_catalog(query: str, max_results: int = 5) -> dict:
        return _run(catalog.search, query, max_results)

    @server.tool(name="get_item", description=GET_ITEM_DESCRIPTION)
    def get_item(code: str) -> dict:
        return _run(catalog.get_item, code)

    @server.tool(name="add_note", description=ADD_NOTE_DESCRIPTION)
    def add_note(text: str) -> dict:
        note = _run(notes.add, text)
        log.info("event=note_added id=%d", note["id"])
        return note

    @server.tool(name="list_notes", description=LIST_NOTES_DESCRIPTION)
    def list_notes(limit: int = 10) -> dict:
        return _run(notes.list, limit)

    @server.tool(name="delete_note", description=DELETE_NOTE_DESCRIPTION)
    def delete_note(note_id: int) -> dict:
        result = _run(notes.delete, note_id)
        log.info("event=note_deleted id=%d", result["deleted"]["id"])
        return result

    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Server MCP degli strumenti del laboratorio")
    parser.add_argument("--notes-db", required=True, help="percorso del file SQLite delle note")
    parser.add_argument(
        "--preferences-file", required=True, help="percorso del file JSON delle preferenze"
    )
    parser.add_argument("--log-level", default="INFO", choices=LOG_LEVELS)
    args = parser.parse_args(argv)

    logging.basicConfig(
        stream=sys.stderr,
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _configure_library_logging(args.log_level)
    build_server(NotesStore(args.notes_db), Catalog.load(), args.preferences_file).run(
        transport="stdio", show_banner=False
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
