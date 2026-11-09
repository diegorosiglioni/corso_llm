"""Startup: configuration → logging → model → graph → session → terminal."""

import logging
import os
import sys
from collections.abc import Mapping

from assistant.config import ConfigError, load_config
from assistant.graph import build_graph
from assistant.model import create_model
from assistant.session import Session
from assistant.terminal import run
from assistant.tools import create_current_time_tool


def main(env: Mapping[str, str] = os.environ) -> int:
    try:
        config = load_config(env)
    except ConfigError as error:
        print(f"Configurazione non valida: {error}", file=sys.stderr)
        return 1

    logging.basicConfig(
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=config.log_level,
    )
    if config.log_level != "DEBUG":
        for library in ("httpx", "httpx2", "openai"):  # openai 3.x uses httpx2
            logging.getLogger(library).setLevel(logging.WARNING)

    tools = [create_current_time_tool()]
    model = create_model(config, tools)
    session = Session(build_graph(model, tools, config.max_steps))
    print(
        f"Assistente del laboratorio — modello {config.model} su {config.base_url}. "
        "Scrivi 'esci' per uscire."
    )
    run(session)
    return 0


if __name__ == "__main__":
    sys.exit(main())
