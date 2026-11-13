import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import ValidationError

from assistant.mcp_client import ALLOWED_MCP_TOOLS
from assistant.reviewer import (
    REVIEWER_PROMPT,
    ReviewDecision,
    feedback_message,
    is_feedback,
    review_messages,
    user_question,
)

FEEDBACK_TAIL = (
    " Scrivi una nuova risposta completa all'ultima domanda dell'utente. Usa i risultati degli "
    "strumenti già ottenuti e non ripetere le azioni già eseguite (per esempio una nota già "
    "salvata)."
)


def test_feedback_message():
    message = feedback_message("  Manca il calcolo. ")
    assert isinstance(message, HumanMessage) and message.name == "reviewer"
    assert message.content == (
        "Revisione: la risposta precedente non è coerente con la domanda: Manca il calcolo."
        + FEEDBACK_TAIL
    )
    assert feedback_message(" . ").content == (
        "Revisione: la risposta precedente non è coerente con la domanda." + FEEDBACK_TAIL
    )


def test_is_feedback():
    assert is_feedback(feedback_message("x"))
    assert not is_feedback(HumanMessage("x"))
    assert not is_feedback(HumanMessage("x", name="paolo"))
    assert not is_feedback(AIMessage("x", name="reviewer"))


def test_user_question_skips_feedback():
    history = [
        HumanMessage("q1"), AIMessage("a1"), HumanMessage("q2"),
        AIMessage("bozza"), feedback_message("manca"),
    ]
    assert user_question(history) == "q2"


def test_review_messages_contain_only_prompt_question_and_answer():
    assert review_messages("Che ore sono?", "Sono le 10.") == [
        SystemMessage(REVIEWER_PROMPT),
        HumanMessage("Domanda dell'utente:\nChe ore sono?\n\nRisposta proposta:\nSono le 10."),
    ]


@pytest.mark.parametrize("answer", ["", "  \n"])
def test_empty_answer_is_written_as_empty(answer):
    assert review_messages("q", answer)[1].content.endswith("Risposta proposta:\n(vuota)")


def test_review_decision_schema():
    # reason comes first: with json_schema the model writes the reason before the verdict.
    assert list(ReviewDecision.model_fields) == ["reason", "coherent"]
    with pytest.raises(ValidationError):
        ReviewDecision.model_validate({"reason": "x"})


def test_reviewer_prompt_names_no_tools():
    for name in ["get_current_time", *ALLOWED_MCP_TOOLS]:
        assert name not in REVIEWER_PROMPT


def test_reviewer_prompt_does_not_judge_data_from_the_conversation():
    # After a compression the reviewer still sees only question and answer (lesson 6, step 3).
    assert "conversazione precedente, che tu non vedi" in REVIEWER_PROMPT
