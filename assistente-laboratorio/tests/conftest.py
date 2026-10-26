from datetime import datetime, timezone

import httpx
import openai
from langchain_core.messages import AIMessage, BaseMessage

from assistente.grafo import costruisci_grafo
from assistente.strumenti import crea_ora_corrente

ORA_FISSA = datetime(2026, 10, 26, 15, 47, 12, 345678, tzinfo=timezone.utc)


class ModelloFinto:
    """Modello con risposte programmate: le restituisce in ordine e solleva quelle che sono eccezioni."""

    def __init__(self, risposte: list[AIMessage | BaseException]):
        self._risposte = list(risposte)
        self.chiamate: list[list[BaseMessage]] = []

    def invoke(self, messaggi) -> AIMessage:
        self.chiamate.append(list(messaggi))
        risposta = self._risposte.pop(0)
        if isinstance(risposta, BaseException):
            raise risposta
        return risposta


def grafo_finto(modello, strumenti=None, max_passi=5):
    if strumenti is None:
        strumenti = [crea_ora_corrente(lambda: ORA_FISSA)]
    return costruisci_grafo(modello, list(strumenti), max_passi)


def chiamata(fuso: str | None = "Asia/Tokyo", id: str = "c1", nome: str = "ora_corrente") -> AIMessage:
    """Risposta del modello che chiede uno strumento; fuso=None → argomenti vuoti."""
    args = {} if fuso is None else {"fuso": fuso}
    return AIMessage("", tool_calls=[{"name": nome, "args": args, "id": id}])


def errore_lm_studio() -> openai.APIConnectionError:
    return openai.APIConnectionError(
        request=httpx.Request("POST", "http://localhost:1234/v1/chat/completions")
    )
