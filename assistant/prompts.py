"""Texts of the MCP prompts spiega and riassumi_conversazione (pure logic, no MCP)."""

LEVELS = {
    "base": "con parole semplici, senza dare per scontate conoscenze tecniche, e con un esempio concreto",
    "intermedio": "per chi conosce già le basi, con i termini tecnici essenziali",
    "avanzato": "in modo tecnico e preciso, con i dettagli di funzionamento e i limiti",
}
SUMMARY_STYLES = {
    "sintetico": "in pochi punti essenziali",
    "dettagliato": "turno per turno, con le domande, le risposte e i risultati ottenuti",
}
MAX_TOPIC_LENGTH = 200

EXPLAIN_DESCRIPTION = "Spiega un argomento al livello scelto."
TOPIC_DESCRIPTION = "Argomento da spiegare (per esempio Model Context Protocol)."
LEVEL_DESCRIPTION = "Livello della spiegazione: base, intermedio o avanzato (predefinito: base)."
SUMMARY_DESCRIPTION = "Riassume i turni della conversazione corrente."
STYLE_DESCRIPTION = "Stile del riassunto: sintetico o dettagliato."


def explain_prompt(topic: str, level: str) -> str:
    """Text of the prompt spiega; ValueError (Italian message) for an invalid topic or level."""
    topic, level = topic.strip(), level.strip()
    if not topic:
        raise ValueError("L'argomento da spiegare è vuoto.")
    if len(topic) > MAX_TOPIC_LENGTH:
        raise ValueError(f"L'argomento da spiegare supera {MAX_TOPIC_LENGTH} caratteri.")
    if "\n" in topic or "\r" in topic:
        raise ValueError("L'argomento da spiegare deve stare su una riga.")
    if level not in LEVELS:
        raise ValueError(
            f"Livello non valido: '{level}'. Valori ammessi: {', '.join(LEVELS)}."
        )
    return f"Spiegami {topic} a livello {level}: {LEVELS[level]}."


def summary_prompt(style: str) -> str:
    """Text of the prompt riassumi_conversazione; ValueError (Italian message) for an invalid
    style."""
    style = style.strip()
    if style not in SUMMARY_STYLES:
        raise ValueError(
            f"Stile non valido: '{style}'. Valori ammessi: {', '.join(SUMMARY_STYLES)}."
        )
    return (
        f"Riassumi la nostra conversazione fino a questo momento, {SUMMARY_STYLES[style]}. "
        "Usa solo quanto detto in questa conversazione, compreso l'eventuale riassunto dei turni "
        "precedenti, senza chiamare strumenti."
    )
