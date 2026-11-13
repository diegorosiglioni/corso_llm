import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import ValidationError

from assistant.mcp_client import ALLOWED_MCP_TOOLS
from assistant.reviewer import feedback_message
from assistant.router import ROUTER_PROMPT, RouteDecision, refusal_text, router_messages
from conftest import tool_call

REFUSAL = (
    "Mi dispiace, questa domanda è fuori dal mio ambito: domanda sul calcio. "
    "Chiedimi pure che cosa so fare."
)


def history():
    q1 = HumanMessage("Che ore sono a Tokyo?")
    answer = AIMessage("Sono le 10:00.")
    q2 = HumanMessage("E a Roma?")
    invalid = AIMessage(
        "", invalid_tool_calls=[{"name": "calculate", "args": "{", "id": "c2", "error": None}]
    )
    full = [
        SystemMessage("x"), q1, tool_call(), ToolMessage("{}", tool_call_id="c1"),
        invalid, answer, q2,
    ]
    return full, [q1, answer, q2]


def test_router_messages_keep_only_text_turns():
    full, expected = history()
    assert router_messages(full) == expected


def test_router_messages_do_not_modify_the_history():
    full, _ = history()
    before = list(full)
    router_messages(full)
    assert full == before


def test_router_prompt_contains_the_scope_and_no_tool_names():
    prompt = ROUTER_PROMPT.format(scope="AMBITO-DI-PROVA")
    assert "AMBITO-DI-PROVA" in prompt
    for name in ["get_current_time", *ALLOWED_MCP_TOOLS]:
        assert name not in prompt


def test_route_decision_accepts_only_two_categories():
    assert RouteDecision(category="out_of_scope", reason="x").category == "out_of_scope"
    assert RouteDecision(category="conversation", reason="x").category == "conversation"
    with pytest.raises(ValidationError):
        RouteDecision(category="tools", reason="x")


def test_refusal_text():
    assert refusal_text("domanda sul calcio") == REFUSAL
    assert refusal_text("  domanda sul calcio. ") == REFUSAL
    assert refusal_text("  ") == (
        "Mi dispiace, questa domanda è fuori dal mio ambito. Chiedimi pure che cosa so fare."
    )


def test_router_messages_keep_alternation_after_an_empty_answer():
    # An agent turn may end with an empty answer (Session shows EMPTY_REPLY): dropping it would
    # send two user messages in a row, which some chat templates reject.
    history = [HumanMessage("Ciao"), AIMessage(""), HumanMessage("Che ore sono?")]
    assert router_messages(history) == history


# --- reviewer (lesson 6, step 2) ---

def test_router_messages_drop_rejected_drafts_and_feedback():
    q, answer, q2 = HumanMessage("q"), AIMessage("risposta"), HumanMessage("q2")
    assert router_messages(
        [q, AIMessage("bozza"), feedback_message("manca"), answer, q2]
    ) == [q, answer, q2]


def test_router_messages_drop_a_draft_written_after_tools():
    q, answer = HumanMessage("q"), AIMessage("risposta")
    history = [
        q, tool_call(), ToolMessage("{}", tool_call_id="c1"), AIMessage("bozza"),
        feedback_message("manca"), tool_call(id="c2"), ToolMessage("{}", tool_call_id="c2"),
        answer,
    ]
    assert router_messages(history) == [q, answer]
