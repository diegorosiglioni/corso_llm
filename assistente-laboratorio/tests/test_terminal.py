import pytest

from assistant.terminal import run
from conftest import lm_studio_error


def inputs(*lines):
    """Simulates input(): returns the lines in order, raises the exceptions, then EOFError."""
    queue = list(lines)
    prompts = []

    def read(prompt):
        prompts.append(prompt)
        if not queue:
            raise EOFError
        line = queue.pop(0)
        if isinstance(line, BaseException):
            raise line
        return line

    read.prompts = prompts
    return read


class FakeSession:
    def __init__(self, *outcomes):
        self._outcomes = list(outcomes)
        self.questions = []

    def send(self, text):
        self.questions.append(text)
        outcome = self._outcomes.pop(0) if self._outcomes else f"risposta a {text}"
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def execute(session, *lines):
    outputs = []
    read = inputs(*lines)
    run(session, read=read, write=outputs.append)
    return outputs, read


def test_question_and_answer():
    outputs, read = execute(FakeSession(), "ciao")
    assert outputs == ["Assistente> risposta a ciao", "Arrivederci!"]
    assert set(read.prompts) == {"Tu> "}


@pytest.mark.parametrize("command", ["esci", "ESCI", "  Esci  "])
def test_exit(command):
    session = FakeSession()
    outputs, _ = execute(session, command, "non letta")
    assert outputs == ["Arrivederci!"]
    assert session.questions == []


def test_eof():
    assert execute(FakeSession())[0] == ["Arrivederci!"]


def test_ctrl_c_during_input():
    assert execute(FakeSession(), KeyboardInterrupt())[0] == ["Arrivederci!"]


def test_ctrl_c_while_waiting_for_the_model():
    outputs, _ = execute(FakeSession(KeyboardInterrupt()), "che ore sono?", "non letta")
    assert outputs == ["Arrivederci!"]


def test_empty_input_ignored():
    session = FakeSession()
    outputs, _ = execute(session, "", "   ", "esci")
    assert session.questions == []
    assert outputs == ["Arrivederci!"]


def test_text_sent_without_spaces():
    session = FakeSession()
    execute(session, "  ciao  ")
    assert session.questions == ["ciao"]


def test_lm_studio_error_and_continue():
    session = FakeSession(lm_studio_error(), "eccomi")
    outputs, _ = execute(session, "prima", "seconda")
    assert outputs == [
        "Errore: LM Studio non ha risposto correttamente (Connection error.). Riprova.",
        "Assistente> eccomi",
        "Arrivederci!",
    ]


def test_other_exceptions_not_caught():
    with pytest.raises(RuntimeError):
        execute(FakeSession(RuntimeError("difetto")), "ciao")
