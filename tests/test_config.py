import logging
from pathlib import Path

import pytest

import assistant.config
from assistant.config import (
    DEFAULT_AGENT_URL,
    DEFAULT_PREFERENCES_FILE,
    DEFAULT_SCOPE_FILE,
    QUIET_LIBRARIES,
    ClientConfig,
    Config,
    ConfigError,
    configure_logging,
    load_client_config,
    load_config,
)

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


def test_default_scope_covers_the_mcp_prompts():  # RF-51
    scope = load_config(VALID).scope
    assert (
        "- spiegazioni di concetti di informatica, programmazione e intelligenza artificiale "
        "(per esempio modelli linguistici, agenti, Model Context Protocol);"
    ) in scope.splitlines()
    assert (
        "- l'utente che si presenta o dice qualcosa di sé, le domande su quanto detto in questa "
        "conversazione e i riassunti della conversazione."
    ) in scope.splitlines()


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


# --- preferences (lesson 6, step 4) ---

def test_preferences_file_default_and_override():
    assert load_config(VALID).preferences_file == DEFAULT_PREFERENCES_FILE
    assert Path(DEFAULT_PREFERENCES_FILE) == (
        Path(assistant.config.__file__).parent / "data" / "preferenze.json"
    )
    assert load_config({**VALID, "PREFERENCES_FILE": " p.json "}).preferences_file == "p.json"
    assert load_config({**VALID, "PREFERENCES_FILE": "  "}).preferences_file == (
        DEFAULT_PREFERENCES_FILE
    )


def test_missing_preferences_file_is_not_a_config_error(tmp_path):
    missing = str(tmp_path / "manca.json")
    assert load_config({**VALID, "PREFERENCES_FILE": missing}).preferences_file == missing


# --- HTTP service (lesson 6, step 6) ---

def test_agent_address_default_and_override():
    config = load_config(VALID)
    assert (config.agent_host, config.agent_port) == ("127.0.0.1", 8000)
    config = load_config({**VALID, "AGENT_HOST": " 0.0.0.0 ", "AGENT_PORT": " 8080 "})
    assert (config.agent_host, config.agent_port) == ("0.0.0.0", 8080)
    config = load_config({**VALID, "AGENT_HOST": "  ", "AGENT_PORT": ""})
    assert (config.agent_host, config.agent_port) == ("127.0.0.1", 8000)


@pytest.mark.parametrize("value", ["1", "65535"])
def test_agent_port_limits_accepted(value):
    assert load_config({**VALID, "AGENT_PORT": value}).agent_port == int(value)


@pytest.mark.parametrize("value", ["abc", "0", "-1", "65536", "80.5"])
def test_invalid_agent_port(value):
    assert error({**VALID, "AGENT_PORT": value}) == (
        f"AGENT_PORT deve essere un intero tra 1 e 65535, ricevuto '{value}'."
    )


def test_agent_port_problem_listed_with_the_others():
    assert error({"AGENT_PORT": "0"}) == (
        "Manca LMSTUDIO_BASE_URL. Manca LMSTUDIO_MODEL. "
        "AGENT_PORT deve essere un intero tra 1 e 65535, ricevuto '0'."
    )


# --- configuration of the CLI, a client of the service (step 6, point 5) ---

def client_error(env) -> str:
    with pytest.raises(ConfigError) as e:
        load_client_config(env)
    return str(e.value)


def test_client_defaults_need_no_lm_studio_variables():
    assert load_client_config({}) == ClientConfig("http://127.0.0.1:8000", "INFO")
    assert DEFAULT_AGENT_URL == "http://127.0.0.1:8000"


@pytest.mark.parametrize(("value", "expected"), [
    ("http://agent:8000", "http://agent:8000"),
    (" https://agente.example/ ", "https://agente.example"),
    ("http://127.0.0.1:9000//", "http://127.0.0.1:9000"),
    ("http://[::1]:8000", "http://[::1]:8000"),
    ("http://agent:8000/api/", "http://agent:8000/api"),
    ("", "http://127.0.0.1:8000"),
    ("   ", "http://127.0.0.1:8000"),
])
def test_agent_url(value, expected):
    assert load_client_config({"AGENT_URL": value}).agent_url == expected


@pytest.mark.parametrize("value", [
    "http://[::1", "http://agent:porta", "https://agent:99999", "http://", "http://:8000",
])
def test_malformed_agent_url(value):  # R-B9
    assert client_error({"AGENT_URL": value}) == (
        f"AGENT_URL non è un indirizzo valido, ricevuto '{value}'."
    )


def test_client_log_level():
    assert load_client_config({"LOG_LEVEL": " debug "}).log_level == "DEBUG"


def test_invalid_client_values_listed_together():
    assert client_error({"AGENT_URL": "agent:8000", "LOG_LEVEL": "tanto"}) == (
        "AGENT_URL deve iniziare con http:// o https://, ricevuto 'agent:8000'. "
        "LOG_LEVEL deve essere uno tra DEBUG, INFO, WARNING, ERROR, ricevuto 'tanto'."
    )


def test_client_ignores_the_service_variables():
    env = {"LMSTUDIO_BASE_URL": "x", "AGENT_PORT": "0", "SCOPE_FILE": "manca.txt"}
    assert load_client_config(env) == ClientConfig()


def test_configure_logging_quiets_the_libraries():
    configure_logging("INFO")
    for library in QUIET_LIBRARIES:
        assert logging.getLogger(library).level == logging.WARNING, library
