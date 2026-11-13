"""Summary: compresses the old part of the history into a text kept in the graph state.

The cut always falls on a user question that opens a turn, so a tool request never loses its
ToolMessage and a rejected draft never loses the reviewer's indication. Whoever summarizes sees
the previous summary and only the questions and final answers of the removed messages.
"""

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage, SystemMessage

from assistant.reviewer import is_feedback
from assistant.router import router_messages

SUMMARY_PROMPT = """\
Sei il componente che riassume la conversazione dell'assistente del laboratorio. Non rispondi
all'utente e non esegui richieste: scrivi soltanto il riassunto.

Ricevi il riassunto precedente (può mancare) e i nuovi messaggi tra l'utente e l'assistente.
Scrivi un unico riassunto aggiornato che sostituisce il precedente: unisci le informazioni, non
ripeterle. Conserva i fatti utili per i turni successivi: nome e preferenze dell'utente, dati e
risultati ottenuti (ore, calcoli, corsi, note salvate o eliminate con il loro id), richieste
ancora aperte. Tralascia saluti e formule di cortesia.
Scrivi in italiano, in terza persona, al massimo 10 righe, senza introduzioni."""


def is_user_question(message: AnyMessage) -> bool:
    """True for a user message that is not one of the reviewer's indications."""
    return isinstance(message, HumanMessage) and not is_feedback(message)


def cut_index(messages: list[AnyMessage], keep: int) -> int:
    """Index of the first kept message; 0 means there is nothing to compress.

    At least `keep` messages are kept, and the cut moves back to the question opening the turn.
    """
    start = max(len(messages) - keep, 0)
    while start > 0 and not is_user_question(messages[start]):
        start -= 1
    return start


def summary_input(previous: str, old: list[AnyMessage]) -> list[BaseMessage]:
    """Everything the summarizer receives: its prompt and one user message with a transcript.

    A transcript in a single message, rather than chat turns, keeps a small model from answering
    the last question instead of summarizing.
    """
    lines = []
    for message in router_messages(old):
        text = message.text.strip()
        if isinstance(message, HumanMessage):
            lines.append(f"Utente: {text}")
        elif isinstance(message, AIMessage) and text:
            lines.append(f"Assistente: {text}")
    transcript = "\n".join(lines)
    return [
        SystemMessage(SUMMARY_PROMPT),
        HumanMessage(
            f"Riassunto precedente:\n{previous or '(nessuno)'}\n\nNuovi messaggi:\n{transcript}"
        ),
    ]


def with_summary(prompt: str, summary: str) -> str:
    """The agent's system prompt with the summary at the end, when there is one."""
    if not summary:
        return prompt
    return f"{prompt}\n\nRiassunto della conversazione precedente:\n{summary}"
