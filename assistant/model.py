"""Connection to the model served by LM Studio through its OpenAI-compatible API."""

import openai
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain_openai.chat_models.base import OpenAIRefusalError

from assistant.config import Config
from assistant.router import RouteDecision, RouterOutputError

# Errors of langchain-openai 1.7.2 with method="json_schema" when the reply does not fit the
# schema (pydantic.ValidationError is a ValueError). LM Studio errors (openai.APIError) are not
# among them: they reach the terminal as for the agent.
INVALID_OUTPUT_ERRORS = (
    ValueError,
    OpenAIRefusalError,
    openai.LengthFinishReasonError,
    openai.ContentFilterFinishReasonError,
)


def _chat(config: Config) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=config.base_url,
        model=config.model,
        api_key="lm-studio",  # placeholder: LM Studio does not require keys
        temperature=0,  # more repeatable answers and steadier tool calling
        timeout=120,  # the first load of a local model can be slow
        max_retries=1,  # with LM Studio off the error arrives within seconds
    )


def create_model(config: Config, tools: list[BaseTool]) -> Runnable:
    return _chat(config).bind_tools(tools)


def guard_router_output(structured: Runnable) -> Runnable:
    """Same interface as `structured`; an invalid reply becomes RouterOutputError."""

    def classify(messages):
        try:
            return structured.invoke(messages)
        except INVALID_OUTPUT_ERRORS as error:
            raise RouterOutputError(str(error)) from error

    return RunnableLambda(classify)


def create_router_model(config: Config) -> Runnable:
    """Same model as the agent, without tools, constrained to the RouteDecision schema."""
    structured = _chat(config).with_structured_output(RouteDecision, method="json_schema")
    return guard_router_output(structured)
