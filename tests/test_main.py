"""The CLI as a client of the agent service (step 6, point 5): the real app on a fake graph takes
the place of the service, without a network. The wiring of graph, MCP and models is tested in
test_service.py."""

import io
import logging

import httpx
import pytest
from langchain_core.messages import AIMessage

import assistant.__main__ as entry
from assistant.__main__ import main
from assistant.api_client import AgentClient, RemoteSession
from assistant.commands import PromptCommands
from assistant.mcp_client import PromptArgument, PromptMessage, PromptSpec
from assistant.tools import ToolUnavailableError
from conftest import MCP_SPECS, FakeMcpClient, FakeModel, fake_service, model_ok

WELCOME = (
    "Assistente del laboratorio — agente su http://127.0.0.1:8000, modello google/gemma-4-e2b. "
    "Scrivi /prompts per i prompt disponibili, 'esci' per uscire."
)


def use_service(monkeypatch, model=None, client=None, model_status=model_ok) -> list[str]:
    """main() talks to the real app on a fake graph; returns the URLs main() connects to."""
    urls = []
    http = fake_service(model, client, model_status)

    def connect(url):
        urls.append(url)
        return AgentClient(url, http=http)

    monkeypatch.setattr(entry, "AgentClient", connect)
    return urls


def type_in(monkeypatch, *lines):
    """The lines the user types (input() reads sys.stdin), then end of input."""
    monkeypatch.setattr("sys.stdin", io.StringIO("".join(f"{line}\n" for line in lines)))


def _must_not_call(*args, **kwargs):
    raise AssertionError("non deve essere chiamato")


@pytest.mark.parametrize(("env", "message"), [
    ({"AGENT_URL": "127.0.0.1:8000"},
     "AGENT_URL deve iniziare con http:// o https://, ricevuto '127.0.0.1:8000'."),
    ({"AGENT_URL": "http://[::1"}, "AGENT_URL non è un indirizzo valido, ricevuto 'http://[::1'."),
    ({"LOG_LEVEL": "tanto"}, "LOG_LEVEL deve essere uno tra DEBUG, INFO, WARNING, ERROR"),
])
def test_invalid_config_exits_1(env, message, monkeypatch, capsys):
    monkeypatch.setattr(entry, "AgentClient", _must_not_call)
    assert main(env) == 1
    assert f"Configurazione non valida: {message}" in capsys.readouterr().err


def test_startup_without_lm_studio_variables(monkeypatch, capsys):  # RF-59
    urls = use_service(monkeypatch)
    type_in(monkeypatch, "esci")
    assert main({}) == 0
    assert urls == ["http://127.0.0.1:8000"]
    out = capsys.readouterr().out
    assert out.startswith(WELCOME + "\n")
    assert out.endswith("Arrivederci!\n")


def test_agent_url_from_the_environment(monkeypatch, capsys):
    urls = use_service(monkeypatch)
    type_in(monkeypatch)
    assert main({"AGENT_URL": " http://agent:8000/ "}) == 0
    assert urls == ["http://agent:8000"]
    assert "agente su http://agent:8000, modello" in capsys.readouterr().out


def test_startup_wires_remote_session_and_commands(monkeypatch):
    use_service(monkeypatch)
    received = []
    monkeypatch.setattr(entry, "run", lambda session, **kw: received.append((session, kw)))
    assert main({}) == 0
    [(session, kw)] = received
    assert isinstance(session, RemoteSession)
    assert isinstance(kw["commands"], PromptCommands)


def test_conversation_keeps_the_history_in_the_cli(monkeypatch, capsys):  # CA-66
    model = FakeModel([AIMessage("Piacere, Paolo!"), AIMessage("Ti chiami Paolo.")])
    use_service(monkeypatch, model)
    type_in(monkeypatch, "Mi chiamo Paolo", "Come mi chiamo?", "esci")
    assert main({}) == 0
    out = capsys.readouterr().out
    assert "Tu> Assistente> Piacere, Paolo!\n" in out
    assert "Tu> Assistente> Ti chiami Paolo.\n" in out
    assert [m.content for m in model.calls[1][1:]] == [
        "Mi chiamo Paolo", "Piacere, Paolo!", "Come mi chiamo?"
    ]


def test_prompt_commands_through_the_service(monkeypatch, capsys):  # CA-66
    spec = PromptSpec("spiega", "Spiega un argomento.", (PromptArgument("argomento", "", True),))
    client = FakeMcpClient(
        MCP_SPECS, prompts={"spiega": (spec, lambda a: [PromptMessage("user", "Spiegami MCP.")])}
    )
    model = FakeModel([AIMessage("MCP è un protocollo.")])
    use_service(monkeypatch, model, client)
    type_in(
        monkeypatch, "/prompts", "/prompt spiega livello=base", "/prompt spiega argomento=",
        "/prompt spiega argomento=MCP",
    )
    assert main({}) == 0
    out = capsys.readouterr().out
    assert "Prompt disponibili:\n- spiega: Spiega un argomento.\n" in out
    assert (
        "Errore nel comando: argomenti sconosciuti per 'spiega': 'livello' (attesi: argomento). "
        "Scrivi /prompts per l'elenco dei prompt.\n"
    ) in out
    assert "Errore nel comando: argomento senza valore: 'argomento'. Uso: /prompt" in out
    assert "Assistente> MCP è un protocollo.\n" in out
    assert client.prompt_gets == [("spiega", {"argomento": "MCP"})]
    assert [m.content for m in model.calls[0][1:]] == ["Spiegami MCP."]


def test_agent_unreachable_at_startup_exits_1(monkeypatch, capsys):  # RF-59, CA-66
    def refuse(request):
        raise httpx.ConnectError("connessione rifiutata")

    monkeypatch.setattr(entry, "AgentClient", lambda url: AgentClient(url, http=httpx.Client(
        transport=httpx.MockTransport(refuse), base_url=url
    )))
    monkeypatch.setattr(entry, "run", _must_not_call)
    assert main({}) == 1
    captured = capsys.readouterr()
    assert captured.err == (
        "Agente non disponibile: agente non raggiungibile su http://127.0.0.1:8000. "
        "Avvia il servizio con: python -m assistant.service\n"
    )
    assert captured.out == ""


def test_agent_on_a_closed_port_exits_1(capsys):
    assert main({"AGENT_URL": "http://127.0.0.1:1"}) == 1
    assert "agente non raggiungibile su http://127.0.0.1:1." in capsys.readouterr().err


def test_status_error_at_startup_exits_1(monkeypatch, capsys):
    def broken():
        raise RuntimeError("difetto")

    use_service(monkeypatch, model_status=broken)
    monkeypatch.setattr(entry, "run", _must_not_call)
    assert main({}) == 1
    assert capsys.readouterr().err == (
        "Agente non disponibile: errore interno dell'agente; dettagli nel log.\n"
    )


class ToolListFails(FakeMcpClient):
    def list_tools(self, timeout=None):
        raise ToolUnavailableError("sessione MCP chiusa")


def test_degraded_agent_warns_and_opens_the_conversation(monkeypatch, capsys):  # RF-59
    down = "LM Studio non raggiungibile su http://localhost:1234/v1"
    use_service(monkeypatch, client=ToolListFails(MCP_SPECS), model_status=lambda: (False, down))
    type_in(monkeypatch, "esci")
    assert main({}) == 0
    assert capsys.readouterr().out.startswith(
        "Attenzione: server MCP non disponibile (sessione MCP chiusa).\n"
        f"Attenzione: modello non disponibile ({down}).\n"
        f"{WELCOME}\n"
    )


def test_library_http_logs_hidden_at_info(monkeypatch, caplog):
    caplog.set_level(logging.INFO)  # as in the app, where the root is at INFO
    use_service(monkeypatch)
    monkeypatch.setattr(entry, "run", lambda session, **kw: None)
    main({})
    for library in ("httpx", "httpx2", "openai", "mcp", "fastmcp"):
        assert logging.getLogger(library).getEffectiveLevel() == logging.WARNING, library
