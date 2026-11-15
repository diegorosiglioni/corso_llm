import json
import logging

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from assistant.api_client import AgentClient
from assistant.commands import (
    CommandResult,
    PromptCommands,
    PromptGetError,
    PromptListError,
    PromptRejectedError,
    PromptRequestError,
    available_prompts,
    parse_prompt_command,
    resolve_prompt,
)
from assistant.mcp_client import PromptArgument, PromptMessage, PromptSpec
from assistant.prompts import (
    EXPLAIN_DESCRIPTION,
    LEVEL_DESCRIPTION,
    STYLE_DESCRIPTION,
    SUMMARY_DESCRIPTION,
    TOPIC_DESCRIPTION,
)

from conftest import MCP_SPECS, FakeMcpClient, PromptListFails, fake_service

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


def commands_for(client) -> PromptCommands:
    """The commands of the CLI on the real app of the service with the fake MCP `client`."""
    return PromptCommands(AgentClient("http://agente.test", http=fake_service(client=client)))


def command_lines(caplog) -> list[tuple[int, str]]:
    """Log lines of the commands and of the host check (the API adds its own lines)."""
    return [(r.levelno, r.getMessage()) for r in caplog.records if r.name == "assistant.commands"]


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
    result = commands_for(client).handle("/prompts")
    assert result == CommandResult(output=SERVER_LIST)
    assert client.prompt_lists == 1
    assert client.prompt_gets == []
    assert client.calls == []


def test_list_shows_a_prompt_without_arguments_or_descriptions():
    client = client_with(
        PromptSpec("saluta", "", ()),
        PromptSpec("ripeti", "", (PromptArgument("testo", "", True),)),
    )
    assert commands_for(client).handle("/prompts").output == (
        "Prompt disponibili:\n"
        "- saluta\n"
        "    nessun argomento\n"
        "- ripeti\n"
        "    testo (obbligatorio)\n"
        "Uso: /prompt nome chiave=valore (valori con spazi tra virgolette doppie)."
    )


def test_list_without_prompts():  # CA-56
    client = client_with()
    assert commands_for(client).handle("/prompts").output == "Il server MCP non offre prompt."
    assert client.prompt_lists == 1


@pytest.mark.parametrize("text", ["/PROMPTS", "/Prompts", "/prompts  "])
def test_command_word_ignores_case(text):
    assert commands_for(client_with(EXPLAIN, SUMMARY)).handle(text).output == SERVER_LIST


def test_list_unavailable(caplog):  # CA-56
    caplog.set_level(logging.INFO)
    client = PromptListFails(MCP_SPECS)
    result = commands_for(client).handle("/prompts")
    assert result.output == "Errore: prompt non disponibili (sessione MCP chiusa)."
    assert command_lines(caplog) == [  # in the service, behind GET /prompts
        (logging.WARNING, 'prompts/list status=unavailable error="sessione MCP chiusa"'),
    ]


def test_list_with_the_agent_unreachable():  # CA-66
    def refuse(request):
        raise httpx.ConnectError("connessione rifiutata")

    http = httpx.Client(transport=httpx.MockTransport(refuse), base_url="http://agente.test")
    result = PromptCommands(AgentClient("http://agente.test", http=http)).handle("/prompts")
    assert result.output == "Errore: agente non raggiungibile su http://agente.test."


def test_list_is_logged(caplog):
    caplog.set_level(logging.INFO)
    commands_for(client_with(EXPLAIN, SUMMARY)).handle("/prompts")
    assert command_lines(caplog) == [
        (logging.INFO, "prompts/list count=2 names=spiega,riassumi_conversazione"),
    ]


def test_empty_list_is_logged(caplog):
    caplog.set_level(logging.INFO)
    commands_for(client_with()).handle("/prompts")
    assert command_lines(caplog) == [(logging.INFO, "prompts/list count=0 names=")]


def test_available_prompts_returns_the_list(caplog):  # shared by the CLI and GET /prompts
    caplog.set_level(logging.INFO)
    assert available_prompts(client_with(EXPLAIN, SUMMARY)) == [EXPLAIN, SUMMARY]
    assert [r.getMessage() for r in caplog.records] == [
        "prompts/list count=2 names=spiega,riassumi_conversazione"
    ]


def test_available_prompts_unavailable(caplog):
    caplog.set_level(logging.INFO)
    with pytest.raises(PromptListError) as raised:
        available_prompts(PromptListFails(MCP_SPECS))
    assert str(raised.value) == "prompt non disponibili (sessione MCP chiusa)"
    assert [(r.levelno, r.getMessage()) for r in caplog.records] == [
        (logging.WARNING, 'prompts/list status=unavailable error="sessione MCP chiusa"'),
    ]


def test_list_with_arguments_is_rejected(caplog):
    caplog.set_level(logging.INFO)
    client = client_with(EXPLAIN)
    result = commands_for(client).handle("/prompts spiega")
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
    result = commands_for(client).handle(text)
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
    commands_for(client).handle("/prompts")
    assert calls == [] and client.prompt_gets == []


# --- /prompt (lesson 6, step 5, point 5; since step 6 the host check is in the service) ---

def explain_text(arguments):
    return [PromptMessage("user", f"Spiegami {arguments['argomento']}.")]


def client_answering(messages_for=explain_text, *specs: PromptSpec) -> FakeMcpClient:
    specs = specs or (EXPLAIN, SUMMARY)
    return FakeMcpClient(MCP_SPECS, prompts={spec.name: (spec, messages_for) for spec in specs})


def _json(text):
    return json.dumps(text, ensure_ascii=False)


@pytest.mark.parametrize(("text", "name", "arguments"), [
    ('/prompt spiega argomento="Model Context Protocol" livello=base',
     "spiega", {"argomento": "Model Context Protocol", "livello": "base"}),
    ("/prompt spiega argomento=l'IA", "spiega", {"argomento": "l'IA"}),
    ('/prompt spiega argomento="a=b"', "spiega", {"argomento": "a=b"}),
    ("/prompt spiega argomento=C#", "spiega", {"argomento": "C#"}),
    ("/prompt spiega argomento=x=y", "spiega", {"argomento": "x=y"}),
    ('/prompt spiega "argomento=due parole"', "spiega", {"argomento": "due parole"}),
    ("/prompt   spiega   argomento=MCP  ", "spiega", {"argomento": "MCP"}),
    ("/prompt riassumi_conversazione stile=sintetico", "riassumi_conversazione",
     {"stile": "sintetico"}),
])
def test_parse_prompt_command(text, name, arguments):  # CA-55
    assert parse_prompt_command(text.split(maxsplit=1)[1]) == (name, arguments)


@pytest.mark.parametrize("word", ["/PROMPT", "/Prompt", "/prompt"])
def test_prompt_command_returns_name_and_arguments(word):  # CA-55, CA-66
    client = client_answering()
    result = commands_for(client).handle(f"{word} spiega argomento=MCP")
    assert result == CommandResult(prompt=("spiega", {"argomento": "MCP"}))
    assert client.prompt_lists == 0 and client.prompt_gets == []  # the service checks it later


@pytest.mark.parametrize(("text", "reason"), [
    ('/prompt spiega argomento="Model Context', "virgolette non chiuse"),
    ("/prompt", "manca il nome del prompt"),
    ("/prompt   ", "manca il nome del prompt"),
    ('/prompt ""', "manca il nome del prompt"),
    ("/prompt spiega MCP", "argomento non nella forma chiave=valore: 'MCP'"),
    ("/prompt spiega =MCP", "argomento non nella forma chiave=valore: '=MCP'"),
    ('/prompt spiega ""', "argomento non nella forma chiave=valore: ''"),
    ("/prompt spiega argomento=a argomento=b", "argomento ripetuto: 'argomento'"),
    ("/prompt spiega argomento=", "argomento senza valore: 'argomento'"),
    ('/prompt spiega argomento=""', "argomento senza valore: 'argomento'"),
])
def test_syntax_errors_call_nothing(text, reason, caplog):  # CA-55, CA-66
    caplog.set_level(logging.INFO)
    client = client_answering()
    result = commands_for(client).handle(text)
    assert result == CommandResult(output=(
        f"Errore nel comando: {reason}. "
        "Uso: /prompt nome chiave=valore (valori con spazi tra virgolette doppie)."
    ))
    assert client.prompt_lists == 0 and client.prompt_gets == []
    assert [r.getMessage() for r in caplog.records] == [  # no request to the service
        f"prompt_command status=rejected reason={_json(reason)}",
    ]


def resolve(client, text: str):
    """The host check of the service on the request of the command `text`."""
    name, arguments = parse_prompt_command(text.split(maxsplit=1)[1])
    return resolve_prompt(client, name, arguments)


@pytest.mark.parametrize(("text", "reason"), [
    ("/prompt traduci testo=ciao",
     "prompt sconosciuto: 'traduci' (disponibili: spiega, riassumi_conversazione)"),
    ("/prompt Spiega argomento=MCP",
     "prompt sconosciuto: 'Spiega' (disponibili: spiega, riassumi_conversazione)"),
    ("/prompt spiega argomento=MCP lingua=it tono=serio",
     "argomenti sconosciuti per 'spiega': 'lingua', 'tono' (attesi: argomento, livello)"),
    ("/prompt spiega livello=base",
     "argomenti obbligatori mancanti per 'spiega': 'argomento'"),
    ("/prompt riassumi_conversazione",
     "argomenti obbligatori mancanti per 'riassumi_conversazione': 'stile'"),
    ("/prompt spiega Argomento=MCP",
     "argomenti sconosciuti per 'spiega': 'Argomento' (attesi: argomento, livello)"),
])
def test_request_checked_against_the_list(text, reason, caplog):  # CA-57
    caplog.set_level(logging.INFO)
    client = client_with(EXPLAIN, SUMMARY)  # prompts/get would raise AssertionError
    with pytest.raises(PromptRejectedError) as raised:
        resolve(client, text)
    assert str(raised.value) == reason
    assert client.prompt_lists == 1 and client.prompt_gets == []
    assert [r.getMessage() for r in caplog.records] == [
        "prompts/list count=2 names=spiega,riassumi_conversazione",
        f"prompt_command status=rejected reason={_json(reason)}",
    ]


def test_unknown_prompt_on_a_server_without_prompts():
    with pytest.raises(PromptRejectedError) as raised:
        resolve(client_with(), "/prompt spiega argomento=MCP")
    assert str(raised.value) == "prompt sconosciuto: 'spiega' (disponibili: nessuno)"


def test_arguments_for_a_prompt_without_arguments():
    with pytest.raises(PromptRejectedError) as raised:
        resolve(client_with(PromptSpec("saluta", "", ())), "/prompt saluta a=1")
    assert str(raised.value) == "argomenti sconosciuti per 'saluta': 'a' (attesi: nessuno)"


def test_valid_request_returns_the_messages(caplog):  # CA-57
    caplog.set_level(logging.INFO)
    text = "Spiegami Model Context Protocol a livello base: con parole semplici."
    client = client_answering(lambda a: [PromptMessage("user", text)])
    messages = resolve(client, '/prompt spiega argomento="Model Context Protocol" livello=base')
    assert messages == [HumanMessage(text)]
    assert client.prompt_gets == [
        ("spiega", {"argomento": "Model Context Protocol", "livello": "base"})
    ]
    assert client.calls == []
    assert [(r.name, r.levelno, r.getMessage()) for r in caplog.records] == [
        ("assistant.commands", logging.INFO,
         "prompts/list count=2 names=spiega,riassumi_conversazione"),
        ("assistant.commands", logging.INFO,
         'prompts/get name=spiega arguments={"argomento": "Model Context Protocol", '
         '"livello": "base"} status=ok messages=1'),
        ("assistant.commands", logging.INFO,
         f"prompts/get name=spiega message=1/1 role=user text={_json(text)}"),
    ]


def test_optional_argument_may_be_omitted():
    client = client_answering()
    assert resolve(client, "/prompt spiega argomento=MCP") == [HumanMessage("Spiegami MCP.")]
    assert client.prompt_gets == [("spiega", {"argomento": "MCP"})]


def test_user_and_assistant_messages_are_converted(caplog):
    caplog.set_level(logging.INFO)
    client = client_answering(lambda a: [
        PromptMessage("user", "Esempio di domanda"),
        PromptMessage("assistant", "Esempio di risposta"),
        PromptMessage("user", "Ora tocca a te"),
    ])
    assert resolve(client, "/prompt spiega argomento=MCP") == [
        HumanMessage("Esempio di domanda"), AIMessage("Esempio di risposta"),
        HumanMessage("Ora tocca a te"),
    ]
    assert [r.getMessage() for r in caplog.records][-3:] == [
        'prompts/get name=spiega message=1/3 role=user text="Esempio di domanda"',
        'prompts/get name=spiega message=2/3 role=assistant text="Esempio di risposta"',
        'prompts/get name=spiega message=3/3 role=user text="Ora tocca a te"',
    ]


@pytest.mark.parametrize(("received", "reason"), [
    ([], "nessun messaggio"),
    ([PromptMessage("system", "regole"), PromptMessage("user", "domanda")],
     "ruolo non ammesso nel messaggio 1: 'system'"),
    ([PromptMessage("user", "domanda"), PromptMessage("assistant", "risposta")],
     "l'ultimo messaggio non è dell'utente"),
])
def test_unusable_messages_do_not_reach_the_model(received, reason, caplog):
    caplog.set_level(logging.INFO)
    with pytest.raises(PromptGetError) as raised:
        resolve(client_answering(lambda a: received), "/prompt spiega argomento=MCP")
    assert str(raised.value) == f"il prompt 'spiega' non è utilizzabile ({reason})"
    last = caplog.records[-1]
    assert (last.levelno, last.getMessage()) == (
        logging.WARNING, f"prompt_command status=unusable name=spiega reason={_json(reason)}"
    )


def test_unusable_reason_loses_its_final_period(monkeypatch):  # R-A5
    def unusable(received):
        raise ValueError("motivo con il punto.")

    monkeypatch.setattr("assistant.commands.to_messages", unusable)
    with pytest.raises(PromptGetError) as raised:
        resolve(client_answering(lambda a: [PromptMessage("user", "domanda")]),
                "/prompt spiega argomento=MCP")
    assert str(raised.value) == "il prompt 'spiega' non è utilizzabile (motivo con il punto)"


def test_value_rejected_by_the_server(caplog):  # CA-57
    caplog.set_level(logging.INFO)
    error = "Livello non valido: 'esperto'. Valori ammessi: base, intermedio, avanzato."

    def refuse(arguments):
        raise ValueError(error)

    with pytest.raises(PromptGetError) as raised:
        resolve(client_answering(refuse), "/prompt spiega argomento=MCP livello=esperto")
    assert str(raised.value) == (
        "il prompt 'spiega' non è disponibile "
        "(Livello non valido: 'esperto'. Valori ammessi: base, intermedio, avanzato)"
    )
    assert [(r.levelno, r.getMessage()) for r in caplog.records][-1] == (
        logging.WARNING,
        'prompts/get name=spiega arguments={"argomento": "MCP", "livello": "esperto"} '
        f"status=unavailable error={_json(error)}",
    )


def test_list_unavailable_for_prompt(caplog):
    caplog.set_level(logging.INFO)
    client = PromptListFails(MCP_SPECS)
    with pytest.raises(PromptListError) as raised:
        resolve(client, "/prompt spiega argomento=MCP")
    assert str(raised.value) == "prompt non disponibili (sessione MCP chiusa)"
    assert client.prompt_gets == []
    assert [r.getMessage() for r in caplog.records] == [
        'prompts/list status=unavailable error="sessione MCP chiusa"',
    ]


def test_texts_with_quotes_and_newlines_stay_on_one_log_line(caplog):
    caplog.set_level(logging.INFO)
    client = client_answering(lambda a: [PromptMessage("user", 'Riga "uno"\nriga due')])
    resolve(client, "/prompt spiega argomento=MCP")
    assert caplog.records[-1].getMessage() == (
        r'prompts/get name=spiega message=1/1 role=user text="Riga \"uno\"\nriga due"'
    )


# --- resolve_prompt, shared by the CLI and the HTTP service (lesson 6, step 6, point 3) ---

def test_resolve_prompt_returns_the_messages(caplog):
    caplog.set_level(logging.INFO)
    client = client_answering()
    assert resolve_prompt(client, "spiega", {"argomento": "MCP"}) == [HumanMessage("Spiegami MCP.")]
    assert client.prompt_gets == [("spiega", {"argomento": "MCP"})]
    assert [r.getMessage() for r in caplog.records] == [
        "prompts/list count=2 names=spiega,riassumi_conversazione",
        'prompts/get name=spiega arguments={"argomento": "MCP"} status=ok messages=1',
        'prompts/get name=spiega message=1/1 role=user text="Spiegami MCP."',
    ]


def test_resolve_prompt_rejected_without_prompts_get(caplog):
    caplog.set_level(logging.INFO)
    client = client_with(EXPLAIN, SUMMARY)  # prompts/get would raise AssertionError
    reason = "argomenti obbligatori mancanti per 'spiega': 'argomento'"
    with pytest.raises(PromptRejectedError) as raised:
        resolve_prompt(client, "spiega", {"livello": "base"})
    assert str(raised.value) == reason
    assert client.prompt_gets == []
    assert caplog.records[-1].getMessage() == f"prompt_command status=rejected reason={_json(reason)}"


def test_resolve_prompt_list_unavailable():
    client = PromptListFails(MCP_SPECS)
    with pytest.raises(PromptListError, match=r"^prompt non disponibili \(sessione MCP chiusa\)$"):
        resolve_prompt(client, "spiega", {"argomento": "MCP"})
    assert client.prompt_gets == []


def test_resolve_prompt_value_rejected_by_the_server():
    def refuse(arguments):
        raise ValueError("Livello non valido")

    with pytest.raises(PromptGetError) as raised:
        resolve_prompt(client_answering(refuse), "spiega", {"argomento": "MCP", "livello": "x"})
    assert str(raised.value) == "il prompt 'spiega' non è disponibile (Livello non valido)"


def test_resolve_prompt_unusable_messages():
    client = client_answering(lambda a: [])
    with pytest.raises(PromptGetError) as raised:
        resolve_prompt(client, "spiega", {"argomento": "MCP"})
    assert str(raised.value) == "il prompt 'spiega' non è utilizzabile (nessun messaggio)"


def test_prompt_request_errors_share_a_base_class():
    for error in (PromptRejectedError, PromptListError, PromptGetError):
        assert issubclass(error, PromptRequestError)
