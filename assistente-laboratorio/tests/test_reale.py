"""Prove con LM Studio attivo: eseguire solo su richiesta con `pytest -m reale`."""

import json
import os
from datetime import datetime

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from assistente.config import ErroreConfigurazione, carica_configurazione
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello
from assistente.sessione import Sessione
from assistente.strumenti import crea_ora_corrente

pytestmark = pytest.mark.reale


@pytest.fixture
def sessione_reale():
    try:
        config = carica_configurazione(os.environ)
    except ErroreConfigurazione as errore:
        pytest.fail(f"Prova reale: imposta LMSTUDIO_BASE_URL e LMSTUDIO_MODELLO ({errore})")
    strumenti = [crea_ora_corrente()]
    return Sessione(costruisci_grafo(crea_modello(config, strumenti), strumenti, config.max_passi))


def chiamate_strumento(messaggi) -> list[dict]:
    return [c for m in messaggi if isinstance(m, AIMessage) for c in m.tool_calls]


def test_ricorda_il_nome_senza_strumento(sessione_reale):  # CA-4
    sessione_reale.invia("Mi chiamo Paolo")
    risposta = sessione_reale.invia("Come mi chiamo?")
    assert "Paolo" in risposta, risposta
    assert chiamate_strumento(sessione_reale.messaggi) == [], sessione_reale.messaggi


def test_ora_a_tokyo_e_poi_a_roma(sessione_reale):  # CA-2 e CA-3
    risposta = sessione_reale.invia("Che ore sono a Tokyo?")
    messaggi = sessione_reale.messaggi
    assert {"fuso": "Asia/Tokyo"} in [c["args"] for c in chiamate_strumento(messaggi)], messaggi
    risultati = [json.loads(m.content) for m in messaggi if isinstance(m, ToolMessage)]
    data_ora = datetime.fromisoformat(
        next(r["data_ora"] for r in risultati if r.get("fuso") == "Asia/Tokyo")
    )
    h, m = data_ora.hour, data_ora.minute
    assert f"{h:02d}:{m:02d}" in risposta or f"{h}:{m:02d}" in risposta, risposta

    n = len(sessione_reale.messaggi)
    risposta_roma = sessione_reale.invia("E a Roma?")
    nuove = chiamate_strumento(sessione_reale.messaggi[n:])
    assert {"fuso": "Europe/Rome"} in [c["args"] for c in nuove], (risposta_roma, nuove)
