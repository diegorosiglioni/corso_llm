"""Connection to the model served by LM Studio through its OpenAI-compatible API."""

from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from assistant.config import Config


def create_model(config: Config, tools: list[BaseTool]) -> Runnable:
    return ChatOpenAI(
        base_url=config.base_url,
        model=config.model,
        api_key="lm-studio",  # placeholder: LM Studio does not require keys
        temperature=0,  # more repeatable answers and steadier tool calling
        timeout=120,  # the first load of a local model can be slow
        max_retries=1,  # with LM Studio off the error arrives within seconds
    ).bind_tools(tools)
