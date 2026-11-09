"""McpClient against the real MCP server started as a stdio subprocess (no LM Studio needed)."""

import logging
import sys

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool

from assistant.calculator import CALCULATOR_DESCRIPTION
from assistant.mcp_client import (
    McpClient,
    McpStartupError,
    ToolSpec,
    create_mcp_tools,
    server_command,
)
from assistant.tools import ToolUnavailableError
from conftest import MCP_SPECS, FakeMcpClient


# --- adapter (fake client) ---

def test_adapter_keeps_server_contract():
    spec = ToolSpec("add_note", "Salva una nota", {
        "type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"],
    })
    fake = FakeMcpClient([spec])
    [t] = create_mcp_tools(fake)
    assert (t.name, t.description, t.metadata) == ("add_note", "Salva una nota", {"variant": "mcp"})
    assert convert_to_openai_tool(t)["function"]["parameters"] == spec.input_schema
    assert t.invoke({"text": "ciao"}) == {"ok": True}
    assert fake.calls == [("add_note", {"text": "ciao"})]


def test_adapter_binds_each_tool_to_its_own_name():
    fake = FakeMcpClient(MCP_SPECS)
    tools = create_mcp_tools(fake)
    tools[0].invoke({})
    tools[-1].invoke({})
    assert [name for name, _ in fake.calls] == [MCP_SPECS[0].name, MCP_SPECS[-1].name]


def test_adapter_drops_tools_not_allowed(caplog):
    caplog.set_level(logging.INFO, logger="assistant.mcp_client")
    tools = create_mcp_tools(
        FakeMcpClient(MCP_SPECS + [ToolSpec("shell", "x", {"type": "object"})])
    )
    assert [t.name for t in tools] == [s.name for s in MCP_SPECS]
    assert "non consentito" in caplog.text and "shell" in caplog.text


def test_adapter_warns_on_missing_allowed_tool(caplog):
    create_mcp_tools(FakeMcpClient(MCP_SPECS[1:]))
    assert any(
        r.levelno == logging.WARNING and MCP_SPECS[0].name in r.getMessage()
        for r in caplog.records
    )


# --- real server over stdio ---


@pytest.fixture
def client(tmp_path):
    command, args, cwd = server_command(tmp_path / "n.sqlite3", "WARNING")
    with McpClient(command, args, cwd=cwd) as c:
        yield c


def test_list_tools_over_stdio(client):
    specs = {s.name: s for s in client.list_tools()}
    assert len(specs) == 7 and specs["calculate"].description == CALCULATOR_DESCRIPTION
    assert specs["search_catalog"].input_schema["properties"]["max_results"]["default"] == 5


def test_call_returns_structured_dict(client):
    result = client.call_tool("convert_units", {"value": 10, "from_unit": "km", "to_unit": "mi"})
    assert result["result"] == 6.21371


def test_tool_error_becomes_error_dict(client):
    assert client.call_tool("delete_note", {"note_id": 99}) == {
        "error": "Nessuna nota con id 99: nessuna nota eliminata."
    }


def test_missing_argument_is_tool_error(client):
    assert set(client.call_tool("add_note", {})) == {"error"}


def test_extra_argument_is_tool_error(client):
    assert set(client.call_tool("calculate", {"expression": "1+1", "precision": 2})) == {"error"}


@pytest.mark.parametrize("name,arguments", [
    ("add_note", {}),
    ("calculate", {"expression": "1+1", "precision": 2}),
    ("convert_units", {"value": "dieci", "from_unit": "km", "to_unit": "mi"}),
])
def test_invalid_arguments_reach_the_model_in_italian(client, name, arguments):
    tool = {t.name: t for t in create_mcp_tools(client)}[name]
    error = tool.invoke(arguments)["error"]
    assert error.startswith(f"Argomenti non validi per '{name}'. Argomenti attesi: "), error
    assert "validation error" not in error and "http" not in error, error
    assert tool.description in error


def test_numeric_strings_are_coerced(client):
    result = client.call_tool("convert_units", {"value": "10", "from_unit": "m", "to_unit": "cm"})
    assert result["result"] == 1000
    client.call_tool("add_note", {"text": "a"})
    assert "deleted" in client.call_tool("delete_note", {"note_id": "1"})


def test_unicode_text_round_trips(client):
    text = "Consegnare il report venerdì €"
    assert client.call_tool("add_note", {"text": text})["text"] == text


def test_startup_failure_raises():
    with pytest.raises(McpStartupError):
        with McpClient(sys.executable, ["-m", "assistant.no_such_module"]):
            pass


def test_call_after_close_is_unavailable(tmp_path):
    command, args, cwd = server_command(tmp_path / "n.sqlite3", "WARNING")
    with McpClient(command, args, cwd=cwd) as c:
        pass
    with pytest.raises(ToolUnavailableError):
        c.call_tool("calculate", {"expression": "1+1"})


def test_server_logs_use_module_name_and_hide_library_info(tmp_path, capfd):
    command, args, cwd = server_command(tmp_path / "n.sqlite3", "INFO")
    with McpClient(command, args, cwd=cwd) as c:
        c.call_tool("add_note", {"text": "a"})
    err = capfd.readouterr().err
    assert "INFO assistant.mcp_server: event=note_added id=1" in err
    assert "Starting MCP server" not in err


def test_expected_tool_errors_add_no_server_log_lines(tmp_path, capfd):
    command, args, cwd = server_command(tmp_path / "n.sqlite3", "INFO")
    with McpClient(command, args, cwd=cwd) as c:
        c.call_tool("get_item", {"code": "XX-999"})
        c.call_tool("add_note", {})
    err = capfd.readouterr().err
    assert "Error calling tool" not in err and "Invalid arguments" not in err, err


def test_close_releases_the_database(tmp_path):
    db = tmp_path / "n.sqlite3"
    command, args, cwd = server_command(db, "WARNING")
    with McpClient(command, args, cwd=cwd) as c:
        c.call_tool("add_note", {"text": "a"})
    db.unlink()  # on Windows this fails if the server process still holds the file
