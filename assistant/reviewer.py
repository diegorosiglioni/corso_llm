"""Reviewer: decides whether the agent's final answer is coherent with the user's question.

The reviewer sees only the question and the proposed answer: no history, no tools, no tool
results. A rejection reaches the agent as a user message marked with name="reviewer".
"""

from langchain_core.messages import AnyMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

REVIEWER_PROMPT = """\
Sei il revisore dell'assistente del laboratorio. Non rispondi all'utente: controlli soltanto se la
risposta proposta risponde alla domanda dell'utente.

La risposta è coerente se risponde a tutte le parti della domanda e non esce dal tema.
Non è coerente se ignora una parte della domanda, se parla d'altro o se è vuota.
Non giudicare lo stile, la lunghezza né l'esattezza dei dati: vengono da strumenti che tu non vedi.
Se la risposta spiega che una parte non si può soddisfare (per esempio un corso che non esiste),
quella parte ha comunque una risposta. Se l'utente saluta o si presenta, una risposta cortese e
pertinente è coerente; anche una domanda di chiarimento pertinente è coerente.
Nel motivo spiega la scelta in una frase breve, in italiano; se non è coerente, indica che cosa
manca o che cosa è fuori tema."""

FEEDBACK_NAME = "reviewer"


class ReviewDecision(BaseModel):
    """Structured output of the reviewer; the reason comes before the verdict."""

    reason: str = Field(
        description="Motivo della scelta, in una frase breve in italiano; se non è coerente, "
        "che cosa manca o che cosa è fuori tema"
    )
    coherent: bool = Field(
        description="true se la risposta risponde a tutte le parti della domanda senza uscire "
        "dal tema, altrimenti false"
    )


class ReviewerOutputError(Exception):
    """The reviewer answered without a valid ReviewDecision."""


def is_feedback(message: AnyMessage) -> bool:
    """True for the reviewer's indications to the agent."""
    return isinstance(message, HumanMessage) and message.name == FEEDBACK_NAME


def user_question(history: list[AnyMessage]) -> str:
    """Text of the user's last message, skipping the reviewer's indications."""
    for message in reversed(history):
        if isinstance(message, HumanMessage) and not is_feedback(message):
            return message.text
    return ""


def review_messages(question: str, answer: str) -> list[BaseMessage]:
    """Everything the reviewer receives: its prompt, the question and the proposed answer."""
    shown = answer if answer.strip() else "(vuota)"
    return [
        SystemMessage(REVIEWER_PROMPT),
        HumanMessage(f"Domanda dell'utente:\n{question}\n\nRisposta proposta:\n{shown}"),
    ]


def feedback_message(reason: str) -> HumanMessage:
    """Indication for the agent after a rejection, with the reviewer's reason when there is one."""
    reason = reason.strip().removesuffix(".").strip()
    opening = "Revisione: la risposta precedente non è coerente con la domanda"
    if reason:
        opening += f": {reason}"
    return HumanMessage(
        f"{opening}. Scrivi una nuova risposta completa all'ultima domanda dell'utente. "
        "Usa i risultati degli strumenti già ottenuti e non ripetere le azioni già eseguite "
        "(per esempio una nota già salvata).",
        name=FEEDBACK_NAME,
    )
