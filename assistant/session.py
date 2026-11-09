"""Conversation session: keeps the history for the lifetime of the process."""

from langchain_core.messages import AnyMessage, HumanMessage

EMPTY_REPLY = "(Il modello non ha fornito una risposta.)"


class Session:
    def __init__(self, graph):
        self._graph = graph
        self._messages: list[AnyMessage] = []

    @property
    def messages(self) -> list[AnyMessage]:
        return list(self._messages)

    def send(self, text: str) -> str:
        """Runs one turn; the history changes only if the turn succeeds."""
        result = self._graph.invoke(
            {"messages": self._messages + [HumanMessage(text)], "steps": 0}
        )
        self._messages = result["messages"]
        return self._messages[-1].text.strip() or EMPTY_REPLY
