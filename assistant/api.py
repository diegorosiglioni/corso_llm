"""HTTP service of the agent (FastAPI): the same graph as the terminal, without conversations.

History and summary come from the caller and go back updated; the service keeps open only the
MCP client and the models. The OpenAPI document is generated from the pydantic models below
(/openapi.json, page /docs). Error bodies are {"error": <code>, "detail": <Italian text>}, except
the 422 of FastAPI for a body that does not match the schema.
"""

import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict
from typing import Annotated, Any, Literal

import openai
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel, ConfigDict, Field

from assistant.agent import messages_from_json, messages_to_json, run_turn
from assistant.commands import (
    PromptGetError,
    PromptListError,
    PromptRejectedError,
    available_prompts,
    resolve_prompt,
)
from assistant.tools import ToolUnavailableError

log = logging.getLogger(__name__)

TITLE = "Assistente del laboratorio — agente"
DESCRIPTION = (
    "Agente senza stato: ogni richiesta porta la cronologia e il riassunto della conversazione e "
    "riceve la risposta con la cronologia e il riassunto aggiornati. Il servizio non conserva "
    "nessuna conversazione."
)


# --- Messages (specification of step 6, §4) ---

class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolCall(_Closed):
    id: str = Field(description="Identificativo della chiamata.")
    name: str = Field(description="Nome dello strumento.")
    args: dict[str, Any] = Field(description="Argomenti della chiamata.")


class InvalidToolCall(_Closed):
    id: str | None = Field(description="Identificativo della chiamata.")
    name: str | None = Field(description="Nome dello strumento.")
    args: str | None = Field(None, description="Argomenti ricevuti, non interpretabili.")
    error: str | None = Field(None, description="Motivo per cui la chiamata non è valida.")


class UserMessage(_Closed):
    role: Literal["user"]
    content: str = Field(description="Testo dell'utente.")
    name: str | None = Field(
        None, description="'reviewer' per le indicazioni del revisore all'agente."
    )


class AssistantMessage(_Closed):
    role: Literal["assistant"]
    content: str = Field(description="Testo dell'agente (vuoto se chiama solo strumenti).")
    tool_calls: list[ToolCall] | None = Field(None, description="Chiamate agli strumenti.")
    invalid_tool_calls: list[InvalidToolCall] | None = Field(
        None, description="Chiamate che il programma non ha potuto interpretare."
    )


class ToolResultMessage(_Closed):
    role: Literal["tool"]
    content: str = Field(description="Risultato dello strumento, di solito JSON.")
    tool_call_id: str = Field(description="Identificativo della chiamata a cui risponde.")
    name: str | None = Field(None, description="Nome dello strumento.")


Message = Annotated[
    UserMessage | AssistantMessage | ToolResultMessage, Field(discriminator="role")
]


# --- Requests and responses ---

class PromptRequest(_Closed):
    name: str = Field(description="Nome del prompt MCP (vedi prompts/list).")
    arguments: dict[str, str] = Field({}, description="Argomenti del prompt.")


class ChatRequest(_Closed):
    model_config = ConfigDict(  # merged with extra="forbid" of _Closed
        json_schema_extra={"examples": [
            {"message": "Quanto fa 17 * 23?", "history": [], "summary": ""},
            {"prompt": {"name": "spiega", "arguments": {"argomento": "Model Context Protocol"}}},
        ]},
    )

    message: str | None = Field(None, description="Domanda dell'utente (oppure 'prompt').")
    prompt: PromptRequest | None = Field(None, description="Prompt MCP (oppure 'message').")
    history: list[Message] = Field([], description="Cronologia ricevuta nel turno precedente.")
    summary: str = Field("", description="Riassunto ricevuto nel turno precedente.")


class ToolUse(BaseModel):
    name: str | None = Field(description="Nome dello strumento.")
    args: Any = Field(description="Argomenti della chiamata (testo se non interpretabili).")
    result: Any = Field(description="Risultato dello strumento.")
    ok: bool = Field(description="false se il risultato contiene 'error'.")


class ChatResponse(BaseModel):
    reply: str = Field(description="Risposta finale dell'agente.")
    tools_used: list[ToolUse] = Field(description="Strumenti eseguiti nel turno, in ordine.")
    history: list[Message] = Field(description="Cronologia aggiornata, da rimandare.")
    summary: str = Field(description="Riassunto aggiornato, da rimandare.")


class ErrorBody(BaseModel):
    error: str = Field(description="Codice stabile dell'errore.")
    detail: str = Field(description="Messaggio in italiano.")


class PromptArgumentInfo(BaseModel):
    name: str = Field(description="Nome dell'argomento.")
    description: str = Field(description="Descrizione dell'argomento.")
    required: bool = Field(description="true se l'argomento è obbligatorio.")


class PromptInfo(BaseModel):
    name: str = Field(description="Nome del prompt.")
    description: str = Field(description="Descrizione del prompt.")
    arguments: list[PromptArgumentInfo] = Field(description="Argomenti del prompt.")


class McpStatus(BaseModel):
    status: Literal["ok", "unavailable"] = Field(description="Esito di tools/list.")
    detail: str = Field(description="Numero di strumenti oppure motivo, in italiano.")


class ModelStatus(BaseModel):
    status: Literal["ok", "unavailable"] = Field(description="Esito di GET /models di LM Studio.")
    id: str = Field(description="Identificativo del modello configurato.")
    detail: str = Field(description="Motivo, in italiano; vuoto se il modello è disponibile.")


class StatusBody(BaseModel):
    status: Literal["ok", "degraded"] = Field(
        description="ok se server MCP e modello sono disponibili, altrimenti degraded."
    )
    agent: Literal["ok"] = Field(description="Il servizio dell'agente risponde.")
    mcp: McpStatus
    model: ModelStatus


INTERNAL_ERROR = {"model": ErrorBody, "description": "Errore imprevisto (internal_error)."}

CHAT_ERRORS = {
    400: {"model": ErrorBody, "description": (
        "Richiesta non valida (invalid_request), cronologia non valida (invalid_history) o prompt "
        "rifiutato dal controllo dell'host (prompt_rejected)."
    )},
    500: INTERNAL_ERROR,
    502: {"model": ErrorBody, "description": (
        "Prompt non ottenibile dal server MCP o non utilizzabile (prompt_unavailable), oppure "
        "errore di LM Studio (model_error)."
    )},
    503: {"model": ErrorBody, "description": (
        "Elenco dei prompt non disponibile (mcp_unavailable) o LM Studio non raggiungibile "
        "(model_unavailable)."
    )},
}

PROMPTS_ERRORS = {
    500: INTERNAL_ERROR,
    503: {"model": ErrorBody, "description": "Elenco dei prompt non disponibile (mcp_unavailable)."},
}

STATUS_RESPONSES = {
    500: INTERNAL_ERROR,
    503: {"model": StatusBody, "description": "Server MCP o modello non disponibili (degraded)."},
}

INTERNAL_DETAIL = "errore interno dell'agente; dettagli nel log"


class ApiError(Exception):
    """An error answer: HTTP status, stable code and Italian detail."""

    def __init__(self, status: int, code: str, detail: str):
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail

    def response(self) -> JSONResponse:
        return JSONResponse({"error": self.code, "detail": self.detail}, status_code=self.status)


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _kind(request: ChatRequest) -> str:
    if request.message is not None and request.prompt is not None:
        return "both"
    if request.prompt is not None:
        return f"prompt name={request.prompt.name}"
    return "message" if request.message is not None else "none"


def _history(request: ChatRequest) -> list[BaseMessage]:
    data = [message.model_dump(exclude_unset=True) for message in request.history]
    try:
        return messages_from_json(data)
    except ValueError as error:
        raise ApiError(400, "invalid_history", str(error)) from None


def _opening(client, request: ChatRequest) -> list[BaseMessage]:
    """The messages that open the turn: the question or those of the MCP prompt."""
    if request.prompt is None:
        return [HumanMessage(request.message.strip())]
    prompt = request.prompt
    try:
        return resolve_prompt(client, prompt.name, prompt.arguments)
    except PromptRejectedError as error:
        raise ApiError(400, "prompt_rejected", str(error)) from None
    except PromptListError as error:
        raise ApiError(503, "mcp_unavailable", str(error)) from None
    except PromptGetError as error:
        raise ApiError(502, "prompt_unavailable", str(error)) from None


def _chat(graph, client, request: ChatRequest) -> dict:
    if (request.message is None) == (request.prompt is None):
        raise ApiError(400, "invalid_request", "indicare esattamente uno tra 'message' e 'prompt'")
    if request.message is not None and not request.message.strip():
        raise ApiError(400, "invalid_request", "il campo 'message' è vuoto")
    history = _history(request)  # before the prompt: a bad history calls nothing
    opening = _opening(client, request)
    try:
        result = run_turn(graph, history, request.summary, opening)
    except openai.APIConnectionError as error:  # APITimeoutError included
        raise ApiError(503, "model_unavailable", f"LM Studio non raggiungibile: {error}") from None
    except openai.APIError as error:
        raise ApiError(
            502, "model_error", f"LM Studio non ha risposto correttamente: {error}"
        ) from None
    return {
        "reply": result.reply,
        "tools_used": result.tools_used,
        "history": messages_to_json(result.history),
        "summary": result.summary,
    }


def _mcp_status(client) -> dict:
    try:
        tools = client.list_tools()
    except ToolUnavailableError as error:
        return {"status": "unavailable", "detail": str(error)}
    return {"status": "ok", "detail": f"{len(tools)} strumenti"}


def _status(client, model_id: str, model_status: Callable[[], tuple[bool, str]]) -> dict:
    mcp = _mcp_status(client)
    model_ok, model_detail = model_status()
    model = {"status": "ok" if model_ok else "unavailable", "id": model_id, "detail": model_detail}
    ok = mcp["status"] == "ok" and model_ok
    return {"status": "ok" if ok else "degraded", "agent": "ok", "mcp": mcp, "model": model}


def _log_error(endpoint: str, error: ApiError, started: float, exc_info: bool = False) -> None:
    """4xx at INFO, 5xx at WARNING, 500 at ERROR (with the traceback when `exc_info`)."""
    if error.status == 500:
        level = logging.ERROR
    else:
        level = logging.INFO if error.status < 500 else logging.WARNING
    log.log(
        level, "api response=%s status=%d error=%s detail=%s duration_ms=%d",
        endpoint, error.status, error.code, _json(error.detail), _elapsed_ms(started),
        exc_info=exc_info,
    )


def _elapsed_ms(started: float) -> int:
    return round((time.monotonic() - started) * 1000)


def _answer(endpoint: str, work: Callable[[float], Any]):
    """Result of `work(started)` (which logs its own success), or the logged error response.

    An unexpected exception becomes 500 internal_error, with the traceback in the log only.
    """
    started = time.monotonic()
    try:
        return work(started)
    except ApiError as error:
        _log_error(endpoint, error, started)
        return error.response()
    except Exception:
        error = ApiError(500, "internal_error", INTERNAL_DETAIL)
        _log_error(endpoint, error, started, exc_info=True)
        return error.response()


def create_app(
    *, graph, client, model_id: str, model_status: Callable[[], tuple[bool, str]]
) -> FastAPI:
    """App on the compiled `graph` and the MCP `client` (real or fake).

    `model_id` is the configured model; `model_status()` returns (ok, Italian detail), for
    example `lambda: check_model(config)`.
    """
    app = FastAPI(title=TITLE, description=DESCRIPTION)

    @app.post(
        "/chat",
        response_model=ChatResponse,
        response_model_exclude_unset=True,
        responses=CHAT_ERRORS,
        summary="Un turno di conversazione",
        description=(
            "Esegue un turno del grafo (riassunto, router, agente con gli strumenti, revisore) "
            "aperto da 'message' oppure dai messaggi del prompt MCP 'prompt', controllato prima "
            "rispetto a prompts/list. Cronologia e riassunto del chiamante cambiano solo con una "
            "risposta 200."
        ),
    )
    def chat(request: ChatRequest):
        log.info(
            "api request=chat kind=%s history=%d summary_chars=%d",
            _kind(request), len(request.history), len(request.summary),
        )

        def work(started: float) -> dict:
            body = _chat(graph, client, request)
            log.info(
                "api response=chat status=200 tools=%s reply_chars=%d history=%d duration_ms=%d",
                ",".join(str(tool["name"]) for tool in body["tools_used"]),
                len(body["reply"]), len(body["history"]), _elapsed_ms(started),
            )
            return body

        return _answer("chat", work)

    @app.get(
        "/prompts",
        response_model=list[PromptInfo],
        responses=PROMPTS_ERRORS,
        summary="Prompt MCP disponibili",
        description="Il contenuto di prompts/list del server MCP: nome, descrizione e argomenti.",
    )
    def prompts():
        def work(started: float) -> list[dict]:
            try:
                specs = available_prompts(client)
            except PromptListError as error:
                raise ApiError(503, "mcp_unavailable", str(error)) from None
            log.info(
                "api response=prompts status=200 count=%d duration_ms=%d",
                len(specs), _elapsed_ms(started),
            )
            return [asdict(spec) for spec in specs]

        return _answer("prompts", work)

    @app.get(
        "/status",
        response_model=StatusBody,
        responses=STATUS_RESPONSES,
        summary="Stato dell'agente",
        description=(
            "Controlla il server MCP (tools/list) e LM Studio (GET /models, il modello configurato "
            "deve esserci): 200 se entrambi sono disponibili, 503 con lo stesso corpo altrimenti."
        ),
    )
    def status(response: Response):
        def work(started: float) -> dict:
            body = _status(client, model_id, model_status)
            ok = body["status"] == "ok"
            response.status_code = 200 if ok else 503
            log.log(
                logging.INFO if ok else logging.WARNING,
                "api response=status status=%d mcp=%s model=%s duration_ms=%d",
                response.status_code, body["mcp"]["status"], body["model"]["status"],
                _elapsed_ms(started),
            )
            return body

        return _answer("status", work)

    return app
