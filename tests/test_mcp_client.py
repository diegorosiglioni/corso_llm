"""McpClient against the real MCP server started as a stdio subprocess (no LM Studio needed)."""

import json
import logging
import sys

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool
from mcp import types as mcp_types
from mcp.types import (
    BlobResourceContents,
    GetPromptResult,
    ImageContent,
    Prompt,
    TextContent,
    TextResourceContents,
)

from assistant.calculator import CALCULATOR_DESCRIPTION
from assistant.mcp_client import (
    McpClient,
    McpStartupError,
    PromptArgument,
    PromptMessage,
    PromptSpec,
    PromptUnavailableError,
    ResourceUnavailableError,
    ToolSpec,
    create_mcp_tools,
    server_command,
)
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


# --- resources ---


def test_read_resource_returns_the_preferences_json(tmp_path):
    preferences = tmp_path / "preferenze.json"
    preferences.write_text(
        '{"language": "inglese", "timezone": "America/New_York", "style": "dettagliato"}',
        encoding="utf-8",
    )
    command, args, cwd = server_command(tmp_path / "n.sqlite3", "WARNING", preferences)
    with McpClient(command, args, cwd=cwd) as c:
        text = c.read_resource(PREFERENCES_URI)
    assert json.loads(text) == {
        "language": "inglese", "timezone": "America/New_York", "style": "dettagliato",
    }


def test_read_resource_with_the_default_file(client):
    assert json.loads(client.read_resource(PREFERENCES_URI)) == {
        "language": "italiano", "timezone": "Europe/Rome", "style": "sintetico",
    }


def test_unknown_resource_is_unavailable(client):
    with pytest.raises(ResourceUnavailableError, match="utente://inesistente"):
        client.read_resource("utente://inesistente")


def test_missing_preferences_file_is_unavailable(tmp_path):
    missing = tmp_path / "manca.json"
    command, args, cwd = server_command(tmp_path / "n.sqlite3", "WARNING", missing)
    with McpClient(command, args, cwd=cwd) as c:
        with pytest.raises(ResourceUnavailableError, match="File delle preferenze non leggibile"):
            c.read_resource(PREFERENCES_URI)
        # the session survives the error: tools still work
        assert c.call_tool("calculate", {"expression": "1+1"})["result"] == 2


def test_read_resource_after_close_is_unavailable(tmp_path):
    command, args, cwd = server_command(tmp_path / "n.sqlite3", "WARNING")
    with McpClient(command, args, cwd=cwd) as c:
        pass
    with pytest.raises(ResourceUnavailableError, match="sessione MCP chiusa"):
        c.read_resource(PREFERENCES_URI)


def test_resource_error_is_not_a_tool_error():
    assert not issubclass(ResourceUnavailableError, ToolUnavailableError)


def test_resource_without_text_is_unavailable(monkeypatch):
    blob = BlobResourceContents(uri=PREFERENCES_URI, mimeType="application/json", blob="e30=")
    c = McpClient("unused", [])
    monkeypatch.setattr(c, "_submit", lambda request: [blob])
    with pytest.raises(ResourceUnavailableError, match="nessun contenuto testuale"):
        c.read_resource(PREFERENCES_URI)


def test_text_contents_are_joined(monkeypatch):
    parts = [
        TextResourceContents(uri=PREFERENCES_URI, mimeType="application/json", text='{"a": '),
        TextResourceContents(uri=PREFERENCES_URI, mimeType="application/json", text="1}"),
    ]
    c = McpClient("unused", [])
    monkeypatch.setattr(c, "_submit", lambda request: parts)
    assert c.read_resource(PREFERENCES_URI) == '{"a": 1}'


def test_fake_client_reads_registered_resources():
    fake = FakeMcpClient(MCP_SPECS, resources={PREFERENCES_URI: '{"style": "dettagliato"}'})
    assert fake.read_resource(PREFERENCES_URI) == '{"style": "dettagliato"}'
    with pytest.raises(ResourceUnavailableError):
        fake.read_resource("utente://altro")
    assert fake.resource_reads == [PREFERENCES_URI, "utente://altro"]


def test_fake_client_without_resources_is_unavailable():
    fake = FakeMcpClient(MCP_SPECS)
    with pytest.raises(ResourceUnavailableError):
        fake.read_resource(PREFERENCES_URI)
    assert fake.resource_reads == [PREFERENCES_URI]


# --- prompts ---


def test_list_prompts_over_stdio(client):
    specs = {s.name: s for s in client.list_prompts()}
    assert set(specs) == {"spiega", "riassumi_conversazione"}
    assert specs["spiega"] == PromptSpec("spiega", EXPLAIN_DESCRIPTION, (
        PromptArgument("argomento", TOPIC_DESCRIPTION, True),
        PromptArgument("livello", LEVEL_DESCRIPTION, False),
    ))
    assert specs["riassumi_conversazione"] == PromptSpec(
        "riassumi_conversazione", SUMMARY_DESCRIPTION,
        (PromptArgument("stile", STYLE_DESCRIPTION, True),),
    )


def test_get_prompt_returns_one_user_message(client):
    messages = client.get_prompt(
        "spiega", {"argomento": "Model Context Protocol", "livello": "avanzato"}
    )
    assert messages == [
        PromptMessage("user", explain_prompt("Model Context Protocol", "avanzato"))
    ]


def test_get_prompt_uses_the_default_level(client):
    [message] = client.get_prompt("spiega", {"argomento": "MCP"})
    assert message.text == explain_prompt("MCP", "base")


def test_get_summary_prompt(client):
    assert client.get_prompt("riassumi_conversazione", {"stile": "dettagliato"}) == [
        PromptMessage("user", summary_prompt("dettagliato"))
    ]


def test_rejected_value_is_unavailable_with_the_server_message(client):
    with pytest.raises(PromptUnavailableError, match="Livello non valido: 'esperto'"):
        client.get_prompt("spiega", {"argomento": "MCP", "livello": "esperto"})
    # the session survives the error
    assert client.get_prompt("riassumi_conversazione", {"stile": "sintetico"})
    assert client.call_tool("calculate", {"expression": "1+1"})["result"] == 2


def test_unknown_prompt_is_unavailable(client):
    with pytest.raises(PromptUnavailableError, match="inesistente"):
        client.get_prompt("inesistente", {})


def test_missing_required_argument_is_unavailable(client):
    with pytest.raises(PromptUnavailableError):
        client.get_prompt("riassumi_conversazione", {})


def test_prompts_after_close_are_unavailable(tmp_path):
    command, args, cwd = server_command(tmp_path / "n.sqlite3", "WARNING")
    with McpClient(command, args, cwd=cwd) as c:
        pass
    with pytest.raises(PromptUnavailableError, match="sessione MCP chiusa"):
        c.list_prompts()
    with pytest.raises(PromptUnavailableError, match="sessione MCP chiusa"):
        c.get_prompt("spiega", {"argomento": "MCP"})


def test_prompt_error_is_not_a_tool_or_resource_error():
    assert not issubclass(PromptUnavailableError, ToolUnavailableError)
    assert not issubclass(PromptUnavailableError, ResourceUnavailableError)
    assert not issubclass(ResourceUnavailableError, PromptUnavailableError)


def test_missing_prompt_fields_get_defaults(monkeypatch):
    published = [
        Prompt(name="vuoto"),
        Prompt(name="parziale", arguments=[mcp_types.PromptArgument(name="x")]),
    ]
    c = McpClient("unused", [])
    monkeypatch.setattr(c, "_submit", lambda request: published)
    assert c.list_prompts() == [
        PromptSpec("vuoto", "", ()),
        PromptSpec("parziale", "", (PromptArgument("x", "", False),)),
    ]


def test_non_text_content_is_unavailable(monkeypatch):
    result = GetPromptResult(messages=[
        mcp_types.PromptMessage(role="user", content=TextContent(type="text", text="ciao")),
        mcp_types.PromptMessage(
            role="assistant",
            content=ImageContent(type="image", data="e30=", mimeType="image/png"),
        ),
    ])
    c = McpClient("unused", [])
    monkeypatch.setattr(c, "_submit", lambda request: result)
    with pytest.raises(PromptUnavailableError, match="contenuto non testuale nel messaggio 2"):
        c.get_prompt("x", {})


def test_prompt_messages_keep_role_and_order(monkeypatch):
    result = GetPromptResult(messages=[
        mcp_types.PromptMessage(role="user", content=TextContent(type="text", text="a")),
        mcp_types.PromptMessage(role="assistant", content=TextContent(type="text", text="b")),
        mcp_types.PromptMessage(role="user", content=TextContent(type="text", text="c")),
    ])
    c = McpClient("unused", [])
    monkeypatch.setattr(c, "_submit", lambda request: result)
    assert c.get_prompt("x", {}) == [
        PromptMessage("user", "a"), PromptMessage("assistant", "b"), PromptMessage("user", "c"),
    ]


FAKE_PROMPT = PromptSpec("eco", "Ripete", (PromptArgument("testo", "Testo", True),))


def _echo(arguments: dict[str, str]) -> list[PromptMessage]:
    if not arguments.get("testo"):
        raise ValueError("Testo vuoto.")
    return [PromptMessage("user", arguments["testo"])]


def test_fake_client_lists_and_gets_registered_prompts():
    fake = FakeMcpClient(MCP_SPECS, prompts={"eco": (FAKE_PROMPT, _echo)})
    assert fake.list_prompts() == [FAKE_PROMPT]
    assert fake.get_prompt("eco", {"testo": "ciao"}) == [PromptMessage("user", "ciao")]
    assert fake.prompt_lists == 1
    assert fake.prompt_gets == [("eco", {"testo": "ciao"})]


def test_fake_client_unknown_or_rejected_prompt_is_unavailable():
    fake = FakeMcpClient(MCP_SPECS, prompts={"eco": (FAKE_PROMPT, _echo)})
    with pytest.raises(PromptUnavailableError, match="Testo vuoto."):
        fake.get_prompt("eco", {"testo": ""})
    with pytest.raises(PromptUnavailableError, match="altro"):
        fake.get_prompt("altro", {})
    assert fake.prompt_gets == [("eco", {"testo": ""}), ("altro", {})]


def test_fake_client_without_prompts_lists_none():
    fake = FakeMcpClient(MCP_SPECS)
    assert fake.list_prompts() == []
    with pytest.raises(PromptUnavailableError):
        fake.get_prompt("spiega", {"argomento": "MCP"})


def test_close_releases_the_database(tmp_path):
    db = tmp_path / "n.sqlite3"
    command, args, cwd = server_command(db, "WARNING")
    with McpClient(command, args, cwd=cwd) as c:
        c.call_tool("add_note", {"text": "a"})
    db.unlink()  # on Windows this fails if the server process still holds the file
