"""User preferences (lesson 6, step 4): file read by the MCP server."""

import json

import pytest

from assistant.config import DEFAULT_PREFERENCES_FILE
from assistant.preferences import PREFERENCES_URI, read_preferences_file

DEFAULTS = {"language": "italiano", "timezone": "Europe/Rome", "style": "sintetico"}


def test_uri():
    assert PREFERENCES_URI == "utente://preferenze"


def test_example_file_has_the_defaults():
    assert json.loads(read_preferences_file(DEFAULT_PREFERENCES_FILE)) == DEFAULTS


def test_result_is_normalized_json_on_one_line(tmp_path):
    f = tmp_path / "p.json"
    f.write_text('{\n  "language": "français",\n  "style": "dettagliato"\n}', encoding="utf-8")
    assert read_preferences_file(f) == '{"language": "français", "style": "dettagliato"}'


def test_bom_is_accepted(tmp_path):
    f = tmp_path / "p.json"
    f.write_text(json.dumps(DEFAULTS), encoding="utf-8-sig")
    assert json.loads(read_preferences_file(f)) == DEFAULTS


def test_missing_file(tmp_path):
    missing = tmp_path / "nessuno.json"
    with pytest.raises(ValueError) as e:
        read_preferences_file(missing)
    assert str(e.value).startswith(f"File delle preferenze non leggibile: '{missing}' (")


def test_directory_is_not_readable(tmp_path):
    with pytest.raises(ValueError, match="non leggibile"):
        read_preferences_file(tmp_path)


def test_invalid_json(tmp_path):
    f = tmp_path / "p.json"
    f.write_text("{language: italiano", encoding="utf-8")
    with pytest.raises(ValueError) as e:
        read_preferences_file(f)
    assert str(e.value).startswith(f"File delle preferenze non valido: '{f}' (")


def test_not_utf8(tmp_path):
    f = tmp_path / "p.json"
    f.write_bytes('{"language": "français"}'.encode("cp1252"))
    with pytest.raises(ValueError, match="non leggibile"):  # as SCOPE_FILE
        read_preferences_file(f)


@pytest.mark.parametrize("content", ['["italiano"]', '"italiano"', "null", "3"])
def test_value_must_be_an_object(tmp_path, content):
    f = tmp_path / "p.json"
    f.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError) as e:
        read_preferences_file(f)
    assert str(e.value) == f"File delle preferenze non valido: '{f}' (serve un oggetto JSON)."
