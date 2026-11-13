import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistant.reviewer import feedback_message
from assistant.router import refusal_text
from assistant.summary import (
    SUMMARY_PROMPT,
    cut_index,
    is_user_question,
    summary_input,
    with_summary,
)
from conftest import tool_call


def D(text):
    return HumanMessage(text)


def R(text):
    return AIMessage(text)


def tool_result(id="c1"):
    return ToolMessage(
        '{"datetime": "2026-11-13T10:00:00+09:00"}', tool_call_id=id, name="get_current_time"
    )


def with_tools():
    return [D("d1"), R("r1"), D("d2"), tool_call(), tool_result(), R("r2"), D("d3")]


def with_rewrite():
    return [D("d1"), R("r1"), D("d2"), R("bozza"), feedback_message("m"), R("r2"), D("d3")]


@pytest.mark.parametrize(("messages", "keep", "expected"), [
    ([D("d1"), R("r1"), D("d2")], 2, 0),  # short history
    (with_tools(), 2, 2),  # lands on the final answer → back to D2
    (with_tools(), 3, 2),  # lands on the ToolMessage
    (with_tools(), 4, 2),  # lands on the tool_call
    (with_rewrite(), 3, 2),  # lands on the reviewer's indication
    (with_rewrite(), 4, 2),  # lands on the rejected draft
    ([D("d1"), R("r1"), D("d2"), R("r2"), D("d3")], 3, 2),  # already on a question
    ([D("d1"), R("bozza"), feedback_message("m"), R("r1"), D("d2")], 2, 0),  # one turn + question
    ([D("d1")], 1, 0),
])
def test_cut_index(messages, keep, expected):  # CA-41
    cut = cut_index(messages, keep)
    assert cut == expected
    kept = messages[cut:]
    assert len(kept) >= keep or cut == 0
    assert cut == 0 or is_user_question(kept[0])
    kept_calls = {c["id"] for m in kept if isinstance(m, AIMessage) for c in m.tool_calls}
    assert all(m.tool_call_id in kept_calls for m in kept if isinstance(m, ToolMessage))


def test_is_user_question():
    assert is_user_question(D("ciao"))
    assert not is_user_question(feedback_message("manca"))
    assert not is_user_question(R("ciao"))


def test_summary_input_first_time():
    old = [
        D("Mi chiamo Paolo"), R("Piacere, Paolo."), D("Ore?"), tool_call(), tool_result(),
        R("Sono le 10."),
    ]
    sent = summary_input("", old)
    assert len(sent) == 2 and sent[0] == SystemMessage(SUMMARY_PROMPT)
    assert sent[1] == HumanMessage(
        "Riassunto precedente:\n(nessuno)\n\nNuovi messaggi:\n"
        "Utente: Mi chiamo Paolo\nAssistente: Piacere, Paolo.\n"
        "Utente: Ore?\nAssistente: Sono le 10."
    )


def test_summary_input_with_previous_summary_and_empty_answer():
    sent = summary_input("L'utente si chiama Paolo.", [D("ciao"), R("  ")])
    assert sent[1].content == (
        "Riassunto precedente:\nL'utente si chiama Paolo.\n\nNuovi messaggi:\nUtente: ciao"
    )


def test_summary_input_with_rewrite_refusal_and_limit():  # Review Focus 5
    notice = "Ho raggiunto il limite di 1 passaggi senza una risposta finale."
    old = [
        D("d1"), R("bozza"), feedback_message("manca"), R("riscritta"),
        D("Mondiali?"), R(refusal_text("fuori ambito")),
        D("d3"), tool_call(), tool_result(), R(notice),
    ]
    text = summary_input("", old)[1].content
    assert "Assistente: riscritta" in text
    assert "bozza" not in text and "Revisione:" not in text
    assert f"Assistente: {refusal_text('fuori ambito')}" in text
    assert f"Assistente: {notice}" in text and "datetime" not in text


def test_with_summary():
    assert with_summary("P", "") == "P"
    assert with_summary("P", "S") == "P\n\nRiassunto della conversazione precedente:\nS"
