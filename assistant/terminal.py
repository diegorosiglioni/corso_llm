"""Terminal interface: reads the questions and shows the answers."""

import logging

from assistant.api_client import AgentError
from assistant.commands import LIST_HINT

log = logging.getLogger(__name__)

PROMPT_REJECTED = "prompt_rejected"  # error code of the host check, done by the service


def run(session, read=input, write=print, commands=None) -> None:
    """Conversation loop; ends with 'esci', end of input (EOF) or Ctrl+C.

    Text that starts with "/" is a command: it goes to `commands.handle`, never to the model as
    text. A command that returns an MCP prompt opens a turn with it (`session.send_prompt`).
    An AgentError is shown and the conversation goes on with the history unchanged.
    """
    while True:
        try:
            text = read("Tu> ").strip()
            if not text:
                continue
            if text.lower() == "esci":
                break
            if text.startswith("/"):
                if commands is None:
                    write("Comandi non disponibili.")
                    continue
                result = commands.handle(text)
                if result.output is not None:
                    write(result.output)
                if result.prompt is not None:
                    write("Assistente> " + session.send_prompt(*result.prompt))
                continue
            write("Assistente> " + session.send(text))
        except (EOFError, KeyboardInterrupt):
            break
        except AgentError as error:
            log.debug("Errore dall'agente: code=%s", error.code, exc_info=error)
            if error.code == PROMPT_REJECTED:
                write(f"Errore nel comando: {error.phrase}. {LIST_HINT}")
            else:
                write(f"Errore: {error.phrase}. Riprova.")
    write("Arrivederci!")
