# Correzioni di `auto-claude` (F4), sistemazione (F5) e integrazione (F6) — piano

> **Per chi esegue:** OBBLIGATORIO usare superpowers:subagent-driven-development (consigliato) oppure
> superpowers:executing-plans, un task alla volta. I passi usano le caselle (`- [ ]`).

**Obiettivo:** chiudere le 20 correzioni approvate, far rivedere il diff a un revisore indipendente,
sistemare i file del loop e portare `dev` su `auto-claude` con avanzamento rapido, pronti per il
push che l'utente chiederà.

**Architettura:** correzioni piccole e indipendenti, ognuna nel suo modulo (grafo, servizio
dell'agente, client, back-end, pagina, Compose, documentazione), in ordine di rischio: prima R-B1,
poi i messaggi del servizio, il back-end, la pagina, l'ambito e le prove reali dello Step 5, Docker;
infine revisione, sistemazione e verifica completa.

**Strumenti:** Python 3.13, pytest (marcatori `real` e `browser`), FastAPI/Starlette, LangGraph e
langchain-openai, httpx, SQLAlchemy con SQLite e PostgreSQL, Node (`node --test`), Playwright con
Edge e Chrome, Docker Compose, LM Studio (`google/gemma-4-e2b`).

**Specifica:** [`../specs/2026-11-15-correzioni-auto-claude-design.md`](../specs/2026-11-15-correzioni-auto-claude-design.md)

## Vincoli globali

- Branch `auto-claude` per tutto; niente commit su `dev` o `main` prima del Task 16; nessun push,
  nessun `--force`, nessun merge che non sia `--ff-only`.
- Commit in Conventional Commits in italiano (`fix(agente): …`, `test(reali): …`, `docs: …`), con
  `git status`, controllo del diff e staging selettivo; ultima riga del messaggio
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- TDD: il test nuovo o cambiato si esegue e si vede fallire prima della correzione; dopo la
  correzione, il test e poi `.\.venv\Scripts\python.exe -m pytest` completo (oggi `1003 passed, 90
  deselected`) devono passare prima del commit.
- Codice, identificativi e commenti in inglese; messaggi d'errore, log descrittivi per l'utente,
  testi e documentazione in italiano.
- Nessuna dipendenza nuova.
- Comandi da PowerShell nella radice; Python sempre `.\.venv\Scripts\python.exe`.
- Prova reale fallita: si ripete una volta; se passa è «instabile» e si annota in `PROGRESS.md`, se
  fallisce di nuovo è un problema: ci si ferma e si porta all'utente (salvo i gradini di R-A1, Task
  10). Mai simulare l'esito.
- Ogni resoconto distingue **modello simulato** (test senza LM Studio) da **modello vero**.
- Prove reali (sessione PowerShell con le variabili del Task 0):
  `$env:LMSTUDIO_BASE_URL = "http://localhost:1234/v1"`, `$env:LMSTUDIO_MODEL = "google/gemma-4-e2b"`,
  `$env:TEST_DATABASE_URL = "postgresql://lab:labprova@127.0.0.1:5433/assistente"`.

## Punti di attenzione (Review Focus)

Casi che la specifica implica e che nessun test di oggi esercita, con il comportamento atteso; ogni
riga ha il suo test nel task indicato:
1. **Chiamate malformate al limite dei passaggi** (`MAX_STEPS` raggiunto con id vuoti o ripetuti):
   il nodo `limit` risponde agli id normalizzati e la cronologia torna accettata → Task 1.
2. **Middleware del charset sui flussi**: `/chat/stream` e `/messages/stream` restano
   `text/event-stream`, le intestazioni CORS restano → Task 4.
3. **NUL nel titolo di `POST /chats` e nella domanda di `/messages/stream`**: `400` JSON prima di
   qualsiasi flusso, nessuna chiamata all'agente → Task 5.
4. **Nome di prompt lunghissimo**: la riga `api request=… kind=prompt name=…` lo tronca a 64
   caratteri, oltre al rifiuto `400` → Task 2.
5. **Errore dell'agente con detail vuoto nella pagina**: niente parentesi vuote nel messaggio →
   Task 6.

---

### Task 0: Ambiente e punto di partenza

- [x] **Passo 1:** `git branch --show-current` → `auto-claude`; `git status --short` vuoto; ultimo
  commit quello del piano.
- [x] **Passo 2:** `docker compose ps` → nessun servizio attivo (altrimenti `docker compose down`);
  porte 8000, 8001, 8080 libere (`Get-NetTCPConnection -LocalPort 8000,8001,8080 -State Listen`
  senza risultati).
- [x] **Passo 3:** LM Studio: `& "$HOME\.lmstudio\bin\lms.exe" server start`, poi
  `& "$HOME\.lmstudio\bin\lms.exe" load google/gemma-4-e2b --context-length 8192 -y`;
  `Invoke-RestMethod http://localhost:1234/v1/models` elenca `google/gemma-4-e2b`.
- [x] **Passo 4:** `docker start assistente-postgres` (lo ricrea il Task 11).
- [x] **Passo 5:** `.\.venv\Scripts\python.exe -m pytest` → `1003 passed, 90 deselected`.

---

### Task 1: R-B1 · Chiamate a strumento normalizzate nel nodo `llm`

**File:**
- Modifica: `assistant/graph.py` (`llm_node`, nuova funzione e costante)
- Test: `tests/test_graph.py`, `tests/test_api.py`, `tests/test_model.py`, `tests/test_real.py`

**Interfacce:**
- Produce: `UNNAMED_TOOL = "unnamed_tool"` e
  `normalize_tool_calls(message: AIMessage) -> tuple[AIMessage, list[dict]]` in `assistant/graph.py`.
  Restituisce lo stesso oggetto e `[]` se nulla cambia; altrimenti una copia
  (`message.model_copy(update=…)`) e un elemento `{"call_id": nuovo, "original_id": …,
  "original_name": …}` per ogni chiamata cambiata.

Regola (scorre `tool_calls` e poi `invalid_tool_calls`, in ordine): id valido se testo non vuoto e
non già visto nel messaggio, altrimenti `f"call_{uuid4().hex}"`; nome valido se testo non vuoto,
altrimenti `UNNAMED_TOOL`.

- [x] **Passo 1: test del grafo che falliscono** (in `tests/test_graph.py`)

```python
def malformed_reply() -> AIMessage:
    tokyo = {"timezone": "Asia/Tokyo"}
    return AIMessage("", tool_calls=[
        {"name": "get_current_time", "args": tokyo, "id": ""},
        {"name": "get_current_time", "args": tokyo, "id": None},
        {"name": "", "args": {}, "id": "c1"},
        {"name": "get_current_time", "args": tokyo, "id": "c1"},
    ], invalid_tool_calls=[
        {"name": None, "args": "{", "id": "c1", "error": None, "type": "invalid_tool_call"},
    ])


def test_malformed_tool_calls_are_normalized(caplog):  # R-B1
    caplog.set_level(logging.WARNING)
    model = FakeModel([malformed_reply(), AIMessage("fatto")])
    result = start_turn(model)
    asked = result["messages"][1]
    calls = list(asked.tool_calls) + list(asked.invalid_tool_calls)
    ids = [c["id"] for c in calls]
    assert all(ids) and len(set(ids)) == 5
    assert ids[2] == "c1"  # the first valid id is kept
    assert [c["name"] for c in calls] == [
        "get_current_time", "get_current_time", UNNAMED_TOOL, "get_current_time", UNNAMED_TOOL,
    ]
    answers = {m.tool_call_id: m for m in result["messages"] if isinstance(m, ToolMessage)}
    assert set(answers) == set(ids)
    assert "Strumento sconosciuto: 'unnamed_tool'." in answers[ids[2]].content
    assert model.calls[1][2] == asked  # the second call of the model gets the normalized ids
    lines = [r.getMessage() for r in caplog.records if "tool_call_normalized" in r.getMessage()]
    assert len(lines) == 5
    assert lines[2] == (f'step=1/5 tool_call_normalized call_id=c1 original_id="c1" '
                        f'original_name=""')


def test_valid_tool_calls_are_left_unchanged(caplog):
    caplog.set_level(logging.WARNING)
    reply = tool_call()
    assert normalize_tool_calls(reply) == (reply, [])
    result = start_turn(FakeModel([reply, AIMessage("fatto")]))
    assert result["messages"][1].tool_calls[0]["id"] == "c1"
    assert "tool_call_normalized" not in caplog.text


def test_limit_answers_the_normalized_ids():  # Review Focus 1
    result = start_turn(FakeModel([malformed_reply()]), max_steps=1)
    asked = result["messages"][1]
    ids = {c["id"] for c in list(asked.tool_calls) + list(asked.invalid_tool_calls)}
    answered = {m.tool_call_id for m in result["messages"] if isinstance(m, ToolMessage)}
    assert answered == ids
    messages_from_json(messages_to_json(result["messages"]))  # no ValueError
```

- [x] **Passo 2: test del servizio che falliscono** (in `tests/test_api.py`)

```python
MALFORMED = [
    pytest.param([{"name": "get_current_time", "args": {"timezone": "Asia/Tokyo"}, "id": ""}], [],
                 id="empty-id"),
    pytest.param([{"name": "get_current_time", "args": {"timezone": "Asia/Tokyo"}, "id": None}], [],
                 id="null-id"),
    pytest.param([{"name": "get_current_time", "args": {"timezone": "Asia/Tokyo"}, "id": "c1"},
                  {"name": "get_current_time", "args": {"timezone": "Europe/Rome"}, "id": "c1"}], [],
                 id="repeated-id"),
    pytest.param([{"name": "", "args": {}, "id": "c1"}], [], id="empty-name"),
    pytest.param([], [{"name": None, "args": "{", "id": "c1", "error": None,
                       "type": "invalid_tool_call"}], id="null-name"),
]


@pytest.mark.parametrize(("tool_calls", "invalid"), MALFORMED)
def test_history_with_malformed_calls_is_accepted_again(tool_calls, invalid):  # R-B1
    reply = AIMessage("", tool_calls=tool_calls, invalid_tool_calls=invalid)
    service = api(FakeModel([reply, AIMessage("ok"), AIMessage("ancora")]))
    first = service.post("/chat", json={"message": "ore?"})
    assert first.status_code == 200, first.text
    second = service.post("/chat", json={"message": "di nuovo", "history": first.json()["history"]})
    assert second.status_code == 200, second.text


@pytest.mark.parametrize(("tool_calls", "invalid"), MALFORMED)
def test_stream_history_with_malformed_calls_is_accepted_again(tool_calls, invalid):
    reply = AIMessage("", tool_calls=tool_calls, invalid_tool_calls=invalid)
    service = api(StreamingFakeModel(replies=[reply, AIMessage("ok"), AIMessage("ancora")]))
    events = stream(service, {"message": "ore?"})
    done = events[-1][1]
    assistant = next(m for m in done["history"] if m.get("tool_calls") or m.get("invalid_tool_calls"))
    sent = [c["id"] for c in assistant.get("tool_calls", []) + assistant.get("invalid_tool_calls", [])]
    assert [d["id"] for name, d in events if name == "tool_start"] == sent
    assert [d["id"] for name, d in events if name == "tool_end"] == sent
    again = service.post("/chat", json={"message": "di nuovo", "history": done["history"]})
    assert again.status_code == 200, again.text
```

- [x] **Passo 3: test della richiesta a LM Studio** (in `tests/test_model.py`):
  `test_request_payload_uses_the_normalized_ids` normalizza `malformed_reply()` (importato da
  `test_graph` o ricopiato), costruisce `ChatOpenAI(model="m", base_url="http://localhost:9/v1",
  api_key="x")` e chiama `_get_request_payload([HumanMessage("ore?"), normalized])` (metodo privato,
  nessuna rete): gli id di `payload["messages"][1]["tool_calls"]` sono quelli del messaggio
  normalizzato e i nomi comprendono `unnamed_tool`.
- [x] **Passo 4:** `.\.venv\Scripts\python.exe -m pytest tests/test_graph.py tests/test_api.py tests/test_model.py -k "malformed or normalized or unchanged or limit_answers"`
  → falliscono (`ImportError` di `normalize_tool_calls`, poi `400 invalid_history`).
- [x] **Passo 5:** implementare `normalize_tool_calls` e chiamarla in `llm_node` subito dopo
  `model.invoke`, con una riga WARNING per ogni cambio:
  `"step=%d/%d tool_call_normalized call_id=%s original_id=%s original_name=%s"` (originali con
  `json.dumps(…, ensure_ascii=False)`); docstring del modulo e di `llm_node` aggiornate.
- [x] **Passo 6:** i test del Passo 4 passano; poi `pytest` completo verde.
- [x] **Passo 7: prova reale** (in `tests/test_real.py`): `PartialFirstAnswer` accetta come seconda
  argomento anche un `AIMessage` (un testo resta `AIMessage(text)`). Nuovo test:

```python
MALFORMED_FIRST = AIMessage("", tool_calls=[
    {"name": "", "args": {}, "id": "c1"},
    {"name": "calculate", "args": {"expression": "17 * 23"}, "id": "c1"},
])


def test_lm_studio_accepts_a_normalized_history(config, tmp_path, caplog):  # R-B1
    caplog.set_level(logging.WARNING, logger="assistant.graph")
    wrap = lambda model: PartialFirstAnswer(model, MALFORMED_FIRST)  # noqa: E731
    with open_session(config, tmp_path / "notes.sqlite3", wrap_agent=wrap) as (session, _):
        reply = session.send(QUESTION)
        history = messages_from_json(messages_to_json(session.messages))  # no ValueError
        second = session.send("E quanto fa 391 + 9?")
    assert "tool_call_normalized" in caplog.text, caplog.text
    assert "391" in reply, reply
    assert "400" in second, (second, history)
```

  `.\.venv\Scripts\python.exe -m pytest tests/test_real.py -m real -v -k normalized_history` →
  `1 passed`. Se LM Studio rifiuta la cronologia (`BadRequestError`): fermarsi e chiedere
  all'utente (specifica §13).
- [x] **Passo 8: commit**

```bash
git add assistant/graph.py tests/test_graph.py tests/test_api.py tests/test_model.py tests/test_real.py
git commit -m "fix(agente): chiamate a strumento normalizzate nel nodo llm"
```

---

### Task 2: R-A6 e R-A7 · Nome del prompt nel log e limiti degli argomenti

**File:**
- Modifica: `assistant/api.py` (`_kind`, `_prepare`, nuove costanti e `_check_prompt_size`),
  `README.md` (sezione «Un `/prompt` non funziona»)
- Test: `tests/test_api.py`

**Interfacce:**
- Produce in `assistant/api.py`: `MAX_PROMPT_NAME = 64`, `MAX_PROMPT_ARGUMENTS = 10`,
  `MAX_ARGUMENT_NAME = 64`, `MAX_ARGUMENT_VALUE = 1000`;
  `_check_prompt_size(prompt: PromptRequest) -> None`, che solleva
  `ApiError(400, "prompt_rejected", detail)`.

Detail esatti:
- `f"il nome del prompt supera {MAX_PROMPT_NAME} caratteri"`
- `f"il prompt ha più di {MAX_PROMPT_ARGUMENTS} argomenti"`
- `f"un nome di argomento supera {MAX_ARGUMENT_NAME} caratteri"`
- `f"il valore dell'argomento '{key}' supera {MAX_ARGUMENT_VALUE} caratteri"`

- [x] **Passo 1: test che falliscono**
  - `test_chat_with_a_prompt`: riga attesa
    `'api request=chat kind=prompt name="spiega" history=0 summary_chars=0'`.
  - `test_prompt_name_is_escaped_in_the_log(caplog)`: prompt `"a\nb"` → la prima riga di
    `api_lines(caplog)` è `'api request=chat kind=prompt name="a\\nb" history=0 summary_chars=0'`
    (una sola riga, nessun record che cominci con `b`).
  - `test_long_prompt_name_is_cut_in_the_log(caplog)` (Review Focus 4): nome `"p" * 5000` → la riga
    contiene `name="` + `"p" * 64` + `"` e non contiene `"p" * 65`.
  - `test_prompt_size_limits(endpoint, prompt, detail, caplog)`, parametrizzato su
    `endpoint in ("/chat", "/chat/stream")` e sui quattro casi (nome di 65 caratteri; 11 argomenti;
    un nome di argomento di 65; `{"argomento": "x" * 1001}`): `400`,
    `{"error": "prompt_rejected", "detail": detail}`, `client.prompt_gets == []`, `prompts/list`
    mai chiamato (`client.prompt_lists == 0`), `"x" * 1001`
    assente da `caplog.text`.
  - `test_prompt_at_the_size_limits_passes`: nome di 64, 10 argomenti con nomi di 64 e valori di
    1000 → la richiesta arriva al controllo dell'host (`400 prompt_rejected` con il motivo di
    `check_request`, non quello dei limiti), cioè `prompts/list` viene chiamato.
- [x] **Passo 2:** eseguirli → falliscono.
- [x] **Passo 3:** `_kind` scrive `f"prompt name={_json(request.prompt.name[:MAX_PROMPT_NAME])}"`;
  `_prepare` chiama `_check_prompt_size` dopo i controlli di `message` e prima di `_history`.
- [x] **Passo 4:** test verdi; `pytest` completo verde.
- [x] **Passo 5:** README: `kind=prompt name="…"` e una riga sui limiti (con il messaggio della CLI
  «Errore nel comando: …»).
- [x] **Passo 6: commit** `fix(servizio): nome del prompt in JSON nel log e limiti degli argomenti`.

---

### Task 3: R-B5 e R-A5 · Messaggi d'errore di LM Studio e dei prompt

**File:**
- Modifica: `assistant/api.py` (`_model_error`), `assistant/commands.py` (testi di
  `PromptGetError`), `assistant/terminal.py`, `README.md` (diagnosi e «Prompt MCP»)
- Test: `tests/test_api.py`, `tests/test_commands.py`, `tests/test_terminal.py`

- [x] **Passo 1: test che falliscono**
  - `test_lm_studio_errors` e `test_lm_studio_errors_during_the_stream`, caso `timeout`: detail
    `"LM Studio non ha risposto in tempo: Request timed out."`, stesso `503 model_unavailable`.
  - `test_value_rejected_by_the_server` (`test_commands.py`): `str(raised.value) ==
    "il prompt 'spiega' non è disponibile (Livello non valido: 'esperto'. Valori ammessi: base, intermedio, avanzato)"`;
    allo stesso modo il caso «non è utilizzabile» (riga 362) senza punto finale tra parentesi;
    i detail attesi in `tests/test_api.py` (righe 239 e 250) di conseguenza.
  - `test_prompt_unavailable_points_to_the_list` (`test_terminal.py`): con
    `AgentError("prompt_unavailable", "il prompt 'spiega' non è disponibile (Livello non valido: 'esperto'. Valori ammessi: base, intermedio, avanzato)")`
    l'uscita è `["Errore nel prompt: il prompt 'spiega' non è disponibile (Livello non valido: 'esperto'. Valori ammessi: base, intermedio, avanzato). Scrivi /prompts per l'elenco dei prompt.", "Arrivederci!"]`.
- [x] **Passo 2:** eseguirli → falliscono.
- [x] **Passo 3:** `_model_error` controlla `openai.APITimeoutError` prima di
  `APIConnectionError` (detail `f"LM Studio non ha risposto in tempo: {error}"`); in
  `commands.py` il motivo tra parentesi è `str(error).rstrip(".")` nei due `PromptGetError`; in
  `terminal.py` la costante `PROMPT_UNAVAILABLE = "prompt_unavailable"` e il ramo
  `f"Errore nel prompt: {error.phrase}. {LIST_HINT}"`.
- [x] **Passo 4:** test verdi; `pytest` completo verde.
- [x] **Passo 5:** README allineato (riga del tempo scaduto nella diagnosi di LM Studio; esempio
  d'errore del prompt).
- [x] **Passo 6: commit** `fix(servizio): messaggi chiari per il tempo scaduto di LM Studio e i prompt non disponibili`.

---

### Task 4: R-B7 · `charset=utf-8` nelle risposte JSON

**File:**
- Modifica: `assistant/api.py`, `backend/api.py` (stesso middleware in entrambi: i due servizi non
  condividono moduli oltre al client e alla configurazione)
- Test: `tests/test_api.py`, `tests/test_backend_api.py`

**Interfacce:**
- Produce in ciascun modulo `class Utf8JsonMiddleware`: middleware ASGI puro (non
  `BaseHTTPMiddleware`, che interferisce con i flussi) che, nel messaggio `http.response.start`,
  sostituisce l'intestazione `content-type: application/json` con
  `application/json; charset=utf-8`; registrato con `app.add_middleware(Utf8JsonMiddleware)`.
  L'OpenAPI non cambia (il contratto `frontend/backend-openapi.json` resta uguale).

- [x] **Passo 1: test che falliscono**
  - `test_json_answers_declare_utf8(method, path, body)` in `tests/test_api.py`, parametrizzato:
    `GET /prompts` (200), `GET /status` (200), `POST /chat` con `{}` (400), `POST /chat` con un
    campo in più (422), `POST /chat/stream` con `{}` (400 prima del flusso): intestazione esatta
    `"application/json; charset=utf-8"`.
  - `test_errors_before_the_stream_are_the_json_answers_of_chat`: l'uguaglianza su
    `content-type` diventa `"application/json; charset=utf-8"`.
  - Lo stesso in `tests/test_backend_api.py`: `GET /chats` (200), `GET /chats/42` (404),
    `POST /chats` con un campo in più (422), `POST /chats/{id}/messages/stream` con contenuto vuoto
    (400 prima del flusso).
  - `test_streams_keep_their_media_type_and_cors` (Review Focus 2): `/chat/stream` riuscito →
    `text/event-stream`; nel back-end, con `cors_http`, `/messages/stream` riuscito →
    `text/event-stream` e `access-control-allow-origin` presente.
- [x] **Passo 2:** eseguirli → falliscono (manca il charset).
- [x] **Passo 3:** middleware nei due moduli.
- [x] **Passo 4:** test verdi; `.\.venv\Scripts\python.exe -m pytest tests/test_frontend_contract.py`
  verde senza rigenerare il contratto; `pytest` completo verde.
- [x] **Passo 5: commit** `fix(api): charset utf-8 nelle risposte JSON di agente e back-end`.

---

### Task 5: R-C3 · Carattere NUL rifiutato, parametri SQL nascosti

**File:**
- Modifica: `backend/store.py` (`create_chat`, `add_question`), `backend/db.py`
  (`create_db_engine`)
- Test: `tests/test_backend_store.py`, `tests/test_backend_api.py`

Detail esatti: `"il messaggio contiene un carattere non ammesso (NUL)"`,
`"il titolo contiene un carattere non ammesso (NUL)"`.

- [x] **Passo 1: test che falliscono**
  - `test_backend_store.py` (girano su SQLite e, con `-m real`, su PostgreSQL):
    `test_nul_in_the_question_is_rejected(store)` → `InvalidInputError` con il detail, chat senza
    messaggi; `test_nul_in_the_title_is_rejected(store)` → `InvalidInputError`, nessuna chat
    creata; `test_engine_hides_sql_parameters()` → `create_db_engine("sqlite://").hide_parameters
    is True` e lo stesso per un URL PostgreSQL (motore creato senza connettersi).
  - `test_backend_api.py` (Review Focus 3): `POST /chats` con titolo `"a\x00b"` → `400
    invalid_request`; `POST /chats/{id}/messages` e `/messages/stream` con `"ciao\x00"` → `400`
    JSON, agente mai chiamato (`raising(AssertionError)` come agente finto), testo assente dal log.
- [x] **Passo 2:** eseguirli → falliscono.
- [x] **Passo 3:** controllo di `"\x00"` dopo `strip()` e dopo il controllo del vuoto;
  `hide_parameters=True` nei due `create_engine`.
- [x] **Passo 4:** test verdi; `pytest` completo verde.
- [x] **Passo 5: commit** `fix(backend): carattere NUL rifiutato e parametri SQL fuori dal log`.

---

### Task 6: R-D6 · Errore dell'agente senza ripetizioni

**File:**
- Modifica: `backend/api.py` (`_agent_error`), `frontend/static/texts.js` (`errorMessage`),
  `README.md` (diagnosi della pagina)
- Test: `tests/test_backend_api.py`, `tests/frontend/texts.test.mjs`, `tests/frontend/api.test.mjs`
  se ne dipende, `tests/test_frontend_browser.py` (righe 570 e 734)

**Interfacce:**
- `_agent_error` per gli errori diversi da `agent_unreachable` e `agent_timeout` restituisce
  `ApiError(502, "agent_error", error.detail, cause=error.code)`: il codice dell'agente va nella
  riga di log come `cause="model_unavailable"`.

- [x] **Passo 1: test che falliscono**
  - `AGENT_FAILURES`: detail `"LM Studio non raggiungibile: Connection error."` e
    `"risposta inattesa dell'agente (HTTP 200)"`; riga di log attesa con
    ` cause="model_unavailable"` (e `cause="bad_response"`) dopo `duration_ms=N`.
  - `test_history_rejected_by_the_agent_is_502`: detail che comincia con `"messaggio 1:"`.
  - I casi dello streaming (righe 906, 958, 967) allo stesso modo.
  - `texts.test.mjs`: `message(502, "agent_error", "spento.")` →
    `"L'assistente non è riuscito a rispondere (spento). La domanda è salvata nella chat: riprova."`;
    lo stesso con stato 200 (evento `error`); con detail `""` →
    `"L'assistente non è riuscito a rispondere. La domanda è salvata nella chat: riprova."`
    (Review Focus 5).
  - `test_frontend_browser.py`: testo atteso nuovo nelle due prove.
- [x] **Passo 2:** `pytest tests/test_backend_api.py tests/test_frontend_js.py` → falliscono.
- [x] **Passo 3:** correzione in `_agent_error` e nella chiave `"502 agent_error"` di `TEXTS`/`known`.
- [x] **Passo 4:** test verdi; `pytest` completo verde; `pytest -m browser` con Edge verde (modello
  simulato, browser vero).
- [x] **Passo 5:** README allineato.
- [x] **Passo 6: commit** `fix(frontend): messaggio d'errore dell'agente senza ripetizioni`.

---

### Task 7: R-C6 · Connessione di `AgentClient.chat` con 10 s

**File:**
- Modifica: `assistant/api_client.py` (`STREAM_CONNECT_TIMEOUT` → `CONNECT_TIMEOUT`, `_request`)
- Test: `tests/test_api_client.py`

- [x] **Passo 1: test che fallisce** — in `test_timeouts`:
  `requests[1].extensions["timeout"] == {"connect": 10.0, "read": 600.0, "write": 600.0, "pool": 600.0}`
  e `requests[0].extensions["timeout"]["connect"] == 10.0`; import di `CONNECT_TIMEOUT` al posto di
  `STREAM_CONNECT_TIMEOUT` (riga 305).
- [x] **Passo 2:** eseguirlo → fallisce.
- [x] **Passo 3:** `_request` passa `httpx.Timeout(timeout, connect=CONNECT_TIMEOUT)`;
  `chat_stream` usa `CONNECT_TIMEOUT`.
- [x] **Passo 4:** test verdi; `pytest` completo verde.
- [x] **Passo 5: commit** `fix(client): connessione all'agente entro 10 s anche per chat`.

---

### Task 8: R-A3 · File delle preferenze obbligatorio in `server_command`

**File:**
- Modifica: `assistant/mcp_client.py` (`server_command` senza valore predefinito; import non più
  usati tolti), `README.md` (snippet «Le preferenze non hanno effetto»)
- Test: `tests/test_mcp_server.py`, `tests/test_mcp_client.py`

- [x] **Passo 1: test che fallisce** — `test_server_command_defaults_to_the_package_file` diventa
  `test_server_command_needs_the_preferences_file`: `pytest.raises(TypeError)` chiamando
  `server_command(tmp_path / "n.sqlite3", "WARNING")`. Le chiamate a due argomenti in
  `tests/test_mcp_client.py` passano `DEFAULT_PREFERENCES_FILE`.
- [x] **Passo 2:** eseguirlo → fallisce.
- [x] **Passo 3:** togliere il predefinito.
- [x] **Passo 4:** test verdi; `pytest` completo verde.
- [x] **Passo 5:** README, snippet nuovo:

```powershell
@'
import os
from pathlib import Path
from assistant.config import DEFAULT_PREFERENCES_FILE
from assistant.mcp_client import McpClient, server_command
preferences = Path(os.environ.get("PREFERENCES_FILE", "").strip() or DEFAULT_PREFERENCES_FILE).resolve()
command, args, cwd = server_command(Path("data/notes.sqlite3").resolve(), "WARNING", preferences)
with McpClient(command, args, cwd=cwd) as client:
    print(client.read_resource("utente://preferenze"))
'@ | .\.venv\Scripts\python.exe -
```

- [x] **Passo 6: prova reale (senza modello):** con
  `$env:PREFERENCES_FILE` su un file temporaneo nella scratchpad con `"timezone": "America/New_York"`
  lo snippet stampa quel JSON; senza la variabile stampa quello del pacchetto. Annotare l'esito.
- [x] **Passo 7: commit** `fix(preferenze): file delle preferenze obbligatorio e diagnosi del README corretta`.

---

### Task 9: R-A8 · Ambito ristretto ai temi del laboratorio

**File:**
- Modifica: `assistant/data/scope.txt` (riga 7)
- Test: `tests/test_config.py`, `tests/test_real.py`

Riga nuova esatta:
`- spiegazioni dei concetti trattati nel laboratorio: modelli linguistici, agenti, strumenti, Model Context Protocol;`

- [x] **Passo 1: test che fallisce** — `test_default_scope_covers_the_mcp_prompts`: la riga nuova è
  in `scope.splitlines()` e nessuna riga contiene `"informatica, programmazione"`.
- [x] **Passo 2:** eseguirlo → fallisce.
- [x] **Passo 3:** cambiare la riga.
- [x] **Passo 4:** test verde; `pytest` completo verde.
- [x] **Passo 5: prova reale**

```python
def test_router_scope_is_limited_to_lab_topics(real_session, caplog):  # R-A8
    caplog.set_level(logging.INFO, logger="assistant.graph")
    real_session.send("Spiegami che cos'è il Model Context Protocol")
    refused = real_session.send("Spiegami la differenza tra memoria RAM e disco rigido")
    lines = router_lines(caplog)
    assert "category=conversation" in lines[0], lines
    assert "category=out_of_scope" in lines[1], lines
    assert refused.startswith(REFUSAL), refused
```

  `pytest tests/test_real.py -m real -v -k "lab_topics or router"` → passano anche le prove del
  router esistenti. Se il rifiuto manca anche alla ripetizione: fermarsi e chiedere (nessun ritocco
  a `ROUTER_PROMPT`).
- [x] **Passo 6:** nessun commit della correzione. **Esito (2026-11-16):** prova reale fallita due
  volte (domanda su RAM e disco accettata dal router); per decisione dell'utente riga vecchia
  ripristinata e R-A8 registrato come debito noto (vedi `PROGRESS.md`, Task 9).

---

### Task 10: R-A2 e R-A1 · CA-50 e CA-58 dal servizio, con il controllo di merito

**File:**
- Modifica: `tests/test_real.py`; solo al gradino 2 `assistant/prompts.py` e i test del suo testo
  (`tests/test_prompts.py`); documentazione: `docs/superpowers/requisiti.md` (CA-50, CA-58),
  `README.md` («Prompt MCP»), rapporto §6
- Test: `tests/test_real.py`

**Interfacce:**
- Consuma: `start_service(tmp_path, **overrides)`, `post_chat`, `cli_replies`, `write_preferences`,
  `REFUSAL` già in `tests/test_real.py`; la riga `kind=prompt name="spiega"` del Task 2; l'ambito
  del Task 9.

- [x] **Passo 1:** sostituire `test_default_timezone_from_preferences` con

```python
def test_default_timezone_from_preferences_in_the_service(tmp_path):  # CA-50 (R-A2)
    prefs = write_preferences(tmp_path / "preferenze.json", timezone="America/New_York")
    with start_service(tmp_path, PREFERENCES_FILE=str(prefs)) as (base_url, read_log):
        response = post_chat(base_url, "Che ore sono?")
        log = read_log()
    assert response.status_code == 200, response.text
    body = response.json()
    times = [t for t in body["tools_used"] if t["name"] == "get_current_time"]
    assert any(t["args"] == {"timezone": "America/New_York"} for t in times), body
    stamp = datetime.fromisoformat(times[-1]["result"]["datetime"])
    assert f"{stamp.hour}:{stamp.minute:02d}" in body["reply"], body
    assert any("resources/read" in line and "status=ok" in line
               and "timezone=America/New_York" in line for line in log.splitlines()), log
```

  (accettare anche l'ora con due cifre, come `tool_times`).
- [x] **Passo 2:** sostituire `test_explain_prompt` con la versione dalla CLI:

```python
MERIT = re.compile(r"\b(server|client|tools?|strumenti esterni|fonti di dati|dati esterni)\b", re.I)


def test_explain_prompt_from_the_cli(tmp_path):  # CA-58 (R-A1, R-A2)
    command = '/prompt spiega argomento="Model Context Protocol" livello=base'
    with start_service(tmp_path) as (base_url, read_log):
        cli = subprocess.run(
            [sys.executable, "-m", "assistant"], cwd=REPO_ROOT, input=f"{command}\nesci\n",
            capture_output=True, encoding="utf-8", errors="replace", timeout=900,
            env={**os.environ, "AGENT_URL": base_url, "LOG_LEVEL": "INFO",
                 "PYTHONIOENCODING": "utf-8"},
        )
        log = read_log()
    assert cli.returncode == 0, (cli.stdout, cli.stderr)
    (reply,) = cli_replies(cli.stdout)
    print(f"CA-58 risposta: {reply!r}")
    assert 'api request=chat kind=prompt name="spiega"' in log, log
    assert re.search(r"prompts/get name=spiega .*status=ok", log), log
    assert "category=conversation" in log and "node=reviewer" in log, log
    assert reply and not reply.startswith(REFUSAL), reply
    assert MERIT.search(reply), reply
```

  `send_prompt` resta per CA-59.
- [x] **Passo 3: gradino 1** — `pytest tests/test_real.py -m real -v -rP -k "explain_prompt_from_the_cli or timezone_from_preferences_in_the_service"`.
  CA-50 deve passare (regola del §3). Per CA-58: se passa (anche alla ripetizione), leggere la
  risposta stampata, annotare in `PROGRESS.md` se la spiegazione è corretta nel merito, e andare al
  Passo 6.
- [x] **Passo 4: gradino 2** (solo se CA-58 fallisce due volte) — test del testo in
  `tests/test_prompts.py` aggiornati prima (il testo termina con
  `" Se non conosci bene l'argomento, dillo invece di inventare."`), visti fallire; poi
  `explain_prompt` aggiunge la frase; `pytest` completo verde; commit
  `fix(prompt): spiega chiede di non inventare`; CA-58 di nuovo, con la ripetizione. Se passa:
  Passo 6.
- [x] **Passo 5: gradino 3** (solo se fallisce ancora) — `git revert` del commit del gradino 2;
  `@pytest.mark.xfail(strict=False, reason="limite del modello: spiegazione del Model Context Protocol non corretta nel merito (R-A1)")`
  su `test_explain_prompt_from_the_cli`; CA-58 in `requisiti.md`, rapporto §6 e README registrata
  come **non soddisfatta per limite del modello**, con la risposta ottenuta.
- [x] **Passo 6:** `requisiti.md` (CA-50 e CA-58 dal servizio, controllo di merito), README («Prompt
  MCP»: risposta ottenuta oggi al posto della frase del 2026-11-14), rapporto §6 aggiornati.
- [x] **Passo 7: commit** `test(reali): CA-50 e CA-58 dal servizio con controllo di merito`
  (con i documenti).

---

### Task 11: R-C1, R-C2, R-B10 · Porte, avvio di Compose, password fuori dall'agente

**File:**
- Modifica: `README.md` (`docker run` di `assistente-postgres`, nota sulla password di prova),
  `compose.yaml` (healthcheck di `postgres`, `restart` di `backend`, `POSTGRES_PASSWORD: ""` in
  `agent` e `assistant` con un commento), `PROGRESS.md` (nota accanto al comando storico della
  riga 1221)
- Test: `tests/test_docker.py`

- [ ] **Passo 1: test che falliscono**

```python
def test_readme_publishes_docker_ports_only_on_localhost():  # R-C1
    lines = [l for l in (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
             if l.lstrip().startswith("docker run")]
    ports = [p for line in lines for p in re.findall(r"-p (\S+)", line)]
    assert ports and all(p.startswith("127.0.0.1:") for p in ports), ports


def test_every_published_port_is_on_localhost(compose):  # R-C1
    for service in compose["services"].values():
        assert all(p["host_ip"] == "127.0.0.1" for p in service.get("ports", [])), service


def test_postgres_is_ready_only_on_tcp_and_the_backend_restarts(compose):  # R-C2
    assert "-h 127.0.0.1" in compose["services"]["postgres"]["healthcheck"]["test"][1]
    assert compose["services"]["backend"]["restart"] == "unless-stopped"


def test_database_password_stays_out_of_agent_and_cli(tmp_path):  # R-B10
    result = compose_config(tmp_path, profiles=("cli",))
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    for name in ("agent", "assistant"):
        assert services[name]["environment"]["POSTGRES_PASSWORD"] == "", name
    assert "segreta" in services["backend"]["environment"]["DATABASE_URL"]
```

- [ ] **Passo 2:** `pytest tests/test_docker.py` → i tre test su Compose e quello del README
  falliscono.
- [ ] **Passo 3:** correzioni: `-p 127.0.0.1:5433:5432` nel README (e la frase «solo da questo
  computer; `labprova` è la password di questo container di prova»); `pg_isready -h 127.0.0.1 -U
  … -d …`; `restart: unless-stopped`; `POSTGRES_PASSWORD: ""` con il commento «la password serve
  solo a postgres e backend».
- [ ] **Passo 4:** test verdi; `pytest` completo verde.
- [ ] **Passo 5: prova reale (Docker):** `docker rm -f assistente-postgres` (elimina le chat di
  prova), il nuovo `docker run` del README, `docker port assistente-postgres` → solo
  `5432/tcp -> 127.0.0.1:5433`; poi `pytest tests/test_backend_store.py -m real` → verde
  (comprende i test NUL del Task 5 su PostgreSQL).
- [ ] **Passo 6: commit** `fix(compose): porte solo locali, avvio a database pronto in TCP, password solo dove serve`.

---

### Task 12: R-A4, R-A10, R-C9, R-D1 · Documentazione

**File:**
- Modifica: `CLAUDE.md`, `docs/superpowers/requisiti.md` (RF-41, righe dello streaming su
  `client_gone`), `README.md` (front-end, diagnosi dello streaming),
  `docs/superpowers/specs/2026-11-14-streaming-design.md` (§1 riga «Browser che chiude la pagina»,
  §4 e §6 righe di log)

- [ ] **Passo 1: R-D1, osservazione** — script nella scratchpad (non nel progetto): back-end
  (`create_app`) su SQLite in memoria servito da uvicorn in un thread, con un agente finto il cui
  `chat_stream` manda `text`, poi attende 5 s, poi `done`; un client httpx apre
  `/messages/stream`, legge `question`, chiude. Casi: chiusura durante l'attesa; chiusura mentre
  arrivano eventi. Annotare per ciascuno: riga `outcome=…` del log e se la risposta è salvata nella
  chat. Esito in `PROGRESS.md`.
- [ ] **Passo 2: R-D1, testi** — specifica dello streaming, README e requisiti descrivono il
  comportamento osservato (risposta salvata se il turno finisce; `client_gone` solo quando la
  scrittura di un evento fallisce; due turni se l'utente rimanda la domanda, R-C4), con una riga
  «comportamento corretto il 2026-11-15, debito R-D1».
- [ ] **Passo 3: R-A4** — `CLAUDE.md` (Obiettivo, Step 4), RF-41, README: preferenze lette
  all'avvio del servizio dell'agente, una modifica vale dal riavvio del servizio.
- [ ] **Passo 4: R-A10** — README, sezione «Front-end: la chat nel browser»: nella pagina
  «/prompt …» è una domanda normale al modello; i comandi esistono solo nella CLI.
- [ ] **Passo 5: R-C9** — `CLAUDE.md`, prove reali del back-end con
  `.\.venv\Scripts\python.exe -m pytest …`.
- [ ] **Passo 6:** `git diff` riletto; commit `docs: preferenze all'avvio del servizio, /prompt nella pagina, comandi e pagina chiusa nello streaming`.

---

### Task 13: Revisione delle correzioni (specifica §7)

- [ ] **Passo 1:** subagente `general-purpose` con contesto pulito, in sola lettura (può eseguire
  `pytest` senza modello, niente prove reali né Docker), sul diff
  `git diff 41e39a4..HEAD` (dal commit della specifica), con la specifica delle correzioni e il
  rapporto. Chiede: correzioni che non risolvono il problema, test che non lo dimostrano,
  regressioni, problemi nuovi; gravità grave, importante, minore; per ognuno file, riga e scenario.
- [ ] **Passo 2:** Claude verifica ogni problema sul codice. Grave o importante confermato →
  test che fallisce, correzione, commit, poi un secondo giro del revisore solo su quella
  correzione. Minori nuovi → all'utente, che decide (correggere ora o `TODO.md`).
- [ ] **Passo 3:** dopo il secondo giro con un grave o importante ancora aperto: fermarsi e chiedere.
- [ ] **Passo 4:** sezione «Revisione delle correzioni» nel rapporto e in `PROGRESS.md`; commit
  `docs(revisione): esito della revisione delle correzioni`.

---

### Task 14: F5 · Sistemazione dei file del loop (specifica §8)

- [ ] **Passo 1:** `git mv loop.sh _archivio/loop.sh`, `git mv PROMPT.md _archivio/PROMPT.md`.
- [ ] **Passo 2:** `CLAUDE.md`: «Modalità autonoma» diventa una nota storica di due righe (che cosa
  ha fatto il loop il 2026-11-14 su `auto-claude`, dove sono `PROGRESS.md` e `_archivio/`); «Confini»
  senza il riferimento al branch `auto-claude` come lavoro in corso; struttura e comandi allineati
  (`server_command`, limiti dei prompt se citati).
- [ ] **Passo 3:** `TODO.md`: gli step 4–9 e lo streaming riassunti in «Già fatto» (una riga
  ciascuno); sezione «Debiti noti» con la tabella del §6 della specifica (id, che cosa, motivo,
  rimando al rapporto §3); nessun altro punto aperto; intestazione senza le regole della modalità
  autonoma.
- [ ] **Passo 4:** `PROGRESS.md`: «Stato attuale» aggiornato; sezioni F4 e F5 con eseguito ed esito;
  nota sui messaggi dei commit del loop (già nello stato attuale: verificare).
- [ ] **Passo 5:** `docs/superpowers/prossimo-prompt.txt`: riscritto per la sessione dopo
  l'integrazione (push su richiesta, poi i debiti o la lezione successiva).
- [ ] **Passo 6:** README: `assistente-postgres` descritto come container separato da Compose,
  usato solo dalle prove reali del back-end (porta 5433 su `127.0.0.1`).
- [ ] **Passo 7:** `pytest` completo verde (i test non dipendono dai file spostati: verificare con
  `rg "loop.sh|PROMPT.md" tests`); commit `docs: sistemazione dei file del loop autonomo`.

---

### Task 15: F6 · Verifica finale (specifica §9)

Prove nell'ordine; ognuna annotata in `PROGRESS.md` con comando, esito e durata.

- [ ] **Passo 1 — modello simulato:** `.\.venv\Scripts\python.exe -m pytest` → tutto verde;
  `pytest -m browser -v` con Edge; `$env:BROWSER_CHANNEL = "chrome"`, `pytest -m browser -v`, poi
  `Remove-Item Env:BROWSER_CHANNEL`.
- [ ] **Passo 2 — modello vero, suite completa (Compose spento, `assistente-postgres` attivo):**
  `.\.venv\Scripts\python.exe -m pytest -m real -v` (circa 50 minuti) → nessun fallimento
  confermato; atteso `1 skipped` (`PRAGMA` su PostgreSQL) e, se il Task 10 è arrivato al gradino 3,
  `1 xfailed`. Poi `$env:BROWSER_CHANNEL = "chrome"`,
  `pytest tests/test_real.py -m real -v -k frontend`.
- [ ] **Passo 3 — Docker:**
  1. `docker port assistente-postgres` → solo `127.0.0.1:5433` (R-C1);
  2. R-C2: con `$env:POSTGRES_PASSWORD` dal `.env`, `docker compose -p assistente-prova up -d --build`;
     `docker compose -p assistente-prova ps` → `postgres` healthy, `backend` attivo;
     `Invoke-RestMethod http://127.0.0.1:8001/chats` → `200`; `docker compose -p assistente-prova
     logs backend` senza uscite; poi `docker compose -p assistente-prova down -v` (solo i volumi di
     `assistente-prova`);
  3. `docker compose up -d --build` del progetto normale; dalla pagina `http://127.0.0.1:8080`
     (script Playwright temporaneo nella scratchpad, come in F2) una chat nuova con «Quanto fa
     17 * 23?»: bozza visibile, strumento indicato, «391», chat presente dopo il ricaricamento,
     log di `agent` con `tool=calculate` e `outcome=done`;
  4. R-B10: `docker compose exec agent printenv POSTGRES_PASSWORD` → riga vuota;
  5. R-B7: da Windows PowerShell 5.1, `Invoke-RestMethod http://127.0.0.1:8001/chats/<id>` sulla
     chat del punto 3 o su una con lettere accentate → «è» corretto;
  6. `docker compose down`.
- [ ] **Passo 4:** controllo dei criteri del §10 della specifica, uno per uno; resoconto
  all'utente: eseguito, esito, prove instabili, che cosa resta non dimostrato (per esempio
  l'origine delle chiamate malformate col modello vero, la corsa di R-C2, l'avviso del revisore
  nella bozza).
- [ ] **Passo 5:** commit `docs(revisione): verifica finale delle correzioni` (`PROGRESS.md` e
  rapporto).

---

### Task 16: Integrazione (specifica §9, punti 5–6)

- [ ] **Passo 1:** solo con i criteri del §10 soddisfatti e il via libera dell'utente al resoconto
  del Task 15: `git switch dev`, `git merge --ff-only auto-claude` (se rifiutato: fermarsi e
  chiedere).
- [ ] **Passo 2:** `.\.venv\Scripts\python.exe -m pytest` su `dev` → verde.
- [ ] **Passo 3:** fermarsi. Il push (`git push origin dev`, `git push origin dev:main`,
  `git fetch origin main:main`) solo quando l'utente lo chiede; avanzamento rapido di `main`
  rifiutato → fermarsi e chiedere. Dopo il push, su conferma, cancellare o tenere `auto-claude`.
