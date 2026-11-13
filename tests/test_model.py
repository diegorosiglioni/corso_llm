import openai
import pytest
from langchain_openai import ChatOpenAI
from langchain_openai.chat_models.base import OpenAIRefusalError
from openai.types.chat import ChatCompletion
from pydantic import ValidationError

from assistant.config import load_config
from assistant.model import (
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
