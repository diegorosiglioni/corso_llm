"""MCP server tests with fastmcp's in-memory client; the stdio path is tested in test_mcp_client."""

import asyncio
import logging

import pytest
from fastmcp import Client

from assistant.catalog import Catalog
from assistant.mcp_server import build_server
from assistant.notes import ADD_NOTE_DESCRIPTION, NotesStore


def call(server, name, args):
    async def go():
        async with Client(server) as c:
            return await c.call_tool(name, args, raise_on_error=False)
    return asyncio.run(go())


@pytest.fixture
def server(tmp_path):
    return build_server(NotesStore(tmp_path / "n.sqlite3"), Catalog.load())


def test_discovery_lists_the_seven_tools_with_schemas(server):
    async def go():
        async with Client(server) as c:
            return await c.list_tools()
    tools = {t.name: t for t in asyncio.run(go())}
    assert set(tools) == {
        "convert_units", "calculate", "search_catalog", "get_item",
        "add_note", "list_notes", "delete_note",
    }
    assert tools["add_note"].description == ADD_NOTE_DESCRIPTION
    assert tools["convert_units"].input_schema["required"] == ["value", "from_unit", "to_unit"]
    assert tools["delete_note"].input_schema["properties"]["note_id"]["type"] == "integer"


def test_structured_result(server):
    r = call(server, "calculate", {"expression": "17 * 23"})
    assert (r.is_error, r.structured_content) == (False, {"expression": "17 * 23", "result": 391})


def test_tool_error_has_no_false_success(server):
    r = call(server, "get_item", {"code": "XX-999"})
    assert r.is_error and r.structured_content is None
    assert "Nessun corso con codice 'XX-999'" in r.content[0].text


def test_note_round_trip_and_log(server, caplog):
    caplog.set_level(logging.INFO, logger="assistant.mcp_server")
    assert call(server, "add_note", {"text": "x"}).structured_content["id"] == 1
    assert call(server, "delete_note", {"note_id": 1}).structured_content["deleted"]["id"] == 1
    assert "event=note_added id=1" in caplog.text and "event=note_deleted id=1" in caplog.text
