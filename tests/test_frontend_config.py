import pytest

from assistant.config import ConfigError
from frontend.config import FrontendConfig, load_frontend_config


def test_defaults():  # CA-79
    assert load_frontend_config({}) == FrontendConfig(
        backend_url="http://127.0.0.1:8001", host="127.0.0.1", port=8080, log_level="INFO"
    )


def test_values_from_the_environment():  # CA-79
    config = load_frontend_config({
        "BACKEND_URL": " https://chat.example:9443/ ",
        "FRONTEND_HOST": " 0.0.0.0 ",
        "FRONTEND_PORT": "9080",
        "LOG_LEVEL": "debug",
    })
    assert config == FrontendConfig("https://chat.example:9443", "0.0.0.0", 9080, "DEBUG")


@pytest.mark.parametrize("value", ["  ", ""])
def test_empty_values_take_the_defaults(value):
    config = load_frontend_config(
        {"BACKEND_URL": value, "FRONTEND_HOST": value, "FRONTEND_PORT": value}
    )
    assert config == FrontendConfig()


@pytest.mark.parametrize("url", ["127.0.0.1:8001", "ftp://backend", "backend"])
def test_backend_url_must_be_http(url):  # CA-79
    with pytest.raises(ConfigError) as caught:
        load_frontend_config({"BACKEND_URL": url})
    assert str(caught.value) == (
        f"BACKEND_URL deve iniziare con http:// o https://, ricevuto '{url}'."
    )


@pytest.mark.parametrize("port", ["0", "65536", "abc", "-1", "80.5"])
def test_invalid_port(port):  # CA-79
    with pytest.raises(ConfigError) as caught:
        load_frontend_config({"FRONTEND_PORT": port})
    assert str(caught.value) == (
        f"FRONTEND_PORT deve essere un intero tra 1 e 65535, ricevuto '{port}'."
    )


def test_every_problem_in_one_message():  # CA-79
    with pytest.raises(ConfigError) as caught:
        load_frontend_config({"BACKEND_URL": "backend", "FRONTEND_PORT": "x", "LOG_LEVEL": "tanto"})
    assert str(caught.value) == (
        "BACKEND_URL deve iniziare con http:// o https://, ricevuto 'backend'. "
        "FRONTEND_PORT deve essere un intero tra 1 e 65535, ricevuto 'x'. "
        "LOG_LEVEL deve essere uno tra DEBUG, INFO, WARNING, ERROR, ricevuto 'tanto'."
    )
