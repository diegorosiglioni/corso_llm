import json
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistente.grafo import PROMPT_SISTEMA, instrada
from conftest import ModelloFinto, chiamata, grafo_finto


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


# --- instradamento, strumenti e limite ---

def test_instrada_casi():
    invalida = AIMessage("", invalid_tool_calls=[{
        "name": "ora_corrente", "args": "{fuso", "id": "c1", "error": "json", "type": "invalid_tool_call",
    }])
    casi = [
        (AIMessage("ok"), 1, "fine"),
        (chiamata(), 1, "strumenti"),
        (chiamata(), 4, "strumenti"),
        (chiamata(), 5, "limite"),
        (invalida, 1, "fine"),
    ]
    for ultimo, passi, atteso in casi:
        assert instrada({"messaggi": [ultimo], "passi": passi}, 5) == atteso, (ultimo, passi)


def tool_messages(messaggi):
    return [m for m in messaggi if isinstance(m, ToolMessage)]


def test_ciclo_modello_strumento_modello():
    modello = ModelloFinto([chiamata(), AIMessage("A Tokyo sono le 00:47.")])
    r = avvia_turno(modello, "che ore sono a Tokyo?")
    tm = r["messaggi"][2]
    assert isinstance(tm, ToolMessage)
    assert tm.tool_call_id == "c1" and tm.name == "ora_corrente"
    assert json.loads(tm.content) == {"fuso": "Asia/Tokyo", "data_ora": "2026-10-27T00:47:12+09:00"}
    assert modello.chiamate[1][-1] == tm
    assert r["messaggi"][-1].content == "A Tokyo sono le 00:47."
    assert r["passi"] == 2


def test_piu_chiamate_nello_stesso_messaggio():
    doppia = AIMessage("", tool_calls=[
        {"name": "ora_corrente", "args": {"fuso": "Asia/Tokyo"}, "id": "c1"},
        {"name": "ora_corrente", "args": {"fuso": "Europe/Rome"}, "id": "c2"},
    ])
    r = avvia_turno(ModelloFinto([doppia, AIMessage("fatto")]))
    tms = tool_messages(r["messaggi"])
    assert [t.tool_call_id for t in tms] == ["c1", "c2"]
    assert [json.loads(t.content)["fuso"] for t in tms] == ["Asia/Tokyo", "Europe/Rome"]


def test_strumento_sconosciuto():
    r = avvia_turno(ModelloFinto([chiamata(nome="meteo"), AIMessage("ok")]))
    assert json.loads(tool_messages(r["messaggi"])[0].content) == {
        "errore": "Strumento sconosciuto: 'meteo'."
    }


def test_argomenti_non_validi():
    r = avvia_turno(ModelloFinto([chiamata(fuso=None), AIMessage("ok")]))
    errore = json.loads(tool_messages(r["messaggi"])[0].content)["errore"]
    assert errore.startswith("Argomenti non validi per 'ora_corrente':")
    assert "Europe/Rome" in errore


def test_limite():
    modello = ModelloFinto([chiamata(id=f"c{i}") for i in range(5)])
    r = avvia_turno(modello, max_passi=5)
    assert len(modello.chiamate) == 5
    assert r["messaggi"][-1].content == "Ho raggiunto il limite di 5 passaggi senza una risposta finale."
    richieste = [tc["id"] for m in r["messaggi"] if isinstance(m, AIMessage) for tc in m.tool_calls]
    risposte = [t.tool_call_id for t in tool_messages(r["messaggi"])]
    assert richieste == risposte
    assert json.loads(tool_messages(r["messaggi"])[-1].content) == {
        "errore": "Non eseguito: limite di passaggi raggiunto."
    }


def test_limite_alto_senza_errore_di_ricorsione():
    modello = ModelloFinto([chiamata(id=f"c{i}") for i in range(20)])
    r = avvia_turno(modello, max_passi=20)
    assert len(modello.chiamate) == 20
    assert r["messaggi"][-1].content == "Ho raggiunto il limite di 20 passaggi senza una risposta finale."


def test_log_delle_chiamate(caplog):
    caplog.set_level(logging.INFO, logger="assistente.grafo")
    avvia_turno(ModelloFinto([chiamata(), chiamata(fuso="Tokio", id="c2"), AIMessage("ok")]))
    assert "passaggio 1/5 chiamata ora_corrente {'fuso': 'Asia/Tokyo'}" in caplog.text
    assert (
        "passaggio 1/5 risultato ora_corrente "
        "{'fuso': 'Asia/Tokyo', 'data_ora': '2026-10-27T00:47:12+09:00'}"
    ) in caplog.text
    avvisi = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(a.startswith("passaggio 2/5 risultato ora_corrente {'errore'") for a in avvisi)


def test_log_limite_e_argomenti_non_interpretabili(caplog):
    caplog.set_level(logging.INFO, logger="assistente.grafo")
    invalida = AIMessage("", invalid_tool_calls=[{
        "name": "ora_corrente", "args": "{fuso", "id": "x", "error": "json", "type": "invalid_tool_call",
    }])
    avvia_turno(ModelloFinto([invalida]))
    avvia_turno(ModelloFinto([chiamata()]), max_passi=1)
    avvisi = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(a.startswith("passaggio 1/5 argomenti non interpretabili:") for a in avvisi)
    assert "limite di 1 passaggi raggiunto, chiamate non eseguite: ['ora_corrente']" in avvisi
