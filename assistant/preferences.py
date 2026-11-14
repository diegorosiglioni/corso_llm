"""User preferences (lesson 6, step 4): the MCP resource utente://preferenze.

The server reads the JSON file at every resources/read and only checks that it is an object.
The host reads the resource once per session, validates each field on its own (a wrong field
falls back to its default without losing the others) and puts a text at the top of the agent's
system prompt.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple
from zoneinfo import available_timezones

log = logging.getLogger(__name__)

PREFERENCES_URI = "utente://preferenze"

MAX_LANGUAGE_LENGTH = 40

STYLES = {
    # Not "in poche frasi": at the top of the prompt it made the model answer calculations
    # without calling calculate (0/8 in a direct test with gemma-4-e2b, 8/8 without it).
    "sintetico": "breve ed essenziale",
    "dettagliato": "completo, con spiegazioni ed esempi quando servono",
}

_VALID_TIMEZONES = available_timezones()  # the same exact check as the clock tool


@dataclass(frozen=True)
class Preferences:
    language: str = "italiano"
    timezone: str = "Europe/Rome"
    style: str = "sintetico"


DEFAULT_PREFERENCES = Preferences()


class FieldProblem(NamedTuple):
    """A field that took its default: `problem` is "missing" or "invalid"."""

    field: str
    problem: str
    value: object = None


def read_preferences_file(path: str | Path) -> str:
    """The file as normalized one-line JSON; ValueError if unreadable or not a JSON object."""
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        reason = getattr(error, "strerror", None) or str(error)
        raise ValueError(f"File delle preferenze non leggibile: '{path}' ({reason}).") from None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"File delle preferenze non valido: '{path}' ({error}).") from None
    if not isinstance(data, dict):
        raise ValueError(f"File delle preferenze non valido: '{path}' (serve un oggetto JSON).")
    return json.dumps(data, ensure_ascii=False)


def _language(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > MAX_LANGUAGE_LENGTH or "\n" in value or "\r" in value:
        return None
    return value


def _timezone(value: object) -> str | None:
    return value if isinstance(value, str) and value in _VALID_TIMEZONES else None


def _style(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if value in STYLES else None


_VALIDATORS = {"language": _language, "timezone": _timezone, "style": _style}


def parse_preferences(text: str) -> tuple[Preferences, list[FieldProblem]]:
    """Validated preferences and the fields that took their default.

    ValueError if the text is not a JSON object; unknown keys are ignored.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"preferenze non in formato JSON ({error})") from None
    if not isinstance(data, dict):
        raise ValueError("le preferenze non sono un oggetto JSON")
    values, problems = {}, []
    for field, validate in _VALIDATORS.items():
        if field not in data:
            problems.append(FieldProblem(field, "missing"))
            continue
        valid = validate(data[field])
        if valid is None:
            problems.append(FieldProblem(field, "invalid", data[field]))
        else:
            values[field] = valid
    return Preferences(**values), problems


def preferences_prompt(p: Preferences) -> str:
    """Italian text with the preferences, for the top of the agent's system prompt."""
    return (
        f"Preferenze dell'utente (resource {PREFERENCES_URI}):\n"
        f"- lingua delle risposte: {p.language};\n"
        f"- fuso orario predefinito: {p.timezone}; se l'utente chiede data o ora senza indicare "
        "un luogo o un fuso, usa get_current_time con questo fuso, senza chiederlo;\n"
        f"- stile delle risposte: {p.style} ({STYLES[p.style]})."
    )


def with_preferences(prompt: str, preferences_text: str) -> str:
    """The preferences at the top of the prompt, when there are any."""
    if not preferences_text:
        return prompt
    return f"{preferences_text}\n\n{prompt}"


def _value(field: str, value: object) -> str:
    """A value for the log: language as JSON (it may contain spaces), the others as they are."""
    return json.dumps(value, ensure_ascii=False) if field == "language" else str(value)


def _values(p: Preferences) -> str:
    return " ".join(f"{field}={_value(field, getattr(p, field))}" for field in _VALIDATORS)


def load_preferences(client) -> Preferences:
    """Reads the resource once and validates it; never fails: defaults when unavailable."""
    # Imported here: the MCP server imports this module and must not load the client.
    from assistant.mcp_client import ResourceUnavailableError

    prefix = f"resources/read uri={PREFERENCES_URI}"
    try:
        preferences, problems = parse_preferences(client.read_resource(PREFERENCES_URI))
    except (ResourceUnavailableError, ValueError) as error:
        log.warning(
            "%s status=unavailable error=%s fallback=defaults %s",
            prefix, json.dumps(str(error), ensure_ascii=False), _values(DEFAULT_PREFERENCES),
        )
        return DEFAULT_PREFERENCES
    for problem in problems:
        value = (
            "" if problem.problem == "missing"
            else f" value={json.dumps(problem.value, ensure_ascii=False)}"
        )
        log.warning(
            "%s field=%s problem=%s%s fallback=%s",
            prefix, problem.field, problem.problem, value,
            _value(problem.field, getattr(DEFAULT_PREFERENCES, problem.field)),
        )
    status = "partial" if problems else "ok"
    log.info("%s status=%s %s", prefix, status, _values(preferences))
    return preferences
