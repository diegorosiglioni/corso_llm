"""CLI commands that start with "/": the MCP prompts are activated by the user, not by the model.

/prompts lists the prompts of the MCP server (prompts/list). Any other text that starts with "/"
is an unknown command. No command calls the model.
"""

import json
import logging
from dataclasses import dataclass

from assistant.mcp_client import PromptSpec, PromptUnavailableError

log = logging.getLogger(__name__)

LIST_COMMAND = "/prompts"
USAGE = "Uso: /prompt nome chiave=valore (valori con spazi tra virgolette doppie)."
LIST_HINT = "Scrivi /prompts per l'elenco dei prompt."


@dataclass(frozen=True)
class CommandResult:
    """What the terminal shows after a command."""

    output: str | None = None


def _json(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def format_prompts(specs: list[PromptSpec]) -> str:
    """Name, description and arguments of every prompt, then the usage line."""
    if not specs:
        return "Il server MCP non offre prompt."
    lines = ["Prompt disponibili:"]
    for spec in specs:
        lines.append(f"- {spec.name}: {spec.description}" if spec.description else f"- {spec.name}")
        if not spec.arguments:
            lines.append("    nessun argomento")
        for argument in spec.arguments:
            kind = "obbligatorio" if argument.required else "facoltativo"
            line = f"    {argument.name} ({kind})"
            lines.append(f"{line}: {argument.description}" if argument.description else line)
    lines.append(USAGE)
    return "\n".join(lines)


class PromptCommands:
    """Handles the commands of the CLI with the MCP client of the session."""

    def __init__(self, client):
        self._client = client

    def handle(self, text: str) -> CommandResult:
        """`text` starts with "/"; the command word ignores case."""
        word, *rest = text.split(maxsplit=1)
        if word.lower() != LIST_COMMAND:
            return CommandResult(f"Comando sconosciuto: '{word}'. {LIST_HINT}")
        if rest:
            return self._rejected("il comando /prompts non ha argomenti")
        return self._list()

    def _list(self) -> CommandResult:
        try:
            specs = self._client.list_prompts()
        except PromptUnavailableError as error:
            log.warning("prompts/list status=unavailable error=%s", _json(str(error)))
            return CommandResult(f"Errore: prompt non disponibili ({error}).")
        log.info(
            "prompts/list count=%d names=%s", len(specs), ",".join(spec.name for spec in specs)
        )
        return CommandResult(format_prompts(specs))

    @staticmethod
    def _rejected(reason: str) -> CommandResult:
        log.info("prompt_command status=rejected reason=%s", _json(reason))
        return CommandResult(f"Errore nel comando: {reason}.")
