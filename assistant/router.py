"""Router: decides whether the user's message is within the assistant's scope.

The scope text comes from the configuration (scope.txt or SCOPE_FILE); the router sees neither
the tools nor the tool messages: whether a tool is needed is still decided by the agent.
"""

from typing import Literal

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from pydantic import BaseModel, Field

from assistant.reviewer import is_feedback

ROUTER_PROMPT = """\
Sei il router dell'assistente del laboratorio. Non rispondi all'utente: decidi soltanto se il suo
ultimo messaggio rientra nell'ambito dell'assistente.

Ambito:
{scope}

Usa la conversazione precedente solo per capire i messaggi brevi che la continuano (per esempio
«E a Roma?» dopo una domanda sull'ora a Tokyo).
Giudica che cosa chiede l'utente, non l'argomento delle parole. Se il messaggio potrebbe rientrare
nell'ambito, scegli conversation; scegli out_of_scope solo quando chiaramente non rientra.
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
    """User questions and final answers of the assistant, without tool requests or results.

    Final answers are kept even when empty, so user and assistant messages still alternate.
    The reviewer's indications are dropped together with the rejected draft before each one.
    """
    kept: list[AnyMessage] = []
    for message in history:
        if is_feedback(message):
            if kept and isinstance(kept[-1], AIMessage):
                kept.pop()  # the rejected draft
        elif isinstance(message, HumanMessage) or (
            isinstance(message, AIMessage)
            and not message.tool_calls
            and not message.invalid_tool_calls
        ):
            kept.append(message)
    return kept


def refusal_text(reason: str) -> str:
    """Answer of the refusal node, with the router's reason when there is one."""
    reason = reason.strip().removesuffix(".").strip()
    opening = "Mi dispiace, questa domanda è fuori dal mio ambito"
    if reason:
        opening += f": {reason}"
    return f"{opening}. Chiedimi pure che cosa so fare."
