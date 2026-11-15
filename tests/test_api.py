import json
import logging
import re
import threading
import time

import anyio
import httpx2
import openai
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

from assistant.api import StreamTurn, _in_thread, _stream_events
from assistant.mcp_client import PromptArgument, PromptMessage, PromptSpec
from assistant.reviewer import ReviewDecision
from assistant.tools import ToolUnavailableError
from conftest import (
    MCP_SPECS,
    MODEL_ID,
    FakeMcpClient,
    FakeModel,
    PromptListFails,
    StreamingFakeModel,
    fake_graph,
    fake_service,
    lm_studio_error,
    model_ok,
    sse,
    tool_call,
)

TOKYO = {"timezone": "Asia/Tokyo", "datetime": "2026-10-27T00:47:12+09:00"}
EXPLAIN = PromptSpec("spiega", "Spiega un argomento.", (
    PromptArgument("argomento", "Argomento.", True),
    PromptArgument("livello", "Livello.", False),
))


def explain_text(arguments):
    return [PromptMessage("user", f"Spiegami {arguments['argomento']}.")]


def mcp_client(messages_for=explain_text) -> FakeMcpClient:
    return FakeMcpClient(MCP_SPECS, prompts={"spiega": (EXPLAIN, messages_for)})


def api(model=None, client=None, model_status=model_ok, **graph_options) -> TestClient:
    """Service on a fake graph with the prompt 'spiega'; the default model fails if called."""
    return fake_service(model, client or mcp_client(), model_status, **graph_options)


def api_lines(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == "assistant.api"]


def without_duration(line: str) -> str:
    assert re.search(r" duration_ms=\d+$", line), line
    return re.sub(r" duration_ms=\d+$", "", line)


# --- POST /chat with a message (CA-62) ---

def test_chat_with_a_message_and_a_tool():
    model = FakeModel([tool_call(), AIMessage("A Tokyo sono le 00:47.")])
    response = api(model).post("/chat", json={"message": "Che ore sono a Tokyo?"})
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "A Tokyo sono le 00:47."
    assert body["tools_used"] == [
        {"name": "get_current_time", "args": {"timezone": "Asia/Tokyo"}, "result": TOKYO, "ok": True}
    ]
    assert body["summary"] == ""
    history = body["history"]
    assert history[0] == {"role": "user", "content": "Che ore sono a Tokyo?"}
    assert history[1] == {"role": "assistant", "content": "", "tool_calls": [
        {"id": "c1", "name": "get_current_time", "args": {"timezone": "Asia/Tokyo"}}
    ]}
    assert {k: v for k, v in history[2].items() if k != "content"} == {
        "role": "tool", "tool_call_id": "c1", "name": "get_current_time"
    }
    assert json.loads(history[2]["content"]) == TOKYO
    assert history[3] == {"role": "assistant", "content": "A Tokyo sono le 00:47."}
    assert len(history) == 4


def test_message_is_stripped_like_in_the_terminal():
    model = FakeModel([AIMessage("Ciao!")])
    body = api(model).post("/chat", json={"message": "  ciao  "}).json()
    assert model.calls[0][-1].content == "ciao"
    assert body["history"][0] == {"role": "user", "content": "ciao"}


def test_chat_continues_a_previous_turn():  # CA-62
    model = FakeModel([AIMessage("Piacere, Paolo."), AIMessage("Ti chiami Paolo.")])
    service = api(model)
    first = service.post("/chat", json={"message": "Mi chiamo Paolo"}).json()
    second = service.post("/chat", json={
        "message": "Come mi chiamo?", "history": first["history"], "summary": first["summary"],
    }).json()
    assert [m.content for m in model.calls[1][1:]] == [
        "Mi chiamo Paolo", "Piacere, Paolo.", "Come mi chiamo?"
    ]
    assert second["reply"] == "Ti chiami Paolo."
    assert second["history"][:2] == first["history"]
    assert [m["content"] for m in second["history"][2:]] == ["Come mi chiamo?", "Ti chiami Paolo."]


def test_service_keeps_no_conversation():
    model = FakeModel([AIMessage("Piacere."), AIMessage("Non lo so.")])
    service = api(model)
    service.post("/chat", json={"message": "Mi chiamo Paolo"})
    body = service.post("/chat", json={"message": "Come mi chiamo?"}).json()
    assert [m.content for m in model.calls[1][1:]] == ["Come mi chiamo?"]
    assert len(body["history"]) == 2


def test_summary_of_the_caller_reaches_the_agent():
    model = FakeModel([AIMessage("Ti chiami Paolo.")])
    body = api(model).post("/chat", json={"message": "Come mi chiamo?", "summary": "S0"}).json()
    assert model.calls[0][0].content.endswith("Riassunto della conversazione precedente:\nS0")
    assert body["summary"] == "S0"


def test_summary_and_history_after_a_compression():
    service = api(
        FakeModel([AIMessage("r3")]), summary_model=FakeModel([AIMessage("S1")]),
        summary_max_messages=4, summary_keep_messages=3,
    )
    history = [
        {"role": "user", "content": "d1"}, {"role": "assistant", "content": "r1"},
        {"role": "user", "content": "d2"}, {"role": "assistant", "content": "r2"},
    ]
    body = service.post("/chat", json={"message": "d3", "history": history}).json()
    assert body["summary"] == "S1"
    assert body["history"] == history[2:] + [
        {"role": "user", "content": "d3"}, {"role": "assistant", "content": "r3"}
    ]


def test_history_with_every_role_and_field_comes_back_unchanged():
    history = [
        {"role": "user", "content": "d1"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c1", "name": "calculate", "args": {"expression": "2+2"}}
        ]},
        {"role": "tool", "content": '{"result": 4}', "tool_call_id": "c1", "name": "calculate"},
        {"role": "assistant", "content": "", "invalid_tool_calls": [
            {"id": "c2", "name": "calculate", "args": None, "error": None}
        ]},
        {"role": "tool", "content": '{"error": "x"}', "tool_call_id": "c2", "name": "calculate"},
        {"role": "assistant", "content": "bozza"},
        {"role": "user", "content": "rivedi", "name": "reviewer"},
        {"role": "assistant", "content": "Fa 4."},
    ]
    model = FakeModel([AIMessage("Ciao.")])
    body = api(model).post("/chat", json={"message": "ciao", "history": history}).json()
    assert body["history"][:len(history)] == history
    assert body["tools_used"] == []  # tools of earlier turns are not counted


def test_tool_error_stays_in_the_turn():
    model = FakeModel([tool_call("Marte/Base"), AIMessage("Fuso sconosciuto.")])
    response = api(model).post("/chat", json={"message": "ore su Marte?"})
    assert response.status_code == 200
    [used] = response.json()["tools_used"]
    assert used["ok"] is False and "Fuso orario sconosciuto" in used["result"]["error"]


# --- POST /chat with an MCP prompt (CA-62) ---

def test_chat_with_a_prompt(caplog):
    caplog.set_level(logging.INFO)
    model = FakeModel([AIMessage("MCP è un protocollo.")])
    client = mcp_client()
    response = api(model, client).post("/chat", json={
        "prompt": {"name": "spiega", "arguments": {"argomento": "MCP"}}
    })
    assert response.status_code == 200
    assert response.json()["reply"] == "MCP è un protocollo."
    assert model.calls[0][-1].content == "Spiegami MCP."
    assert response.json()["history"][0] == {"role": "user", "content": "Spiegami MCP."}
    assert client.prompt_gets == [("spiega", {"argomento": "MCP"})]
    messages = [r.getMessage() for r in caplog.records]
    assert 'prompts/get name=spiega arguments={"argomento": "MCP"} status=ok messages=1' in messages
    assert api_lines(caplog)[0] == (
        'api request=chat kind=prompt name="spiega" history=0 summary_chars=0'
    )


def test_prompt_name_is_escaped_in_the_log(caplog):  # R-A6
    caplog.set_level(logging.INFO)
    api().post("/chat", json={"prompt": {"name": "a\nb"}})
    assert api_lines(caplog)[0] == (
        'api request=chat kind=prompt name="a\\nb" history=0 summary_chars=0'
    )
    assert not any(r.getMessage().startswith("b") for r in caplog.records)


def test_long_prompt_name_is_cut_in_the_log(caplog):  # Review Focus 4
    caplog.set_level(logging.INFO)
    api().post("/chat", json={"prompt": {"name": "p" * 5000}})
    line = api_lines(caplog)[0]
    assert 'name="' + "p" * 64 + '"' in line, line
    assert "p" * 65 not in line, line


PROMPT_LIMITS = [
    pytest.param({"name": "p" * 65}, "il nome del prompt supera 64 caratteri", id="name"),
    pytest.param({"name": "spiega", "arguments": {f"a{i}": "x" for i in range(11)}},
                 "il prompt ha più di 10 argomenti", id="arguments"),
    pytest.param({"name": "spiega", "arguments": {"a" * 65: "x"}},
                 "un nome di argomento supera 64 caratteri", id="argument-name"),
    pytest.param({"name": "spiega", "arguments": {"argomento": "x" * 1001}},
                 "il valore dell'argomento 'argomento' supera 1000 caratteri", id="value"),
]


@pytest.mark.parametrize("endpoint", ["/chat", "/chat/stream"])
@pytest.mark.parametrize(("prompt", "detail"), PROMPT_LIMITS)
def test_prompt_size_limits(endpoint, prompt, detail, caplog):  # R-A7
    caplog.set_level(logging.DEBUG)
    client = mcp_client()
    response = api(client=client).post(endpoint, json={"prompt": prompt})
    assert response.status_code == 400, response.text
    assert response.json() == {"error": "prompt_rejected", "detail": detail}
    assert client.prompt_gets == []
    assert client.prompt_lists == 0
    assert "x" * 1001 not in caplog.text


def test_prompt_at_the_size_limits_passes():  # R-A7
    client = mcp_client()
    arguments = {f"{i}" + "a" * 63: "x" * 1000 for i in range(10)}
    response = api(client=client).post("/chat", json={"prompt": {"name": "p" * 64, "arguments": arguments}})
    assert response.status_code == 400, response.text
    assert response.json()["error"] == "prompt_rejected"
    assert "supera" not in response.json()["detail"] and "più di" not in response.json()["detail"]
    assert client.prompt_lists == 1


def test_prompt_arguments_are_optional():
    model = FakeModel([AIMessage("ok")])
    client = FakeMcpClient(MCP_SPECS, prompts={
        "saluta": (PromptSpec("saluta", "", ()), lambda a: [PromptMessage("user", "Ciao")])
    })
    response = api(model, client).post("/chat", json={"prompt": {"name": "saluta"}})
    assert response.status_code == 200
    assert client.prompt_gets == [("saluta", {})]


def _never_called(arguments):
    raise AssertionError("prompts/get non deve essere chiamato")


@pytest.mark.parametrize(("prompt", "detail"), [
    ({"name": "traduci"}, "prompt sconosciuto: 'traduci' (disponibili: spiega)"),
    ({"name": "spiega", "arguments": {"argomento": "MCP", "tono": "serio"}},
     "argomenti sconosciuti per 'spiega': 'tono' (attesi: argomento, livello)"),
    ({"name": "spiega", "arguments": {"livello": "base"}},
     "argomenti obbligatori mancanti per 'spiega': 'argomento'"),
])
def test_prompt_rejected_by_the_host(prompt, detail):  # CA-62
    client = mcp_client(_never_called)
    response = api(client=client).post("/chat", json={"prompt": prompt})  # model never called
    assert (response.status_code, response.json()) == (
        400, {"error": "prompt_rejected", "detail": detail}
    )
    assert client.prompt_lists == 1 and client.prompt_gets == []


def test_prompt_list_unavailable(caplog):
    caplog.set_level(logging.INFO)
    client = PromptListFails(MCP_SPECS)
    response = api(client=client).post("/chat", json={"prompt": {"name": "spiega"}})
    assert (response.status_code, response.json()) == (503, {
        "error": "mcp_unavailable", "detail": "prompt non disponibili (sessione MCP chiusa)"
    })
    assert client.prompt_gets == []
    [record] = [r for r in caplog.records if r.name == "assistant.api" and "response" in r.msg]
    assert record.levelno == logging.WARNING


def test_prompt_value_rejected_by_the_server():
    def refuse(arguments):
        raise ValueError("Livello non valido: 'esperto'.")

    response = api(client=mcp_client(refuse)).post("/chat", json={
        "prompt": {"name": "spiega", "arguments": {"argomento": "MCP", "livello": "esperto"}}
    })
    assert (response.status_code, response.json()) == (502, {
        "error": "prompt_unavailable",
        "detail": "il prompt 'spiega' non è disponibile (Livello non valido: 'esperto'.)",
    })


def test_prompt_with_unusable_messages():
    client = mcp_client(lambda a: [PromptMessage("assistant", "risposta")])
    response = api(client=client).post("/chat", json={
        "prompt": {"name": "spiega", "arguments": {"argomento": "MCP"}}
    })
    assert (response.status_code, response.json()) == (502, {
        "error": "prompt_unavailable",
        "detail": "il prompt 'spiega' non è utilizzabile (l'ultimo messaggio non è dell'utente)",
    })


# --- Request errors ---

@pytest.mark.parametrize(("body", "detail"), [
    ({}, "indicare esattamente uno tra 'message' e 'prompt'"),
    ({"message": None, "prompt": None}, "indicare esattamente uno tra 'message' e 'prompt'"),
    ({"message": "ciao", "prompt": {"name": "spiega"}},
     "indicare esattamente uno tra 'message' e 'prompt'"),
    ({"message": ""}, "il campo 'message' è vuoto"),
    ({"message": " \n "}, "il campo 'message' è vuoto"),
])
def test_invalid_request(body, detail):
    client = mcp_client(_never_called)
    response = api(client=client).post("/chat", json=body)
    assert (response.status_code, response.json()) == (
        400, {"error": "invalid_request", "detail": detail}
    )
    assert client.prompt_lists == 0


@pytest.mark.parametrize(("history", "detail"), [
    ([{"role": "tool", "content": "{}", "tool_call_id": "c1"}],
     "messaggio 1: risposta di uno strumento senza una chiamata corrispondente"),
    ([{"role": "user", "content": "d1"},
      {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "name": "calculate",
                                                           "args": {}}]}],
     "messaggio 2: chiamata 'calculate' (id 'c1') senza risposta alla fine della cronologia"),
    ([{"role": "tool", "content": "{}", "tool_call_id": ""}],
     "messaggio 1: il campo 'tool_call_id' deve essere un testo non vuoto"),
    ([{"role": "assistant", "content": "", "tool_calls": [{"id": "", "name": "x", "args": {}}]}],
     "messaggio 1: chiamata 1 di 'tool_calls' non valida (il campo 'id' deve essere un testo "
     "non vuoto)"),
])
def test_invalid_history(history, detail):
    client = mcp_client(_never_called)
    for opening in ({"message": "ciao"}, {"prompt": {"name": "spiega"}}):
        response = api(client=client).post("/chat", json={**opening, "history": history})
        assert (response.status_code, response.json()) == (
            400, {"error": "invalid_history", "detail": detail}
        )
    assert client.prompt_lists == 0  # a bad history calls nothing


@pytest.mark.parametrize("body", [
    {"message": "ciao", "history": [{"role": "system", "content": "regole"}]},
    {"message": "ciao", "history": [{"role": "robot", "content": "x"}]},
    {"message": "ciao", "history": [{"content": "x"}]},
    {"message": "ciao", "history": [{"role": "user"}]},
    {"message": "ciao", "history": [{"role": "user", "content": 3}]},
    {"message": "ciao", "history": [{"role": "user", "content": "x", "id": "m1"}]},
    {"message": "ciao", "history": [{"role": "tool", "content": "x"}]},
    {"message": "ciao", "history": {"role": "user", "content": "x"}},
    {"message": 3},
    {"message": "ciao", "summary": None},
    {"message": "ciao", "session": "s1"},
    {"prompt": {"name": "spiega", "arguments": {"argomento": 3}}},
    {"prompt": {"arguments": {}}},
])
def test_body_not_matching_the_schema(body, caplog):
    caplog.set_level(logging.INFO)
    client = mcp_client(_never_called)
    response = api(client=client).post("/chat", json=body)
    assert response.status_code == 422
    assert "detail" in response.json()  # FastAPI's format
    assert client.prompt_lists == 0
    assert api_lines(caplog) == []  # FastAPI rejects the body before the endpoint


# --- Logs (specification §7) ---

def test_log_lines_of_a_turn(caplog):
    caplog.set_level(logging.INFO)
    model = FakeModel([tool_call(), AIMessage("A Tokyo sono le 00:47.")])
    history = [{"role": "user", "content": "d1"}, {"role": "assistant", "content": "r1"}]
    api(model).post("/chat", json={"message": "Che ore sono?", "history": history, "summary": "S0"})
    request, response = api_lines(caplog)
    assert request == "api request=chat kind=message history=2 summary_chars=2"
    assert without_duration(response) == (
        "api response=chat status=200 tools=get_current_time reply_chars=22 history=6"
    )
    texts = " ".join(api_lines(caplog))
    assert "Che ore sono" not in texts and "d1" not in texts


def test_log_line_without_tools(caplog):
    caplog.set_level(logging.INFO)
    api(FakeModel([AIMessage("Ciao!")])).post("/chat", json={"message": "ciao"})
    assert without_duration(api_lines(caplog)[1]) == (
        "api response=chat status=200 tools= reply_chars=5 history=2"
    )


def test_log_lines_of_an_error(caplog):
    caplog.set_level(logging.INFO)
    history = [{"role": "tool", "content": "{}", "tool_call_id": "c1"}]
    api().post("/chat", json={"message": "ciao", "history": history})
    records = [r for r in caplog.records if r.name == "assistant.api"]
    assert [r.levelno for r in records] == [logging.INFO, logging.INFO]
    assert records[0].getMessage() == "api request=chat kind=message history=1 summary_chars=0"
    assert without_duration(records[1].getMessage()) == (
        'api response=chat status=400 error=invalid_history detail="messaggio 1: risposta di uno '
        'strumento senza una chiamata corrispondente"'
    )


@pytest.mark.parametrize(("body", "kind"), [
    ({}, "none"),
    ({"message": "x", "prompt": {"name": "spiega"}}, "both"),
])
def test_request_line_of_an_invalid_request(body, kind, caplog):
    caplog.set_level(logging.INFO)
    api().post("/chat", json=body)
    assert api_lines(caplog)[0] == f"api request=chat kind={kind} history=0 summary_chars=0"


# --- OpenAPI (CA-62) ---

def test_openapi_documents_the_chat_endpoint():
    service = api()
    document = service.get("/openapi.json").json()
    assert document["info"]["title"] == "Assistente del laboratorio — agente"
    operation = document["paths"]["/chat"]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ChatRequest"
    }
    assert set(operation["responses"]) == {"200", "400", "422", "500", "502", "503"}
    for code in ("400", "500", "502", "503"):
        schema = operation["responses"][code]["content"]["application/json"]["schema"]
        assert schema == {"$ref": "#/components/schemas/ErrorBody"}
    schemas = document["components"]["schemas"]
    for name in ("ChatRequest", "ChatResponse", "ErrorBody", "PromptRequest", "ToolUse",
                 "UserMessage", "AssistantMessage", "ToolResultMessage", "ToolCall",
                 "InvalidToolCall"):
        assert name in schemas
    history = schemas["ChatRequest"]["properties"]["history"]["items"]
    assert history["discriminator"]["propertyName"] == "role"
    assert set(schemas["ChatResponse"]["required"]) == {"reply", "tools_used", "history", "summary"}


def test_docs_page_is_served():
    response = api().get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()


# --- LM Studio and unexpected errors (specification §6, CA-63) ---

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"


def lm_studio_timeout() -> openai.APITimeoutError:
    return openai.APITimeoutError(request=httpx2.Request("POST", LM_STUDIO_URL))


def lm_studio_status_error() -> openai.InternalServerError:
    request = httpx2.Request("POST", LM_STUDIO_URL)
    return openai.InternalServerError(
        "Model unloaded", response=httpx2.Response(500, request=request), body=None
    )


def lm_studio_generic_error() -> openai.APIError:
    return openai.APIError("risposta inattesa", httpx2.Request("POST", LM_STUDIO_URL), body=None)


@pytest.mark.parametrize(("error", "status", "code", "detail"), [
    (lm_studio_error(), 503, "model_unavailable", "LM Studio non raggiungibile: Connection error."),
    (lm_studio_timeout(), 503, "model_unavailable",
     "LM Studio non raggiungibile: Request timed out."),
    (lm_studio_status_error(), 502, "model_error",
     "LM Studio non ha risposto correttamente: Model unloaded"),
    (lm_studio_generic_error(), 502, "model_error",
     "LM Studio non ha risposto correttamente: risposta inattesa"),
], ids=["connection", "timeout", "status", "generic"])
def test_lm_studio_errors(error, status, code, detail, caplog):
    caplog.set_level(logging.INFO)
    history = [{"role": "user", "content": "d1"}, {"role": "assistant", "content": "r1"}]
    response = api(FakeModel([error])).post("/chat", json={"message": "ciao", "history": history})
    assert (response.status_code, response.json()) == (status, {"error": code, "detail": detail})
    records = [r for r in caplog.records if r.name == "assistant.api"]
    assert records[-1].levelno == logging.WARNING
    assert without_duration(records[-1].getMessage()) == (
        f"api response=chat status={status} error={code} "
        f"detail={json.dumps(detail, ensure_ascii=False)}"
    )


def test_lm_studio_error_during_a_prompt_turn():
    response = api(FakeModel([lm_studio_error()])).post("/chat", json={
        "prompt": {"name": "spiega", "arguments": {"argomento": "MCP"}}
    })
    assert (response.status_code, response.json()["error"]) == (503, "model_unavailable")


def test_unexpected_error_is_500_with_the_traceback_only_in_the_log(caplog):
    caplog.set_level(logging.INFO)
    response = api(FakeModel([RuntimeError("segreto interno")])).post(
        "/chat", json={"message": "ciao"}
    )
    assert (response.status_code, response.json()) == (500, {
        "error": "internal_error", "detail": "errore interno dell'agente; dettagli nel log"
    })
    assert "segreto interno" not in response.text
    record = [r for r in caplog.records if r.name == "assistant.api"][-1]
    assert record.levelno == logging.ERROR
    assert record.exc_info and isinstance(record.exc_info[1], RuntimeError)
    assert without_duration(record.getMessage()) == (
        "api response=chat status=500 error=internal_error "
        "detail=\"errore interno dell'agente; dettagli nel log\""
    )


# --- GET /prompts (CA-64) ---

def test_prompts_lists_the_mcp_prompts(caplog):
    caplog.set_level(logging.INFO)
    client = mcp_client()
    response = api(client=client).get("/prompts")
    assert response.status_code == 200
    assert response.json() == [{
        "name": "spiega", "description": "Spiega un argomento.", "arguments": [
            {"name": "argomento", "description": "Argomento.", "required": True},
            {"name": "livello", "description": "Livello.", "required": False},
        ],
    }]
    assert client.prompt_lists == 1 and client.prompt_gets == []
    assert "prompts/list count=1 names=spiega" in [r.getMessage() for r in caplog.records]
    assert without_duration(api_lines(caplog)[-1]) == "api response=prompts status=200 count=1"


def test_prompts_without_prompts():
    response = api(client=FakeMcpClient(MCP_SPECS)).get("/prompts")
    assert (response.status_code, response.json()) == (200, [])


def test_prompts_unavailable(caplog):
    caplog.set_level(logging.INFO)
    response = api(client=PromptListFails(MCP_SPECS)).get("/prompts")
    assert (response.status_code, response.json()) == (503, {
        "error": "mcp_unavailable", "detail": "prompt non disponibili (sessione MCP chiusa)"
    })
    record = [r for r in caplog.records if r.name == "assistant.api"][-1]
    assert record.levelno == logging.WARNING
    assert without_duration(record.getMessage()) == (
        "api response=prompts status=503 error=mcp_unavailable "
        "detail=\"prompt non disponibili (sessione MCP chiusa)\""
    )


def test_prompts_unexpected_error_is_500():
    class Broken(FakeMcpClient):
        def list_prompts(self):
            raise RuntimeError("guasto")

    response = api(client=Broken(MCP_SPECS)).get("/prompts")
    assert (response.status_code, response.json()["error"]) == (500, "internal_error")


# --- GET /status (CA-64) ---

class ToolListFails(FakeMcpClient):
    """FakeMcpClient whose tools/list fails as with a closed MCP session."""

    def list_tools(self):
        raise ToolUnavailableError("sessione MCP chiusa")


MODEL_DOWN = "LM Studio non raggiungibile su http://localhost:1234/v1"
MCP_OK = {"status": "ok", "detail": "7 strumenti"}
MCP_DOWN = {"status": "unavailable", "detail": "sessione MCP chiusa"}
MODEL_UP = {"status": "ok", "id": MODEL_ID, "detail": ""}
MODEL_GONE = {"status": "unavailable", "id": MODEL_ID, "detail": MODEL_DOWN}


def model_down() -> tuple[bool, str]:
    return False, MODEL_DOWN


@pytest.mark.parametrize(("client_type", "model_status", "code", "mcp", "model"), [
    (FakeMcpClient, model_ok, 200, MCP_OK, MODEL_UP),
    (FakeMcpClient, model_down, 503, MCP_OK, MODEL_GONE),
    (ToolListFails, model_ok, 503, MCP_DOWN, MODEL_UP),
    (ToolListFails, model_down, 503, MCP_DOWN, MODEL_GONE),
], ids=["all-ok", "model-down", "mcp-down", "both-down"])
def test_status_combinations(client_type, model_status, code, mcp, model, caplog):
    caplog.set_level(logging.INFO)
    response = api(client=client_type(MCP_SPECS), model_status=model_status).get("/status")
    assert response.status_code == code
    assert response.json() == {
        "status": "ok" if code == 200 else "degraded", "agent": "ok", "mcp": mcp, "model": model,
    }
    record = [r for r in caplog.records if r.name == "assistant.api"][-1]
    assert record.levelno == (logging.INFO if code == 200 else logging.WARNING)
    assert without_duration(record.getMessage()) == (
        f"api response=status status={code} mcp={mcp['status']} model={model['status']}"
    )


def test_status_checks_again_at_every_request():
    answers = [(False, MODEL_DOWN), (True, "")]
    service = api(model_status=lambda: answers.pop(0))
    assert service.get("/status").status_code == 503
    assert service.get("/status").status_code == 200


def test_status_calls_neither_the_model_nor_the_prompts():
    client = mcp_client()
    assert api(client=client).get("/status").status_code == 200  # the FakeModel([]) is unused
    assert client.prompt_lists == 0 and client.calls == []


def test_status_unexpected_error_is_500():
    def broken():
        raise RuntimeError("guasto")

    response = api(model_status=broken).get("/status")
    assert (response.status_code, response.json()["error"]) == (500, "internal_error")


# --- OpenAPI of /prompts and /status ---

def test_openapi_documents_prompts_and_status():
    document = api().get("/openapi.json").json()
    assert {"/chat", "/prompts", "/status"} <= set(document["paths"])
    prompts = document["paths"]["/prompts"]["get"]["responses"]
    assert set(prompts) == {"200", "500", "503"}
    assert prompts["200"]["content"]["application/json"]["schema"]["items"] == {
        "$ref": "#/components/schemas/PromptInfo"
    }
    assert prompts["503"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorBody"
    }
    status = document["paths"]["/status"]["get"]["responses"]
    assert set(status) == {"200", "500", "503"}
    for code in ("200", "503"):
        assert status[code]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/StatusBody"
        }
    schemas = document["components"]["schemas"]
    for name in ("PromptInfo", "PromptArgumentInfo", "StatusBody", "McpStatus", "ModelStatus"):
        assert name in schemas


# --- POST /chat/stream (specification of the streaming, §4; CA-95) ---

def stream(service: TestClient, body: dict) -> list[tuple[str, object]]:
    with service.stream("POST", "/chat/stream", json=body) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-cache"
        return sse(response.read().decode())


def time_call_with_text() -> AIMessage:
    return AIMessage("Controllo.", tool_calls=[
        {"name": "get_current_time", "args": {"timezone": "Asia/Tokyo"}, "id": "c1"}
    ])


def test_stream_of_a_turn_with_a_tool():
    replies = [time_call_with_text(), AIMessage("A Tokyo sono le 00:47.")]
    history = [{"role": "user", "content": "d1"}, {"role": "assistant", "content": "r1"}]
    body = {"message": "Che ore sono a Tokyo?", "history": history, "summary": "S0"}
    events = stream(api(StreamingFakeModel(replies=list(replies))), body)
    assert [name for name, _ in events] == [
        "text", "reset", "tool_start", "tool_end", "text", "text", "text", "text", "text", "done",
    ]
    assert events[1][1] == {"reason": "tools", "detail": ""}
    assert events[2][1] == {
        "id": "c1", "name": "get_current_time", "args": {"timezone": "Asia/Tokyo"}
    }
    assert events[3][1] == {
        "id": "c1", "name": "get_current_time", "args": {"timezone": "Asia/Tokyo"},
        "result": TOKYO, "ok": True,
    }
    assert "".join(data["delta"] for name, data in events[4:-1]) == "A Tokyo sono le 00:47."
    # done is the answer of POST /chat to the same request
    expected = api(StreamingFakeModel(replies=list(replies))).post("/chat", json=body).json()
    assert events[-1][1] == expected


def test_stream_with_a_prompt():
    client = mcp_client()
    events = stream(api(FakeModel([AIMessage("MCP è un protocollo.")]), client), {
        "prompt": {"name": "spiega", "arguments": {"argomento": "MCP"}}
    })
    assert [name for name, _ in events] == ["done"]  # a model that does not stream: no text
    assert events[0][1]["reply"] == "MCP è un protocollo."
    assert client.prompt_gets == [("spiega", {"argomento": "MCP"})]


def test_stream_when_the_reviewer_rejects():
    reviewer = FakeModel([
        ReviewDecision(reason="manca il fuso", coherent=False),
        ReviewDecision(reason="ok", coherent=True),
    ])
    model = StreamingFakeModel(replies=[AIMessage("Bozza"), AIMessage("Finale")])
    events = stream(api(model, reviewer=reviewer), {"message": "ore?"})
    assert events[:3] == [
        ("text", {"delta": "Bozza"}),
        ("reset", {"reason": "review", "detail": "manca il fuso"}),
        ("text", {"delta": "Finale"}),
    ]
    assert events[-1][0] == "done" and events[-1][1]["reply"] == "Finale"


def unusable_prompt(arguments):
    return [PromptMessage("assistant", "risposta")]


@pytest.mark.parametrize(("body", "client"), [
    pytest.param({}, None, id="none"),
    pytest.param({"message": " "}, None, id="empty"),
    pytest.param({"message": "ciao", "history": [
        {"role": "tool", "content": "{}", "tool_call_id": "c1"}
    ]}, None, id="history"),
    pytest.param({"prompt": {"name": "traduci"}}, None, id="prompt-rejected"),
    pytest.param({"prompt": {"name": "spiega"}}, PromptListFails(MCP_SPECS), id="mcp"),
    pytest.param(
        {"prompt": {"name": "spiega", "arguments": {"argomento": "MCP"}}},
        mcp_client(unusable_prompt), id="prompt-unusable",
    ),
])
def test_errors_before_the_stream_are_the_json_answers_of_chat(body, client, caplog):
    caplog.set_level(logging.INFO)
    service = api(client=client)  # the model fails if it is ever called
    expected = service.post("/chat", json=body)
    chat_lines = api_lines(caplog)
    caplog.clear()
    response = service.post("/chat/stream", json=body)
    assert response.status_code == expected.status_code and response.status_code >= 400
    assert response.headers["content-type"] == "application/json"
    assert response.json() == expected.json()
    assert [without_duration(line) for line in api_lines(caplog)[1:]] == [
        without_duration(line).replace("=chat ", "=chat_stream ") for line in chat_lines[1:]
    ]
    assert api_lines(caplog)[0] == chat_lines[0].replace("=chat ", "=chat_stream ")


def test_body_not_matching_the_schema_is_422_before_the_stream(caplog):
    caplog.set_level(logging.INFO)
    response = api().post("/chat/stream", json={"message": "ciao", "session": "s1"})
    assert response.status_code == 422
    assert api_lines(caplog) == []


@pytest.mark.parametrize(("error", "code", "detail"), [
    (lm_studio_error(), "model_unavailable", "LM Studio non raggiungibile: Connection error."),
    (lm_studio_timeout(), "model_unavailable", "LM Studio non raggiungibile: Request timed out."),
    (lm_studio_status_error(), "model_error",
     "LM Studio non ha risposto correttamente: Model unloaded"),
    (lm_studio_generic_error(), "model_error",
     "LM Studio non ha risposto correttamente: risposta inattesa"),
], ids=["connection", "timeout", "status", "generic"])
def test_lm_studio_errors_during_the_stream(error, code, detail, caplog):
    caplog.set_level(logging.INFO)
    model = StreamingFakeModel(replies=[time_call_with_text(), error])
    events = stream(api(model), {"message": "ore a Tokyo?"})
    assert [name for name, _ in events] == ["text", "reset", "tool_start", "tool_end", "error"]
    assert events[-1][1] == {"error": code, "detail": detail}
    record = [r for r in caplog.records if r.name == "assistant.api"][-1]
    assert record.levelno == logging.WARNING
    assert without_duration(record.getMessage()) == (
        f"api response=chat_stream status=200 outcome=error error={code} "
        f"detail={json.dumps(detail, ensure_ascii=False)} text_events=1 resets=1"
    )


def test_unexpected_error_during_the_stream(caplog):
    caplog.set_level(logging.INFO)
    model = StreamingFakeModel(replies=[RuntimeError("segreto interno")])
    events = stream(api(model), {"message": "ciao"})
    assert events == [("error", {
        "error": "internal_error", "detail": "errore interno dell'agente; dettagli nel log"
    })]
    record = [r for r in caplog.records if r.name == "assistant.api"][-1]
    assert record.levelno == logging.ERROR
    assert record.exc_info and isinstance(record.exc_info[1], RuntimeError)
    assert "segreto" not in record.getMessage()


def test_log_lines_of_a_stream(caplog):
    caplog.set_level(logging.INFO)
    model = StreamingFakeModel(replies=[time_call_with_text(), AIMessage("Sono le 00:47.")])
    history = [{"role": "user", "content": "d1"}, {"role": "assistant", "content": "r1"}]
    stream(api(model), {"message": "Che ore sono?", "history": history, "summary": "S0"})
    lines = api_lines(caplog)
    assert lines[0] == "api request=chat_stream kind=message history=2 summary_chars=2"
    assert without_duration(lines[1]) == (
        "api response=chat_stream status=200 outcome=done tools=get_current_time "
        "reply_chars=14 history=6 text_events=4 resets=1"
    )
    assert len(lines) == 2
    texts = " ".join(lines)
    assert "Che ore sono" not in texts and "d1" not in texts and "Sono le" not in texts


def test_a_stream_closed_by_the_client_is_logged(caplog):
    caplog.set_level(logging.INFO)
    graph = fake_graph(StreamingFakeModel(replies=[AIMessage("Una risposta lunga")]))
    turn = StreamTurn([], "", [HumanMessage("ciao")], time.monotonic())
    events = _stream_events(graph, turn)
    assert next(events).event == "text"
    events.close()
    assert without_duration(api_lines(caplog)[-1]) == (
        "api response=chat_stream status=200 outcome=client_gone text_events=1 resets=0"
    )


def test_events_are_read_and_closed_in_a_worker_thread():
    threads = []
    closed = []

    def numbers():
        try:
            for n in range(5):
                threads.append(threading.get_ident())
                yield n
        finally:
            closed.append(threading.get_ident())

    async def first_two():
        received = []
        iterator = _in_thread(numbers())
        async for n in iterator:
            received.append(n)
            if len(received) == 2:
                break
        await iterator.aclose()
        return received

    assert anyio.run(first_two) == [0, 1]
    assert threading.get_ident() not in threads + closed
    assert len(closed) == 1


def test_openapi_documents_the_stream_endpoint():
    document = api().get("/openapi.json").json()
    operation = document["paths"]["/chat/stream"]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ChatRequest"
    }
    assert set(operation["responses"]) == {"200", "400", "422", "500", "502", "503"}
    assert set(operation["responses"]["200"]["content"]) == {"text/event-stream"}
    for code in ("400", "500", "502", "503"):
        schema = operation["responses"][code]["content"]["application/json"]["schema"]
        assert schema == {"$ref": "#/components/schemas/ErrorBody"}
    for event in ("text", "reset", "tool_start", "tool_end", "done", "error"):
        assert f"`{event}`" in operation["description"]


MALFORMED = [
    pytest.param([{"name": "get_current_time", "args": {"timezone": "Asia/Tokyo"}, "id": ""}], [],
                 id="empty-id"),
    pytest.param([{"name": "get_current_time", "args": {"timezone": "Asia/Tokyo"}, "id": None}], [],
                 id="null-id"),
    pytest.param([{"name": "get_current_time", "args": {"timezone": "Asia/Tokyo"}, "id": "c1"},
                  {"name": "get_current_time", "args": {"timezone": "Europe/Rome"}, "id": "c1"}], [],
                 id="repeated-id"),
    pytest.param([{"name": "", "args": {}, "id": "c1"}], [], id="empty-name"),
    pytest.param([], [{"name": None, "args": "{", "id": "c1", "error": None,
                       "type": "invalid_tool_call"}], id="null-name"),
]


@pytest.mark.parametrize(("tool_calls", "invalid"), MALFORMED)
def test_history_with_malformed_calls_is_accepted_again(tool_calls, invalid):  # R-B1
    reply = AIMessage("", tool_calls=tool_calls, invalid_tool_calls=invalid)
    service = api(FakeModel([reply, AIMessage("ok"), AIMessage("ancora")]))
    first = service.post("/chat", json={"message": "ore?"})
    assert first.status_code == 200, first.text
    second = service.post("/chat", json={"message": "di nuovo", "history": first.json()["history"]})
    assert second.status_code == 200, second.text


@pytest.mark.parametrize(("tool_calls", "invalid"), MALFORMED)
def test_stream_history_with_malformed_calls_is_accepted_again(tool_calls, invalid):
    reply = AIMessage("", tool_calls=tool_calls, invalid_tool_calls=invalid)
    service = api(StreamingFakeModel(replies=[reply, AIMessage("ok"), AIMessage("ancora")]))
    events = stream(service, {"message": "ore?"})
    done = events[-1][1]
    assistant = next(m for m in done["history"] if m.get("tool_calls") or m.get("invalid_tool_calls"))
    sent = [c["id"] for c in assistant.get("tool_calls", []) + assistant.get("invalid_tool_calls", [])]
    assert [d["id"] for name, d in events if name == "tool_start"] == sent
    assert [d["id"] for name, d in events if name == "tool_end"] == sent
    again = service.post("/chat", json={"message": "di nuovo", "history": done["history"]})
    assert again.status_code == 200, again.text
