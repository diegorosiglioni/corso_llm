"""Stateless agent turn and JSON form of the messages.

The same turn serves the in-process terminal session and the HTTP service: history and summary
come from the caller and go back updated, nothing is kept between two calls.
"""

import json
from dataclasses import dataclass
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

EMPTY_REPLY = "(Il modello non ha fornito una risposta.)"


@dataclass(frozen=True)
class TurnResult:
    reply: str  # text of the last message, EMPTY_REPLY if empty
    tools_used: list[dict]  # {"name", "args", "result", "ok"} in execution order
    history: list[BaseMessage]  # updated history (after the summary, if any)
    summary: str  # updated summary


def run_turn(
    graph, history: list[BaseMessage], summary: str, messages: list[BaseMessage]
) -> TurnResult:
    """Runs one turn opened by `messages` on `history` and `summary`, left untouched.

    The graph's exceptions (for example openai.APIError) reach the caller.
    """
    if not messages:
        raise ValueError("nessun messaggio per aprire il turno")
    # Copies: add_messages assigns the missing ids by changing the messages it receives.
    opening = [m.model_copy(update={"id": str(uuid4())}) for m in messages]
    result = graph.invoke({
        "messages": [m.model_copy() for m in history] + opening,
        "summary": summary,
        "steps": 0,
        "reviews": 0,
    })
    new_history = list(result["messages"])
    # The summary node removes messages from the start only and keeps at least the last one,
    # which is the last opening message: the turn is what comes after it.
    last_id = opening[-1].id
    start = next(i for i, m in enumerate(new_history) if m.id == last_id) + 1
    return TurnResult(
        reply=new_history[-1].text.strip() or EMPTY_REPLY,
        tools_used=_tools_used(new_history[start:]),
        history=new_history,
        summary=result["summary"],
    )


def _decode(content: str):
    try:
        return json.loads(content)
    except (TypeError, ValueError):
        return content


def _tools_used(turn: list[BaseMessage]) -> list[dict]:
    """One entry for each tool answer of the turn, with the arguments of its call."""
    calls: dict[str, dict] = {}
    used = []
    for message in turn:
        if isinstance(message, AIMessage):
            for call in list(message.tool_calls) + list(message.invalid_tool_calls):
                calls[call["id"]] = call
        elif isinstance(message, ToolMessage):
            call = calls.get(message.tool_call_id, {})
            result = _decode(message.content)
            used.append({
                "name": message.name or call.get("name"),
                "args": call.get("args"),
                "result": result,
                "ok": not (isinstance(result, dict) and "error" in result),
            })
    return used


# --- JSON form (specification of step 6, §4) ---

def _content(message: BaseMessage) -> str:
    return message.content if isinstance(message.content, str) else message.text


def messages_to_json(messages: list[BaseMessage]) -> list[dict]:
    """Messages in the JSON form of the API; absent or empty fields are left out."""
    data = []
    for message in messages:
        if isinstance(message, HumanMessage):
            item = {"role": "user", "content": _content(message)}
            if message.name:
                item["name"] = message.name
        elif isinstance(message, AIMessage):
            item = {"role": "assistant", "content": _content(message)}
            if message.tool_calls:
                item["tool_calls"] = [
                    {"id": c["id"], "name": c["name"], "args": c["args"]}
                    for c in message.tool_calls
                ]
            if message.invalid_tool_calls:
                item["invalid_tool_calls"] = [
                    {"id": c["id"], "name": c["name"], "args": c.get("args"),
                     "error": c.get("error")}
                    for c in message.invalid_tool_calls
                ]
        elif isinstance(message, ToolMessage):
            item = {"role": "tool", "content": _content(message),
                    "tool_call_id": message.tool_call_id}
            if message.name:
                item["name"] = message.name
        else:
            raise ValueError(f"tipo di messaggio non previsto: {type(message).__name__}")
        data.append(item)
    return data


_FIELDS = {
    "user": {"role", "content", "name"},
    "assistant": {"role", "content", "tool_calls", "invalid_tool_calls"},
    "tool": {"role", "content", "tool_call_id", "name"},
}
_CALL_FIELDS = {
    "tool_calls": {"id", "name", "args"},
    "invalid_tool_calls": {"id", "name", "args", "error"},
}


def _is_text(value) -> bool:
    return isinstance(value, str) and value != ""


def _check_call(call, kind: str) -> dict:
    """The call as LangChain wants it; ValueError with the reason if it is not valid."""
    if not isinstance(call, dict):
        raise ValueError("deve essere un oggetto")
    for key in call:
        if key not in _CALL_FIELDS[kind]:
            raise ValueError(f"campo sconosciuto '{key}'")
    required = ("id", "name", "args") if kind == "tool_calls" else ("id", "name")
    for key in required:
        if key not in call:
            raise ValueError(f"manca il campo '{key}'")
    for key in ("id", "name"):
        if not _is_text(call[key]):
            raise ValueError(f"il campo '{key}' deve essere un testo non vuoto")
    if kind == "tool_calls":
        if not isinstance(call["args"], dict):
            raise ValueError("il campo 'args' deve essere un oggetto")
        return {"id": call["id"], "name": call["name"], "args": call["args"],
                "type": "tool_call"}
    for key in ("args", "error"):
        if call.get(key) is not None and not isinstance(call[key], str):
            raise ValueError(f"il campo '{key}' deve essere un testo o null")
    return {"id": call["id"], "name": call["name"], "args": call.get("args"),
            "error": call.get("error"), "type": "invalid_tool_call"}


def _message_from_json(item) -> BaseMessage:
    """One message; ValueError with the reason (without the position) if it is not valid."""
    if not isinstance(item, dict):
        raise ValueError("deve essere un oggetto")
    if "role" not in item:
        raise ValueError("manca il campo 'role'")
    role = item["role"]
    if role == "system":
        raise ValueError("i messaggi di sistema non sono ammessi")
    if role not in _FIELDS:
        raise ValueError(f"ruolo sconosciuto '{role}'")
    if "content" not in item:
        raise ValueError("manca il campo 'content'")
    if not isinstance(item["content"], str):
        raise ValueError("il campo 'content' deve essere un testo")
    for key in item:
        if key not in _FIELDS[role]:
            raise ValueError(f"campo sconosciuto '{key}' per il ruolo '{role}'")
    if item.get("name") is not None and not isinstance(item["name"], str):
        raise ValueError("il campo 'name' deve essere un testo")
    name = item.get("name") or None
    if role == "user":
        return HumanMessage(item["content"], name=name)
    if role == "tool":
        if "tool_call_id" not in item:
            raise ValueError("manca il campo 'tool_call_id'")
        if not _is_text(item["tool_call_id"]):
            raise ValueError("il campo 'tool_call_id' deve essere un testo non vuoto")
        return ToolMessage(item["content"], tool_call_id=item["tool_call_id"], name=name)
    calls = {}
    for kind in ("tool_calls", "invalid_tool_calls"):
        received = item.get(kind)
        if received is None:
            received = []
        if not isinstance(received, list):
            raise ValueError(f"il campo '{kind}' deve essere un elenco")
        checked = []
        for n, call in enumerate(received, start=1):
            try:
                checked.append(_check_call(call, kind))
            except ValueError as error:
                raise ValueError(f"chiamata {n} di '{kind}' non valida ({error})") from None
        calls[kind] = checked
    ids = [c["id"] for c in calls["tool_calls"] + calls["invalid_tool_calls"]]
    for i, call_id in enumerate(ids):
        if call_id in ids[:i]:
            raise ValueError(f"id di chiamata ripetuto '{call_id}'")
    return AIMessage(
        item["content"], tool_calls=calls["tool_calls"],
        invalid_tool_calls=calls["invalid_tool_calls"],
    )


def messages_from_json(data: list[dict]) -> list[BaseMessage]:
    """History from its JSON form, checked; ValueError with the first problem and its position.

    Besides the fields, it checks the order LM Studio requires: every tool answer replies to a
    call of the assistant message before it, and every call has its answer before the next
    message that is not a tool answer.
    """
    if not isinstance(data, list):
        raise ValueError("la cronologia deve essere un elenco di messaggi")
    messages = []
    pending: dict[str, str] = {}  # id → name of the calls still without an answer
    caller = 0  # position of the assistant message with the pending calls
    for position, item in enumerate(data, start=1):
        try:
            message = _message_from_json(item)
        except ValueError as error:
            raise ValueError(f"messaggio {position}: {error}") from None
        if isinstance(message, ToolMessage):
            if message.tool_call_id not in pending:
                raise ValueError(
                    f"messaggio {position}: risposta di uno strumento senza una chiamata "
                    "corrispondente"
                )
            del pending[message.tool_call_id]
        else:
            if pending:
                raise ValueError(_unanswered(caller, pending, f"prima del messaggio {position}"))
            if isinstance(message, AIMessage):
                pending = {
                    c["id"]: c["name"]
                    for c in list(message.tool_calls) + list(message.invalid_tool_calls)
                }
                caller = position
        messages.append(message)
    if pending:
        raise ValueError(_unanswered(caller, pending, "alla fine della cronologia"))
    return messages


def _unanswered(caller: int, pending: dict[str, str], where: str) -> str:
    call_id, name = next(iter(pending.items()))
    return f"messaggio {caller}: chiamata '{name}' (id '{call_id}') senza risposta {where}"
