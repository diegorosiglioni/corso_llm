"""LangGraph graph of the assistant: explicit state, nodes and routing.

START → [llm] ──route──┬─ no tool_call ─────────────────────→ END
          ▲            ├─ tool_call and steps < max_steps ──→ [tools] ─┐
          └────────────┼───────────────────────────────────────────────┘
                       └─ tool_call and steps ≥ max_steps ──→ [limit] → END
"""

import json
import logging
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Sei l'assistente del laboratorio. Rispondi in italiano, in modo breve. Per qualsiasi "
    "domanda sulla data o sull'ora usa lo strumento get_current_time con un nome di fuso IANA "
    "(per esempio Europe/Rome); non inventare l'orario."
)


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]  # history + current turn
    steps: int  # model calls in the turn


def _calls(message) -> tuple[list[dict], list[dict]]:
    """Valid calls and calls with unparsable arguments in the last message.

    The latter get an answer too: langchain-openai sends them back to the server as
    tool_calls, and a call without an answer would make the history invalid for the API.
    """
    return (
        list(getattr(message, "tool_calls", None) or []),
        list(getattr(message, "invalid_tool_calls", None) or []),
    )


def route(state: State, max_steps: int) -> Literal["tools", "limit", "end"]:
    """Chooses the next step from the model's last message."""
    valid, invalid = _calls(state["messages"][-1])
    if not valid and not invalid:
        return "end"
    if state["steps"] < max_steps:
        return "tools"
    return "limit"


def _tool_message(call: dict, result: dict) -> ToolMessage:
    return ToolMessage(
        content=json.dumps(result, ensure_ascii=False),
        tool_call_id=call["id"],
        name=call["name"],
    )


def build_graph(model: Runnable, tools: list[BaseTool], max_steps: int):
    """Returns the compiled graph with the llm, tools and limit nodes."""
    by_name = {tool.name: tool for tool in tools}

    def llm_node(state: State) -> dict:
        step = state["steps"] + 1
        log.info("passaggio %d/%d → modello", step, max_steps)
        reply = model.invoke([SystemMessage(SYSTEM_PROMPT)] + state["messages"])
        if getattr(reply, "invalid_tool_calls", None):
            log.warning(
                "passaggio %d/%d argomenti non interpretabili: %s",
                step, max_steps, reply.invalid_tool_calls,
            )
        return {"messages": [reply], "steps": step}

    def tools_node(state: State) -> dict:
        steps = state["steps"]
        replies = []
        valid, invalid = _calls(state["messages"][-1])
        for call in valid + invalid:
            name, arguments = call["name"], call["args"]
            log.info("passaggio %d/%d chiamata %s %s", steps, max_steps, name, arguments)
            tool = by_name.get(name)
            if tool is None:
                result = {"error": f"Strumento sconosciuto: '{name}'."}
            elif call in invalid:
                result = {
                    "error": f"Argomenti non interpretabili per '{name}': '{arguments}'. "
                    f"Uso: {tool.description}"
                }
            else:
                try:
                    result = tool.invoke(arguments)
                except Exception as error:
                    result = {
                        "error": f"Argomenti non validi per '{name}': {error}. "
                        f"Uso: {tool.description}"
                    }
            level = logging.WARNING if "error" in result else logging.INFO
            log.log(level, "passaggio %d/%d risultato %s %s", steps, max_steps, name, result)
            replies.append(_tool_message(call, result))
        return {"messages": replies}

    def limit_node(state: State) -> dict:
        valid, invalid = _calls(state["messages"][-1])
        pending = valid + invalid
        log.warning(
            "limite di %d passaggi raggiunto, chiamate non eseguite: %s",
            max_steps, [call["name"] for call in pending],
        )
        not_run = {"error": "Non eseguito: limite di passaggi raggiunto."}
        replies = [_tool_message(call, not_run) for call in pending]
        notice = AIMessage(
            f"Ho raggiunto il limite di {max_steps} passaggi senza una risposta finale."
        )
        return {"messages": replies + [notice]}

    graph = StateGraph(State)
    graph.add_node("llm", llm_node)
    graph.add_node("tools", tools_node)
    graph.add_node("limit", limit_node)
    graph.add_edge(START, "llm")
    graph.add_conditional_edges(
        "llm",
        lambda state: route(state, max_steps),
        {"tools": "tools", "limit": "limit", "end": END},
    )
    graph.add_edge("tools", "llm")
    graph.add_edge("limit", END)
    return graph.compile()
