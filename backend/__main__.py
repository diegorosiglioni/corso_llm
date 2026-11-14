"""Startup of the back-end: configuration → logging → database (tables created if missing) →
agent client → FastAPI app served by uvicorn.

Start with `python -m backend`; address from BACKEND_HOST and BACKEND_PORT. A database that cannot
be reached stops the startup; an agent switched off does not (every message sent reports it).
"""

import logging
import os
import sys
from collections.abc import Mapping

import uvicorn
from sqlalchemy.exc import OperationalError

from assistant.api_client import AgentClient
from assistant.config import ConfigError, configure_logging
from backend.api import create_app
from backend.config import display_url, load_backend_config
from backend.db import create_db_engine, init_db
from backend.store import ChatStore

log = logging.getLogger("backend.service")  # not "__main__" with python -m


def main(env: Mapping[str, str] = os.environ) -> int:
    try:
        config = load_backend_config(env)
    except ConfigError as error:
        print(f"Configurazione non valida: {error}", file=sys.stderr)
        return 1
    configure_logging(config.log_level)

    engine = create_db_engine(config.database_url)
    try:
        init_db(engine)
    except OperationalError as error:  # the driver's message has no password
        print(f"Database non raggiungibile: {str(error.orig).strip()}", file=sys.stderr)
        engine.dispose()
        return 1

    try:
        with AgentClient(config.agent_url) as agent:
            app = create_app(
                store=ChatStore(engine), agent=agent, cors_origins=config.cors_origins
            )
            log.info(
                "backend listening=http://%s:%d docs=/docs agent_url=%s database=%s "
                "cors_origins=%s",
                config.host, config.port, config.agent_url, display_url(config.database_url),
                ",".join(config.cors_origins),
            )
            uvicorn.run(
                app, host=config.host, port=config.port, access_log=False, log_config=None
            )
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
