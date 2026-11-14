import copy

import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistant.agent import (
    EMPTY_REPLY,
    TurnResult,
    messages_from_json,
    messages_to_json,
    run_turn,
)
from assistant.reviewer import ReviewDecision, feedback_message, is_feedback
from assistant.router import RouteDecision, refusal_text
from conftest import FakeModel, fake_graph, lm_studio_error, tool_call

TOKYO = {"timezone": "Asia/Tokyo", "datetime": "2026-10-27T00:47:12+09:00"}


def contents(messages):
    return [m.content for m in messages]


def invalid_call(id="c1"):
    return AIMessage("", invalid_tool_calls=[{
        "name": "get_current_time", "args": "{timezone", "id": id, "error": "json",
        "type": "invalid_tool_call",
    }])


# --- run_turn ---

def test_turn_with_a_tool():
    model = FakeModel([tool_call(), AIMessage("A Tokyo sono le 00:47.")])
    result = run_turn(fake_graph(model), [], "", [HumanMessage("Che ore sono a Tokyo?")])
    assert isinstance(result, TurnResult)
    assert result.reply == "A Tokyo sono le 00:47."
    assert result.tools_used == [
        {"name": "get_current_time", "args": {"timezone": "Asia/Tokyo"}, "result": TOKYO, "ok": True}
    ]
    assert contents(result.history)[0] == "Che ore sono a Tokyo?"
    assert isinstance(result.history[2], ToolMessage)
    assert result.history[-1].content == "A Tokyo sono le 00:47."
    assert result.summary == ""


def test_turn_receives_history_and_summary():
    model = FakeModel([AIMessage("Ti chiami Paolo.")])
    history = [HumanMessage("Mi chiamo Paolo"), AIMessage("Piacere.")]
    result = run_turn(fake_graph(model), history, "S0", [HumanMessage("Come mi chiamo?")])
    assert contents(model.calls[0][1:]) == ["Mi chiamo Paolo", "Piacere.", "Come mi chiamo?"]
    assert model.calls[0][0].content.endswith("Riassunto della conversazione precedente:\nS0")
    assert contents(result.history) == [
        "Mi chiamo Paolo", "Piacere.", "Come mi chiamo?", "Ti chiami Paolo."
    ]
    assert result.summary == "S0" and result.tools_used == []


def test_turn_is_stateless_and_leaves_the_arguments_untouched():
    history = [HumanMessage("Mi chiamo Paolo"), AIMessage("Piacere.")]
    opening = [HumanMessage("Come mi chiamo?")]
    saved = copy.deepcopy((history, opening))
    graph = fake_graph(FakeModel([AIMessage("Paolo."), AIMessage("Paolo.")]))
    first = run_turn(graph, history, "", opening)
    second = run_turn(graph, history, "", opening)
    assert (history, opening) == saved
    assert all(m.id is None for m in history + opening)
    assert first.reply == second.reply == "Paolo."
    assert contents(first.history) == contents(second.history)
    assert len(first.history) == 4


def test_opening_messages_get_new_ids():
    history = [HumanMessage("uno", id="h1"), AIMessage("due", id="h2")]
    opening = [HumanMessage("tre", id="h1")]  # same id as a history message
    result = run_turn(fake_graph(FakeModel([AIMessage("quattro")])), history, "", opening)
    assert contents(result.history) == ["uno", "due", "tre", "quattro"]
    assert result.history[2].id not in ("h1", "h2")


def test_turn_opened_by_several_messages():
    model = FakeModel([AIMessage("Tocca a me.")])
    opening = [HumanMessage("Esempio"), AIMessage("Risposta d'esempio"), HumanMessage("Ora tu")]
    result = run_turn(fake_graph(model), [], "", opening)
    assert result.reply == "Tocca a me." and result.tools_used == []
    assert contents(result.history) == ["Esempio", "Risposta d'esempio", "Ora tu", "Tocca a me."]


def test_turn_without_opening_messages():
    with pytest.raises(ValueError):
        run_turn(fake_graph(FakeModel([])), [], "", [])


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_reply(text):
    result = run_turn(fake_graph(FakeModel([AIMessage(text)])), [], "", [HumanMessage("ciao")])
    assert result.reply == EMPTY_REPLY == "(Il modello non ha fornito una risposta.)"


def test_tool_error_is_not_ok():
    model = FakeModel([tool_call("Marte/Base"), AIMessage("Fuso sconosciuto.")])
    result = run_turn(fake_graph(model), [], "", [HumanMessage("ore su Marte?")])
    [used] = result.tools_used
    assert used["name"] == "get_current_time" and used["args"] == {"timezone": "Marte/Base"}
    assert used["ok"] is False and "Fuso orario sconosciuto" in used["result"]["error"]


def test_invalid_call_reports_the_received_text():
    model = FakeModel([invalid_call(), AIMessage("Riprovo più tardi.")])
    result = run_turn(fake_graph(model), [], "", [HumanMessage("ore?")])
    [used] = result.tools_used
    assert used["name"] == "get_current_time" and used["args"] == "{timezone"
    assert used["ok"] is False and "non interpretabili" in used["result"]["error"]


def test_calls_not_run_for_the_limit():
    model = FakeModel([tool_call(id="c1"), tool_call(id="c2")])
    result = run_turn(fake_graph(model, max_steps=2), [], "", [HumanMessage("ore?")])
    assert result.reply == "Ho raggiunto il limite di 2 passaggi senza una risposta finale."
    assert [u["ok"] for u in result.tools_used] == [True, False]
    assert result.tools_used[1]["result"] == {
        "error": "Non eseguito: limite di passaggi raggiunto."
    }


def test_tools_of_previous_turns_are_not_reported():
    model = FakeModel([tool_call(), AIMessage("Sono le 00:47."), AIMessage("Prego.")])
    graph = fake_graph(model)
    first = run_turn(graph, [], "", [HumanMessage("ore a Tokyo?")])
    second = run_turn(graph, first.history, first.summary, [HumanMessage("grazie")])
    assert len(first.tools_used) == 1 and second.tools_used == []


def test_refusal_of_the_router():
    router = FakeModel([RouteDecision(category="out_of_scope", reason="calcio")])
    model = FakeModel([])
    result = run_turn(fake_graph(model, router=router), [], "", [HumanMessage("Mondiali?")])
    assert result.reply == refusal_text("calcio") and result.tools_used == []
    assert model.calls == []


def test_history_and_summary_after_a_compression():
    graph = fake_graph(
        FakeModel([AIMessage("r3")]), summary_model=FakeModel([AIMessage("S1")]),
        summary_max_messages=4, summary_keep_messages=3,
    )
    history = [HumanMessage("d1"), AIMessage("r1"), HumanMessage("d2"), AIMessage("r2")]
    result = run_turn(graph, history, "", [HumanMessage("d3")])
    assert result.summary == "S1"
    assert contents(result.history) == ["d2", "r2", "d3", "r3"]
    assert result.reply == "r3"


def test_compression_keeps_the_tools_of_the_turn():
    graph = fake_graph(
        FakeModel([tool_call(), AIMessage("r3")]), summary_model=FakeModel([AIMessage("S1")]),
        summary_max_messages=4, summary_keep_messages=1,
    )
    history = [HumanMessage("d1"), AIMessage("r1"), HumanMessage("d2"), AIMessage("r2")]
    result = run_turn(graph, history, "", [HumanMessage("d3")])
    assert contents(result.history)[0] == "d3"
    assert [u["name"] for u in result.tools_used] == ["get_current_time"]


def test_errors_reach_the_caller():
    with pytest.raises(openai.APIConnectionError):
        run_turn(fake_graph(FakeModel([lm_studio_error()])), [], "", [HumanMessage("ciao")])


def test_feedback_of_the_reviewer_stays_in_the_history():
    reviewer = FakeModel([
        ReviewDecision(reason="manca", coherent=False), ReviewDecision(reason="ok", coherent=True)
    ])
    model = FakeModel([AIMessage("bozza"), AIMessage("completa")])
    result = run_turn(fake_graph(model, reviewer=reviewer), [], "", [HumanMessage("domanda")])
    assert result.reply == "completa"
    assert is_feedback(result.history[2])


# --- JSON form of the messages ---

FULL_HISTORY = [
    {"role": "user", "content": "Che ore sono a Tokyo?"},
    {"role": "assistant", "content": "",
     "tool_calls": [{"id": "c1", "name": "get_current_time", "args": {"timezone": "Asia/Tokyo"}}]},
    {"role": "tool", "content": '{"timezone": "Asia/Tokyo"}', "tool_call_id": "c1",
     "name": "get_current_time"},
    {"role": "assistant", "content": "",
     "invalid_tool_calls": [{"id": "c2", "name": "calculate", "args": "{expr", "error": "json"}]},
    {"role": "tool", "content": '{"error": "Argomenti non interpretabili"}', "tool_call_id": "c2",
     "name": "calculate"},
    {"role": "assistant", "content": "Sono le 00:47."},
    {"role": "user", "content": "Revisione: …", "name": "reviewer"},
    {"role": "assistant", "content": "A Tokyo sono le 00:47.",
     "tool_calls": [{"id": "c3", "name": "calculate", "args": {"expression": "1+1"}}],
     "invalid_tool_calls": [{"id": "c4", "name": "x", "args": None, "error": None}]},
    {"role": "tool", "content": "testo", "tool_call_id": "c3"},
    {"role": "tool", "content": "{}", "tool_call_id": "c4", "name": "x"},
    {"role": "assistant", "content": "Fatto."},
]


def test_round_trip():
    assert messages_to_json(messages_from_json(FULL_HISTORY)) == FULL_HISTORY


def test_empty_history():
    assert messages_from_json([]) == [] and messages_to_json([]) == []


def test_messages_from_json_types():
    messages = messages_from_json(FULL_HISTORY)
    assert [type(m) for m in messages[:3]] == [HumanMessage, AIMessage, ToolMessage]
    assert messages[1].tool_calls[0]["args"] == {"timezone": "Asia/Tokyo"}
    assert messages[3].invalid_tool_calls[0]["args"] == "{expr"
    assert messages[2].tool_call_id == "c1" and messages[2].name == "get_current_time"
    assert is_feedback(messages[6])
    assert all(m.id is None for m in messages)


def test_messages_to_json_of_graph_messages():
    reply = AIMessage(
        "ok", id="run-1", response_metadata={"model": "x"}, additional_kwargs={"a": 1},
        tool_calls=[],
    )
    feedback = feedback_message("manca")
    assert messages_to_json([HumanMessage("ciao", id="h"), reply, feedback]) == [
        {"role": "user", "content": "ciao"},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": feedback.content, "name": "reviewer"},
    ]


def test_messages_to_json_with_content_blocks():
    reply = AIMessage([{"type": "text", "text": "Ciao "}, {"type": "text", "text": "Paolo"}])
    assert messages_to_json([reply]) == [{"role": "assistant", "content": "Ciao Paolo"}]


def test_messages_to_json_rejects_system_messages():
    with pytest.raises(ValueError):
        messages_to_json([SystemMessage("istruzioni")])


def test_empty_call_lists_are_absent():
    data = [{"role": "assistant", "content": "ok", "tool_calls": [], "invalid_tool_calls": []}]
    assert messages_to_json(messages_from_json(data)) == [{"role": "assistant", "content": "ok"}]


def test_invalid_call_without_args_and_error():
    data = [
        {"role": "assistant", "content": "", "invalid_tool_calls": [{"id": "c1", "name": "x"}]},
        {"role": "tool", "content": "{}", "tool_call_id": "c1"},
    ]
    assert messages_to_json(messages_from_json(data))[0]["invalid_tool_calls"] == [
        {"id": "c1", "name": "x", "args": None, "error": None}
    ]


def test_json_history_goes_back_to_the_graph():
    model = FakeModel([tool_call(), AIMessage("Sono le 00:47."), AIMessage("Prego.")])
    graph = fake_graph(model)
    first = run_turn(graph, [], "", [HumanMessage("ore a Tokyo?")])
    data = messages_to_json(first.history)
    assert [m["role"] for m in data] == ["user", "assistant", "tool", "assistant"]
    second = run_turn(graph, messages_from_json(data), first.summary, [HumanMessage("grazie")])
    assert second.reply == "Prego."
    sent = model.calls[-1][1:]
    assert messages_to_json(sent) == data + [{"role": "user", "content": "grazie"}]


USER = {"role": "user", "content": "ciao"}
CALL = {"role": "assistant", "content": "",
        "tool_calls": [{"id": "c1", "name": "calculate", "args": {"expression": "1"}}]}
ANSWER = {"role": "tool", "content": "{}", "tool_call_id": "c1", "name": "calculate"}


@pytest.mark.parametrize("data, message", [
    ("ciao", "la cronologia deve essere un elenco di messaggi"),
    ([USER, "ciao"], "messaggio 2: deve essere un oggetto"),
    ([{"content": "x"}], "messaggio 1: manca il campo 'role'"),
    ([{"role": "system", "content": "x"}], "messaggio 1: i messaggi di sistema non sono ammessi"),
    ([{"role": "robot", "content": "x"}], "messaggio 1: ruolo sconosciuto 'robot'"),
    ([{"role": "user"}], "messaggio 1: manca il campo 'content'"),
    ([{"role": "user", "content": 3}], "messaggio 1: il campo 'content' deve essere un testo"),
    ([{"role": "user", "content": "x", "colore": "blu"}],
     "messaggio 1: campo sconosciuto 'colore' per il ruolo 'user'"),
    ([{"role": "user", "content": "x", "tool_call_id": "c1"}],
     "messaggio 1: campo sconosciuto 'tool_call_id' per il ruolo 'user'"),
    ([{"role": "user", "content": "x", "name": 1}],
     "messaggio 1: il campo 'name' deve essere un testo"),
    ([{"role": "assistant", "content": "", "tool_calls": {}}],
     "messaggio 1: il campo 'tool_calls' deve essere un elenco"),
    ([{"role": "assistant", "content": "", "tool_calls": ["c1"]}],
     "messaggio 1: chiamata 1 di 'tool_calls' non valida (deve essere un oggetto)"),
    ([{"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "name": "x"}]}],
     "messaggio 1: chiamata 1 di 'tool_calls' non valida (manca il campo 'args')"),
    ([{"role": "assistant", "content": "", "tool_calls": [{"id": "", "name": "x", "args": {}}]}],
     "messaggio 1: chiamata 1 di 'tool_calls' non valida (il campo 'id' deve essere un testo "
     "non vuoto)"),
    ([{"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "name": "x", "args": "{}"}]}],
     "messaggio 1: chiamata 1 di 'tool_calls' non valida (il campo 'args' deve essere un oggetto)"),
    ([{"role": "assistant", "content": "",
       "tool_calls": [{"id": "c1", "name": "x", "args": {}, "type": "tool_call"}]}],
     "messaggio 1: chiamata 1 di 'tool_calls' non valida (campo sconosciuto 'type')"),
    ([{"role": "assistant", "content": "", "invalid_tool_calls": [{"id": "c1", "name": "x",
                                                                   "args": {}}]}],
     "messaggio 1: chiamata 1 di 'invalid_tool_calls' non valida (il campo 'args' deve essere un "
     "testo o null)"),
    ([{"role": "assistant", "content": "", "invalid_tool_calls": [{"id": "c1", "name": "x",
                                                                   "error": 1}]}],
     "messaggio 1: chiamata 1 di 'invalid_tool_calls' non valida (il campo 'error' deve essere un "
     "testo o null)"),
    ([{"role": "assistant", "content": "",
       "tool_calls": [{"id": "c1", "name": "x", "args": {}}],
       "invalid_tool_calls": [{"id": "c1", "name": "y"}]}],
     "messaggio 1: id di chiamata ripetuto 'c1'"),
    ([{"role": "tool", "content": "{}", "name": "x"}], "messaggio 1: manca il campo 'tool_call_id'"),
    ([{"role": "tool", "content": "{}", "tool_call_id": ""}],
     "messaggio 1: il campo 'tool_call_id' deve essere un testo non vuoto"),
    ([USER, ANSWER], "messaggio 2: risposta di uno strumento senza una chiamata corrispondente"),
    ([CALL, ANSWER, ANSWER],
     "messaggio 3: risposta di uno strumento senza una chiamata corrispondente"),
    ([CALL, {**ANSWER, "tool_call_id": "c9"}],
     "messaggio 2: risposta di uno strumento senza una chiamata corrispondente"),
    ([CALL, USER], "messaggio 1: chiamata 'calculate' (id 'c1') senza risposta prima del messaggio 2"),
    ([USER, CALL], "messaggio 2: chiamata 'calculate' (id 'c1') senza risposta alla fine della "
                   "cronologia"),
])
def test_invalid_histories(data, message):
    with pytest.raises(ValueError) as error:
        messages_from_json(data)
    assert str(error.value) == message
