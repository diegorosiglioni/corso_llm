import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from assistant.router import RouteDecision, refusal_text
from assistant.session import Session
from conftest import FakeModel, fake_graph, lm_studio_error, tool_call


def contents(messages):
    return [m.content for m in messages]


def test_second_turn_sends_the_history():
    model = FakeModel([AIMessage("Piacere, Paolo."), AIMessage("Ti chiami Paolo.")])
    s = Session(fake_graph(model))
    assert s.send("Mi chiamo Paolo") == "Piacere, Paolo."
    assert s.send("Come mi chiamo?") == "Ti chiami Paolo."
    assert contents(model.calls[1][1:]) == [
        "Mi chiamo Paolo", "Piacere, Paolo.", "Come mi chiamo?"
    ]


class RecordingGraph:
    def __init__(self):
        self.incoming_steps = []

    def invoke(self, state):
        self.incoming_steps.append(state["steps"])
        return {"messages": state["messages"] + [AIMessage("ok")], "steps": 1}


def test_steps_restart_from_zero():
    graph = RecordingGraph()
    s = Session(graph)
    s.send("uno")
    s.send("due")
    assert graph.incoming_steps == [0, 0]


def test_failed_turn_leaves_history_untouched():
    model = FakeModel([AIMessage("Piacere."), lm_studio_error(), AIMessage("Ancora qui.")])
    s = Session(fake_graph(model))
    s.send("Mi chiamo Paolo")
    before = contents(s.messages)
    with pytest.raises(openai.APIConnectionError):
        s.send("Domanda persa")
    assert contents(s.messages) == before == ["Mi chiamo Paolo", "Piacere."]
    assert s.send("Riprovo") == "Ancora qui."
    assert contents(model.calls[2][1:]) == ["Mi chiamo Paolo", "Piacere.", "Riprovo"]


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_reply(text):
    s = Session(fake_graph(FakeModel([AIMessage(text)])))
    assert s.send("ciao") == "(Il modello non ha fornito una risposta.)"


def test_messages_is_a_copy():
    s = Session(fake_graph(FakeModel([AIMessage("ok")])))
    s.send("ciao")
    s.messages.append(HumanMessage("intruso"))
    assert contents(s.messages) == ["ciao", "ok"]


def test_session_continues_after_the_limit():
    model = FakeModel([tool_call(id=f"c{i}") for i in range(5)] + [AIMessage("ok")])
    s = Session(fake_graph(model))
    assert s.send("ore?") == "Ho raggiunto il limite di 5 passaggi senza una risposta finale."
    previous = s.messages
    assert s.send("e adesso?") == "ok"
    assert model.calls[-1][1:] == previous + [s.messages[-2]]


def test_error_after_the_tool_leaves_no_orphans():
    model = FakeModel([AIMessage("Ciao."), tool_call(), lm_studio_error()])
    s = Session(fake_graph(model))
    s.send("salve")
    with pytest.raises(openai.APIConnectionError):
        s.send("che ore sono a Tokyo?")
    assert contents(s.messages) == ["salve", "Ciao."]


# --- router (lesson 6, step 1) ---

def test_router_error_leaves_history_untouched():
    router = FakeModel([RouteDecision(category="conversation", reason="saluto"), lm_studio_error()])
    s = Session(fake_graph(FakeModel([AIMessage("Ciao!")]), router=router))
    s.send("Ciao")
    before = contents(s.messages)
    with pytest.raises(openai.APIConnectionError):
        s.send("Domanda persa")
    assert contents(s.messages) == before


def test_conversation_continues_after_a_refusal():
    router = FakeModel([
        RouteDecision(category="out_of_scope", reason="calcio"),
        RouteDecision(category="conversation", reason="chiede l'ora"),
    ])
    model = FakeModel([AIMessage("Sono le 10.")])
    s = Session(fake_graph(model, router=router))
    assert s.send("Chi ha vinto i Mondiali?") == refusal_text("calcio")
    assert s.send("Che ore sono?") == "Sono le 10."
    refusal = refusal_text("calcio")
    assert contents(model.calls[0][1:]) == ["Chi ha vinto i Mondiali?", refusal, "Che ore sono?"]
    assert contents(router.calls[1][1:]) == ["Chi ha vinto i Mondiali?", refusal, "Che ore sono?"]
