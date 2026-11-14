"""HTTP API of the back-end (FastAPI): the chats saved in the database, the only service the
front-end talks to.

The OpenAPI document (/openapi.json, page /docs) is generated from the pydantic models below and is
the contract of the front-end. Error bodies are {"error": <code>, "detail": <Italian text>},
except the 422 of FastAPI for a request that does not match the schema.
"""

import json
import logging
import time
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import Body, FastAPI, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import OperationalError

from assistant.api_client import AgentError
from backend.store import (
    MAX_TITLE_LENGTH,
    AgentState,
    ChatNotFoundError,
    ChatRecord,
    ChatStore,
    InvalidInputError,
    MessageRecord,
)

log = logging.getLogger(__name__)

TITLE = "Assistente del laboratorio — back-end"
DESCRIPTION = (
    "Chat salvate nel database: creazione, elenco, lettura, invio di un messaggio all'agente ed "
    "eliminazione. È l'unico servizio che il front-end usa; l'agente si raggiunge solo da qui."
)
UNTITLED = "Nuova chat"  # title shown until the first question gives one
INTERNAL_DETAIL = "errore interno del back-end; dettagli nel log"
DATABASE_DETAIL = "database non disponibile; dettagli nel log"


# --- Requests and responses (specification of step 7, §5) ---

class CreateChatRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"examples": [{"title": "Conversioni di unità"}, {}]}
    )

    title: str | None = Field(None, description=(
        f"Titolo della chat (al più {MAX_TITLE_LENGTH} caratteri). Se manca, lo dà la prima "
        "domanda."
    ))


class ChatInfo(BaseModel):
    id: int = Field(description="Identificativo della chat.")
    title: str = Field(description=f"Titolo della chat ('{UNTITLED}' finché non ne ha uno).")
    created_at: datetime = Field(description="Data di creazione (ISO 8601, UTC).")
    last_message_at: datetime | None = Field(
        description="Data dell'ultimo messaggio (ISO 8601, UTC); null se la chat è vuota."
    )


class ChatMessageInfo(BaseModel):
    id: int = Field(description="Identificativo del messaggio (cresce con l'ordine di invio).")
    role: Literal["user", "assistant"] = Field(description="'user' domanda, 'assistant' risposta.")
    content: str = Field(description="Testo del messaggio.")
    tools_used: list[dict[str, Any]] = Field(description=(
        "Strumenti usati dall'agente per la risposta (name, args, result, ok); vuoto per le "
        "domande."
    ))
    created_at: datetime = Field(description="Data del messaggio (ISO 8601, UTC).")


class ChatDetail(ChatInfo):
    messages: list[ChatMessageInfo] = Field(description="Messaggi della chat in ordine cronologico.")


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"examples": [{"content": "Quanto fa 17 * 23?"}]}
    )

    content: str = Field(description=(
        "Domanda dell'utente; gli spazi iniziali e finali si tolgono e non può restare vuota."
    ))


class SendMessageResponse(BaseModel):
    question: ChatMessageInfo = Field(description="La domanda salvata.")
    answer: ChatMessageInfo = Field(description="La risposta dell'agente salvata.")


class ErrorBody(BaseModel):
    error: str = Field(description="Codice stabile dell'errore.")
    detail: str = Field(description="Messaggio in italiano.")


def _error(description: str) -> dict:
    return {"model": ErrorBody, "description": description}


INVALID_REQUEST = _error("Richiesta non valida (invalid_request).")
CHAT_NOT_FOUND = _error("Chat inesistente (chat_not_found).")
DATABASE_UNAVAILABLE = _error("Database non disponibile (database_unavailable).")
INTERNAL_ERROR = _error("Errore imprevisto (internal_error).")
AGENT_ERROR = _error("L'agente ha risposto con un errore (agent_error).")
SERVICE_UNAVAILABLE = _error(
    "Agente non raggiungibile (agent_unavailable) o database non disponibile "
    "(database_unavailable)."
)
AGENT_TIMEOUT = _error("L'agente non ha risposto entro il tempo massimo (agent_timeout).")


# --- Errors and logs (specification of step 7, §6 and §7) ---

class ApiError(Exception):
    """An error answer: HTTP status, stable code, Italian detail and, for the log only, a cause."""

    def __init__(self, status: int, code: str, detail: str, cause: str | None = None):
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail
        self.cause = cause

    def response(self) -> JSONResponse:
        return JSONResponse({"error": self.code, "detail": self.detail}, status_code=self.status)


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _elapsed_ms(started: float) -> int:
    return round((time.monotonic() - started) * 1000)


def _agent_error(error: AgentError) -> ApiError:
    """Agent switched off → 503, too slow → 504, any other failure of the agent → 502."""
    if error.code == "agent_unreachable":
        return ApiError(503, "agent_unavailable", error.detail)
    if error.code == "agent_timeout":
        return ApiError(504, "agent_timeout", error.detail)
    return ApiError(
        502, "agent_error", f"l'agente ha risposto con un errore ({error.code}): {error.detail}"
    )


def _api_error(error: Exception) -> ApiError | None:
    """The answer for an error of the archive or of the agent; None if it is unexpected."""
    if isinstance(error, ApiError):
        return error
    if isinstance(error, AgentError):
        return _agent_error(error)
    if isinstance(error, ChatNotFoundError):
        return ApiError(404, "chat_not_found", str(error))
    if isinstance(error, InvalidInputError):
        return ApiError(400, "invalid_request", str(error))
    if isinstance(error, OperationalError):  # the driver's message may name host and user
        return ApiError(503, "database_unavailable", DATABASE_DETAIL, cause=str(error.orig))
    return None


def _log_error(prefix: str, error: ApiError, started: float, exc_info: bool = False) -> None:
    """4xx at INFO, 5xx at WARNING, 500 at ERROR (with the traceback when `exc_info`)."""
    if error.status == 500:
        level = logging.ERROR
    else:
        level = logging.INFO if error.status < 500 else logging.WARNING
    cause = f" cause={_json(error.cause.strip())}" if error.cause else ""
    log.log(
        level, "%s status=%d error=%s detail=%s duration_ms=%d%s",
        prefix, error.status, error.code, _json(error.detail), _elapsed_ms(started), cause,
        exc_info=exc_info,
    )


def _answer(prefix: str, work: Callable[[float], Any]):
    """Result of `work(started)` (which logs its own success), or the logged error response.

    `prefix` starts the log line ("backend response=get_chat chat=3"). Errors of the archive
    become their HTTP answer; an unexpected exception becomes 500 internal_error, with the
    traceback in the log only.
    """
    started = time.monotonic()
    try:
        return work(started)
    except Exception as exception:  # every error becomes an answer
        error = _api_error(exception)
        if error is None:
            error = ApiError(500, "internal_error", INTERNAL_DETAIL)
            _log_error(prefix, error, started, exc_info=True)
        else:
            _log_error(prefix, error, started)
        return error.response()


def _chat_info(chat: ChatRecord) -> dict:
    return {
        "id": chat.id,
        "title": chat.title or UNTITLED,
        "created_at": chat.created_at,
        "last_message_at": chat.last_message_at,
    }


def _message_info(message: MessageRecord) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "tools_used": message.tools_used,
        "created_at": message.created_at,
    }


def create_app(*, store: ChatStore, agent) -> FastAPI:
    """App on the chat archive `store`; `agent` answers the questions (an AgentClient or a fake
    with the same `chat` method)."""
    app = FastAPI(title=TITLE, description=DESCRIPTION)

    @app.post(
        "/chats",
        status_code=201,
        response_model=ChatInfo,
        responses={400: INVALID_REQUEST, 500: INTERNAL_ERROR, 503: DATABASE_UNAVAILABLE},
        summary="Crea una chat",
        description=(
            "Crea una chat vuota, con il titolo dato oppure senza: in quel caso il titolo arriva "
            "dalla prima domanda. Il corpo è facoltativo."
        ),
    )
    def create_chat(request: Annotated[CreateChatRequest | None, Body()] = None):
        def work(started: float) -> dict:
            chat = store.create_chat(request.title if request is not None else None)
            log.info(
                "backend response=create_chat status=201 chat=%d duration_ms=%d",
                chat.id, _elapsed_ms(started),
            )
            return _chat_info(chat)

        return _answer("backend response=create_chat", work)

    @app.get(
        "/chats",
        response_model=list[ChatInfo],
        responses={500: INTERNAL_ERROR, 503: DATABASE_UNAVAILABLE},
        summary="Elenca le chat",
        description=(
            "Tutte le chat con titolo e data dell'ultimo messaggio, dalla più recente (ultimo "
            "messaggio o, per una chat vuota, creazione)."
        ),
    )
    def list_chats():
        def work(started: float) -> list[dict]:
            chats = store.list_chats()
            log.info(
                "backend response=list_chats status=200 count=%d duration_ms=%d",
                len(chats), _elapsed_ms(started),
            )
            return [_chat_info(chat) for chat in chats]

        return _answer("backend response=list_chats", work)

    @app.get(
        "/chats/{chat_id}",
        response_model=ChatDetail,
        responses={404: CHAT_NOT_FOUND, 500: INTERNAL_ERROR, 503: DATABASE_UNAVAILABLE},
        summary="Legge una chat",
        description="La chat con tutti i suoi messaggi in ordine cronologico.",
    )
    def get_chat(chat_id: int):
        def work(started: float) -> dict:
            chat, messages = store.get_chat(chat_id)
            log.info(
                "backend response=get_chat chat=%d status=200 messages=%d duration_ms=%d",
                chat_id, len(messages), _elapsed_ms(started),
            )
            return {**_chat_info(chat), "messages": [_message_info(m) for m in messages]}

        return _answer(f"backend response=get_chat chat={chat_id}", work)

    @app.post(
        "/chats/{chat_id}/messages",
        status_code=201,
        response_model=SendMessageResponse,
        responses={
            400: INVALID_REQUEST, 404: CHAT_NOT_FOUND, 500: INTERNAL_ERROR, 502: AGENT_ERROR,
            503: SERVICE_UNAVAILABLE, 504: AGENT_TIMEOUT,
        },
        summary="Invia un messaggio",
        description=(
            "Salva la domanda, la manda all'agente con la cronologia e il riassunto della chat, "
            "poi salva e restituisce la risposta con gli strumenti usati. Se l'agente non risponde "
            "la domanda resta nella chat senza risposta e la cronologia dell'agente non cambia."
        ),
    )
    def send_message(chat_id: int, request: SendMessageRequest):
        log.info(
            "backend request=send_message chat=%d chars=%d", chat_id, len(request.content)
        )

        def work(started: float) -> dict:
            question, state = store.add_question(chat_id, request.content)
            log.info(
                "backend agent_call chat=%d history=%d summary_chars=%d",
                chat_id, len(state.history), len(state.summary),
            )
            result = agent.chat(state.history, state.summary, message=question.content)
            answer = store.add_answer(
                chat_id, result["reply"], result["tools_used"],
                AgentState(history=result["history"], summary=result["summary"]),
            )
            log.info(
                "backend response=send_message chat=%d status=201 tools=%s reply_chars=%d "
                "duration_ms=%d",
                chat_id, ",".join(str(tool.get("name")) for tool in answer.tools_used),
                len(answer.content), _elapsed_ms(started),
            )
            return {"question": _message_info(question), "answer": _message_info(answer)}

        return _answer(f"backend response=send_message chat={chat_id}", work)

    @app.delete(
        "/chats/{chat_id}",
        status_code=204,
        response_class=Response,
        responses={404: CHAT_NOT_FOUND, 500: INTERNAL_ERROR, 503: DATABASE_UNAVAILABLE},
        summary="Elimina una chat",
        description="Elimina la chat e tutti i suoi messaggi.",
    )
    def delete_chat(chat_id: int):
        def work(started: float) -> Response:
            store.delete_chat(chat_id)
            log.info(
                "backend response=delete_chat chat=%d status=204 duration_ms=%d",
                chat_id, _elapsed_ms(started),
            )
            return Response(status_code=204)

        return _answer(f"backend response=delete_chat chat={chat_id}", work)

    return app
