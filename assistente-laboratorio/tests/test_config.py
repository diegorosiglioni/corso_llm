import pytest

from assistente.config import Configurazione, ErroreConfigurazione, carica_configurazione

VALIDO = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODELLO": "google/gemma-4-e2b"}


def errore(env) -> str:
    with pytest.raises(ErroreConfigurazione) as e:
        carica_configurazione(env)
    return str(e.value)


def test_valori_validi_e_default():
    c = carica_configurazione(VALIDO)
    assert c == Configurazione("http://localhost:1234/v1", "google/gemma-4-e2b", 5, "INFO")


def test_valori_facoltativi():
    c = carica_configurazione({**VALIDO, "MAX_PASSI": " 3 ", "LOG_LEVEL": "debug"})
    assert (c.max_passi, c.log_level) == (3, "DEBUG")


def test_facoltativi_vuoti_usano_i_default():
    c = carica_configurazione({**VALIDO, "MAX_PASSI": "", "LOG_LEVEL": "  "})
    assert (c.max_passi, c.log_level) == (5, "INFO")


def test_spazi_rimossi():
    c = carica_configurazione({"LMSTUDIO_BASE_URL": " http://h:1/v1 ", "LMSTUDIO_MODELLO": " m "})
    assert (c.base_url, c.modello) == ("http://h:1/v1", "m")


def test_obbligatorie_mancanti():
    assert errore({}) == "Manca LMSTUDIO_BASE_URL. Manca LMSTUDIO_MODELLO."


def test_obbligatorie_vuote():
    assert errore({**VALIDO, "LMSTUDIO_MODELLO": "   "}) == "Manca LMSTUDIO_MODELLO."


def test_url_senza_schema():
    assert errore({**VALIDO, "LMSTUDIO_BASE_URL": "localhost:1234"}) == (
        "LMSTUDIO_BASE_URL deve iniziare con http:// o https://, ricevuto 'localhost:1234'."
    )


def test_url_https_accettato():
    assert carica_configurazione({**VALIDO, "LMSTUDIO_BASE_URL": "https://h/v1"}).base_url == "https://h/v1"


@pytest.mark.parametrize("valore", ["zero", "0", "-1", "2.5"])
def test_max_passi_non_valido(valore):
    assert errore({**VALIDO, "MAX_PASSI": valore}) == (
        f"MAX_PASSI deve essere un intero ≥ 1, ricevuto '{valore}'."
    )


def test_log_level_non_valido():
    assert errore({**VALIDO, "LOG_LEVEL": "TRACE"}) == (
        "LOG_LEVEL deve essere uno tra DEBUG, INFO, WARNING, ERROR, ricevuto 'TRACE'."
    )


def test_tutti_i_problemi_in_un_messaggio():
    assert errore({"MAX_PASSI": "zero"}) == (
        "Manca LMSTUDIO_BASE_URL. Manca LMSTUDIO_MODELLO. "
        "MAX_PASSI deve essere un intero ≥ 1, ricevuto 'zero'."
    )
