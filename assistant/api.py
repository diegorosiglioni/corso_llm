"""HTTP service of the agent (FastAPI): the same graph as the terminal, without conversations.

History and summary come from the caller and go back updated; the service keeps open only the
MCP client and the models. The OpenAPI document is generated from the pydantic models below
(/openapi.json, page /docs). Error bodies are {"error": <code>, "detail": <Italian text>}, except
the 422 of FastAPI for a body that does not match the schema.
"""

import json
import logging
import time
from typing import Annotated, Any, Literal

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel, ConfigDict, Field

from assistant.agent import messages_from_json, messages_to_json, run_turn
from assistant.commands import (
    PromptGetError,
    PromptListError,
    PromptRejectedError,
    resolve_prompt,
)

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


CHAT_ERRORS = {
    400: {"model": ErrorBody, "description": (
        "Richiesta non valida (invalid_request), cronologia non valida (invalid_history) o prompt "
        "rifiutato dal controllo dell'host (prompt_rejected)."
    )},
    502: {"model": ErrorBody, "description": (
        "Prompt non ottenibile dal server MCP o non utilizzabile (prompt_unavailable)."
    )},
    503: {"model": ErrorBody, "description": "Elenco dei prompt non disponibile (mcp_unavailable)."},
}


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
    result = run_turn(graph, history, request.summary, _opening(client, request))
    return {
        "reply": result.reply,
        "tools_used": result.tools_used,
        "history": messages_to_json(result.history),
        "summary": result.summary,
    }


def _log_error(endpoint: str, error: ApiError, started: float) -> None:
    log.log(
        logging.INFO if error.status < 500 else logging.WARNING,
        "api response=%s status=%d error=%s detail=%s duration_ms=%d",
        endpoint, error.status, error.code, _json(error.detail), _elapsed_ms(started),
    )


def _elapsed_ms(started: float) -> int:
    return round((time.monotonic() - started) * 1000)


def create_app(*, graph, client) -> FastAPI:
    """App on the compiled `graph` and the MCP `client` (real or fake)."""
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
        started = time.monotonic()
        log.info(
            "api request=chat kind=%s history=%d summary_chars=%d",
            _kind(request), len(request.history), len(request.summary),
        )
        try:
            body = _chat(graph, client, request)
        except ApiError as error:
            _log_error("chat", error, started)
            return error.response()
        log.info(
            "api response=chat status=200 tools=%s reply_chars=%d history=%d duration_ms=%d",
            ",".join(str(tool["name"]) for tool in body["tools_used"]),
            len(body["reply"]), len(body["history"]), _elapsed_ms(started),
        )
        return body

    return app
