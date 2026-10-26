import pytest

from assistente.terminale import avvia
from conftest import errore_lm_studio


def ingressi(*righe):
    """Simula input(): restituisce le righe in ordine, solleva le eccezioni, poi EOFError."""
    coda = list(righe)
    prompt_ricevuti = []

    def leggi(prompt):
        prompt_ricevuti.append(prompt)
        if not coda:
            raise EOFError
        riga = coda.pop(0)
        if isinstance(riga, BaseException):
            raise riga
        return riga

    leggi.prompt_ricevuti = prompt_ricevuti
    return leggi


class SessioneFinta:
    def __init__(self, *esiti):
        self._esiti = list(esiti)
        self.domande = []

    def invia(self, testo):
        self.domande.append(testo)
        esito = self._esiti.pop(0) if self._esiti else f"risposta a {testo}"
        if isinstance(esito, BaseException):
            raise esito
        return esito


def esegui(sessione, *righe):
    uscite = []
    leggi = ingressi(*righe)
    avvia(sessione, leggi=leggi, scrivi=uscite.append)
    return uscite, leggi


def test_domanda_e_risposta():
    uscite, leggi = esegui(SessioneFinta(), "ciao")
    assert uscite == ["Assistente> risposta a ciao", "Arrivederci!"]
    assert set(leggi.prompt_ricevuti) == {"Tu> "}


@pytest.mark.parametrize("comando", ["esci", "ESCI", "  Esci  "])
def test_esci(comando):
    sessione = SessioneFinta()
    uscite, _ = esegui(sessione, comando, "non letta")
    assert uscite == ["Arrivederci!"]
    assert sessione.domande == []


def test_eof():
    assert esegui(SessioneFinta())[0] == ["Arrivederci!"]


def test_ctrl_c_durante_input():
    assert esegui(SessioneFinta(), KeyboardInterrupt())[0] == ["Arrivederci!"]


def test_ctrl_c_durante_attesa_del_modello():
    uscite, _ = esegui(SessioneFinta(KeyboardInterrupt()), "che ore sono?", "non letta")
    assert uscite == ["Arrivederci!"]


def test_input_vuoto_ignorato():
    sessione = SessioneFinta()
    uscite, _ = esegui(sessione, "", "   ", "esci")
    assert sessione.domande == []
    assert uscite == ["Arrivederci!"]


def test_testo_inviato_senza_spazi():
    sessione = SessioneFinta()
    esegui(sessione, "  ciao  ")
    assert sessione.domande == ["ciao"]


def test_errore_lm_studio_e_si_continua():
    sessione = SessioneFinta(errore_lm_studio(), "eccomi")
    uscite, _ = esegui(sessione, "prima", "seconda")
    assert uscite == [
        "Errore: LM Studio non ha risposto correttamente (Connection error.). Riprova.",
        "Assistente> eccomi",
        "Arrivederci!",
    ]


def test_altre_eccezioni_non_intercettate():
    with pytest.raises(RuntimeError):
        esegui(SessioneFinta(RuntimeError("difetto")), "ciao")
