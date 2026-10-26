"""Configurazione letta dalle variabili d'ambiente."""

from collections.abc import Mapping
from dataclasses import dataclass

LIVELLI_LOG = ("DEBUG", "INFO", "WARNING", "ERROR")


@dataclass(frozen=True)
class Configurazione:
    base_url: str  # LMSTUDIO_BASE_URL  (obbligatoria)
    modello: str  # LMSTUDIO_MODELLO   (obbligatoria)
    max_passi: int = 5  # MAX_PASSI          (intero >= 1)
    log_level: str = "INFO"  # LOG_LEVEL   (DEBUG, INFO, WARNING, ERROR)


class ErroreConfigurazione(Exception):
    """Configurazione mancante o non valida; il messaggio elenca tutti i problemi."""


def carica_configurazione(env: Mapping[str, str]) -> Configurazione:
    """Legge e valida la configurazione; i valori vuoti o di soli spazi contano come mancanti."""
    problemi = []

    def leggi(nome: str) -> str:
        return env.get(nome, "").strip()

    base_url = leggi("LMSTUDIO_BASE_URL")
    if not base_url:
        problemi.append("Manca LMSTUDIO_BASE_URL.")
    elif not base_url.startswith(("http://", "https://")):
        problemi.append(
            f"LMSTUDIO_BASE_URL deve iniziare con http:// o https://, ricevuto '{base_url}'."
        )

    modello = leggi("LMSTUDIO_MODELLO")
    if not modello:
        problemi.append("Manca LMSTUDIO_MODELLO.")

    max_passi = 5
    testo_passi = leggi("MAX_PASSI")
    if testo_passi:
        try:
            max_passi = int(testo_passi)
        except ValueError:
            max_passi = 0
        if max_passi < 1:
            problemi.append(f"MAX_PASSI deve essere un intero ≥ 1, ricevuto '{testo_passi}'.")

    log_level = leggi("LOG_LEVEL").upper() or "INFO"
    if log_level not in LIVELLI_LOG:
        problemi.append(
            f"LOG_LEVEL deve essere uno tra {', '.join(LIVELLI_LOG)}, "
            f"ricevuto '{leggi('LOG_LEVEL')}'."
        )

    if problemi:
        raise ErroreConfigurazione(" ".join(problemi))
    return Configurazione(base_url, modello, max_passi, log_level)
