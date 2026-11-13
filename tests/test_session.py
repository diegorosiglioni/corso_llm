import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from assistant.reviewer import ReviewDecision, feedback_message, is_feedback, review_messages
from assistant.graph import SYSTEM_PROMPT
from assistant.router import ROUTER_PROMPT, RouteDecision, refusal_text
from assistant.session import Session
from assistant.summary import with_summary
from conftest import (
    TEST_SCOPE,
    ApprovingReviewer,
    ConversationRouter,
    FakeModel,
    fake_graph,
    lm_studio_error,
    tool_call,
)


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
        self.incoming_reviews = []
        self.incoming_summaries = []

    def invoke(self, state):
        self.incoming_steps.append(state["steps"])
        self.incoming_reviews.append(state["reviews"])
        self.incoming_summaries.append(state["summary"])
        return {
            "messages": state["messages"] + [AIMessage("ok")], "steps": 1,
            "summary": state["summary"],
        }


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


# --- reviewer (lesson 6, step 2) ---

def verdict(coherent, reason="manca"):
    return ReviewDecision(reason=reason, coherent=coherent)


def test_reviews_restart_from_zero():
    graph = RecordingGraph()
    s = Session(graph)
    s.send("uno")
    s.send("due")
    assert graph.incoming_reviews == [0, 0]


def test_draft_and_feedback_stay_in_the_history():
    reviewer = FakeModel([verdict(False), verdict(True)])
    model = FakeModel([AIMessage("bozza"), AIMessage("completa")])
    s = Session(fake_graph(model, reviewer=reviewer))
    assert s.send("domanda") == "completa"
    assert contents(s.messages) == [
        "domanda", "bozza", feedback_message("manca").content, "completa"
    ]
    assert is_feedback(s.messages[2])


def test_reviewer_error_leaves_history_untouched():
    reviewer = FakeModel([verdict(True), lm_studio_error()])
    model = FakeModel([AIMessage("Ciao!"), AIMessage("Persa.")])
    s = Session(fake_graph(model, reviewer=reviewer))
    s.send("Ciao")
    before = contents(s.messages)
    with pytest.raises(openai.APIConnectionError):
        s.send("Domanda persa")
    assert contents(s.messages) == before == ["Ciao", "Ciao!"]


def test_next_turn_after_a_rewrite():
    router = ConversationRouter()
    reviewer = FakeModel([verdict(False), verdict(True), verdict(True)])
    model = FakeModel([AIMessage("bozza"), AIMessage("completa"), AIMessage("Sono le 3.")])
    s = Session(fake_graph(model, router=router, reviewer=reviewer))
    s.send("Che ore sono a Tokyo?")
    assert s.send("E a Roma?") == "Sono le 3."
    assert contents(router.calls[1][1:]) == ["Che ore sono a Tokyo?", "completa", "E a Roma?"]
    assert contents(model.calls[2][1:]) == [
        "Che ore sono a Tokyo?", "bozza", feedback_message("manca").content, "completa",
        "E a Roma?",
    ]
    assert reviewer.calls[2] == review_messages("E a Roma?", "Sono le 3.")


# --- summary (lesson 6, step 3) ---

def small_session(model, summarizer, **kw):
    """Thresholds 4 and 3: compression at the third turn and again at the fourth."""
    return Session(fake_graph(
        model, summary_model=summarizer, summary_max_messages=4, summary_keep_messages=3, **kw
    ))


def test_summary_carries_over_between_turns():
    model = FakeModel([AIMessage(t) for t in ("r1", "r2", "r3", "r4")])
    summarizer = FakeModel([AIMessage("S1"), AIMessage("S2")])
    s = small_session(model, summarizer)
    for text in ("d1", "d2", "d3"):
        s.send(text)
    assert s.summary == "S1" and contents(s.messages) == ["d2", "r2", "d3", "r3"]
    s.send("d4")
    assert summarizer.calls[1][1].content.startswith("Riassunto precedente:\nS1\n\n")
    assert s.summary == "S2"
    assert model.calls[-1][0] == SystemMessage(with_summary(SYSTEM_PROMPT, "S2"))


def test_router_and_reviewer_never_see_the_summary():  # Review Focus 1
    router, reviewer = ConversationRouter(), ApprovingReviewer()
    model = FakeModel([AIMessage(t) for t in ("r1", "r2", "r3")])
    s = small_session(model, FakeModel([AIMessage("S1")]), router=router, reviewer=reviewer)
    for text in ("d1", "d2", "d3"):
        s.send(text)
    sent = router.calls[-1]
    assert sent[0] == SystemMessage(ROUTER_PROMPT.format(scope=TEST_SCOPE))
    assert contents(sent[1:]) == ["d2", "r2", "d3"]  # kept messages only, no summary
    assert reviewer.calls[-1] == review_messages("d3", "r3")
    assert model.calls[-1][0] == SystemMessage(with_summary(SYSTEM_PROMPT, "S1"))


def test_summary_error_leaves_history_and_summary_untouched():  # CA-42
    s = small_session(
        FakeModel([AIMessage("r1"), AIMessage("r2")]), FakeModel([lm_studio_error()])
    )
    s.send("d1")
    s.send("d2")
    with pytest.raises(openai.APIConnectionError):
        s.send("d3")
    assert contents(s.messages) == ["d1", "r1", "d2", "r2"] and s.summary == ""


def test_agent_error_after_compression_keeps_history_and_summary():  # Review Focus 2
    model = FakeModel([AIMessage("r1"), AIMessage("r2"), lm_studio_error(), AIMessage("r3")])
    summarizer = FakeModel([AIMessage("S1"), AIMessage("S1 bis")])
    s = small_session(model, summarizer)
    s.send("d1")
    s.send("d2")
    with pytest.raises(openai.APIConnectionError):
        s.send("d3")
    assert contents(s.messages) == ["d1", "r1", "d2", "r2"] and s.summary == ""
    s.send("d3")
    assert len(summarizer.calls) == 2 and s.summary == "S1 bis"


def test_summary_restarts_empty():
    graph = RecordingGraph()
    s = Session(graph)
    s.send("uno")
    assert graph.incoming_summaries == [""]
