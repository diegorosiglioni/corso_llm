import json

import httpx
import pytest
from langchain_core.messages import AIMessage

from assistant.api_client import (
    CHAT_TIMEOUT,
    STATUS_TIMEOUT,
    AgentClient,
    AgentError,
    RemoteSession,
)
from assistant.mcp_client import PromptArgument, PromptMessage, PromptSpec
from conftest import (
    MCP_SPECS,
    MODEL_ID,
    FakeMcpClient,
    FakeModel,
    PromptListFails,
    fake_service,
    lm_studio_error,
    tool_call,
)

URL = "http://agente.test:8000"
EXPLAIN = PromptSpec("spiega", "Spiega un argomento.", (
    PromptArgument("argomento", "Argomento.", True),
    PromptArgument("livello", "Livello.", False),
))


def explain_text(arguments):
    return [PromptMessage("user", f"Spiegami {arguments['argomento']}.")]


def agent(model=None, client=None, **options) -> AgentClient:
    """Client of the real app on a fake graph (no network)."""
    return AgentClient(URL, http=fake_service(model, client, **options))


def scripted(*answers, requests=None) -> AgentClient:
    """Client whose requests get `answers` in order (httpx.Response or an exception to raise);
    the requests sent go to `requests`."""
    queue = list(answers)

    def handler(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        answer = queue.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    return AgentClient(URL, http=httpx.Client(transport=httpx.MockTransport(handler), base_url=URL))


def chat_body(reply="ok", history=(), summary="") -> dict:
    return {"reply": reply, "tools_used": [], "history": list(history), "summary": summary}


def raised(call) -> AgentError:
    with pytest.raises(AgentError) as error:
        call()
    return error.value


# --- status ---

def test_status_ok():
    body = agent().status()
    assert body["status"] == "ok"
    assert body["mcp"] == {"status": "ok", "detail": "7 strumenti"}
    assert body["model"] == {"status": "ok", "id": MODEL_ID, "detail": ""}


def test_status_degraded_is_not_an_error():
    body = agent(model_status=lambda: (False, "LM Studio non raggiungibile su x")).status()
    assert body["status"] == "degraded"
    assert body["model"]["detail"] == "LM Studio non raggiungibile su x"


def test_status_internal_error():
    def broken():
        raise RuntimeError("difetto")

    error = raised(agent(model_status=broken).status)
    assert (error.code, error.detail) == (
        "internal_error", "errore interno dell'agente; dettagli nel log"
    )


@pytest.mark.parametrize("response", [
    httpx.Response(200, text="non json"),
    httpx.Response(200, json={"status": "ok"}),
    httpx.Response(503, json={"status": "degraded", "mcp": {"status": "ok"}}),
    httpx.Response(404, json={"detail": "Not Found"}),
])
def test_status_unexpected_answer(response):
    error = raised(scripted(response).status)
    assert (error.code, error.detail) == (
        "bad_response", f"risposta inattesa dell'agente (HTTP {response.status_code})"
    )


@pytest.mark.parametrize("exception", [
    httpx.ConnectError("connessione rifiutata"),
    httpx.ConnectTimeout("nessuna risposta"),
    httpx.RemoteProtocolError("connessione chiusa"),
])
def test_agent_unreachable(exception):
    error = raised(scripted(exception).status)
    assert (error.code, error.detail) == ("agent_unreachable", f"agente non raggiungibile su {URL}")


def test_agent_unreachable_on_a_closed_port():
    with AgentClient("http://127.0.0.1:1/") as client:
        error = raised(client.status)
    assert (error.code, error.detail) == (
        "agent_unreachable", "agente non raggiungibile su http://127.0.0.1:1"
    )


def test_timeouts():
    requests = []
    client = scripted(
        httpx.Response(200, json=[]), httpx.Response(200, json=chat_body()), requests=requests
    )
    client.prompts()
    client.chat([], "", message="ciao")
    assert [r.extensions["timeout"]["read"] for r in requests] == [STATUS_TIMEOUT, CHAT_TIMEOUT]
    assert (STATUS_TIMEOUT, CHAT_TIMEOUT) == (10, 600)


def test_turn_without_answer_in_time():
    error = raised(lambda: scripted(httpx.ReadTimeout("lento")).chat([], "", message="ciao"))
    assert (error.code, error.detail) == ("agent_timeout", "l'agente non ha risposto entro 600 s")


# --- prompts ---

def test_prompts_as_prompt_specs():
    client = FakeMcpClient(MCP_SPECS, prompts={"spiega": (EXPLAIN, explain_text)})
    assert agent(client=client).prompts() == [EXPLAIN]
    assert client.prompt_gets == []


def test_prompts_unavailable():
    error = raised(agent(client=PromptListFails(MCP_SPECS)).prompts)
    assert (error.code, error.detail) == (
        "mcp_unavailable", "prompt non disponibili (sessione MCP chiusa)"
    )


@pytest.mark.parametrize("body", [{"name": "spiega"}, [{"name": "spiega"}], [{"x": 1}], None])
def test_prompts_malformed(body):
    error = raised(scripted(httpx.Response(200, json=body)).prompts)
    assert (error.code, error.detail) == ("bad_response", "risposta inattesa dell'agente (HTTP 200)")


# --- chat ---

def test_chat_with_a_message():
    model = FakeModel([tool_call(), AIMessage("A Tokyo sono le 00:47.")])
    body = agent(model).chat([], "", message="Che ore sono a Tokyo?")
    assert body["reply"] == "A Tokyo sono le 00:47."
    assert [tool["name"] for tool in body["tools_used"]] == ["get_current_time"]
    assert [m["role"] for m in body["history"]] == ["user", "assistant", "tool", "assistant"]


def test_chat_request_body():
    requests = []
    client = scripted(
        httpx.Response(200, json=chat_body()), httpx.Response(200, json=chat_body()),
        requests=requests,
    )
    history = [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
    client.chat(history, "riassunto", message="ciao")
    client.chat([], "", prompt=("spiega", {"argomento": "MCP"}))
    assert [(r.method, r.url.path) for r in requests] == [("POST", "/chat")] * 2
    assert json.loads(requests[0].content) == {
        "history": history, "summary": "riassunto", "message": "ciao"
    }
    assert json.loads(requests[1].content) == {
        "history": [], "summary": "", "prompt": {"name": "spiega", "arguments": {"argomento": "MCP"}}
    }


def test_chat_with_a_prompt():
    client = FakeMcpClient(MCP_SPECS, prompts={"spiega": (EXPLAIN, explain_text)})
    body = agent(FakeModel([AIMessage("MCP è un protocollo.")]), client).chat(
        [], "", prompt=("spiega", {"argomento": "MCP"})
    )
    assert body["reply"] == "MCP è un protocollo."
    assert body["history"][0] == {"role": "user", "content": "Spiegami MCP."}
    assert client.prompt_gets == [("spiega", {"argomento": "MCP"})]


def test_chat_with_a_rejected_prompt():
    client = FakeMcpClient(MCP_SPECS, prompts={"spiega": (EXPLAIN, explain_text)})
    error = raised(lambda: agent(client=client).chat([], "", prompt=("spiega", {"livello": "x"})))
    assert (error.code, error.detail) == (
        "prompt_rejected", "argomenti obbligatori mancanti per 'spiega': 'argomento'"
    )
    assert client.prompt_gets == []


def test_chat_with_lm_studio_switched_off():
    error = raised(lambda: agent(FakeModel([lm_studio_error()])).chat([], "", message="ciao"))
    assert (error.code, error.detail) == (
        "model_unavailable", "LM Studio non raggiungibile: Connection error."
    )


@pytest.mark.parametrize("response", [
    httpx.Response(200, json={"reply": "manca il resto"}),
    httpx.Response(200, json=[]),
    httpx.Response(200, json={**chat_body(), "reply": None}),
    httpx.Response(200, json={**chat_body(), "tools_used": {"name": "calculate"}}),
    httpx.Response(200, json={**chat_body(), "history": "testo"}),
    httpx.Response(200, json={**chat_body(), "summary": []}),
    httpx.Response(200, text="non json"),
    httpx.Response(502, text="Bad Gateway"),
])
def test_chat_unexpected_answer(response):
    error = raised(lambda: scripted(response).chat([], "", message="ciao"))
    assert error.code == "bad_response"


# --- connection ---

def test_base_url_without_final_slash():
    assert AgentClient("http://127.0.0.1:8000/").base_url == "http://127.0.0.1:8000"


def test_close_closes_only_its_own_connection():
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    AgentClient(URL, http=http).close()
    assert not http.is_closed
    own = AgentClient(URL)
    own.close()
    assert own._http.is_closed


# --- RemoteSession ---

def test_session_keeps_history_and_summary_between_turns():
    model = FakeModel([AIMessage("Piacere, Paolo!"), AIMessage("Ti chiami Paolo.")])
    session = RemoteSession(agent(model))
    assert session.send("Mi chiamo Paolo") == "Piacere, Paolo!"
    assert session.send("Come mi chiamo?") == "Ti chiami Paolo."
    assert [m.content for m in model.calls[1][1:]] == [
        "Mi chiamo Paolo", "Piacere, Paolo!", "Come mi chiamo?"
    ]
    assert [m["content"] for m in session.history] == [
        "Mi chiamo Paolo", "Piacere, Paolo!", "Come mi chiamo?", "Ti chiami Paolo."
    ]
    assert session.summary == ""


def test_session_sends_back_the_summary_it_received():
    requests = []
    first = chat_body("uno", [{"role": "user", "content": "a"}], "riassunto vecchio")
    client = scripted(
        httpx.Response(200, json=first), httpx.Response(200, json=chat_body("due")),
        requests=requests,
    )
    session = RemoteSession(client)
    session.send("a")
    session.send("b")
    sent = json.loads(requests[1].content)
    assert (sent["history"], sent["summary"]) == (first["history"], "riassunto vecchio")


def test_session_unchanged_after_an_error():
    model = FakeModel([AIMessage("Ciao!"), lm_studio_error(), AIMessage("Eccomi.")])
    session = RemoteSession(agent(model))
    session.send("ciao")
    before = (session.history, session.summary)
    with pytest.raises(AgentError):
        session.send("seconda")
    assert (session.history, session.summary) == before
    assert session.send("terza") == "Eccomi."
    assert [m.content for m in model.calls[2][1:]] == ["ciao", "Ciao!", "terza"]


def test_session_prompt():
    client = FakeMcpClient(MCP_SPECS, prompts={"spiega": (EXPLAIN, explain_text)})
    session = RemoteSession(agent(FakeModel([AIMessage("MCP è un protocollo.")]), client))
    assert session.send_prompt("spiega", {"argomento": "MCP"}) == "MCP è un protocollo."
    assert [m["content"] for m in session.history] == ["Spiegami MCP.", "MCP è un protocollo."]


def test_session_history_is_a_copy():
    session = RemoteSession(agent(FakeModel([AIMessage("Ciao!")])))
    session.send("ciao")
    session.history.clear()
    assert len(session.history) == 2
