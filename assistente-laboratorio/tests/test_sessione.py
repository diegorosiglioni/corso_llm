import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from assistente.sessione import Sessione
from conftest import ModelloFinto, errore_lm_studio, grafo_finto


def contenuti(messaggi):
    return [m.content for m in messaggi]


def test_il_secondo_turno_invia_la_cronologia():
    modello = ModelloFinto([AIMessage("Piacere, Paolo."), AIMessage("Ti chiami Paolo.")])
    s = Sessione(grafo_finto(modello))
    assert s.invia("Mi chiamo Paolo") == "Piacere, Paolo."
    assert s.invia("Come mi chiamo?") == "Ti chiami Paolo."
    assert contenuti(modello.chiamate[1][1:]) == [
        "Mi chiamo Paolo", "Piacere, Paolo.", "Come mi chiamo?"
    ]


class GrafoCheRegistra:
    def __init__(self):
        self.passi_in_ingresso = []

    def invoke(self, stato):
        self.passi_in_ingresso.append(stato["passi"])
        return {"messaggi": stato["messaggi"] + [AIMessage("ok")], "passi": 1}


def test_passi_ripartono_da_zero():
    grafo = GrafoCheRegistra()
    s = Sessione(grafo)
    s.invia("uno")
    s.invia("due")
    assert grafo.passi_in_ingresso == [0, 0]


def test_turno_fallito_non_tocca_la_cronologia():
    modello = ModelloFinto([AIMessage("Piacere."), errore_lm_studio(), AIMessage("Ancora qui.")])
    s = Sessione(grafo_finto(modello))
    s.invia("Mi chiamo Paolo")
    prima = contenuti(s.messaggi)
    with pytest.raises(openai.APIConnectionError):
        s.invia("Domanda persa")
    assert contenuti(s.messaggi) == prima == ["Mi chiamo Paolo", "Piacere."]
    assert s.invia("Riprovo") == "Ancora qui."
    assert contenuti(modello.chiamate[2][1:]) == ["Mi chiamo Paolo", "Piacere.", "Riprovo"]


@pytest.mark.parametrize("testo", ["", "   "])
def test_risposta_vuota(testo):
    s = Sessione(grafo_finto(ModelloFinto([AIMessage(testo)])))
    assert s.invia("ciao") == "(Il modello non ha fornito una risposta.)"


def test_messaggi_e_una_copia():
    s = Sessione(grafo_finto(ModelloFinto([AIMessage("ok")])))
    s.invia("ciao")
    s.messaggi.append(HumanMessage("intruso"))
    assert contenuti(s.messaggi) == ["ciao", "ok"]
