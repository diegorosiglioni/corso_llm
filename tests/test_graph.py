import json
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool

from assistant.graph import SYSTEM_PROMPT, route, route_after_router
from assistant.mcp_client import ALLOWED_MCP_TOOLS
from assistant.router import (
    ROUTER_PROMPT,
    RouteDecision,
    RouterOutputError,
    refusal_text,
    router_messages,
)
from assistant.tools import ToolUnavailableError
from conftest import TEST_SCOPE, ConversationRouter, FakeModel, fake_graph, tool_call


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


def test_system_prompt_mentions_every_tool():
    for name in ["get_current_time", *ALLOWED_MCP_TOOLS]:
        assert name in SYSTEM_PROMPT


def test_llm_step_log(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    start_turn(FakeModel([AIMessage("Ciao!")]))
    assert "step=1/5 node=llm" in caplog.text


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


def test_tool_call_logs_follow_slide_26(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    start_turn(FakeModel([tool_call(), tool_call(timezone="Tokio", id="c2"), AIMessage("ok")]))
    assert (
        "step=1/5 variant=local tool=get_current_time call_id=c1 "
        "arguments={'timezone': 'Asia/Tokyo'}"
    ) in caplog.text
    assert (
        "step=1/5 execution=ok call_id=c1 result="
        "{'timezone': 'Asia/Tokyo', 'datetime': '2026-10-27T00:47:12+09:00'}"
    ) in caplog.text
    assert "tool_message.call_id=c1 next_node=llm" in caplog.text
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        w.startswith("step=2/5 execution=tool_error call_id=c2 result={'error'") for w in warnings
    )


def test_unavailable_tool_is_transport_error(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")

    def down(**_):
        raise ToolUnavailableError("server terminato")

    remote = StructuredTool.from_function(
        down, name="add_note", description="d",
        args_schema={"type": "object", "properties": {}},
        metadata={"variant": "mcp"},
    )
    r = start_turn(FakeModel([tool_call(name="add_note"), AIMessage("ok")]), tools=[remote])
    assert json.loads(tool_messages(r["messages"])[0].content) == {
        "error": "Strumento non raggiungibile: server terminato. Riprova o riavvia l'assistente."
    }
    assert "variant=mcp tool=add_note call_id=c1" in caplog.text
    assert "step=1/5 execution=transport_error call_id=c1" in caplog.text


def test_limit_and_invalid_calls_logs(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    invalid = AIMessage("", invalid_tool_calls=[{
        "name": "get_current_time", "args": "{timezone", "id": "x", "error": "json",
        "type": "invalid_tool_call",
    }])
    start_turn(FakeModel([invalid, AIMessage("ok")]))
    start_turn(FakeModel([tool_call()]), max_steps=1)
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(w.startswith("step=1/5 invalid_tool_calls=") for w in warnings)
    assert "step=1/1 limit_reached pending=['get_current_time']" in warnings


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


# --- router (lesson 6, step 1) ---

def routed_turn(router, model, history=None, **kwargs):
    messages = history if history is not None else [HumanMessage("domanda")]
    return fake_graph(model, router=router, **kwargs).invoke({"messages": messages, "steps": 0})


def decision(category, reason):
    return RouteDecision(category=category, reason=reason)


def test_in_scope_question_reaches_the_agent(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    model = FakeModel([AIMessage("Sono le 10.")])
    result = routed_turn(FakeModel([decision("conversation", "chiede l'ora")]), model)
    assert result["messages"][-1].content == "Sono le 10."
    assert len(model.calls) == 1
    assert (result["category"], result["reason"]) == ("conversation", "chiede l'ora")
    assert 'node=router category=conversation reason="chiede l\'ora" next_node=llm' in caplog.text
    assert "step=1/5 node=llm" in caplog.text


def test_out_of_scope_question_never_reaches_the_agent(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    model = FakeModel([])
    result = routed_turn(FakeModel([decision("out_of_scope", "domanda sul calcio")]), model)
    refusal = result["messages"][-1]
    assert isinstance(refusal, AIMessage)
    assert refusal.content == refusal_text("domanda sul calcio")
    assert model.calls == []
    assert (
        'node=router category=out_of_scope reason="domanda sul calcio" next_node=refusal'
        in caplog.text
    )
    assert "node=refusal" in caplog.text
    assert "node=llm" not in caplog.text


def test_router_sees_scope_and_filtered_history():
    history = [
        HumanMessage("Che ore sono a Tokyo?"), tool_call(),
        ToolMessage("{}", tool_call_id="c1"), AIMessage("Sono le 10."), HumanMessage("E a Roma?"),
    ]
    router = ConversationRouter()
    routed_turn(router, FakeModel([AIMessage("Sono le 3.")]), history=history)
    sent = router.calls[0]
    assert sent[0] == SystemMessage(ROUTER_PROMPT.format(scope=TEST_SCOPE))
    assert sent[1:] == router_messages(history)


def fallback_line(error):
    return (
        f"node=router fallback=invalid_output error={error} category=conversation next_node=llm"
    )


def test_invalid_router_output_falls_back_to_the_agent(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    model = FakeModel([AIMessage("Risposta.")])
    result = routed_turn(FakeModel([RouterOutputError("JSON troncato")]), model)
    assert result["messages"][-1].content == "Risposta."
    assert result["category"] == "conversation"
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == [fallback_line('"JSON troncato"')]


def test_router_without_decision_falls_back(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    model = FakeModel([AIMessage("Risposta.")])
    result = routed_turn(FakeModel([None]), model)
    assert result["messages"][-1].content == "Risposta."
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1 and "node=router fallback=invalid_output" in warnings[0]


def test_router_reason_is_logged_on_one_line(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    routed_turn(FakeModel([decision("out_of_scope", 'riga 1\n"riga 2"')]), FakeModel([]))
    line = next(r.getMessage() for r in caplog.records if "node=router" in r.getMessage())
    assert "\n" not in line
    assert r'reason="riga 1\n\"riga 2\""' in line


def test_router_does_not_consume_steps(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    result = routed_turn(ConversationRouter(), FakeModel([AIMessage("ok")]), max_steps=1)
    assert result["steps"] == 1
    assert "step=1/1 node=llm" in caplog.text


def test_graph_has_router_and_refusal_nodes():
    nodes = set(fake_graph(FakeModel([])).get_graph().nodes)
    assert {"router", "refusal", "llm", "tools", "limit"} <= nodes


def test_route_after_router_cases():
    assert route_after_router({"category": "conversation"}) == "llm"
    assert route_after_router({"category": "out_of_scope"}) == "refusal"
