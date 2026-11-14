import pytest

from assistant.config import ConfigError
from backend.config import BackendConfig, display_url, load_backend_config

URL = "postgresql+psycopg://lab:segreta@localhost:5432/assistente"
VALID = {"DATABASE_URL": URL}


def test_defaults():  # CA-70
    assert load_backend_config(VALID) == BackendConfig(
        database_url=URL,
        agent_url="http://127.0.0.1:8000",
        host="127.0.0.1",
        port=8001,
        log_level="INFO",
    )


def test_values_from_the_environment():
    config = load_backend_config({
        **VALID,
        "AGENT_URL": "http://agent:8000/",
        "BACKEND_HOST": " 0.0.0.0 ",
        "BACKEND_PORT": "9001",
        "LOG_LEVEL": "debug",
    })
    assert (config.agent_url, config.host, config.port, config.log_level) == (
        "http://agent:8000", "0.0.0.0", 9001, "DEBUG"
    )


def test_postgresql_scheme_gets_the_psycopg_driver():  # CA-70
    config = load_backend_config({"DATABASE_URL": "postgresql://lab:segreta@db/assistente"})
    assert config.database_url == "postgresql+psycopg://lab:segreta@db/assistente"


@pytest.mark.parametrize("env", [{}, {"DATABASE_URL": "   "}])
def test_database_url_is_required(env):  # CA-70
    with pytest.raises(ConfigError, match="Manca DATABASE_URL."):
        load_backend_config(env)


@pytest.mark.parametrize(("url", "scheme"), [
    ("sqlite:///chat.sqlite3", "sqlite"),
    ("mysql://lab:segreta@db/assistente", "mysql"),
    ("postgresql+psycopg2://lab:segreta@db/assistente", "postgresql+psycopg2"),
])
def test_other_schemes_are_rejected_without_the_password(url, scheme):  # CA-70
    with pytest.raises(ConfigError) as caught:
        load_backend_config({"DATABASE_URL": url})
    message = str(caught.value)
    assert message == (
        "DATABASE_URL deve iniziare con postgresql:// o postgresql+psycopg://, ricevuto lo schema "
        f"'{scheme}'."
    )
    assert "segreta" not in message


def test_text_without_scheme_is_rejected_without_quoting_it():
    with pytest.raises(ConfigError) as caught:
        load_backend_config({"DATABASE_URL": "lab:segreta@db"})
    assert str(caught.value) == (
        "DATABASE_URL deve iniziare con postgresql:// o postgresql+psycopg://."
    )


def test_unreadable_url_is_rejected_without_quoting_it():
    with pytest.raises(ConfigError) as caught:
        load_backend_config({"DATABASE_URL": "postgresql://lab:segreta@db:porta/assistente"})
    message = str(caught.value)
    assert message.startswith("DATABASE_URL non interpretabile")
    assert "segreta" not in message


@pytest.mark.parametrize("port", ["0", "65536", "abc", "-1"])
def test_invalid_port(port):  # CA-70
    with pytest.raises(ConfigError, match=f"BACKEND_PORT deve essere un intero tra 1 e 65535, "
                                          f"ricevuto '{port}'."):
        load_backend_config({**VALID, "BACKEND_PORT": port})


def test_every_problem_in_one_message():  # CA-70
    with pytest.raises(ConfigError) as caught:
        load_backend_config({
            "AGENT_URL": "agent:8000", "LOG_LEVEL": "molto", "BACKEND_PORT": "x",
        })
    assert str(caught.value) == (
        "Manca DATABASE_URL. "
        "AGENT_URL deve iniziare con http:// o https://, ricevuto 'agent:8000'. "
        "LOG_LEVEL deve essere uno tra DEBUG, INFO, WARNING, ERROR, ricevuto 'molto'. "
        "BACKEND_PORT deve essere un intero tra 1 e 65535, ricevuto 'x'."
    )


def test_display_url_hides_the_password():
    assert display_url(URL) == "postgresql+psycopg://lab:***@localhost:5432/assistente"
    assert display_url("postgresql+psycopg://db/assistente") == "postgresql+psycopg://db/assistente"
