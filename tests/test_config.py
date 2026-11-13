from pathlib import Path

import pytest

import assistant.config
from assistant.config import DEFAULT_SCOPE_FILE, Config, ConfigError, load_config

VALID = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "google/gemma-4-e2b"}

DEFAULT_SCOPE = Path(DEFAULT_SCOPE_FILE).read_text(encoding="utf-8").strip()


def error(env) -> str:
    with pytest.raises(ConfigError) as e:
        load_config(env)
    return str(e.value)


def test_valid_values_and_defaults():
    assert load_config(VALID) == Config(
        "http://localhost:1234/v1", "google/gemma-4-e2b", 5, "INFO", "data/notes.sqlite3",
        DEFAULT_SCOPE_FILE, DEFAULT_SCOPE,
    )


def test_notes_db_default_and_override():
    assert load_config(VALID).notes_db == "data/notes.sqlite3"
    assert load_config({**VALID, "NOTES_DB": " x.db "}).notes_db == "x.db"
    assert load_config({**VALID, "NOTES_DB": ""}).notes_db == "data/notes.sqlite3"


def test_optional_values():
    c = load_config({**VALID, "MAX_STEPS": " 3 ", "LOG_LEVEL": "debug"})
    assert (c.max_steps, c.log_level) == (3, "DEBUG")


def test_empty_optional_values_use_defaults():
    c = load_config({**VALID, "MAX_STEPS": "", "LOG_LEVEL": "  "})
    assert (c.max_steps, c.log_level) == (5, "INFO")


def test_spaces_are_stripped():
    c = load_config({"LMSTUDIO_BASE_URL": " http://h:1/v1 ", "LMSTUDIO_MODEL": " m "})
    assert (c.base_url, c.model) == ("http://h:1/v1", "m")


def test_required_missing():
    assert error({}) == "Manca LMSTUDIO_BASE_URL. Manca LMSTUDIO_MODEL."


def test_required_blank():
    assert error({**VALID, "LMSTUDIO_MODEL": "   "}) == "Manca LMSTUDIO_MODEL."


def test_url_without_scheme():
    assert error({**VALID, "LMSTUDIO_BASE_URL": "localhost:1234"}) == (
        "LMSTUDIO_BASE_URL deve iniziare con http:// o https://, ricevuto 'localhost:1234'."
    )


def test_https_url_accepted():
    assert load_config({**VALID, "LMSTUDIO_BASE_URL": "https://h/v1"}).base_url == "https://h/v1"


@pytest.mark.parametrize("value", ["zero", "0", "-1", "2.5"])
def test_invalid_max_steps(value):
    assert error({**VALID, "MAX_STEPS": value}) == (
        f"MAX_STEPS deve essere un intero ≥ 1, ricevuto '{value}'."
    )


def test_invalid_log_level():
    assert error({**VALID, "LOG_LEVEL": "TRACE"}) == (
        "LOG_LEVEL deve essere uno tra DEBUG, INFO, WARNING, ERROR, ricevuto 'TRACE'."
    )


def test_all_problems_in_one_message():
    assert error({"MAX_STEPS": "zero"}) == (
        "Manca LMSTUDIO_BASE_URL. Manca LMSTUDIO_MODEL. "
        "MAX_STEPS deve essere un intero ≥ 1, ricevuto 'zero'."
    )


# --- scope (lesson 6, step 1) ---

def test_default_scope_is_the_package_file():
    c = load_config(VALID)
    assert Path(c.scope_file) == Path(assistant.config.__file__).parent / "data" / "scope.txt"
    assert c.scope.startswith("L'assistente del laboratorio si occupa solo di:")
    assert c.scope.endswith("Ogni altra richiesta è fuori ambito.")


def test_scope_file_override(tmp_path):
    f = tmp_path / "ambito.txt"
    f.write_text("  Solo calcoli.\n", encoding="utf-8")
    c = load_config({**VALID, "SCOPE_FILE": f" {f} "})
    assert (c.scope_file, c.scope) == (str(f), "Solo calcoli.")


def test_blank_scope_file_uses_default():
    assert load_config({**VALID, "SCOPE_FILE": "  "}).scope_file == DEFAULT_SCOPE_FILE


def test_missing_scope_file(tmp_path):
    missing = tmp_path / "manca.txt"
    assert f"SCOPE_FILE non leggibile: '{missing}' (" in error({**VALID, "SCOPE_FILE": str(missing)})


def test_scope_file_is_a_directory(tmp_path):
    assert f"SCOPE_FILE non leggibile: '{tmp_path}' (" in error(
        {**VALID, "SCOPE_FILE": str(tmp_path)}
    )


def test_empty_scope_file(tmp_path):
    f = tmp_path / "vuoto.txt"
    f.write_text("  \n", encoding="utf-8")
    assert error({**VALID, "SCOPE_FILE": str(f)}) == f"SCOPE_FILE vuoto: '{f}'."


def test_scope_file_with_bom(tmp_path):
    f = tmp_path / "bom.txt"
    f.write_bytes(b"\xef\xbb\xbfSolo calcoli.")
    assert load_config({**VALID, "SCOPE_FILE": str(f)}).scope == "Solo calcoli."


def test_scope_problem_listed_with_the_others(tmp_path):
    missing = tmp_path / "manca.txt"
    message = error({"LMSTUDIO_BASE_URL": "http://h/v1", "SCOPE_FILE": str(missing)})
    assert message.startswith("Manca LMSTUDIO_MODEL. SCOPE_FILE non leggibile: ")


# --- reviewer (lesson 6, step 2) ---

def test_max_reviews_default_and_override():
    assert load_config(VALID).max_reviews == 2
    assert load_config({**VALID, "MAX_REVIEWS": " 3 "}).max_reviews == 3
    assert load_config({**VALID, "MAX_REVIEWS": "  "}).max_reviews == 2


@pytest.mark.parametrize("value", ["abc", "0", "-1", "2.5"])
def test_invalid_max_reviews(value):
    assert error({**VALID, "MAX_REVIEWS": value}) == (
        f"MAX_REVIEWS deve essere un intero ≥ 1, ricevuto '{value}'."
    )


def test_max_reviews_problem_listed_with_the_others():
    assert error({"MAX_REVIEWS": "0"}) == (
        "Manca LMSTUDIO_BASE_URL. Manca LMSTUDIO_MODEL. "
        "MAX_REVIEWS deve essere un intero ≥ 1, ricevuto '0'."
    )


# --- summary (lesson 6, step 3) ---

def test_summary_thresholds_default_and_override():
    config = load_config(VALID)
    assert (config.summary_max_messages, config.summary_keep_messages) == (20, 6)
    config = load_config({**VALID, "SUMMARY_MAX_MESSAGES": " 4 ", "SUMMARY_KEEP_MESSAGES": "2"})
    assert (config.summary_max_messages, config.summary_keep_messages) == (4, 2)


@pytest.mark.parametrize("name", ["SUMMARY_MAX_MESSAGES", "SUMMARY_KEEP_MESSAGES"])
@pytest.mark.parametrize("value", ["abc", "0", "-1", "2.5"])
def test_invalid_summary_threshold(name, value):
    assert error({**VALID, name: value}) == (
        f"{name} deve essere un intero ≥ 1, ricevuto '{value}'."
    )


@pytest.mark.parametrize(("env", "keep", "maximum"), [
    ({"SUMMARY_KEEP_MESSAGES": "20"}, 20, 20),
    ({"SUMMARY_MAX_MESSAGES": "4", "SUMMARY_KEEP_MESSAGES": "5"}, 5, 4),
    ({"SUMMARY_MAX_MESSAGES": "3"}, 6, 3),
])
def test_keep_must_be_below_max(env, keep, maximum):
    assert error({**VALID, **env}) == (
        "SUMMARY_KEEP_MESSAGES deve essere minore di SUMMARY_MAX_MESSAGES, "
        f"ricevuti '{keep}' e '{maximum}'."
    )


def test_summary_problems_listed_with_the_others():
    assert error({"SUMMARY_MAX_MESSAGES": "0", "SUMMARY_KEEP_MESSAGES": "x"}) == (
        "Manca LMSTUDIO_BASE_URL. Manca LMSTUDIO_MODEL. "
        "SUMMARY_MAX_MESSAGES deve essere un intero ≥ 1, ricevuto '0'. "
        "SUMMARY_KEEP_MESSAGES deve essere un intero ≥ 1, ricevuto 'x'."
    )
