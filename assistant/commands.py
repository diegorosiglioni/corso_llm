"""CLI commands that start with "/": the MCP prompts are activated by the user, not by the model.

/prompts lists the prompts of the MCP server (prompts/list). /prompt nome chiave=valore checks
the request against prompts/list, asks the server for the messages (prompts/get) and returns them
for the graph. Any other text that starts with "/" is an unknown command. No command calls the
model directly: the messages of /prompt go to the session like a question.
resolve_prompt does the host check and prompts/get for both the CLI and the HTTP service.
"""

import json
import logging
import shlex
from dataclasses import dataclass

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from assistant.mcp_client import PromptMessage, PromptSpec, PromptUnavailableError

log = logging.getLogger(__name__)

LIST_COMMAND = "/prompts"
PROMPT_COMMAND = "/prompt"
USAGE = "Uso: /prompt nome chiave=valore (valori con spazi tra virgolette doppie)."
LIST_HINT = "Scrivi /prompts per l'elenco dei prompt."


@dataclass(frozen=True)
class CommandResult:
    """What the terminal does after a command: show `output` or send `messages` to the graph."""

    output: str | None = None
    messages: list[BaseMessage] | None = None


class CommandSyntaxError(ValueError):
    """The text of /prompt is not in the form `nome chiave=valore …`."""


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _quoted(names) -> str:
    return ", ".join(f"'{name}'" for name in names)


def _listed(names) -> str:
    return ", ".join(names) or "nessuno"


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


def parse_prompt_command(text: str) -> tuple[str, dict[str, str]]:
    """Name and arguments from the text after /prompt.

    Words are separated by spaces; double quotes keep spaces and "=" in a value; the apostrophe
    and "#" are ordinary characters; there is no escape character.
    """
    lexer = shlex.shlex(text, posix=True)
    lexer.whitespace_split = True
    lexer.quotes = '"'
    lexer.escape = ""
    lexer.commenters = ""
    try:
        words = list(lexer)
    except ValueError as error:  # "No closing quotation"
        raise CommandSyntaxError("virgolette non chiuse") from error
    if not words or not words[0]:
        raise CommandSyntaxError("manca il nome del prompt")
    name, arguments = words[0], {}
    for word in words[1:]:
        key, equals, value = word.partition("=")
        if not equals or not key:
            raise CommandSyntaxError(f"argomento non nella forma chiave=valore: '{word}'")
        if key in arguments:
            raise CommandSyntaxError(f"argomento ripetuto: '{key}'")
        if not value:
            raise CommandSyntaxError(f"argomento senza valore: '{key}'")
        arguments[key] = value
    return name, arguments


def check_request(specs: list[PromptSpec], name: str, arguments: dict[str, str]) -> str | None:
    """Why the request does not match prompts/list, or None if it does."""
    by_name = {spec.name: spec for spec in specs}
    if name not in by_name:
        return f"prompt sconosciuto: '{name}' (disponibili: {_listed(by_name)})"
    declared = [argument.name for argument in by_name[name].arguments]
    unknown = [key for key in arguments if key not in declared]
    if unknown:
        return (
            f"argomenti sconosciuti per '{name}': {_quoted(unknown)} "
            f"(attesi: {_listed(declared)})"
        )
    missing = [
        argument.name for argument in by_name[name].arguments
        if argument.required and argument.name not in arguments
    ]
    if missing:
        return f"argomenti obbligatori mancanti per '{name}': {_quoted(missing)}"
    return None


class PromptRequestError(Exception):
    """A prompt request that cannot open a turn; the text is for the user."""


class PromptRejectedError(PromptRequestError):
    """The request does not match prompts/list (the host check of step 5)."""


class PromptListError(PromptRequestError):
    """prompts/list failed."""


class PromptGetError(PromptRequestError):
    """prompts/get failed, or its messages cannot open a turn."""


ROLES = {"user": HumanMessage, "assistant": AIMessage}


def to_messages(received: list[PromptMessage]) -> list[BaseMessage]:
    """Messages for the graph; ValueError if the prompt cannot open a turn."""
    if not received:
        raise ValueError("nessun messaggio")
    for number, message in enumerate(received, start=1):
        if message.role not in ROLES:
            raise ValueError(f"ruolo non ammesso nel messaggio {number}: '{message.role}'")
    if received[-1].role != "user":
        raise ValueError("l'ultimo messaggio non è dell'utente")
    return [ROLES[message.role](message.text) for message in received]


def _specs(client) -> list[PromptSpec]:
    """prompts/list, logged in both outcomes; PromptUnavailableError goes to the caller."""
    try:
        specs = client.list_prompts()
    except PromptUnavailableError as error:
        log.warning("prompts/list status=unavailable error=%s", _json(str(error)))
        raise
    log.info("prompts/list count=%d names=%s", len(specs), ",".join(spec.name for spec in specs))
    return specs


def _rejected(reason: str) -> None:
    log.info("prompt_command status=rejected reason=%s", _json(reason))


def resolve_prompt(client, name: str, arguments: dict[str, str]) -> list[BaseMessage]:
    """Messages of the MCP prompt `name` for the graph, after the host check of step 5.

    Raises PromptRejectedError, PromptListError or PromptGetError; prompts/get is called only
    for a request that matches prompts/list.
    """
    try:
        specs = _specs(client)
    except PromptUnavailableError as error:
        raise PromptListError(f"prompt non disponibili ({error})") from error
    problem = check_request(specs, name, arguments)
    if problem:
        _rejected(problem)
        raise PromptRejectedError(problem)

    request = f"prompts/get name={name} arguments={_json(arguments)}"
    try:
        received = client.get_prompt(name, arguments)
    except PromptUnavailableError as error:
        log.warning("%s status=unavailable error=%s", request, _json(str(error)))
        raise PromptGetError(f"il prompt '{name}' non è disponibile ({error})") from error
    log.info("%s status=ok messages=%d", request, len(received))
    for number, message in enumerate(received, start=1):
        log.info(
            "prompts/get name=%s message=%d/%d role=%s text=%s",
            name, number, len(received), message.role, _json(message.text),
        )
    try:
        return to_messages(received)
    except ValueError as error:
        log.warning("prompt_command status=unusable name=%s reason=%s", name, _json(str(error)))
        raise PromptGetError(f"il prompt '{name}' non è utilizzabile ({error})") from error


class PromptCommands:
    """Handles the commands of the CLI with the MCP client of the session."""

    def __init__(self, client):
        self._client = client

    def handle(self, text: str) -> CommandResult:
        """`text` starts with "/"; the command word ignores case."""
        word, *rest = text.split(maxsplit=1)
        if word.lower() == LIST_COMMAND:
            if rest:
                return self._rejected("il comando /prompts non ha argomenti")
            return self._list()
        if word.lower() == PROMPT_COMMAND:
            return self._prompt(rest[0] if rest else "")
        return CommandResult(f"Comando sconosciuto: '{word}'. {LIST_HINT}")

    def _list(self) -> CommandResult:
        try:
            specs = _specs(self._client)
        except PromptUnavailableError as error:
            return CommandResult(f"Errore: prompt non disponibili ({error}).")
        return CommandResult(format_prompts(specs))

    def _prompt(self, text: str) -> CommandResult:
        try:
            name, arguments = parse_prompt_command(text)
        except CommandSyntaxError as error:
            return self._rejected(str(error), USAGE)
        try:
            return CommandResult(messages=resolve_prompt(self._client, name, arguments))
        except PromptRejectedError as error:  # already logged by resolve_prompt
            return CommandResult(f"Errore nel comando: {error}. {LIST_HINT}")
        except PromptRequestError as error:
            return CommandResult(f"Errore: {error}.")

    @staticmethod
    def _rejected(reason: str, hint: str = "") -> CommandResult:
        _rejected(reason)
        return CommandResult(f"Errore nel comando: {reason}. {hint}".rstrip())
