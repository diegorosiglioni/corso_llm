import openai
import pytest
from langchain_openai.chat_models.base import OpenAIRefusalError
from openai.types.chat import ChatCompletion
from pydantic import ValidationError

from assistant.config import load_config
from assistant.model import create_router_model, guard_router_output
from assistant.router import RouteDecision, RouterOutputError
from conftest import FakeModel, lm_studio_error

VALID = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "google/gemma-4-e2b"}


def validation_error() -> ValidationError:
    try:
        RouteDecision.model_validate({})
    except ValidationError as error:
        return error
    raise AssertionError("RouteDecision ha accettato un oggetto vuoto")


@pytest.mark.parametrize("error", [
    ValueError("Structured Output response does not have a 'parsed' field"),
    validation_error(),
    OpenAIRefusalError("rifiuto"),
    openai.LengthFinishReasonError(completion=ChatCompletion.model_construct(usage=None)),
    openai.ContentFilterFinishReasonError(),
], ids=["value", "validation", "refusal", "length", "content_filter"])
def test_invalid_output_becomes_router_output_error(error):
    with pytest.raises(RouterOutputError) as raised:
        guard_router_output(FakeModel([error])).invoke([])
    assert raised.value.__cause__ is error


def test_lm_studio_errors_pass_through():
    with pytest.raises(openai.APIConnectionError):
        guard_router_output(FakeModel([lm_studio_error()])).invoke([])


def test_valid_decision_passes_through():
    decision = RouteDecision(category="conversation", reason="saluto")
    assert guard_router_output(FakeModel([decision])).invoke([]) is decision


def test_create_router_model_needs_no_server():
    assert hasattr(create_router_model(load_config(VALID)), "invoke")
