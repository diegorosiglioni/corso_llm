from datetime import datetime, timezone

import pytest

from assistente.strumenti import crea_ora_corrente
from conftest import ORA_FISSA


def ora(fuso, adesso=ORA_FISSA):
    return crea_ora_corrente(lambda: adesso).invoke({"fuso": fuso})


def test_tokyo():
    assert ora("Asia/Tokyo") == {"fuso": "Asia/Tokyo", "data_ora": "2026-10-27T00:47:12+09:00"}


def test_roma_inverno():
    assert ora("Europe/Rome")["data_ora"] == "2026-10-26T16:47:12+01:00"


def test_roma_estate():
    estate = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    assert ora("Europe/Rome", estate)["data_ora"] == "2026-07-01T12:00:00+02:00"


@pytest.mark.parametrize("fuso", ["Tokio", "", "../x", "asia/tokyo"])
def test_fuso_non_valido(fuso):
    assert ora(fuso) == {
        "errore": f"Fuso orario sconosciuto: '{fuso}'. Usa un nome IANA, es. 'Asia/Tokyo'."
    }


def test_nome_parametri_e_descrizione():
    s = crea_ora_corrente()
    assert s.name == "ora_corrente"
    assert s.tool_call_schema.model_json_schema()["required"] == ["fuso"]
    assert set(s.args) == {"fuso"}
    assert "Europe/Rome" in s.description and "Asia/Tokyo" in s.description


def test_orologio_reale_predefinito():
    ora_reale = crea_ora_corrente().invoke({"fuso": "UTC"})
    assert ora_reale["data_ora"].endswith("+00:00")
