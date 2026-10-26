"""Grafo LangGraph dell'assistente: stato, nodi e collegamenti espliciti."""

import logging
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage, SystemMessage
from langchain_core.runnables import Runnable
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


def costruisci_grafo(modello: Runnable, max_passi: int):
    """Restituisce il grafo compilato: START → modello → END."""

    def nodo_modello(stato: Stato) -> dict:
        passo = stato["passi"] + 1
        log.info("passaggio %d/%d → modello", passo, max_passi)
        risposta = modello.invoke([SystemMessage(PROMPT_SISTEMA)] + stato["messaggi"])
        return {"messaggi": [risposta], "passi": passo}

    grafo = StateGraph(Stato)
    grafo.add_node("modello", nodo_modello)
    grafo.add_edge(START, "modello")
    grafo.add_edge("modello", END)
    return grafo.compile()
