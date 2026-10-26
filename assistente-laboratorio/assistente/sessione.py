"""Sessione di conversazione: conserva la cronologia per la durata del processo."""

from langchain_core.messages import AnyMessage, HumanMessage

RISPOSTA_VUOTA = "(Il modello non ha fornito una risposta.)"


class Sessione:
    def __init__(self, grafo):
        self._grafo = grafo
        self._messaggi: list[AnyMessage] = []

    @property
    def messaggi(self) -> list[AnyMessage]:
        return list(self._messaggi)

    def invia(self, testo: str) -> str:
        """Esegue un turno; la cronologia cambia solo se il turno riesce."""
        risultato = self._grafo.invoke(
            {"messaggi": self._messaggi + [HumanMessage(testo)], "passi": 0}
        )
        self._messaggi = risultato["messaggi"]
        return self._messaggi[-1].text.strip() or RISPOSTA_VUOTA
