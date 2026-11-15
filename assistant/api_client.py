"""Synchronous HTTP client of the agent service, used by the CLI (specification of step 6, §9).

AgentClient calls GET /status, GET /prompts, POST /chat and, for the back-end, POST /chat/stream
(Server-Sent Events read by iter_sse); every failure becomes AgentError with
a stable code and an Italian detail: the code and detail of the service for its error answers,
`agent_unreachable`, `agent_timeout` or `bad_response` for the others. RemoteSession keeps history
and summary of the conversation (JSON, as received) and updates them only after a 200 answer.
"""

import json
import time
from collections.abc import Iterable, Iterator

import httpx

from assistant.mcp_client import PromptArgument, PromptSpec

STATUS_TIMEOUT = 10.0  # GET /status and GET /prompts (the model check lasts at most 5 s)
CHAT_TIMEOUT = 600.0  # POST /chat: a turn may contain several calls to the local model
CONNECT_TIMEOUT = 10.0  # connection to the agent, for every request
STREAM_IDLE_TIMEOUT = 60.0  # POST /chat/stream: most time without data (": ping" every 15 s)
STREAM_EVENTS = {"text", "reset", "tool_start", "tool_end", "done", "error"}


def iter_sse(lines: Iterable[str]) -> Iterator[tuple[str, str]]:
    """(event, data) of the Server-Sent Events in `lines` (without their line breaks).

    An event ends at an empty line; the lines of `data` are joined with "\\n"; an event without
    a name is "message"; comments and unknown fields are ignored; an event without data or not
    ended by an empty line (a cut stream) is dropped, as the SSE standard says.
    """
    event, data = "", []
    for line in lines:
        line = line.rstrip("\r")
        if not line:
            if data:
                yield event or "message", "\n".join(data)
            event, data = "", []
            continue
        if line.startswith(":"):
            continue
        name, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if name == "event":
            event = value
        elif name == "data":
            data.append(value)


def _chat_request(history, summary, message, prompt) -> dict:
    request = {"history": history, "summary": summary}
    if message is not None:
        request["message"] = message
    if prompt is not None:
        request["prompt"] = {"name": prompt[0], "arguments": dict(prompt[1])}
    return request


def _bad_stream(reason: str) -> "AgentError":
    return AgentError("bad_response", f"flusso dell'agente non valido: {reason}")


class AgentError(Exception):
    """A request to the agent that gave no usable answer; `detail` is for the user."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail

    @property
    def phrase(self) -> str:
        """`detail` without its final period, to be followed by "." in a sentence."""
        return self.detail.rstrip(".")


def _body(response):
    try:
        return response.json()
    except ValueError:
        return None


def _error(response, body) -> AgentError:
    """The error of the service ({"error", "detail"}) or an unexpected answer."""
    if (
        isinstance(body, dict)
        and isinstance(body.get("error"), str)
        and isinstance(body.get("detail"), str)
    ):
        return AgentError(body["error"], body["detail"])
    return AgentError(
        "bad_response", f"risposta inattesa dell'agente (HTTP {response.status_code})"
    )


def _is_status(body) -> bool:
    """True for the body of GET /status: mcp and model with status and detail, model with id."""
    if not isinstance(body, dict):
        return False
    parts = [body.get("mcp"), body.get("model")]
    return all(
        isinstance(part, dict) and isinstance(part.get("status"), str)
        and isinstance(part.get("detail"), str)
        for part in parts
    ) and isinstance(body["model"].get("id"), str)


CHAT_FIELDS = {"reply": str, "tools_used": list, "history": list, "summary": str}


def _is_chat(body) -> bool:
    """True for the body of a 200 POST /chat: the four fields with their JSON types."""
    return isinstance(body, dict) and all(
        isinstance(body.get(key), kind) for key, kind in CHAT_FIELDS.items()
    )


def _prompt_specs(data) -> list[PromptSpec]:
    """The body of GET /prompts as the PromptSpec of prompts/list; ValueError if malformed."""
    try:
        return [
            PromptSpec(item["name"], item["description"], tuple(
                PromptArgument(argument["name"], argument["description"], argument["required"])
                for argument in item["arguments"]
            ))
            for item in data
        ]
    except (KeyError, TypeError) as error:
        raise ValueError(str(error)) from error


class AgentClient:
    """Client of the agent at `base_url`; `http` (an httpx.Client, or the TestClient of the app)
    replaces the connection in the tests and is not closed by `close()`."""

    def __init__(self, base_url: str, http=None):
        self.base_url = base_url.rstrip("/")
        self._own_http = http is None
        self._http = httpx.Client(base_url=self.base_url) if http is None else http

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        if self._own_http:
            self._http.close()

    def status(self) -> dict:
        """The body of GET /status, also when it is 503 (degraded: MCP or model unavailable)."""
        response = self._request("GET", "/status", STATUS_TIMEOUT)
        body = _body(response)
        if response.status_code in (200, 503) and _is_status(body):
            return body
        raise _error(response, body)

    def prompts(self) -> list[PromptSpec]:
        """The prompts of the MCP server, as prompts/list describes them."""
        response = self._request("GET", "/prompts", STATUS_TIMEOUT)
        body = _body(response)
        if response.status_code != 200:
            raise _error(response, body)
        try:
            return _prompt_specs(body)
        except ValueError:
            raise _error(response, None) from None

    def chat(
        self, history: list[dict], summary: str, *,
        message: str | None = None, prompt: tuple[str, dict[str, str]] | None = None,
    ) -> dict:
        """One turn opened by `message` or by the MCP prompt (name, arguments).

        Returns the body of the 200 answer: reply, tools_used, history and summary.
        """
        request = _chat_request(history, summary, message, prompt)
        response = self._request("POST", "/chat", CHAT_TIMEOUT, request)
        body = _body(response)
        if response.status_code == 200 and _is_chat(body):
            return body
        raise _error(response, body)

    def chat_stream(
        self, history: list[dict], summary: str, *,
        message: str | None = None, prompt: tuple[str, dict[str, str]] | None = None,
    ) -> Iterator[tuple[str, dict]]:
        """The same turn as `chat` through POST /chat/stream (specification of the streaming, §5).

        The request is sent and its answer checked here: an error answer, or an agent that cannot
        be reached, raises AgentError before any event. Returns the generator of the events
        (name, data): "text", "reset", "tool_start" and "tool_end" as they arrive, last "done"
        with the body of `chat`. An "error" event raises AgentError with its code and detail;
        more than STREAM_IDLE_TIMEOUT s without data or CHAT_TIMEOUT s in all → agent_timeout;
        a stream that ends without done, or malformed → bad_response. Closing the generator
        closes the connection.
        """
        started = time.monotonic()
        request = self._http.build_request(
            "POST", "/chat/stream", json=_chat_request(history, summary, message, prompt),
            timeout=httpx.Timeout(STREAM_IDLE_TIMEOUT, connect=CONNECT_TIMEOUT),
        )
        response = self._send(lambda: self._http.send(request, stream=True), STREAM_IDLE_TIMEOUT)
        if response.status_code != 200:
            try:
                self._send(response.read, STREAM_IDLE_TIMEOUT)
                body = _body(response)
            finally:
                response.close()
            raise _error(response, body)
        return self._events(response, started)

    def _events(self, response, started: float) -> Iterator[tuple[str, dict]]:
        try:
            lines = self._lines(response, started + CHAT_TIMEOUT)
            for event, data in iter_sse(lines):
                if event not in STREAM_EVENTS:
                    continue
                try:
                    body = json.loads(data)
                except ValueError:
                    raise _bad_stream(f"dati non validi nell'evento '{event}'") from None
                if event == "done":
                    if not _is_chat(body):
                        raise _bad_stream("evento 'done' non valido")
                    yield event, body
                    return
                if event == "error":
                    raise _error(response, body if isinstance(body, dict) else None)
                if not isinstance(body, dict):
                    raise _bad_stream(f"dati non validi nell'evento '{event}'")
                yield event, body
            raise _bad_stream("flusso interrotto prima della fine del turno")
        finally:
            response.close()

    def _lines(self, response, deadline: float) -> Iterator[str]:
        """The lines of the stream; AgentError for a slow or broken stream."""
        lines = response.iter_lines()
        while True:
            line = self._send(lambda: next(lines, None), STREAM_IDLE_TIMEOUT, broken=True)
            if line is None:
                return
            if time.monotonic() > deadline:
                raise AgentError(
                    "agent_timeout", f"l'agente non ha finito il turno entro {CHAT_TIMEOUT:g} s"
                )
            yield line

    def _request(self, method: str, path: str, timeout: float, json=None):
        return self._send(
            lambda: self._http.request(
                method, path, json=json, timeout=httpx.Timeout(timeout, connect=CONNECT_TIMEOUT)
            ),
            timeout,
        )

    def _send(self, call, timeout: float, *, broken: bool = False):
        """`call()` with the errors of httpx as AgentError; `broken` for a stream already
        open, whose transport errors mean that it was cut, not that the agent is off."""
        try:
            return call()
        except httpx.ConnectTimeout as error:
            raise self._unreachable() from error
        except httpx.TimeoutException as error:
            raise AgentError(
                "agent_timeout", f"l'agente non ha risposto entro {timeout:g} s"
            ) from error
        except httpx.TransportError as error:
            if broken:
                raise _bad_stream("flusso interrotto prima della fine del turno") from error
            raise self._unreachable() from error

    def _unreachable(self) -> AgentError:
        return AgentError("agent_unreachable", f"agente non raggiungibile su {self.base_url}")


class RemoteSession:
    """Conversation of the CLI through the agent: history and summary live here, not in the
    service, and change only after a turn that succeeds."""

    def __init__(self, agent: AgentClient):
        self._agent = agent
        self._history: list[dict] = []
        self._summary = ""

    @property
    def history(self) -> list[dict]:
        return list(self._history)

    @property
    def summary(self) -> str:
        return self._summary

    def send(self, text: str) -> str:
        """One turn with the user's question; returns the reply."""
        return self._turn(message=text)

    def send_prompt(self, name: str, arguments: dict[str, str]) -> str:
        """One turn opened by the MCP prompt `name` (checked by the service); returns the reply."""
        return self._turn(prompt=(name, arguments))

    def _turn(self, **opening) -> str:
        result = self._agent.chat(self._history, self._summary, **opening)
        self._history = result["history"]
        self._summary = result["summary"]
        return result["reply"]
