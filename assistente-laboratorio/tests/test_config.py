import pytest

from assistant.config import Config, ConfigError, load_config

VALID = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "google/gemma-4-e2b"}


def error(env) -> str:
    with pytest.raises(ConfigError) as e:
        load_config(env)
    return str(e.value)


def test_valid_values_and_defaults():
    c = load_config(VALID)
    assert c == Config("http://localhost:1234/v1", "google/gemma-4-e2b", 5, "INFO")


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
