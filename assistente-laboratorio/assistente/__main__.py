"""Avvio: configurazione → logging → modello → grafo → sessione → terminale."""

import logging
import os
import sys
from collections.abc import Mapping

from assistente.config import ErroreConfigurazione, carica_configurazione
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello
from assistente.sessione import Sessione
from assistente.terminale import avvia


def main(env: Mapping[str, str] = os.environ) -> int:
    try:
        config = carica_configurazione(env)
    except ErroreConfigurazione as errore:
        print(f"Configurazione non valida: {errore}", file=sys.stderr)
        return 1

    logging.basicConfig(
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=config.log_level,
    )
    if config.log_level != "DEBUG":
        for libreria in ("httpx", "httpx2", "openai"):  # openai 3.x usa httpx2
            logging.getLogger(libreria).setLevel(logging.WARNING)

    modello = crea_modello(config)
    sessione = Sessione(costruisci_grafo(modello, [], config.max_passi))
    print(
        f"Assistente del laboratorio — modello {config.modello} su {config.base_url}. "
        "Scrivi 'esci' per uscire."
    )
    avvia(sessione)
    return 0


if __name__ == "__main__":
    sys.exit(main())
