"""Synchronous MCP client: one stdio session kept open in a thread with its own event loop.

The asynchrony stays inside this module: the rest of the application calls blocking methods.
"""

import asyncio
import concurrent.futures
import logging
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from langchain_core.tools import BaseTool, StructuredTool

from assistant.tools import ToolUnavailableError

log = logging.getLogger(__name__)

CLOSE_TIMEOUT = 10.0


@dataclass(frozen=True)
class ToolSpec:
    """A tool as published by the server with tools/list."""

    name: str
    description: str
    input_schema: dict


class McpStartupError(Exception):
    """The MCP server could not be started or did not complete the handshake."""


def server_command(notes_db: Path, log_level: str) -> tuple[str, list[str], str]:
    """Command, arguments and working directory that start the local MCP server."""
    package_parent = Path(__file__).resolve().parent.parent
    args = ["-m", "assistant.mcp_server", "--notes-db", str(notes_db), "--log-level", log_level]
    return sys.executable, args, str(package_parent)


def _reason(error: BaseException) -> str:
    return str(error) or type(error).__name__


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
        return self

    def __exit__(self, *exc) -> None:
        self._shutdown()

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

    def list_tools(self) -> list[ToolSpec]:
        tools = self._submit(lambda client: client.list_tools())
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

    def _submit(self, request):
        """Runs `request(client)` on the session loop; connection problems → ToolUnavailableError."""
        client, loop = self._client, self._loop
        if client is None or loop is None:
            raise ToolUnavailableError("sessione MCP chiusa")
        future = asyncio.run_coroutine_threadsafe(request(client), loop)
        try:
            return future.result(self._timeout + 5)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise ToolUnavailableError(
                f"nessuna risposta entro {self._timeout:g} s"
            ) from None
        except Exception as error:
            raise ToolUnavailableError(_reason(error)) from error


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
