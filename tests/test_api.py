import json
import logging
import re

import httpx2
import openai
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from assistant.api import create_app
from assistant.mcp_client import PromptArgument, PromptMessage, PromptSpec
from assistant.tools import ToolUnavailableError
from conftest import (
    MCP_SPECS,
    FakeMcpClient,
    FakeModel,
    PromptListFails,
    fake_graph,
    lm_studio_error,
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


MODEL_ID = "google/gemma-4-e2b"


def model_ok() -> tuple[bool, str]:
    return True, ""


def api(model=None, client=None, model_status=model_ok, **graph_options) -> TestClient:
    """Service on a fake graph; the default model fails if it is ever called."""
    graph = fake_graph(FakeModel([]) if model is None else model, **graph_options)
    return TestClient(create_app(
        graph=graph, client=client or mcp_client(), model_id=MODEL_ID, model_status=model_status,
    ))


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
    assert api_lines(caplog)[0] == "api request=chat kind=prompt name=spiega history=0 summary_chars=0"


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
