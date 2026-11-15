import httpx
import openai
import pytest
from langchain_openai import ChatOpenAI
from langchain_openai.chat_models.base import OpenAIRefusalError
from openai.types.chat import ChatCompletion
from pydantic import ValidationError

from assistant import model as model_module
from assistant.config import load_config
from assistant.model import (
    check_model,
    create_model,
    create_reviewer_model,
    create_router_model,
    create_summary_model,
    guard_structured_output,
)
from assistant.reviewer import ReviewDecision, ReviewerOutputError
from assistant.router import RouteDecision, RouterOutputError
from conftest import FakeModel, lm_studio_error

VALID = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "google/gemma-4-e2b"}

# Error type of each structured model and a valid decision for it.
GUARDS = [
    (RouterOutputError, RouteDecision(category="conversation", reason="saluto")),
    (ReviewerOutputError, ReviewDecision(reason="risponde", coherent=True)),
]
GUARD_IDS = ["router", "reviewer"]


def validation_error() -> ValidationError:
    try:
        RouteDecision.model_validate({})
    except ValidationError as error:
        return error
    raise AssertionError("RouteDecision ha accettato un oggetto vuoto")


@pytest.mark.parametrize("error_type", [g[0] for g in GUARDS], ids=GUARD_IDS)
@pytest.mark.parametrize("error", [
    ValueError("Structured Output response does not have a 'parsed' field"),
    validation_error(),
    OpenAIRefusalError("rifiuto"),
    openai.LengthFinishReasonError(completion=ChatCompletion.model_construct(usage=None)),
    openai.ContentFilterFinishReasonError(),
], ids=["value", "validation", "refusal", "length", "content_filter"])
def test_invalid_output_becomes_the_given_error(error, error_type):
    with pytest.raises(error_type) as raised:
        guard_structured_output(FakeModel([error]), error_type).invoke([])
    assert raised.value.__cause__ is error


@pytest.mark.parametrize("error_type", [g[0] for g in GUARDS], ids=GUARD_IDS)
def test_lm_studio_errors_pass_through(error_type):
    with pytest.raises(openai.APIConnectionError):
        guard_structured_output(FakeModel([lm_studio_error()]), error_type).invoke([])


@pytest.mark.parametrize(("error_type", "decision"), GUARDS, ids=GUARD_IDS)
def test_valid_decision_passes_through(error_type, decision):
    assert guard_structured_output(FakeModel([decision]), error_type).invoke([]) is decision


def test_create_router_model_needs_no_server():
    assert hasattr(create_router_model(load_config(VALID)), "invoke")


def test_create_reviewer_model_needs_no_server():
    assert hasattr(create_reviewer_model(load_config(VALID)), "invoke")


def test_create_summary_model_needs_no_server():
    model = create_summary_model(load_config(VALID))
    assert isinstance(model, ChatOpenAI) and model.model_name == "google/gemma-4-e2b"


@pytest.mark.parametrize(("create", "disabled"), [
    (lambda config: create_model(config, []), False),
    (create_router_model, True),
    (create_reviewer_model, True),
    (create_summary_model, True),
], ids=["agent", "router", "reviewer", "summary"])
def test_only_the_agent_streams(monkeypatch, create, disabled):  # CA-96
    built = []

    class Recording(ChatOpenAI):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            built.append(self)

    monkeypatch.setattr(model_module, "ChatOpenAI", Recording)
    create(load_config(VALID))
    assert [model.disable_streaming for model in built] == [disabled]


# --- check_model: GET <base_url>/models ---

def lm_studio(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def models(*ids) -> dict:
    return {"object": "list", "data": [{"id": i, "object": "model"} for i in ids]}


def test_check_model_ok_and_request():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=models("altro", "google/gemma-4-e2b"))

    assert check_model(load_config(VALID), lm_studio(handler)) == (True, "")
    [request] = requests
    assert (request.method, str(request.url)) == ("GET", "http://localhost:1234/v1/models")
    assert request.extensions["timeout"]["connect"] == 5.0


def test_check_model_with_a_trailing_slash():
    urls = []

    def handler(request):
        urls.append(str(request.url))
        return httpx.Response(200, json=models("google/gemma-4-e2b"))

    config = load_config({**VALID, "LMSTUDIO_BASE_URL": "http://localhost:1234/v1/"})
    assert check_model(config, lm_studio(handler)) == (True, "")
    assert urls == ["http://localhost:1234/v1/models"]


@pytest.mark.parametrize(("response", "detail"), [
    (httpx.Response(200, json=models("altro")),
     "modello 'google/gemma-4-e2b' non presente in /models"),
    (httpx.Response(200, json=models()), "modello 'google/gemma-4-e2b' non presente in /models"),
    (httpx.Response(500, text="errore"), "LM Studio ha risposto 500 a GET /models"),
    (httpx.Response(200, text="non json"), "risposta di GET /models non valida"),
    (httpx.Response(200, json={"oggetti": []}), "risposta di GET /models non valida"),
    (httpx.Response(200, json={"data": ["google/gemma-4-e2b"]}),
     "risposta di GET /models non valida"),
    (httpx.Response(200, json=[1, 2]), "risposta di GET /models non valida"),
], ids=["absent", "empty", "status", "not-json", "no-data", "strings", "list"])
def test_check_model_problems(response, detail):
    assert check_model(load_config(VALID), lm_studio(lambda request: response)) == (False, detail)


@pytest.mark.parametrize("error", [
    httpx.ConnectError("rifiutata"), httpx.ReadTimeout("scaduto"),
], ids=["connect", "timeout"])
def test_check_model_unreachable(error):
    def handler(request):
        raise error

    assert check_model(load_config(VALID), lm_studio(handler)) == (
        False, "LM Studio non raggiungibile su http://localhost:1234/v1"
    )


def test_check_model_without_a_client_on_a_closed_port():
    config = load_config({**VALID, "LMSTUDIO_BASE_URL": "http://127.0.0.1:1/v1"})
    assert check_model(config) == (False, "LM Studio non raggiungibile su http://127.0.0.1:1/v1")


def test_request_payload_uses_the_normalized_ids():  # R-B1
    from langchain_core.messages import HumanMessage

    from assistant.graph import UNNAMED_TOOL, normalize_tool_calls
    from test_graph import malformed_reply

    normalized, changes = normalize_tool_calls(malformed_reply())
    assert changes
    chat = ChatOpenAI(model="m", base_url="http://localhost:9/v1", api_key="x")
    payload = chat._get_request_payload([HumanMessage("ore?"), normalized])
    sent = payload["messages"][1]["tool_calls"]
    expected = list(normalized.tool_calls) + list(normalized.invalid_tool_calls)
    assert [c["id"] for c in sent] == [c["id"] for c in expected]
    assert UNNAMED_TOOL in [c["function"]["name"] for c in sent]
