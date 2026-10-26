import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from assistente.grafo import PROMPT_SISTEMA
from conftest import ModelloFinto, grafo_finto


def avvia_turno(modello, testo="salve", **kwargs):
    return grafo_finto(modello, **kwargs).invoke({"messaggi": [HumanMessage(testo)], "passi": 0})


def test_risposta_fissa_in_un_passo():
    modello = ModelloFinto([AIMessage("Ciao!")])
    risultato = avvia_turno(modello)
    assert [m.content for m in risultato["messaggi"]] == ["salve", "Ciao!"]
    assert risultato["passi"] == 1
    assert len(modello.chiamate) == 1


def test_prompt_di_sistema_inviato_ma_non_salvato():
    modello = ModelloFinto([AIMessage("Ciao!")])
    risultato = avvia_turno(modello)
    ricevuti = modello.chiamate[0]
    assert isinstance(ricevuti[0], SystemMessage)
    assert ricevuti[0].content == PROMPT_SISTEMA
    assert ricevuti[1].content == "salve"
    assert not any(isinstance(m, SystemMessage) for m in risultato["messaggi"])


def test_log_del_passaggio(caplog):
    caplog.set_level(logging.INFO, logger="assistente.grafo")
    avvia_turno(ModelloFinto([AIMessage("Ciao!")]))
    assert "passaggio 1/5 → modello" in caplog.text
