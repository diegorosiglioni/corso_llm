"""McpClient against the real MCP server started as a stdio subprocess (no LM Studio needed)."""

import sys

import pytest

from assistant.calculator import CALCULATOR_DESCRIPTION
from assistant.mcp_client import McpClient, McpStartupError, server_command
from assistant.tools import ToolUnavailableError


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


def test_close_releases_the_database(tmp_path):
    db = tmp_path / "n.sqlite3"
    command, args, cwd = server_command(db, "WARNING")
    with McpClient(command, args, cwd=cwd) as c:
        c.call_tool("add_note", {"text": "a"})
    db.unlink()  # on Windows this fails if the server process still holds the file
