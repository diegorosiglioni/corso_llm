"""Startup of the front-end: configuration → logging → static page served by uvicorn.

Start with `python -m frontend`; address from FRONTEND_HOST and FRONTEND_PORT, back-end from
BACKEND_URL. A back-end switched off does not stop the startup: the page reports it.
"""

import logging
import os
import sys
from collections.abc import Mapping

import uvicorn

from assistant.config import ConfigError, configure_logging
from frontend.app import create_app
from frontend.config import load_frontend_config

log = logging.getLogger("frontend.service")  # not "__main__" with python -m


def main(env: Mapping[str, str] = os.environ) -> int:
    try:
        config = load_frontend_config(env)
    except ConfigError as error:
        print(f"Configurazione non valida: {error}", file=sys.stderr)
        return 1
    configure_logging(config.log_level)

    app = create_app(config)
    log.info(
        "frontend listening=http://%s:%d backend_url=%s",
        config.host, config.port, config.backend_url,
    )
    uvicorn.run(app, host=config.host, port=config.port, access_log=False, log_config=None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
