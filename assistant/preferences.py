"""User preferences (lesson 6, step 4): the MCP resource utente://preferenze.

The server reads the JSON file at every resources/read and only checks that it is an object.
"""

import json
from pathlib import Path

PREFERENCES_URI = "utente://preferenze"


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
