"""Router: decides whether the user's message is within the assistant's scope.

The scope text comes from the configuration (scope.txt or SCOPE_FILE); the router sees neither
the tools nor the tool messages: whether a tool is needed is still decided by the agent.
"""

from typing import Literal

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from pydantic import BaseModel, Field

ROUTER_PROMPT = """\
Sei il router dell'assistente del laboratorio. Non rispondi all'utente: decidi soltanto se il suo
ultimo messaggio rientra nell'ambito dell'assistente.

Ambito:
{scope}

Usa la conversazione precedente solo per capire i messaggi brevi che la continuano (per esempio
«E a Roma?» dopo una domanda sull'ora a Tokyo).
- conversation: l'ultimo messaggio rientra nell'ambito;
- out_of_scope: l'ultimo messaggio non rientra nell'ambito.
Nel motivo spiega la scelta in una frase breve, in italiano."""


class RouteDecision(BaseModel):
    """Structured output of the router."""

    category: Literal["conversation", "out_of_scope"] = Field(
        description="conversation se il messaggio rientra nell'ambito, altrimenti out_of_scope"
    )
    reason: str = Field(description="Motivo della scelta, in una frase breve in italiano")


class RouterOutputError(Exception):
    """The router answered without a valid RouteDecision."""


def router_messages(history: list[AnyMessage]) -> list[AnyMessage]:
    """User questions and text answers of the assistant, without tool requests or results."""
    return [
        message
        for message in history
        if isinstance(message, HumanMessage)
        or (
            isinstance(message, AIMessage)
            and message.text.strip()
            and not message.tool_calls
            and not message.invalid_tool_calls
        )
    ]


def refusal_text(reason: str) -> str:
    """Answer of the refusal node, with the router's reason when there is one."""
    reason = reason.strip().removesuffix(".").strip()
    opening = "Mi dispiace, questa domanda è fuori dal mio ambito"
    if reason:
        opening += f": {reason}"
    return f"{opening}. Chiedimi pure che cosa so fare."
