"""Synchronous MCP client: one stdio session kept open in a thread with its own event loop.

The asynchrony stays inside this module: the rest of the application calls blocking methods.
If the server dies, the client starts it again at the next request (R-B3).
"""

import asyncio
import concurrent.futures
import json
import logging
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import anyio
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from langchain_core.tools import BaseTool, StructuredTool
from mcp.shared.exceptions import MCPError
from mcp.types import CONNECTION_CLOSED, REQUEST_TIMEOUT, TextContent, TextResourceContents

from assistant.tools import ToolUnavailableError

log = logging.getLogger(__name__)

CLOSE_TIMEOUT = 10.0


@dataclass(frozen=True)
class ToolSpec:
    """A tool as published by the server with tools/list."""

    name: str
    description: str
    input_schema: dict


@dataclass(frozen=True)
class PromptArgument:
    """An argument of a prompt as published by prompts/list."""

    name: str
    description: str
    required: bool


@dataclass(frozen=True)
class PromptSpec:
    """A prompt as published by the server with prompts/list."""

    name: str
    description: str
    arguments: tuple[PromptArgument, ...]


@dataclass(frozen=True)
class PromptMessage:
    """A text message returned by prompts/get; role is "user" or "assistant"."""

    role: str
    text: str


class McpStartupError(Exception):
    """The MCP server could not be started or did not complete the handshake."""


class ResourceUnavailableError(Exception):
    """A resource could not be read: MCP error, closed session, timeout or no text content.

    Kept apart from ToolUnavailableError: resources are not tools, in the code and in the logs.
    """


class PromptUnavailableError(Exception):
    """A prompt could not be listed or obtained: MCP error (unknown prompt, value rejected by the
    server), closed session, timeout or non-text content.

    Kept apart from ToolUnavailableError and ResourceUnavailableError, as in the logs.
    """


def server_command(
    notes_db: Path, log_level: str, preferences_file: str | Path
) -> tuple[str, list[str], str]:
    """Command, arguments and working directory that start the local MCP server.

    The server runs in another working directory: relative paths must be resolved first. The
    preferences file has no default: the caller passes the one it uses (R-A3).
    """
    package_parent = Path(__file__).resolve().parent.parent
    args = [
        "-m", "assistant.mcp_server", "--notes-db", str(notes_db),
        "--preferences-file", str(preferences_file), "--log-level", log_level,
    ]
    return sys.executable, args, str(package_parent)


def _reason(error: BaseException) -> str:
    return str(error) or type(error).__name__


def _is_closed(error: BaseException) -> bool:
    """The connection to the server is gone (the server died): a restart can help."""
    if isinstance(error, MCPError):
        return error.code == CONNECTION_CLOSED
    return isinstance(error, (anyio.ClosedResourceError, anyio.BrokenResourceError))


def _is_timeout(error: BaseException) -> bool:
    """The library gave up waiting for the server (call_tool has its own timeout)."""
    return isinstance(error, MCPError) and error.code == REQUEST_TIMEOUT


class _ConnectionClosed(Exception):
    """Internal: a request found the connection closed; `generation` is the session it used."""

    def __init__(self, generation: int, reason: str):
        super().__init__(reason)
        self.generation = generation
        self.reason = reason


class McpClient:
    def __init__(
        self, command: str, args: list[str], cwd: str | None = None, timeout: float = 30.0
    ):
        self._command = command
        self._args = list(args)
        self._cwd = cwd
        self._timeout = timeout
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._serving: concurrent.futures.Future | None = None
        self._client: Client | None = None
        self._stop: asyncio.Event | None = None
        self._opened = False  # between __enter__ and __exit__: only then a restart is allowed
        self._lock = threading.Lock()  # one restart at a time
        self._generation = 0  # number of restarts: tells a thread whether another restarted
        self._stale_reason: str | None = None  # set by a timeout: restart before the next request

    async def _serve(self, ready: concurrent.futures.Future) -> None:
        """Keeps the fastmcp client open; entering and leaving happen in this same task."""
        try:
            transport = StdioTransport(
                self._command, self._args, cwd=self._cwd, keep_alive=False, log_file=sys.stderr
            )
            async with Client(transport) as client:
                self._client, self._stop = client, asyncio.Event()
                ready.set_result(None)
                await self._stop.wait()
        except BaseException as error:
            if not ready.done():
                ready.set_exception(error)
            raise
        finally:
            self._client = None

    def __enter__(self) -> "McpClient":
        self._open()
        self._opened = True
        return self

    def __exit__(self, *exc) -> None:
        self._opened = False
        with self._lock:  # waits for a restart in progress
            self._shutdown()

    def _open(self) -> None:
        """Starts the server and the session; McpStartupError if it does not answer."""
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, name="mcp-client", daemon=True
        )
        self._thread.start()
        ready: concurrent.futures.Future = concurrent.futures.Future()
        self._serving = asyncio.run_coroutine_threadsafe(self._serve(ready), self._loop)
        try:
            ready.result(self._timeout)
        except concurrent.futures.TimeoutError:
            self._shutdown()
            raise McpStartupError(
                f"nessuna risposta dal server entro {self._timeout:g} s"
            ) from None
        except BaseException as error:
            self._shutdown()
            raise McpStartupError(_reason(error)) from error

    def _shutdown(self) -> None:
        """Closes the session and the subprocess, then stops the loop and its thread."""
        loop = self._loop
        if loop is None:
            return
        if self._stop is not None:
            loop.call_soon_threadsafe(self._stop.set)
        if self._serving is not None:
            try:
                self._serving.result(CLOSE_TIMEOUT)
            except BaseException:  # closing errors do not matter any more
                self._serving.cancel()
        loop.call_soon_threadsafe(loop.stop)
        self._thread.join(CLOSE_TIMEOUT)
        if not loop.is_running():
            loop.close()
        self._loop = None
        self._client = None

    def list_tools(self, timeout: float | None = None) -> list[ToolSpec]:
        """Tools published with tools/list; `timeout` replaces the usual wait (GET /status)."""
        tools = self._submit(lambda client: client.list_tools(), timeout)
        return [ToolSpec(t.name, t.description or "", t.input_schema) for t in tools]

    def call_tool(self, name: str, arguments: dict) -> dict:
        """Tool result as a dict; a tool error becomes {"error": ...}."""
        result = self._submit(
            lambda client: client.call_tool(
                name, arguments, timeout=self._timeout, raise_on_error=False
            )
        )
        if result.is_error:
            return {"error": "\n".join(getattr(c, "text", "") for c in result.content)}
        return result.structured_content or {}

    def read_resource(self, uri: str) -> str:
        """Text of the resource (resources/read); binary contents are ignored."""
        contents = self._submit_as(
            ResourceUnavailableError, lambda client: client.read_resource(uri)
        )
        texts = [c.text for c in contents if isinstance(c, TextResourceContents)]
        if not texts:
            raise ResourceUnavailableError("nessun contenuto testuale")
        return "".join(texts)

    def list_prompts(self) -> list[PromptSpec]:
        """Prompts published with prompts/list; missing fields become "", () and False."""
        prompts = self._submit_as(PromptUnavailableError, lambda client: client.list_prompts())
        return [
            PromptSpec(p.name, p.description or "", tuple(
                PromptArgument(a.name, a.description or "", bool(a.required))
                for a in p.arguments or ()
            ))
            for p in prompts
        ]

    def get_prompt(self, name: str, arguments: dict[str, str]) -> list[PromptMessage]:
        """Messages of the prompt (prompts/get); only text contents are accepted."""
        result = self._submit_as(
            PromptUnavailableError, lambda client: client.get_prompt(name, arguments)
        )
        messages = []
        for number, message in enumerate(result.messages, start=1):
            if not isinstance(message.content, TextContent):
                raise PromptUnavailableError(f"contenuto non testuale nel messaggio {number}")
            messages.append(PromptMessage(message.role, message.content.text))
        return messages

    def _submit_as(self, error_type: type[Exception], request):
        """Like `_submit`, but connection problems become `error_type` with the same reason."""
        try:
            return self._submit(request)
        except ToolUnavailableError as error:
            raise error_type(str(error)) from error

    def _submit(self, request, timeout: float | None = None):
        """Runs `request(client)` on the session loop; connection problems → ToolUnavailableError.

        Without `timeout` the wait is the session timeout plus 5 s; with it, exactly `timeout`.
        A closed connection restarts the server and repeats the request once; a timeout repeats
        nothing, but the server is restarted before the next request.
        """
        if not self._opened:
            raise ToolUnavailableError("sessione MCP chiusa")
        stale = self._stale_reason
        if stale is not None:
            self._restart(self._generation, stale)
        try:
            return self._run(request, timeout)
        except _ConnectionClosed as closed:
            self._restart(closed.generation, closed.reason)
        try:
            return self._run(request, timeout)
        except _ConnectionClosed as closed:
            raise ToolUnavailableError(closed.reason) from None

    def _run(self, request, timeout: float | None):
        """One attempt of `_submit`; a closed connection becomes _ConnectionClosed."""
        generation = self._generation
        client, loop = self._client, self._loop
        if client is None or loop is None:
            raise _ConnectionClosed(generation, "sessione MCP chiusa")
        future = asyncio.run_coroutine_threadsafe(request(client), loop)
        wait, shown = (self._timeout + 5, self._timeout) if timeout is None else (timeout, timeout)
        try:
            return future.result(wait)
        except concurrent.futures.TimeoutError:
            future.cancel()
            reason = f"nessuna risposta entro {shown:g} s"
            self._stale_reason = reason
            raise ToolUnavailableError(reason) from None
        except Exception as error:
            if _is_closed(error):
                raise _ConnectionClosed(generation, _reason(error)) from error
            if _is_timeout(error):
                self._stale_reason = _reason(error)
            raise ToolUnavailableError(_reason(error)) from error

    def _restart(self, seen_generation: int, reason: str) -> None:
        """Starts a new server process unless another thread already did after `seen_generation`.

        ToolUnavailableError if the client was closed or the server does not start again; in the
        second case the next request tries again.
        """
        with self._lock:
            if not self._opened:
                raise ToolUnavailableError("sessione MCP chiusa")
            if self._generation != seen_generation and self._stale_reason is None:
                return
            log.warning("mcp_restart reason=%s", json.dumps(reason, ensure_ascii=False))
            started = time.monotonic()
            self._shutdown()
            try:
                self._open()
            except McpStartupError as error:
                self._stale_reason = reason
                log.warning(
                    "mcp_restart_failed error=%s", json.dumps(str(error), ensure_ascii=False)
                )
                raise ToolUnavailableError(f"server MCP non riavviato: {error}") from error
            self._generation += 1
            self._stale_reason = None
            log.info("mcp_restarted duration_ms=%d", round((time.monotonic() - started) * 1000))


# --- adapter: tools/list catalog → LangChain tools ---

ALLOWED_MCP_TOOLS = (
    "convert_units", "calculate", "search_catalog", "get_item",
    "add_note", "list_notes", "delete_note",
)


# Marker of the argument-validation errors produced by the server (pydantic, in English).
_VALIDATION_MARKER = "validation error for call["


def _expected_arguments(schema: dict) -> str:
    required = set(schema.get("required", []))
    names = [
        f"{name} (obbligatorio)" if name in required else name
        for name in schema.get("properties", {})
    ]
    return ", ".join(names) or "nessuno"


def _caller(client, spec: ToolSpec):
    """Function that forwards a call to `spec`; a factory avoids late binding in the loop.

    The server's argument-validation errors are in English and carry a URL: the model gets
    an Italian message with the expected arguments and the tool description instead.
    """
    def call(**arguments) -> dict:
        result = client.call_tool(spec.name, arguments)
        if _VALIDATION_MARKER in str(result.get("error", "")):
            return {
                "error": f"Argomenti non validi per '{spec.name}'. Argomenti attesi: "
                f"{_expected_arguments(spec.input_schema)}. Uso: {spec.description}"
            }
        return result
    return call


def create_mcp_tools(client, allowed=ALLOWED_MCP_TOOLS) -> list[BaseTool]:
    """One StructuredTool per allowed tool, with name, description and schema from the server."""
    specs = client.list_tools()
    published = {spec.name for spec in specs}
    tools = []
    for spec in specs:
        if spec.name not in allowed:
            log.info("strumento MCP non consentito, ignorato: %s", spec.name)
            continue
        tools.append(StructuredTool(
            name=spec.name,
            description=spec.description,
            args_schema=spec.input_schema,  # the server's JSON Schema, passed on unchanged
            func=_caller(client, spec),
            metadata={"variant": "mcp"},
        ))
    for name in allowed:
        if name not in published:
            log.warning("strumento MCP consentito ma assente dal catalogo: %s", name)
    return tools
