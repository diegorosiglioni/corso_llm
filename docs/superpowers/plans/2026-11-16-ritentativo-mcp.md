# I-1 · Ritentativo MCP senza ripetere gli strumenti — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** dopo una connessione chiusa il client MCP non ripete più `call_tool`, e il modello riceve
un testo che non lo invita a ripetere alla cieca.

**Architecture:** `_submit` riceve un parametro `repeat`; `call_tool` lo passa a `False` e ogni
connessione chiusa diventa `ToolOutcomeUnknownError` (sottoclasse di `ToolUnavailableError`), che
`run_tool` nel grafo traduce in un testo proprio. Le richieste di sola lettura restano come sono.

**Tech Stack:** Python 3.13, fastmcp 4.1.6, LangGraph, pytest. Nessuna dipendenza nuova.

**Spec:** `docs/superpowers/specs/2026-11-16-ritentativo-mcp-design.md`

## Global Constraints

- Branch `dev`, nessun push. Commit in Conventional Commits italiani, staging selettivo, con la
  riga finale `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.
- Codice e commenti in inglese; testi per il modello e documentazione in italiano.
- Prima il test che fallisce, poi il codice.
- Comandi da PowerShell nella radice: `.\.venv\Scripts\python.exe -m pytest`.
- Log invariati: `mcp_restart`, `mcp_restarted`, `mcp_restart_failed`; esito `transport_error`.
- Tempo scaduto, `tools/list`, `prompts/*`, `resources/read`: comportamento invariato.

## Review Focus

- Due thread chiamano `call_tool` mentre il server è morto: ciascuno deve ricevere
  `ToolOutcomeUnknownError`, con un solo riavvio (test nel Task 1, passo 1).
- `call_tool` dopo un tempo scaduto (riavvio *prima* della richiesta): la chiamata non è ancora
  partita, quindi deve riuscire normalmente — già coperto da
  `test_library_timeout_counts_as_timeout`, che deve restare verde.
- `ToolOutcomeUnknownError` non deve arrivare a `/status`: usa `list_tools`, che ripete ancora —
  coperto da `test_dead_server_is_restarted_and_the_request_repeated`.
- Test che sostituiscono `_submit` con `lambda request: …`: `call_tool` ora passa `repeat=False`
  per nome; se un test esistente sostituisce `_submit` e poi chiama `call_tool`, va adattato
  (`lambda request, **_: …`). Si scopre con la suite completa del Task 1, passo 4.

---

### Task 1: Client — `call_tool` non viene ripetuto

**Files:**
- Modify: `assistant/tools.py:10-12`
- Modify: `assistant/mcp_client.py` (`call_tool`, `_submit`, docstring del modulo)
- Test: `tests/test_mcp_client.py` (sezione «reconnection (R-B3)»)

**Interfaces:**
- Produces: `assistant.tools.ToolOutcomeUnknownError(ToolUnavailableError)`; il suo `str()` è il
  motivo: `"Connection closed"` oppure `"server MCP non riavviato: <motivo>"`.
- Produces: `McpClient._submit(request, timeout: float | None = None, *, repeat: bool = True)`.

- [ ] **Step 1: test che falliscono** in `tests/test_mcp_client.py`

Importare `ToolOutcomeUnknownError` da `assistant.tools` e `CONNECTION_CLOSED` da `mcp.types`.
Sostituire `test_call_tool_is_repeated_on_the_new_server` con:

```python
def test_call_tool_is_not_repeated_after_a_closed_connection(restartable, caplog):
    client, _ = restartable
    caplog.set_level(logging.INFO, "assistant.mcp_client")
    old = kill_server(client)
    with pytest.raises(ToolOutcomeUnknownError, match="^Connection closed$"):
        client.call_tool("pid", {})
    assert sum(text.startswith("mcp_restart reason=") for _, text in restart_logs(caplog)) == 1
    assert server_pid(client) != old  # the next call finds the new server


def test_call_tool_is_sent_once(restartable, monkeypatch):
    client, _ = restartable
    old, calls = server_pid(client), []

    async def closed(self, *args, **kwargs):
        calls.append(1)
        raise MCPError(code=CONNECTION_CLOSED, message="Connection closed")
    monkeypatch.setattr(Client, "call_tool", closed)
    with pytest.raises(ToolOutcomeUnknownError):
        client.call_tool("pid", {})
    assert calls == [1]
    monkeypatch.undo()
    assert server_pid(client) != old


def test_call_tool_outcome_is_unknown_when_the_restart_fails(restartable):
    client, flag = restartable
    flag.touch()
    kill_server(client)
    with pytest.raises(ToolOutcomeUnknownError, match=r"^server MCP non riavviato: "):
        client.call_tool("pid", {})
    flag.unlink()
    assert server_pid(client) > 0


def test_concurrent_tool_calls_restart_once(restartable, caplog):
    client, _ = restartable
    caplog.set_level(logging.INFO, "assistant.mcp_client")
    kill_server(client)
    barrier, errors = threading.Barrier(2), []

    def work():
        barrier.wait()
        try:
            client.call_tool("pid", {})
        except ToolOutcomeUnknownError as error:
            errors.append(str(error))
    threads = [threading.Thread(target=work) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert len(errors) == 2
    assert sum(text.startswith("mcp_restart reason=") for _, text in restart_logs(caplog)) == 1


def test_unknown_outcome_is_a_tool_unavailable_error():
    assert issubclass(ToolOutcomeUnknownError, ToolUnavailableError)
```

- [ ] **Step 2: verificare che falliscano**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mcp_client.py -k "not_repeated or sent_once or outcome_is_unknown or concurrent_tool_calls or unknown_outcome" -v`
Expected: errore di raccolta (`ImportError: ToolOutcomeUnknownError`).

- [ ] **Step 3: implementare**

- `assistant/tools.py`: `class ToolOutcomeUnknownError(ToolUnavailableError)` con docstring «The
  connection closed during a tool call: the tool may or may not have run.»; sistemare le due
  righe vuote dopo le classi.
- `assistant/mcp_client.py`, `_submit(request, timeout=None, *, repeat=True)`: con
  `repeat=False`, al primo `_ConnectionClosed` chiamare `_restart`; se `_restart` solleva
  `ToolUnavailableError`, rilanciarla come `ToolOutcomeUnknownError(str(error))`; altrimenti
  sollevare `ToolOutcomeUnknownError(closed.reason)`. Con `repeat=True` il codice attuale.
  Il riavvio «stale» in testa a `_submit` resta fuori da questa regola (la richiesta non è partita).
- `call_tool`: `self._submit(..., repeat=False)`.
- Aggiornare la docstring di `_submit` e quella del modulo (riga 4): le chiamate agli strumenti
  non vengono ripetute (I-1).

- [ ] **Step 4: verificare**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mcp_client.py -v`, poi
`.\.venv\Scripts\python.exe -m pytest`
Expected: tutto verde; totale 1074 − 1 + 5 = 1078 passed, 93 deselected.

- [ ] **Step 5: commit**

`git add assistant/tools.py assistant/mcp_client.py tests/test_mcp_client.py`
`fix(mcp): call_tool non viene ripetuto dopo una connessione chiusa (I-1)`

### Task 2: Grafo — testo per il modello con esito incerto

**Files:**
- Modify: `assistant/graph.py:302-307` (`run_tool`) e import alla riga 52
- Test: `tests/test_graph.py` (dopo `test_unavailable_tool_is_transport_error`)

**Interfaces:**
- Consumes: `assistant.tools.ToolOutcomeUnknownError` (Task 1).

- [ ] **Step 1: test che fallisce**

```python
def test_unknown_outcome_does_not_invite_a_blind_retry(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")

    def lost(**_):
        raise ToolOutcomeUnknownError("Connection closed")

    remote = StructuredTool.from_function(
        lost, name="add_note", description="d",
        args_schema={"type": "object", "properties": {}},
        metadata={"variant": "mcp"},
    )
    r = start_turn(FakeModel([tool_call(name="add_note"), AIMessage("ok")]), tools=[remote])
    assert json.loads(tool_messages(r["messages"])[0].content) == {
        "error": "Connessione con lo strumento caduta durante la chiamata (Connection closed): "
        "l'esito è incerto. Se la chiamata modificava dati, controlla lo stato (per esempio con "
        "list_notes) prima di ripeterla."
    }
    assert "step=1/5 execution=transport_error call_id=c1" in caplog.text
```

- [ ] **Step 2: verificare che fallisca**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_graph.py -k unknown_outcome -v`
Expected: FAIL, il messaggio è ancora «Strumento non raggiungibile: … Riprova o riavvia…».

- [ ] **Step 3: implementare**

In `run_tool`, un `except ToolOutcomeUnknownError` **prima** di `except ToolUnavailableError`, con
il testo esatto del test e l'esito `"transport_error"`. Il ramo esistente non cambia.

- [ ] **Step 4: verificare**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_graph.py -v`, poi la suite completa.
Expected: 1079 passed, 93 deselected; `test_unavailable_tool_is_transport_error` invariato e verde.

- [ ] **Step 5: commit**

`git add assistant/graph.py tests/test_graph.py`
`fix(grafo): esito incerto di uno strumento senza invito a riprovare (I-1)`

### Task 3: Documentazione e chiusura del punto

**Files:**
- Modify: `README.md` (righe 740-750 circa, riavvio del server MCP)
- Modify: `docs/superpowers/specs/2026-11-16-robustezza-servizio-design.md` (§3, «Che cosa
  succede» e «Rischio accettato»)
- Modify: `REVIEW.md`, `PROGRESS.md`, `TODO.md`

- [ ] **Step 1: README** — nel paragrafo del riavvio: le richieste di sola lettura vengono
  ripetute; una chiamata a uno strumento no, e il modello riceve il testo «Connessione con lo
  strumento caduta durante la chiamata (…): l'esito è incerto. …».
- [ ] **Step 2: specifica di R-B3** — sotto «Rischio accettato» una riga: «Superato il 2026-11-16
  da `2026-11-16-ritentativo-mcp-design.md` (I-1): `call_tool` non viene più ripetuto.» Il testo
  storico resta.
- [ ] **Step 3: `REVIEW.md`** — casella I-1 spuntata, con il rimando alla specifica; aggiornare la
  riga «Nessuno è stato ancora corretto».
- [ ] **Step 4: `PROGRESS.md`** — in «Stato attuale» una voce su I-1 (che cosa è cambiato, esito
  di `pytest`, che cosa resta da provare: comportamento del modello con il testo nuovo, prove
  `real`, Docker) e «Prossimo: I-2». `TODO.md` — una riga in «Già fatto».
- [ ] **Step 5: verifica** — `.\.venv\Scripts\python.exe -m pytest` → 1079 passed; aggiornare i
  conteggi dei test nel README se li riporta.
- [ ] **Step 6: commit** — staging dei soli file elencati più specifica e piano di I-1
  (`REVIEW.md` entra in Git per la prima volta):
  `docs: I-1 chiuso, call_tool non ripetuto nel README, nel diario e nella revisione`
