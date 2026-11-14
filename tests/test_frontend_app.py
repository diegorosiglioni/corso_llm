import json
import re

import pytest
from fastapi.testclient import TestClient

from frontend.app import STATIC_DIR, config_script, create_app
from frontend.config import FrontendConfig


@pytest.fixture
def http() -> TestClient:
    return TestClient(create_app(FrontendConfig(backend_url="http://backend.example:8001")))


def test_root_is_the_page(http):  # CA-80
    response = http.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    page = response.text
    assert '<html lang="it">' in page
    assert '<script src="/config.js"></script>' in page
    assert '<script type="module" src="/app.js"></script>' in page
    assert '<link rel="stylesheet" href="/style.css">' in page
    assert page.index("/config.js") < page.index("/app.js")  # configuration before the app


def test_config_js_has_the_configured_backend(http):  # CA-80
    response = http.get("/config.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/javascript")
    assert response.headers["cache-control"] == "no-store"
    assert response.text == 'window.APP_CONFIG = {"backendUrl": "http://backend.example:8001"};\n'


def test_config_script_is_valid_json_for_any_address():
    url = 'http://x/"</script><script>alert(1)</script>'
    script = config_script(url)
    match = re.fullmatch(r"window\.APP_CONFIG = (.*);\n", script)
    assert json.loads(match.group(1)) == {"backendUrl": url}


@pytest.mark.parametrize(("path", "kind"), [
    ("/app.js", "text/javascript"),
    ("/api.js", "text/javascript"),
    ("/texts.js", "text/javascript"),
    ("/style.css", "text/css"),
    ("/index.html", "text/html"),
])
def test_static_files_with_their_type(http, path, kind):  # CA-80
    response = http.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(kind)
    assert response.content == (STATIC_DIR / path.lstrip("/")).read_bytes()


@pytest.mark.parametrize("path", ["/missing.js", "/backend-openapi.json", "/../config.py"])
def test_missing_file_is_404(http, path):  # CA-80
    assert http.get(path).status_code == 404


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_no_api_documentation(http, path):  # CA-80
    assert http.get(path).status_code == 404


def test_page_reads_only_the_configured_address():
    """The JavaScript knows neither the agent nor the database: only window.APP_CONFIG."""
    for name in ("app.js", "api.js", "texts.js"):
        text = (STATIC_DIR / name).read_text(encoding="utf-8")
        assert ":8000" not in text and ":8001" not in text
        assert "postgres" not in text.lower()
