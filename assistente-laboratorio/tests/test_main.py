import logging

import assistente.__main__ as avvio
from assistente.__main__ import main
from assistente.sessione import Sessione

VALIDO = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODELLO": "google/gemma-4-e2b"}


def _non_chiamare(*args, **kwargs):
    raise AssertionError("LM Studio non deve essere contattato")


def test_configurazione_mancante_esce_con_1(capsys, monkeypatch):
    monkeypatch.setattr(avvio, "crea_modello", _non_chiamare)
    monkeypatch.setattr(avvio, "avvia", _non_chiamare)
    assert main({"LMSTUDIO_BASE_URL": "http://localhost:1234/v1"}) == 1
    assert "Manca LMSTUDIO_MODELLO." in capsys.readouterr().err


def test_avvio_collega_i_moduli(capsys, monkeypatch):
    ricevute = []
    monkeypatch.setattr(avvio, "avvia", ricevute.append)
    assert main(VALIDO) == 0
    assert len(ricevute) == 1 and isinstance(ricevute[0], Sessione)
    assert (
        "Assistente del laboratorio — modello google/gemma-4-e2b su http://localhost:1234/v1. "
        "Scrivi 'esci' per uscire."
    ) in capsys.readouterr().out


def test_log_http_delle_librerie_nascosti_a_info(monkeypatch, caplog):
    caplog.set_level(logging.INFO)  # come nell'app, dove la radice è a INFO
    monkeypatch.setattr(avvio, "avvia", lambda sessione: None)
    main(VALIDO)
    for libreria in ("httpx", "httpx2", "openai"):
        assert logging.getLogger(libreria).getEffectiveLevel() == logging.WARNING, libreria
