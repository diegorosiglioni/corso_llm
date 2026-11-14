"""MCP server tests with fastmcp's in-memory client; the stdio path is tested in test_mcp_client
(plus one stdio check here for the --preferences-file argument)."""

import asyncio
import json
import logging
import sys

import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from mcp.shared.exceptions import MCPError

from assistant.catalog import Catalog
from assistant.config import DEFAULT_PREFERENCES_FILE
from assistant.mcp_client import server_command
from assistant.mcp_server import PREFERENCES_DESCRIPTION, build_server
from assistant.notes import ADD_NOTE_DESCRIPTION, NotesStore
from assistant.preferences import PREFERENCES_URI

PREFERENCES = {"language": "inglese", "timezone": "America/New_York", "style": "dettagliato"}


def call(server, name, args):
    async def go():
        async with Client(server) as c:
            return await c.call_tool(name, args, raise_on_error=False)
    return asyncio.run(go())


def session(target, request):
    """Runs `request(client)` in a fastmcp client session on `target` (server or transport)."""
    async def go():
        async with Client(target) as c:
            return await request(c)
    return asyncio.run(go())


@pytest.fixture
def preferences_file(tmp_path):
    f = tmp_path / "preferenze.json"
    f.write_text(json.dumps(PREFERENCES), encoding="utf-8")
    return f


@pytest.fixture
def server(tmp_path, preferences_file):
    return build_server(NotesStore(tmp_path / "n.sqlite3"), Catalog.load(), preferences_file)


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


# --- resource utente://preferenze (lesson 6, step 4) ---


def test_preferences_resource_is_listed_and_is_not_a_tool(server):
    [resource] = session(server, lambda c: c.list_resources())
    assert (str(resource.uri), resource.name, resource.mime_type) == (
        PREFERENCES_URI, "preferenze", "application/json"
    )
    assert resource.description == PREFERENCES_DESCRIPTION
    tools = session(server, lambda c: c.list_tools())
    assert len(tools) == 7 and "preferenze" not in {t.name for t in tools}


def test_preferences_resource_returns_the_file(server, caplog):
    caplog.set_level(logging.INFO, logger="assistant.mcp_server")
    [content] = session(server, lambda c: c.read_resource(PREFERENCES_URI))
    assert json.loads(content.text) == PREFERENCES
    assert content.mime_type == "application/json"
    assert f"event=resource_read uri={PREFERENCES_URI}" in caplog.text


def test_preferences_file_is_read_at_every_request(server, preferences_file):
    preferences_file.write_text('{"style": "sintetico"}', encoding="utf-8")
    [content] = session(server, lambda c: c.read_resource(PREFERENCES_URI))
    assert json.loads(content.text) == {"style": "sintetico"}


def test_missing_preferences_file_is_an_mcp_error(tmp_path, caplog):
    missing = tmp_path / "nessuno.json"
    server = build_server(NotesStore(tmp_path / "n.sqlite3"), Catalog.load(), missing)
    with pytest.raises(MCPError) as e:
        session(server, lambda c: c.read_resource(PREFERENCES_URI))
    assert f"File delle preferenze non leggibile: '{missing}'" in str(e.value)
    assert "event=resource_read" not in caplog.text


def test_preferences_over_stdio_use_the_command_line_file(tmp_path, preferences_file):
    command, args, cwd = server_command(tmp_path / "n.sqlite3", "WARNING", preferences_file)
    assert args[args.index("--preferences-file") + 1] == str(preferences_file)

    async def check(c):
        resources, tools = await c.list_resources(), await c.list_tools()
        return resources, tools, await c.read_resource(PREFERENCES_URI)

    resources, tools, [content] = session(
        StdioTransport(command, args, cwd=cwd, keep_alive=False), check
    )
    assert [str(r.uri) for r in resources] == [PREFERENCES_URI]
    assert len(tools) == 7
    assert json.loads(content.text) == PREFERENCES


def test_server_command_defaults_to_the_package_file(tmp_path):
    _, args, _ = server_command(tmp_path / "n.sqlite3", "WARNING")
    assert args[args.index("--preferences-file") + 1] == str(DEFAULT_PREFERENCES_FILE)


def test_missing_preferences_file_adds_no_server_error_lines(tmp_path, capfd):
    command, args, cwd = server_command(tmp_path / "n.sqlite3", "INFO", tmp_path / "manca.json")

    async def read(c):
        with pytest.raises(MCPError, match="non leggibile"):
            await c.read_resource(PREFERENCES_URI)

    session(StdioTransport(command, args, cwd=cwd, keep_alive=False, log_file=sys.stderr), read)
    err = capfd.readouterr().err
    assert "Error reading resource" not in err and "Traceback" not in err, err
    assert "event=resource_read" not in err
