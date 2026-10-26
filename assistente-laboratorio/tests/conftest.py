import httpx
import openai
from langchain_core.messages import AIMessage, BaseMessage

from assistente.grafo import costruisci_grafo


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


def grafo_finto(modello, strumenti=(), max_passi=5):
    return costruisci_grafo(modello, max_passi)


def errore_lm_studio() -> openai.APIConnectionError:
    return openai.APIConnectionError(
        request=httpx.Request("POST", "http://localhost:1234/v1/chat/completions")
    )
