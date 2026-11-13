import json
import logging

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool

from assistant.graph import SYSTEM_PROMPT, route, route_after_reviewer, route_after_router
from assistant.mcp_client import ALLOWED_MCP_TOOLS
from assistant.reviewer import (
    ReviewDecision,
    ReviewerOutputError,
    feedback_message,
    is_feedback,
    review_messages,
)
from assistant.router import (
    ROUTER_PROMPT,
    RouteDecision,
    RouterOutputError,
    refusal_text,
    router_messages,
)
from assistant.tools import ToolUnavailableError
from conftest import (
    TEST_SCOPE,
    ApprovingReviewer,
    ConversationRouter,
    FakeModel,
    fake_graph,
    tool_call,
)


def start_turn(model, text="salve", **kwargs):
    return fake_graph(model, **kwargs).invoke(
        {"messages": [HumanMessage(text)], "steps": 0, "reviews": 0}
    )


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
        (AIMessage("ok"), 1, "reviewer"),
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
    return fake_graph(model, router=router, **kwargs).invoke(
        {"messages": messages, "steps": 0, "reviews": 0}
    )


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


# --- reviewer (lesson 6, step 2) ---

QUESTION = "Che ore sono a Tokyo e quanto fa 17 * 23?"


def reviewed_turn(reviewer, model, text="domanda", **kwargs):
    return fake_graph(model, reviewer=reviewer, **kwargs).invoke(
        {"messages": [HumanMessage(text)], "steps": 0, "reviews": 0}
    )


def verdict(coherent, reason="incompleta"):
    return ReviewDecision(reason=reason, coherent=coherent)


def reviewer_lines(caplog, level=None):
    return [
        r.getMessage() for r in caplog.records
        if r.getMessage().startswith("node=reviewer") and (level is None or r.levelno == level)
    ]


def test_approved_answer_is_reviewed_once(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    model, reviewer = FakeModel([AIMessage("Sono le 10.")]), ApprovingReviewer()
    result = reviewed_turn(reviewer, model)
    assert len(model.calls) == 1 and len(reviewer.calls) == 1
    assert (result["reviews"], result["coherent"], result["review_reason"]) == (1, True, "test")
    assert reviewer_lines(caplog) == [
        'node=reviewer review=1/2 coherent=true reason="test" next_node=end'
    ]
    assert not any(is_feedback(m) for m in result["messages"])


def test_partial_answer_is_rewritten(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    partial, complete = "A Tokyo sono le 00:47.", "A Tokyo sono le 00:47 e 17 * 23 = 391."
    model = FakeModel([tool_call(), AIMessage(partial), AIMessage(complete)])
    reviewer = FakeModel([
        verdict(False, "Manca il risultato di 17 * 23."),
        verdict(True, "Risponde a entrambe le parti."),
    ])
    result = reviewed_turn(reviewer, model, QUESTION)
    sent = model.calls[2][-1]
    assert is_feedback(sent)
    assert sent.content == feedback_message("Manca il risultato di 17 * 23.").content
    assert result["messages"][-1].content == complete
    assert (result["reviews"], result["steps"]) == (2, 3)
    # Only question and answer reach the reviewer, after the tools and at the second review too.
    assert reviewer.calls == [
        review_messages(QUESTION, partial), review_messages(QUESTION, complete)
    ]
    assert reviewer_lines(caplog) == [
        'node=reviewer review=1/2 coherent=false reason="Manca il risultato di 17 * 23." '
        "next_node=llm",
        'node=reviewer review=2/2 coherent=true reason="Risponde a entrambe le parti." '
        "next_node=end",
    ]


@pytest.mark.parametrize("max_reviews", [1, 2, 3])
def test_reviewer_that_always_rejects_stops_at_the_limit(caplog, max_reviews):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    model = FakeModel([AIMessage(f"bozza {i}") for i in range(max_reviews)])
    reviewer = FakeModel([verdict(False)] * max_reviews)
    result = reviewed_turn(reviewer, model, max_reviews=max_reviews)
    assert len(model.calls) == len(reviewer.calls) == max_reviews
    assert sum(is_feedback(m) for m in result["messages"]) == max_reviews - 1
    assert result["messages"][-1].content == f"bozza {max_reviews - 1}"
    assert reviewer_lines(caplog, logging.WARNING) == [
        f'node=reviewer review={max_reviews}/{max_reviews} coherent=false reason="incompleta" '
        "review_limit_reached next_node=end"
    ]


@pytest.mark.parametrize("output", [ReviewerOutputError("JSON troncato"), None])
def test_invalid_reviewer_output_approves_the_answer(caplog, output):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    model = FakeModel([AIMessage("Risposta.")])
    result = reviewed_turn(FakeModel([output]), model)
    assert result["messages"][-1].content == "Risposta." and len(model.calls) == 1
    assert (result["reviews"], result["coherent"], result["review_reason"]) == (1, True, "")
    error = json.dumps(str(output), ensure_ascii=False)
    assert reviewer_lines(caplog, logging.WARNING) == [
        f"node=reviewer review=1/2 fallback=invalid_output error={error} coherent=true "
        "next_node=end"
    ]


def test_refusal_and_limit_notice_are_not_reviewed():
    reviewer = ApprovingReviewer()
    router = FakeModel([decision("out_of_scope", "calcio")])
    fake_graph(FakeModel([]), router=router, reviewer=reviewer).invoke(
        {"messages": [HumanMessage("Chi ha vinto?")], "steps": 0, "reviews": 0}
    )
    result = reviewed_turn(reviewer, FakeModel([tool_call(id=f"c{i}") for i in range(5)]))
    assert result["messages"][-1].content.startswith("Ho raggiunto il limite di 5 passaggi")
    assert reviewer.calls == []


def test_reviewer_does_not_consume_steps(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    model = FakeModel([AIMessage("bozza"), AIMessage("finale")])
    result = reviewed_turn(FakeModel([verdict(False), verdict(True)]), model, max_steps=2)
    assert result["steps"] == 2
    assert result["messages"][-1].content == "finale"
    assert "limit_reached" not in caplog.text


def test_step_limit_during_a_rewrite_goes_to_limit(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    reviewer = FakeModel([verdict(False)])
    result = reviewed_turn(reviewer, FakeModel([AIMessage("bozza"), tool_call()]), max_steps=2)
    assert result["messages"][-1].content == (
        "Ho raggiunto il limite di 2 passaggi senza una risposta finale."
    )
    assert len(reviewer.calls) == 1
    assert "step=2/2 limit_reached" in caplog.text


def test_reviewer_reason_is_logged_on_one_line(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    reviewed_turn(FakeModel([verdict(True, 'riga 1\n"riga 2"')]), FakeModel([AIMessage("ok")]))
    [line] = reviewer_lines(caplog)
    assert "\n" not in line
    assert r'reason="riga 1\n\"riga 2\""' in line


def test_empty_answer_reaches_the_reviewer_as_empty():
    reviewer = ApprovingReviewer()
    reviewed_turn(reviewer, FakeModel([AIMessage("")]))
    assert reviewer.calls[0] == review_messages("domanda", "")
    assert reviewer.calls[0][1].content.endswith("(vuota)")


def test_route_after_reviewer_cases():
    def after(coherent, reviews, steps=1):
        state = {"coherent": coherent, "reviews": reviews, "steps": steps}
        return route_after_reviewer(state, max_reviews=2, max_steps=5)

    assert after(True, 1) == "end"
    assert after(False, 1) == "llm"
    assert after(False, 2) == "end"
    assert after(False, 1, steps=5) == "end"  # no agent call beyond MAX_STEPS


def test_rejection_at_the_last_step_ends_the_turn(caplog):
    # MAX_STEPS stays the total limit of agent calls in the turn, rewrites included (RF-31).
    caplog.set_level(logging.INFO, logger="assistant.graph")
    model = FakeModel([AIMessage("bozza")])
    reviewer = FakeModel([verdict(False)])
    result = reviewed_turn(reviewer, model, max_steps=1)
    assert len(model.calls) == 1 and len(reviewer.calls) == 1
    assert result["messages"][-1].content == "bozza"
    assert not any(is_feedback(m) for m in result["messages"])
    assert reviewer_lines(caplog, logging.WARNING) == [
        'node=reviewer review=1/2 coherent=false reason="incompleta" '
        "step_limit_reached next_node=end"
    ]


def test_rewrite_never_exceeds_max_steps(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    model = FakeModel([tool_call(id=f"c{i}") for i in range(4)] + [AIMessage("bozza")])
    result = reviewed_turn(FakeModel([verdict(False)]), model, max_steps=5)
    assert len(model.calls) == 5 and result["steps"] == 5
    assert "step=6/5" not in caplog.text


def test_graph_has_reviewer_node():
    assert "reviewer" in set(fake_graph(FakeModel([])).get_graph().nodes)
