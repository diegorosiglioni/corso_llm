"""Terminal interface: reads the questions and shows the answers."""

import logging

import openai

log = logging.getLogger(__name__)


def run(session, read=input, write=print, commands=None) -> None:
    """Conversation loop; ends with 'esci', end of input (EOF) or Ctrl+C.

    Text that starts with "/" is a command: it goes to `commands.handle`, never to the model as
    text. A command that returns messages (an MCP prompt) sends them to the session as a turn.
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
                if result.messages:
                    write("Assistente> " + session.send_messages(result.messages))
                continue
            write("Assistente> " + session.send(text))
        except (EOFError, KeyboardInterrupt):
            break
        except openai.APIError as error:
            log.debug("Errore da LM Studio", exc_info=error)
            write(f"Errore: LM Studio non ha risposto correttamente ({error}). Riprova.")
    write("Arrivederci!")
