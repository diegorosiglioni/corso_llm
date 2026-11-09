import json
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistant.graph import SYSTEM_PROMPT, route
from conftest import FakeModel, fake_graph, tool_call


def start_turn(model, text="salve", **kwargs):
    return fake_graph(model, **kwargs).invoke({"messages": [HumanMessage(text)], "steps": 0})


def test_fixed_reply_in_one_step():
    model = FakeModel([AIMessage("Ciao!")])
    result = start_turn(model)
    assert [m.content for m in result["messages"]] == ["salve", "Ciao!"]
    assert result["steps"] == 1
    assert len(model.calls) == 1


def test_system_prompt_sent_but_not_stored():
    model = FakeModel([AIMessage("Ciao!")])
    result = start_turn(model)
    received = model.calls[0]
    assert isinstance(received[0], SystemMessage)
    assert received[0].content == SYSTEM_PROMPT
    assert received[1].content == "salve"
    assert not any(isinstance(m, SystemMessage) for m in result["messages"])


def test_step_log(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    start_turn(FakeModel([AIMessage("Ciao!")]))
    assert "passaggio 1/5 → modello" in caplog.text


# --- routing, tools and limit ---

def test_route_cases():
    invalid = AIMessage("", invalid_tool_calls=[{
        "name": "get_current_time", "args": "{timezone", "id": "c1", "error": "json",
        "type": "invalid_tool_call",
    }])
    cases = [
        (AIMessage("ok"), 1, "end"),
        (tool_call(), 1, "tools"),
        (tool_call(), 4, "tools"),
        (tool_call(), 5, "limit"),
        (invalid, 1, "tools"),
        (invalid, 5, "limit"),
    ]
    for last, steps, expected in cases:
        assert route({"messages": [last], "steps": steps}, 5) == expected, (last, steps)


def tool_messages(messages):
    return [m for m in messages if isinstance(m, ToolMessage)]


def test_llm_tool_llm_cycle():
    model = FakeModel([tool_call(), AIMessage("A Tokyo sono le 00:47.")])
    r = start_turn(model, "che ore sono a Tokyo?")
    tm = r["messages"][2]
    assert isinstance(tm, ToolMessage)
    assert tm.tool_call_id == "c1" and tm.name == "get_current_time"
    assert json.loads(tm.content) == {
        "timezone": "Asia/Tokyo", "datetime": "2026-10-27T00:47:12+09:00"
    }
    assert model.calls[1][-1] == tm
    assert r["messages"][-1].content == "A Tokyo sono le 00:47."
    assert r["steps"] == 2


def test_several_calls_in_the_same_message():
    double = AIMessage("", tool_calls=[
        {"name": "get_current_time", "args": {"timezone": "Asia/Tokyo"}, "id": "c1"},
        {"name": "get_current_time", "args": {"timezone": "Europe/Rome"}, "id": "c2"},
    ])
    r = start_turn(FakeModel([double, AIMessage("fatto")]))
    tms = tool_messages(r["messages"])
    assert [t.tool_call_id for t in tms] == ["c1", "c2"]
    assert [json.loads(t.content)["timezone"] for t in tms] == ["Asia/Tokyo", "Europe/Rome"]


def test_unknown_tool():
    r = start_turn(FakeModel([tool_call(name="meteo"), AIMessage("ok")]))
    assert json.loads(tool_messages(r["messages"])[0].content) == {
        "error": "Strumento sconosciuto: 'meteo'."
    }


def test_invalid_arguments():
    r = start_turn(FakeModel([tool_call(timezone=None), AIMessage("ok")]))
    error = json.loads(tool_messages(r["messages"])[0].content)["error"]
    assert error.startswith("Argomenti non validi per 'get_current_time':")
    assert "Europe/Rome" in error


def test_limit():
    model = FakeModel([tool_call(id=f"c{i}") for i in range(5)])
    r = start_turn(model, max_steps=5)
    assert len(model.calls) == 5
    assert r["messages"][-1].content == "Ho raggiunto il limite di 5 passaggi senza una risposta finale."
    requests = [tc["id"] for m in r["messages"] if isinstance(m, AIMessage) for tc in m.tool_calls]
    answers = [t.tool_call_id for t in tool_messages(r["messages"])]
    assert requests == answers
    assert json.loads(tool_messages(r["messages"])[-1].content) == {
        "error": "Non eseguito: limite di passaggi raggiunto."
    }


def test_high_limit_without_recursion_error():
    model = FakeModel([tool_call(id=f"c{i}") for i in range(20)])
    r = start_turn(model, max_steps=20)
    assert len(model.calls) == 20
    assert r["messages"][-1].content == "Ho raggiunto il limite di 20 passaggi senza una risposta finale."


def test_call_logs(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    start_turn(FakeModel([tool_call(), tool_call(timezone="Tokio", id="c2"), AIMessage("ok")]))
    assert "passaggio 1/5 chiamata get_current_time {'timezone': 'Asia/Tokyo'}" in caplog.text
    assert (
        "passaggio 1/5 risultato get_current_time "
        "{'timezone': 'Asia/Tokyo', 'datetime': '2026-10-27T00:47:12+09:00'}"
    ) in caplog.text
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(w.startswith("passaggio 2/5 risultato get_current_time {'error'") for w in warnings)


def test_limit_and_unparsable_arguments_logs(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    invalid = AIMessage("", invalid_tool_calls=[{
        "name": "get_current_time", "args": "{timezone", "id": "x", "error": "json",
        "type": "invalid_tool_call",
    }])
    start_turn(FakeModel([invalid, AIMessage("ok")]))
    start_turn(FakeModel([tool_call()]), max_steps=1)
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(w.startswith("passaggio 1/5 argomenti non interpretabili:") for w in warnings)
    assert "limite di 1 passaggi raggiunto, chiamate non eseguite: ['get_current_time']" in warnings


def invalid_call(id="x"):
    return AIMessage("", invalid_tool_calls=[{
        "name": "get_current_time", "args": "{timezone", "id": id, "error": "json",
        "type": "invalid_tool_call",
    }])


def test_unparsable_arguments_get_an_answer_and_the_model_recovers():
    model = FakeModel([invalid_call(), tool_call(id="c2"), AIMessage("Sono le 00:47.")])
    r = start_turn(model)
    tm = tool_messages(r["messages"])
    assert tm[0].tool_call_id == "x" and tm[0].name == "get_current_time"
    error = json.loads(tm[0].content)["error"]
    assert error.startswith("Argomenti non interpretabili per 'get_current_time': '{timezone'.")
    assert "Europe/Rome" in error
    assert model.calls[1][-1] == tm[0]
    assert r["messages"][-1].content == "Sono le 00:47."


def test_limit_also_answers_unparsable_arguments():
    model = FakeModel([invalid_call(id=f"x{i}") for i in range(5)])
    r = start_turn(model)
    requests = [c["id"] for m in r["messages"] if isinstance(m, AIMessage) for c in m.invalid_tool_calls]
    assert [t.tool_call_id for t in tool_messages(r["messages"])] == requests
    assert r["messages"][-1].content == "Ho raggiunto il limite di 5 passaggi senza una risposta finale."
