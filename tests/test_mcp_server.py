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
from assistant.prompts import (
    EXPLAIN_DESCRIPTION,
    LEVEL_DESCRIPTION,
    STYLE_DESCRIPTION,
    SUMMARY_DESCRIPTION,
    TOPIC_DESCRIPTION,
    explain_prompt,
    summary_prompt,
)

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


def test_server_command_needs_the_preferences_file(tmp_path):  # R-A3
    with pytest.raises(TypeError):
        server_command(tmp_path / "n.sqlite3", "WARNING")


def test_missing_preferences_file_adds_no_server_error_lines(tmp_path, capfd):
    command, args, cwd = server_command(tmp_path / "n.sqlite3", "INFO", tmp_path / "manca.json")

    async def read(c):
        with pytest.raises(MCPError, match="non leggibile"):
            await c.read_resource(PREFERENCES_URI)

    session(StdioTransport(command, args, cwd=cwd, keep_alive=False, log_file=sys.stderr), read)
    err = capfd.readouterr().err
    assert "Error reading resource" not in err and "Traceback" not in err, err
    assert "event=resource_read" not in err


# --- prompts spiega and riassumi_conversazione (lesson 6, step 5) ---


def prompt_text(result):
    """Role and text of the only message of a prompts/get result."""
    [message] = result.messages
    return message.role, message.content.text


def test_prompts_are_listed_with_descriptions_and_arguments(server):
    prompts = {p.name: p for p in session(server, lambda c: c.list_prompts())}
    assert list(prompts) == ["spiega", "riassumi_conversazione"]
    assert prompts["spiega"].description == EXPLAIN_DESCRIPTION
    assert [(a.name, a.description, a.required) for a in prompts["spiega"].arguments] == [
        ("argomento", TOPIC_DESCRIPTION, True),
        ("livello", LEVEL_DESCRIPTION, False),
    ]
    assert prompts["riassumi_conversazione"].description == SUMMARY_DESCRIPTION
    assert [
        (a.name, a.description, a.required)
        for a in prompts["riassumi_conversazione"].arguments
    ] == [("stile", STYLE_DESCRIPTION, True)]


def test_prompts_are_not_tools(server):
    tools = {t.name for t in session(server, lambda c: c.list_tools())}
    assert len(tools) == 7
    assert not tools & {"spiega", "riassumi_conversazione"}


def test_explain_prompt_returns_one_user_message(server, caplog):
    caplog.set_level(logging.INFO, logger="assistant.mcp_server")
    result = session(
        server,
        lambda c: c.get_prompt(
            "spiega", {"argomento": "Model Context Protocol", "livello": "avanzato"}
        ),
    )
    assert prompt_text(result) == ("user", explain_prompt("Model Context Protocol", "avanzato"))
    assert "event=prompt_get name=spiega" in caplog.text


def test_explain_prompt_level_defaults_to_base(server):
    result = session(server, lambda c: c.get_prompt("spiega", {"argomento": "MCP"}))
    assert prompt_text(result) == ("user", explain_prompt("MCP", "base"))


def test_summary_prompt_returns_one_user_message(server, caplog):
    caplog.set_level(logging.INFO, logger="assistant.mcp_server")
    result = session(
        server, lambda c: c.get_prompt("riassumi_conversazione", {"stile": "dettagliato"})
    )
    assert prompt_text(result) == ("user", summary_prompt("dettagliato"))
    assert "event=prompt_get name=riassumi_conversazione" in caplog.text


@pytest.mark.parametrize(
    ("name", "arguments", "message"),
    [
        (
            "spiega",
            {"argomento": "MCP", "livello": "esperto"},
            "Livello non valido: 'esperto'. Valori ammessi: base, intermedio, avanzato.",
        ),
        ("spiega", {"argomento": " "}, "L'argomento da spiegare è vuoto."),
        (
            "riassumi_conversazione",
            {"stile": "breve"},
            "Stile non valido: 'breve'. Valori ammessi: sintetico, dettagliato.",
        ),
    ],
)
def test_invalid_prompt_value_is_an_mcp_error(server, caplog, name, arguments, message):
    caplog.set_level(logging.INFO, logger="assistant.mcp_server")
    with pytest.raises(MCPError) as e:
        session(server, lambda c: c.get_prompt(name, arguments))
    assert message in str(e.value)
    assert "event=prompt_get" not in caplog.text


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("spiega", {"livello": "base"}),  # required argument missing
        ("riassumi_conversazione", {}),
        ("inesistente", {}),
    ],
)
def test_missing_argument_or_unknown_prompt_is_an_mcp_error(server, name, arguments):
    with pytest.raises(MCPError):
        session(server, lambda c: c.get_prompt(name, arguments))


def test_prompts_over_stdio(tmp_path, capfd):
    command, args, cwd = server_command(
        tmp_path / "n.sqlite3", "INFO", DEFAULT_PREFERENCES_FILE
    )

    async def check(c):
        prompts = await c.list_prompts()
        result = await c.get_prompt("spiega", {"argomento": "MCP"})
        with pytest.raises(MCPError, match="Livello non valido"):
            await c.get_prompt("spiega", {"argomento": "MCP", "livello": "esperto"})
        return prompts, result

    prompts, result = session(
        StdioTransport(command, args, cwd=cwd, keep_alive=False, log_file=sys.stderr), check
    )
    assert [p.name for p in prompts] == ["spiega", "riassumi_conversazione"]
    assert prompt_text(result) == ("user", explain_prompt("MCP", "base"))
    err = capfd.readouterr().err
    assert "event=prompt_get name=spiega" in err
    assert "Traceback" not in err, err
