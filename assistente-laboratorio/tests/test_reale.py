"""Prove con LM Studio attivo: eseguire solo su richiesta con `pytest -m reale`."""

import os

import pytest

from assistente.config import ErroreConfigurazione, carica_configurazione
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello
from assistente.sessione import Sessione

pytestmark = pytest.mark.reale


@pytest.fixture
def sessione_reale():
    try:
        config = carica_configurazione(os.environ)
    except ErroreConfigurazione as errore:
        pytest.fail(f"Prova reale: imposta LMSTUDIO_BASE_URL e LMSTUDIO_MODELLO ({errore})")
    return Sessione(costruisci_grafo(crea_modello(config), config.max_passi))


def test_ricorda_il_nome(sessione_reale):
    sessione_reale.invia("Mi chiamo Paolo")
    risposta = sessione_reale.invia("Come mi chiamo?")
    assert "Paolo" in risposta, risposta
