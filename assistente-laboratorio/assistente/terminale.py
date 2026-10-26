"""Interfaccia da terminale: legge le domande e mostra le risposte."""

import logging

import openai

log = logging.getLogger(__name__)


def avvia(sessione, leggi=input, scrivi=print) -> None:
    """Ciclo di conversazione; termina con 'esci', fine input (EOF) o Ctrl+C."""
    while True:
        try:
            testo = leggi("Tu> ").strip()
            if not testo:
                continue
            if testo.lower() == "esci":
                break
            scrivi("Assistente> " + sessione.invia(testo))
        except (EOFError, KeyboardInterrupt):
            break
        except openai.APIError as errore:
            log.debug("Errore da LM Studio", exc_info=errore)
            scrivi(f"Errore: LM Studio non ha risposto correttamente ({errore}). Riprova.")
    scrivi("Arrivederci!")
