import pytest
from langchain_core.messages import HumanMessage

from assistant.commands import CommandResult, PromptCommands
from assistant.mcp_client import PromptArgument, PromptSpec
from assistant.session import Session
from assistant.terminal import run
from conftest import MCP_SPECS, FakeMcpClient, FakeModel, fake_graph, lm_studio_error


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
        self.message_lists = []

    def send(self, text):
        self.questions.append(text)
        return self._next(f"risposta a {text}")

    def send_messages(self, messages):
        self.message_lists.append(list(messages))
        return self._next(f"risposta a {messages[-1].content}")

    def _next(self, default):
        outcome = self._outcomes.pop(0) if self._outcomes else default
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeCommands:
    """Records the commands and answers with the scripted results (text → output only)."""

    def __init__(self, *results):
        self._results = list(results)
        self.texts = []

    def handle(self, text):
        self.texts.append(text)
        result = self._results.pop(0)
        return result if isinstance(result, CommandResult) else CommandResult(result)


def execute(session, *lines, commands=None):
    outputs = []
    read = inputs(*lines)
    run(session, read=read, write=outputs.append, commands=commands)
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


# --- commands (lesson 6, step 5) ---

def test_command_goes_to_the_commands_not_to_the_model():  # CA-56
    session, commands = FakeSession(), FakeCommands("elenco")
    outputs, _ = execute(session, "  /prompts  ", "ciao", commands=commands)
    assert commands.texts == ["/prompts"]
    assert session.questions == ["ciao"]
    assert outputs == ["elenco", "Assistente> risposta a ciao", "Arrivederci!"]


def test_unknown_command_with_the_real_commands():
    session = FakeSession()
    client = FakeMcpClient(MCP_SPECS)
    outputs, _ = execute(session, "/promt", commands=PromptCommands(client))
    assert outputs == [
        "Comando sconosciuto: '/promt'. Scrivi /prompts per l'elenco dei prompt.",
        "Arrivederci!",
    ]
    assert session.questions == [] and client.prompt_lists == 0


def test_prompts_with_the_real_commands():
    session = FakeSession()
    client = FakeMcpClient(MCP_SPECS)
    outputs, _ = execute(session, "/PROMPTS", commands=PromptCommands(client))
    assert outputs == ["Il server MCP non offre prompt.", "Arrivederci!"]
    assert session.questions == [] and client.prompt_lists == 1


def test_command_without_commands():
    session = FakeSession()
    outputs, _ = execute(session, "/prompts", "esci")
    assert outputs == ["Comandi non disponibili.", "Arrivederci!"]
    assert session.questions == []


def test_prompt_messages_go_to_the_session():  # CA-57
    session = FakeSession("Il protocollo MCP…")
    messages = [HumanMessage("Spiegami MCP.")]
    commands = FakeCommands(CommandResult(messages=messages))
    outputs, _ = execute(session, "/prompt spiega argomento=MCP", commands=commands)
    assert commands.texts == ["/prompt spiega argomento=MCP"]
    assert session.message_lists == [messages] and session.questions == []
    assert outputs == ["Assistente> Il protocollo MCP…", "Arrivederci!"]


def test_lm_studio_error_after_a_prompt_and_continue():
    session = FakeSession(lm_studio_error(), "eccomi")
    commands = FakeCommands(CommandResult(messages=[HumanMessage("Spiegami MCP.")]))
    outputs, _ = execute(session, "/prompt spiega argomento=MCP", "ancora", commands=commands)
    assert outputs == [
        "Errore: LM Studio non ha risposto correttamente (Connection error.). Riprova.",
        "Assistente> eccomi",
        "Arrivederci!",
    ]


def test_blocked_prompt_never_reaches_the_model():  # CA-57
    model = FakeModel([])  # any call would fail: no scripted replies
    session = Session(fake_graph(model))
    spec = PromptSpec("spiega", "", (PromptArgument("argomento", "", True),))
    client = FakeMcpClient(MCP_SPECS, prompts={"spiega": (spec, lambda a: [])})
    outputs, _ = execute(
        session, "/prompt spiega livello=base", "/prompt spiega argomento=MCP",
        commands=PromptCommands(client),
    )
    assert outputs == [
        "Errore nel comando: argomenti sconosciuti per 'spiega': 'livello' (attesi: argomento). "
        "Scrivi /prompts per l'elenco dei prompt.",
        "Errore: il prompt 'spiega' non è utilizzabile (nessun messaggio).",
        "Arrivederci!",
    ]
    assert model.calls == [] and session.messages == []
    assert client.prompt_gets == [("spiega", {"argomento": "MCP"})]


def test_slash_inside_a_question_is_not_a_command():
    session, commands = FakeSession(), FakeCommands()
    execute(session, "quanto fa 6 / 3?", commands=commands)
    assert session.questions == ["quanto fa 6 / 3?"]
    assert commands.texts == []
