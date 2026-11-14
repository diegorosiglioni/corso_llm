import pytest
from langchain_core.messages import AIMessage

from assistant.api_client import AgentClient, AgentError, RemoteSession
from assistant.commands import CommandResult, PromptCommands
from assistant.mcp_client import PromptArgument, PromptMessage, PromptSpec
from assistant.terminal import run
from conftest import MCP_SPECS, FakeMcpClient, FakeModel, fake_service, lm_studio_error

MODEL_DOWN = AgentError("model_unavailable", "LM Studio non raggiungibile: Connection error.")


def agent(model=None, client=None) -> AgentClient:
    """Client of the real app of the service on a fake graph (no network)."""
    return AgentClient("http://agente.test", http=fake_service(model, client))


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
        self.prompts = []

    def send(self, text):
        self.questions.append(text)
        return self._next(f"risposta a {text}")

    def send_prompt(self, name, arguments):
        self.prompts.append((name, arguments))
        return self._next(f"risposta al prompt {name}")

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


def test_agent_error_and_continue():  # CA-66
    session = FakeSession(MODEL_DOWN, "eccomi")
    outputs, _ = execute(session, "prima", "seconda")
    assert outputs == [
        "Errore: LM Studio non raggiungibile: Connection error. Riprova.",
        "Assistente> eccomi",
        "Arrivederci!",
    ]


def test_agent_unreachable_during_the_session():
    session = FakeSession(AgentError("agent_unreachable", "agente non raggiungibile su http://x"))
    outputs, _ = execute(session, "ciao")
    assert outputs == ["Errore: agente non raggiungibile su http://x. Riprova.", "Arrivederci!"]


def test_service_error_keeps_the_history():  # CA-66, with the real app of the service
    model = FakeModel([AIMessage("Ciao!"), lm_studio_error(), AIMessage("Eccomi.")])
    session = RemoteSession(agent(model))
    outputs, _ = execute(session, "ciao", "seconda", "terza")
    assert outputs == [
        "Assistente> Ciao!",
        "Errore: LM Studio non raggiungibile: Connection error. Riprova.",
        "Assistente> Eccomi.",
        "Arrivederci!",
    ]
    assert [m.content for m in model.calls[2][1:]] == ["ciao", "Ciao!", "terza"]
    assert [m["content"] for m in session.history] == ["ciao", "Ciao!", "terza", "Eccomi."]


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
    outputs, _ = execute(session, "/promt", commands=PromptCommands(agent(client=client)))
    assert outputs == [
        "Comando sconosciuto: '/promt'. Scrivi /prompts per l'elenco dei prompt.",
        "Arrivederci!",
    ]
    assert session.questions == [] and client.prompt_lists == 0


def test_prompts_with_the_real_commands():
    session = FakeSession()
    client = FakeMcpClient(MCP_SPECS)
    outputs, _ = execute(session, "/PROMPTS", commands=PromptCommands(agent(client=client)))
    assert outputs == ["Il server MCP non offre prompt.", "Arrivederci!"]
    assert session.questions == [] and client.prompt_lists == 1


def test_command_without_commands():
    session = FakeSession()
    outputs, _ = execute(session, "/prompts", "esci")
    assert outputs == ["Comandi non disponibili.", "Arrivederci!"]
    assert session.questions == []


def test_prompt_goes_to_the_session():  # CA-57
    session = FakeSession("Il protocollo MCP…")
    commands = FakeCommands(CommandResult(prompt=("spiega", {"argomento": "MCP"})))
    outputs, _ = execute(session, "/prompt spiega argomento=MCP", commands=commands)
    assert commands.texts == ["/prompt spiega argomento=MCP"]
    assert session.prompts == [("spiega", {"argomento": "MCP"})] and session.questions == []
    assert outputs == ["Assistente> Il protocollo MCP…", "Arrivederci!"]


def test_agent_error_after_a_prompt_and_continue():
    session = FakeSession(MODEL_DOWN, "eccomi")
    commands = FakeCommands(CommandResult(prompt=("spiega", {"argomento": "MCP"})))
    outputs, _ = execute(session, "/prompt spiega argomento=MCP", "ancora", commands=commands)
    assert outputs == [
        "Errore: LM Studio non raggiungibile: Connection error. Riprova.",
        "Assistente> eccomi",
        "Arrivederci!",
    ]


def test_prompt_rejected_by_the_service():
    reason = "argomenti obbligatori mancanti per 'spiega': 'argomento'"
    session = FakeSession(AgentError("prompt_rejected", reason))
    commands = FakeCommands(CommandResult(prompt=("spiega", {})))
    outputs, _ = execute(session, "/prompt spiega", commands=commands)
    assert outputs == [
        f"Errore nel comando: {reason}. Scrivi /prompts per l'elenco dei prompt.",
        "Arrivederci!",
    ]


def test_blocked_prompt_never_reaches_the_model():  # CA-57, CA-66
    model = FakeModel([])  # any call would fail: no scripted replies
    spec = PromptSpec("spiega", "", (PromptArgument("argomento", "", True),))
    client = FakeMcpClient(MCP_SPECS, prompts={"spiega": (spec, lambda a: [])})
    service = agent(model, client)
    session = RemoteSession(service)
    outputs, _ = execute(
        session, "/prompt spiega livello=base", "/prompt spiega argomento=MCP",
        "/prompt spiega argomento=", commands=PromptCommands(service),
    )
    assert outputs == [
        "Errore nel comando: argomenti sconosciuti per 'spiega': 'livello' (attesi: argomento). "
        "Scrivi /prompts per l'elenco dei prompt.",
        "Errore: il prompt 'spiega' non è utilizzabile (nessun messaggio). Riprova.",
        "Errore nel comando: argomento senza valore: 'argomento'. "
        "Uso: /prompt nome chiave=valore (valori con spazi tra virgolette doppie).",
        "Arrivederci!",
    ]
    assert model.calls == [] and session.history == []
    assert client.prompt_gets == [("spiega", {"argomento": "MCP"})]
    assert client.prompt_lists == 2  # the syntax error never reached the service


def test_prompt_through_the_service():  # CA-66
    spec = PromptSpec("spiega", "", (PromptArgument("argomento", "", True),))
    client = FakeMcpClient(
        MCP_SPECS, prompts={"spiega": (spec, lambda a: [PromptMessage("user", "Spiegami MCP.")])}
    )
    model = FakeModel([AIMessage("MCP è un protocollo.")])
    service = agent(model, client)
    session = RemoteSession(service)
    outputs, _ = execute(session, "/prompt spiega argomento=MCP", commands=PromptCommands(service))
    assert outputs == ["Assistente> MCP è un protocollo.", "Arrivederci!"]
    assert model.calls[0][-1].content == "Spiegami MCP."
    assert [m["content"] for m in session.history] == ["Spiegami MCP.", "MCP è un protocollo."]


def test_slash_inside_a_question_is_not_a_command():
    session, commands = FakeSession(), FakeCommands()
    execute(session, "quanto fa 6 / 3?", commands=commands)
    assert session.questions == ["quanto fa 6 / 3?"]
    assert commands.texts == []
