"""The CLI, a client of the agent service: configuration → logging → GET /status → terminal with
the prompt commands. History and summary of the conversation live in the CLI (RemoteSession);
graph, MCP server and models live in the service (`python -m assistant.service`)."""

import os
import sys
from collections.abc import Mapping

from assistant.api_client import AgentClient, AgentError, RemoteSession
from assistant.commands import PromptCommands
from assistant.config import ConfigError, configure_logging, load_client_config
from assistant.terminal import run

SERVICE_HINT = "Avvia il servizio con: python -m assistant.service"
COMPONENTS = (("mcp", "server MCP"), ("model", "modello"))


def main(env: Mapping[str, str] = os.environ) -> int:
    try:
        config = load_client_config(env)
    except ConfigError as error:
        print(f"Configurazione non valida: {error}", file=sys.stderr)
        return 1
    configure_logging(config.log_level)

    with AgentClient(config.agent_url) as agent:
        try:
            status = agent.status()
        except AgentError as error:
            message = f"Agente non disponibile: {error.phrase}."
            if error.code == "agent_unreachable":
                message += f" {SERVICE_HINT}"
            print(message, file=sys.stderr)
            return 1
        for key, name in COMPONENTS:  # the conversation opens anyway: they may come back
            component = status[key]
            if component["status"] != "ok":
                print(f"Attenzione: {name} non disponibile ({component['detail']}).")
        print(
            f"Assistente del laboratorio — agente su {config.agent_url}, "
            f"modello {status['model']['id']}. "
            "Scrivi /prompts per i prompt disponibili, 'esci' per uscire."
        )
        run(RemoteSession(agent), commands=PromptCommands(agent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
