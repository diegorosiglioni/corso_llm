"""Local MCP server (FastMCP, stdio) exposing unit converter, calculator, catalog and notes.

Run as a subprocess by the client: python -m assistant.mcp_server --notes-db PATH [--log-level L]
stdout is reserved for the protocol: logs go to stderr.
"""

import argparse
import logging
import sys
from collections.abc import Callable

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from assistant.calculator import CALCULATOR_DESCRIPTION, calculate
from assistant.catalog import GET_ITEM_DESCRIPTION, SEARCH_DESCRIPTION, Catalog
from assistant.config import LOG_LEVELS
from assistant.notes import (
    ADD_NOTE_DESCRIPTION,
    DELETE_NOTE_DESCRIPTION,
    LIST_NOTES_DESCRIPTION,
    NotesStore,
)
from assistant.units import UNITS_DESCRIPTION, convert_units

# Explicit name: run with "python -m", __name__ would be "__main__".
log = logging.getLogger("assistant.mcp_server")

# Library loggers kept at WARNING unless --log-level DEBUG, as in the application.
QUIET_LIBRARIES = ("mcp", "fastmcp")

SERVER_NAME = "Strumenti del laboratorio"


def _run(function: Callable[..., dict], *args) -> dict:
    """Calls the pure logic; an invalid input becomes an MCP tool error (isError)."""
    try:
        return function(*args)
    except ValueError as error:
        raise ToolError(str(error)) from None


def build_server(notes: NotesStore, catalog: Catalog) -> FastMCP:
    """Returns a FastMCP server with the seven tools bound to `notes` and `catalog`."""
    server = FastMCP(SERVER_NAME)

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
    parser.add_argument("--log-level", default="INFO", choices=LOG_LEVELS)
    args = parser.parse_args(argv)

    logging.basicConfig(
        stream=sys.stderr,
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if args.log_level != "DEBUG":
        for library in QUIET_LIBRARIES:
            logging.getLogger(library).setLevel(logging.WARNING)
    build_server(NotesStore(args.notes_db), Catalog.load()).run(
        transport="stdio", show_banner=False
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
