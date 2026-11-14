"""Conversation session: keeps the history for the lifetime of the process."""

from langchain_core.messages import AnyMessage, BaseMessage, HumanMessage

from assistant.agent import run_turn


class Session:
    def __init__(self, graph):
        self._graph = graph
        self._messages: list[AnyMessage] = []
        self._summary = ""  # summary of the messages removed from the history

    @property
    def messages(self) -> list[AnyMessage]:
        return list(self._messages)

    @property
    def summary(self) -> str:
        return self._summary

    def send(self, text: str) -> str:
        """Runs one turn with the user's question."""
        return self.send_messages([HumanMessage(text)])

    def send_messages(self, messages: list[BaseMessage]) -> str:
        """Runs one turn opened by `messages` (for example those of an MCP prompt), all added to
        the history; history and summary change only if the turn succeeds."""
        result = run_turn(self._graph, self._messages, self._summary, messages)
        self._messages = result.history
        self._summary = result.summary
        return result.reply
