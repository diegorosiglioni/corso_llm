"""Terminal interface: reads the questions and shows the answers."""

import logging

import openai

log = logging.getLogger(__name__)


def run(session, read=input, write=print) -> None:
    """Conversation loop; ends with 'esci', end of input (EOF) or Ctrl+C."""
    while True:
        try:
            text = read("Tu> ").strip()
            if not text:
                continue
            if text.lower() == "esci":
                break
            write("Assistente> " + session.send(text))
        except (EOFError, KeyboardInterrupt):
            break
        except openai.APIError as error:
            log.debug("Errore da LM Studio", exc_info=error)
            write(f"Errore: LM Studio non ha risposto correttamente ({error}). Riprova.")
    write("Arrivederci!")
