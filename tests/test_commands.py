import logging

import pytest

from assistant.commands import CommandResult, PromptCommands
from assistant.mcp_client import (
    PromptArgument,
    PromptMessage,
    PromptSpec,
    PromptUnavailableError,
)
from assistant.prompts import (
    EXPLAIN_DESCRIPTION,
    LEVEL_DESCRIPTION,
    STYLE_DESCRIPTION,
    SUMMARY_DESCRIPTION,
    TOPIC_DESCRIPTION,
)

from conftest import MCP_SPECS, FakeMcpClient

EXPLAIN = PromptSpec("spiega", EXPLAIN_DESCRIPTION, (
    PromptArgument("argomento", TOPIC_DESCRIPTION, True),
    PromptArgument("livello", LEVEL_DESCRIPTION, False),
))
SUMMARY = PromptSpec("riassumi_conversazione", SUMMARY_DESCRIPTION, (
    PromptArgument("stile", STYLE_DESCRIPTION, True),
))


def _never_called(arguments):
    raise AssertionError("prompts/get non deve essere chiamato")


def client_with(*specs: PromptSpec) -> FakeMcpClient:
    return FakeMcpClient(MCP_SPECS, prompts={spec.name: (spec, _never_called) for spec in specs})


SERVER_LIST = (
    "Prompt disponibili:\n"
    "- spiega: Spiega un argomento al livello scelto.\n"
    "    argomento (obbligatorio): Argomento da spiegare (per esempio Model Context Protocol).\n"
    "    livello (facoltativo): Livello della spiegazione: base, intermedio o avanzato "
    "(predefinito: base).\n"
    "- riassumi_conversazione: Riassume i turni della conversazione corrente.\n"
    "    stile (obbligatorio): Stile del riassunto: sintetico o dettagliato.\n"
    "Uso: /prompt nome chiave=valore (valori con spazi tra virgolette doppie)."
)


def test_list_shows_name_description_and_arguments():  # CA-56
    client = client_with(EXPLAIN, SUMMARY)
    result = PromptCommands(client).handle("/prompts")
    assert result == CommandResult(output=SERVER_LIST)
    assert client.prompt_lists == 1
    assert client.prompt_gets == []
    assert client.calls == []


def test_list_shows_a_prompt_without_arguments_or_descriptions():
    client = client_with(
        PromptSpec("saluta", "", ()),
        PromptSpec("ripeti", "", (PromptArgument("testo", "", True),)),
    )
    assert PromptCommands(client).handle("/prompts").output == (
        "Prompt disponibili:\n"
        "- saluta\n"
        "    nessun argomento\n"
        "- ripeti\n"
        "    testo (obbligatorio)\n"
        "Uso: /prompt nome chiave=valore (valori con spazi tra virgolette doppie)."
    )


def test_list_without_prompts():  # CA-56
    client = client_with()
    assert PromptCommands(client).handle("/prompts").output == "Il server MCP non offre prompt."
    assert client.prompt_lists == 1


@pytest.mark.parametrize("text", ["/PROMPTS", "/Prompts", "/prompts  "])
def test_command_word_ignores_case(text):
    assert PromptCommands(client_with(EXPLAIN, SUMMARY)).handle(text).output == SERVER_LIST


class ListFails(FakeMcpClient):
    def list_prompts(self):
        self.prompt_lists += 1
        raise PromptUnavailableError("sessione MCP chiusa")


def test_list_unavailable(caplog):  # CA-56
    caplog.set_level(logging.INFO)
    client = ListFails(MCP_SPECS)
    result = PromptCommands(client).handle("/prompts")
    assert result.output == "Errore: prompt non disponibili (sessione MCP chiusa)."
    assert [(r.levelno, r.getMessage()) for r in caplog.records] == [
        (logging.WARNING, 'prompts/list status=unavailable error="sessione MCP chiusa"'),
    ]


def test_list_is_logged(caplog):
    caplog.set_level(logging.INFO)
    PromptCommands(client_with(EXPLAIN, SUMMARY)).handle("/prompts")
    assert [(r.name, r.levelno, r.getMessage()) for r in caplog.records] == [
        ("assistant.commands", logging.INFO,
         "prompts/list count=2 names=spiega,riassumi_conversazione"),
    ]


def test_empty_list_is_logged(caplog):
    caplog.set_level(logging.INFO)
    PromptCommands(client_with()).handle("/prompts")
    assert [r.getMessage() for r in caplog.records] == ["prompts/list count=0 names="]


def test_list_with_arguments_is_rejected(caplog):
    caplog.set_level(logging.INFO)
    client = client_with(EXPLAIN)
    result = PromptCommands(client).handle("/prompts spiega")
    assert result.output == "Errore nel comando: il comando /prompts non ha argomenti."
    assert client.prompt_lists == 0
    assert [r.getMessage() for r in caplog.records] == [
        'prompt_command status=rejected reason="il comando /prompts non ha argomenti"',
    ]


@pytest.mark.parametrize(("text", "word"), [
    ("/promt", "/promt"),
    ("/aiuto per favore", "/aiuto"),
    ("/", "/"),
    ("/PROMPTSS", "/PROMPTSS"),
])
def test_unknown_command(text, word, caplog):
    caplog.set_level(logging.INFO)
    client = client_with(EXPLAIN)
    result = PromptCommands(client).handle(text)
    assert result.output == (
        f"Comando sconosciuto: '{word}'. Scrivi /prompts per l'elenco dei prompt."
    )
    assert client.prompt_lists == 0
    assert client.prompt_gets == []
    assert caplog.records == []


def test_prompt_messages_are_not_used_by_the_list():
    """/prompts never asks for the prompt text (prompts/get)."""
    calls = []
    spec = PromptSpec("spiega", "x", ())
    client = FakeMcpClient(
        MCP_SPECS, prompts={"spiega": (spec, lambda a: calls.append(a) or [PromptMessage("user", "t")])}
    )
    PromptCommands(client).handle("/prompts")
    assert calls == [] and client.prompt_gets == []
