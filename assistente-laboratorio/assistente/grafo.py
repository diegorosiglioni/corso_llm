"""Grafo LangGraph dell'assistente: stato, nodi e instradamento espliciti.

START → [modello] ──instrada──┬─ nessuna tool_call ──────────────→ END
            ▲                 ├─ tool_call e passi < max_passi ──→ [strumenti] ─┐
            └─────────────────┼─────────────────────────────────────────────────┘
                              └─ tool_call e passi ≥ max_passi ──→ [limite] → END
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

PROMPT_SISTEMA = (
    "Sei l'assistente del laboratorio. Rispondi in italiano, in modo breve. Per qualsiasi "
    "domanda sulla data o sull'ora usa lo strumento ora_corrente con un nome di fuso IANA "
    "(per esempio Europe/Rome); non inventare l'orario."
)


class Stato(TypedDict):
    messaggi: Annotated[list[AnyMessage], add_messages]  # cronologia + turno corrente
    passi: int  # chiamate al modello nel turno


def _chiamate(messaggio) -> tuple[list[dict], list[dict]]:
    """Chiamate valide e chiamate con argomenti non interpretabili dell'ultimo messaggio.

    Anche queste ultime ricevono una risposta: langchain-openai le rimanda al server come
    tool_calls, e una chiamata senza risposta renderebbe la cronologia non valida per l'API.
    """
    return (
        list(getattr(messaggio, "tool_calls", None) or []),
        list(getattr(messaggio, "invalid_tool_calls", None) or []),
    )


def instrada(stato: Stato, max_passi: int) -> Literal["strumenti", "limite", "fine"]:
    """Decide il passo successivo in base all'ultimo messaggio del modello."""
    validi, non_interpretabili = _chiamate(stato["messaggi"][-1])
    if not validi and not non_interpretabili:
        return "fine"
    if stato["passi"] < max_passi:
        return "strumenti"
    return "limite"


def _risposta_strumento(chiamata: dict, risultato: dict) -> ToolMessage:
    return ToolMessage(
        content=json.dumps(risultato, ensure_ascii=False),
        tool_call_id=chiamata["id"],
        name=chiamata["name"],
    )


def costruisci_grafo(modello: Runnable, strumenti: list[BaseTool], max_passi: int):
    """Restituisce il grafo compilato con i nodi modello, strumenti e limite."""
    per_nome = {strumento.name: strumento for strumento in strumenti}

    def nodo_modello(stato: Stato) -> dict:
        passo = stato["passi"] + 1
        log.info("passaggio %d/%d → modello", passo, max_passi)
        risposta = modello.invoke([SystemMessage(PROMPT_SISTEMA)] + stato["messaggi"])
        if getattr(risposta, "invalid_tool_calls", None):
            log.warning(
                "passaggio %d/%d argomenti non interpretabili: %s",
                passo, max_passi, risposta.invalid_tool_calls,
            )
        return {"messaggi": [risposta], "passi": passo}

    def nodo_strumenti(stato: Stato) -> dict:
        passi = stato["passi"]
        risposte = []
        validi, non_interpretabili = _chiamate(stato["messaggi"][-1])
        for chiamata in validi + non_interpretabili:
            nome, argomenti = chiamata["name"], chiamata["args"]
            log.info("passaggio %d/%d chiamata %s %s", passi, max_passi, nome, argomenti)
            strumento = per_nome.get(nome)
            if strumento is None:
                risultato = {"errore": f"Strumento sconosciuto: '{nome}'."}
            elif chiamata in non_interpretabili:
                risultato = {
                    "errore": f"Argomenti non interpretabili per '{nome}': '{argomenti}'. "
                    f"Uso: {strumento.description}"
                }
            else:
                try:
                    risultato = strumento.invoke(argomenti)
                except Exception as errore:
                    risultato = {
                        "errore": f"Argomenti non validi per '{nome}': {errore}. "
                        f"Uso: {strumento.description}"
                    }
            livello = logging.WARNING if "errore" in risultato else logging.INFO
            log.log(livello, "passaggio %d/%d risultato %s %s", passi, max_passi, nome, risultato)
            risposte.append(_risposta_strumento(chiamata, risultato))
        return {"messaggi": risposte}

    def nodo_limite(stato: Stato) -> dict:
        validi, non_interpretabili = _chiamate(stato["messaggi"][-1])
        pendenti = validi + non_interpretabili
        log.warning(
            "limite di %d passaggi raggiunto, chiamate non eseguite: %s",
            max_passi, [chiamata["name"] for chiamata in pendenti],
        )
        non_eseguito = {"errore": "Non eseguito: limite di passaggi raggiunto."}
        risposte = [_risposta_strumento(chiamata, non_eseguito) for chiamata in pendenti]
        avviso = AIMessage(
            f"Ho raggiunto il limite di {max_passi} passaggi senza una risposta finale."
        )
        return {"messaggi": risposte + [avviso]}

    grafo = StateGraph(Stato)
    grafo.add_node("modello", nodo_modello)
    grafo.add_node("strumenti", nodo_strumenti)
    grafo.add_node("limite", nodo_limite)
    grafo.add_edge(START, "modello")
    grafo.add_conditional_edges(
        "modello",
        lambda stato: instrada(stato, max_passi),
        {"strumenti": "strumenti", "limite": "limite", "fine": END},
    )
    grafo.add_edge("strumenti", "modello")
    grafo.add_edge("limite", END)
    return grafo.compile()
