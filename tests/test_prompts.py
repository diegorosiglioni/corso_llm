"""Texts of the MCP prompts spiega and riassumi_conversazione (pure logic, no MCP)."""

import pytest

from assistant.prompts import (
    LEVELS,
    MAX_TOPIC_LENGTH,
    SUMMARY_STYLES,
    explain_prompt,
    summary_prompt,
)


@pytest.mark.parametrize("level", ["base", "intermedio", "avanzato"])
def test_explain_prompt_for_each_level(level):
    assert explain_prompt("Model Context Protocol", level) == (
        f"Spiegami Model Context Protocol a livello {level}: {LEVELS[level]}."
    )


def test_explain_prompt_base_text():
    assert explain_prompt("MCP", "base") == (
        "Spiegami MCP a livello base: con parole semplici, senza dare per scontate conoscenze "
        "tecniche, e con un esempio concreto."
    )


def test_explain_prompt_strips_spaces():
    assert explain_prompt("  MCP  ", " avanzato ") == explain_prompt("MCP", "avanzato")


def test_explain_prompt_keeps_apostrophe_and_max_length():
    assert explain_prompt("l'IA", "base").startswith("Spiegami l'IA a livello base")
    topic = "x" * MAX_TOPIC_LENGTH
    assert topic in explain_prompt(topic, "base")


@pytest.mark.parametrize(
    ("topic", "message"),
    [
        ("", "L'argomento da spiegare è vuoto."),
        ("   ", "L'argomento da spiegare è vuoto."),
        ("x" * (MAX_TOPIC_LENGTH + 1), "L'argomento da spiegare supera 200 caratteri."),
        ("prima\nseconda", "L'argomento da spiegare deve stare su una riga."),
        ("prima\rseconda", "L'argomento da spiegare deve stare su una riga."),
    ],
)
def test_explain_prompt_rejects_invalid_topics(topic, message):
    with pytest.raises(ValueError) as e:
        explain_prompt(topic, "base")
    assert str(e.value) == message


@pytest.mark.parametrize("level", ["esperto", "", "Base"])
def test_explain_prompt_rejects_invalid_levels(level):
    with pytest.raises(ValueError) as e:
        explain_prompt("MCP", level)
    assert str(e.value) == (
        f"Livello non valido: '{level}'. Valori ammessi: base, intermedio, avanzato."
    )


@pytest.mark.parametrize("style", ["sintetico", "dettagliato"])
def test_summary_prompt_for_each_style(style):
    assert summary_prompt(style) == (
        f"Riassumi la nostra conversazione fino a questo momento, {SUMMARY_STYLES[style]}. "
        "Usa solo quanto detto in questa conversazione, compreso l'eventuale riassunto dei turni "
        "precedenti, senza chiamare strumenti."
    )


def test_summary_prompt_strips_spaces():
    assert summary_prompt(" sintetico ") == summary_prompt("sintetico")


@pytest.mark.parametrize("style", ["breve", "", "  ", "Sintetico"])
def test_summary_prompt_rejects_invalid_styles(style):
    with pytest.raises(ValueError) as e:
        summary_prompt(style)
    assert str(e.value) == (
        f"Stile non valido: '{style.strip()}'. Valori ammessi: sintetico, dettagliato."
    )
