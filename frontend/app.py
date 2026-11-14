"""The front-end service: the static chat page and /config.js with the address of the back-end.

It is not an API (no OpenAPI document): the page talks only to the back-end, directly from the
browser.
"""

import json
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles

from frontend.config import FrontendConfig

STATIC_DIR = Path(__file__).parent / "static"


def config_script(backend_url: str) -> str:
    """The JavaScript that gives the page its configuration (window.APP_CONFIG)."""
    return f"window.APP_CONFIG = {json.dumps({'backendUrl': backend_url})};\n"


def create_app(config: FrontendConfig) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    script = config_script(config.backend_url)

    @app.get("/config.js", include_in_schema=False)
    def config_js() -> Response:
        # no-store: after changing BACKEND_URL a restart is enough, no browser cache in the way
        return Response(
            script, media_type="text/javascript", headers={"Cache-Control": "no-store"}
        )

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app
