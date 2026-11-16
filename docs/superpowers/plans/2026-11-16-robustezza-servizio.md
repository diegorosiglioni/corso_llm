# Robustezza del servizio dell'agente (R-B3, R-B4, R-B9) — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** il servizio dell'agente riavvia da solo il server MCP quando muore, `/status` non fa più
chiudere la CLI con MCP bloccato e un `AGENT_URL` malformato dà «Configurazione non valida».

**Architecture:** la riconnessione sta tutta in `McpClient` (`assistant/mcp_client.py`): stessi
metodi pubblici, più un lock, un contatore di generazione e un segno «da riavviare» per i tempi
scaduti. `/status` passa a `list_tools` un tempo massimo suo. Il controllo dell'indirizzo sta in
`load_client_config`, usata da CLI e back-end. Compose cambia solo il controllo di salute di `agent`.

**Tech Stack:** Python 3.13, fastmcp, mcp (`MCPError`, `CONNECTION_CLOSED`, `REQUEST_TIMEOUT`),
FastAPI, httpx, pytest. Nessuna dipendenza nuova.

**Spec:** [`../specs/2026-11-16-robustezza-servizio-design.md`](../specs/2026-11-16-robustezza-servizio-design.md)

## Global Constraints

- Codice, identificatori, chiavi dei log e nomi dei test in inglese; messaggi per l'utente in
  italiano.
- Testi esatti:
  - `AGENT_URL non è un indirizzo valido, ricevuto '<valore>'.` (valore dopo `strip()`).
  - `server MCP non riavviato: <motivo>` (messaggio di `ToolUnavailableError`).
  - `nessuna risposta entro <t:g> s` con il tempo massimo effettivo della richiesta.
  - Grafo: `Strumento non raggiungibile: {error}. Riprova o riavvia il servizio dell'agente.`
- Log esatti, logger `assistant.mcp_client`, `<json>` = `json.dumps(testo, ensure_ascii=False)`:
  - `WARNING mcp_restart reason=<json>`
  - `INFO mcp_restarted duration_ms=<n>`
  - `WARNING mcp_restart_failed error=<json>`
- Valori: `STATUS_MCP_TIMEOUT = 5.0` (`assistant/api.py`), `STATUS_TIMEOUT = 20.0`
  (`assistant/api_client.py`).
- Connessione chiusa = `MCPError` con `error.code == CONNECTION_CLOSED` (−32000), oppure
  `anyio.ClosedResourceError` o `anyio.BrokenResourceError`. Tempo scaduto =
  `concurrent.futures.TimeoutError` dell'attesa, oppure `MCPError` con `REQUEST_TIMEOUT` (−32001).
  Tutto il resto è un errore normale: nessun riavvio.
- Dopo `__exit__` il client non riavvia mai: le richieste danno `sessione MCP chiusa` come oggi.
- Comandi da PowerShell nella radice: `.\.venv\Scripts\python.exe -m pytest …`; in Git Bash
  `.venv/Scripts/python.exe`, mai `python`.
- Commit su `dev`, Conventional Commits in italiano, con la riga
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; prima di ogni commit `git status`,
  controllo del diff, staging selettivo. Nessun push senza richiesta.

## Review Focus

- Servizio che si chiude (`__exit__`) mentre una richiesta fallisce: non deve ripartire nessun
  server → `test_no_restart_after_close` (Task 3).
- Server che non riparte mai (file delle preferenze sparito): ogni richiesta fallisce subito con
  «server MCP non riavviato», senza cicli → `test_failed_restart_is_reported_and_retried` (Task 3).
- Tempo scaduto segnalato dalla libreria invece che dall'attesa (`call_tool` ha un suo `timeout`):
  vale come tempo scaduto, non come errore normale → `test_library_timeout_counts_as_timeout`
  (Task 3).
- LM Studio spento in Docker: `agent` deve restare sano → `test_agent_healthcheck_follows_mcp`
  (Task 4).
- Indirizzi validi meno comuni (IPv6 tra parentesi, percorso finale) devono continuare a passare
  → casi aggiunti a `test_agent_url` (Task 1).

---

### Task 1: controllo completo di `AGENT_URL` (R-B9)

**Files:**
- Modify: `assistant/config.py` (`load_client_config`)
- Test: `tests/test_config.py`, `tests/test_main.py`, `tests/test_backend_service.py`

**Interfaces:**
- Produces: `load_client_config(env) -> ClientConfig`, firma invariata; nuovo `ConfigError` per
  gli indirizzi malformati.

- [ ] **Step 1: Write the failing tests**

In `tests/test_config.py` aggiungere a `test_agent_url` i casi
`("http://[::1]:8000", "http://[::1]:8000")` e `("http://agent:8000/api/", "http://agent:8000/api")`,
e:

```python
@pytest.mark.parametrize("value", [
    "http://[::1", "http://agent:porta", "https://agent:99999", "http://", "http://:8000",
])
def test_malformed_agent_url(value):
    assert client_error({"AGENT_URL": value}) == (
        f"AGENT_URL non è un indirizzo valido, ricevuto '{value}'."
    )
```

In `tests/test_main.py`, a `test_invalid_config_exits_1`:
`({"AGENT_URL": "http://[::1"}, "AGENT_URL non è un indirizzo valido, ricevuto 'http://[::1'.")`.
In `tests/test_backend_service.py`, a `test_invalid_config_exits_1`:
`({**VALID, "AGENT_URL": "http://[::1"}, "AGENT_URL non è un indirizzo valido")`.

- [ ] **Step 2: Run them, they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_config.py tests/test_main.py tests/test_backend_service.py -q`
Expected: FAIL sui nuovi casi (nessun errore, oppure `InvalidURL` più avanti).

- [ ] **Step 3: Implement**

In `load_client_config`, se lo schema è giusto, `urlsplit(agent_url)`: l'indirizzo è valido se
`urlsplit` non solleva `ValueError`, `hostname` non è vuoto e la lettura di `.port` non solleva
`ValueError`. Altrimenti si aggiunge ai `problems` il testo esatto. Il controllo dello schema e il
suo messaggio restano invariati, e i due messaggi non compaiono mai insieme.

- [ ] **Step 4: Run them, they pass**

Run: lo stesso comando dello Step 2 → PASS.

- [ ] **Step 5: Commit**

```bash
git add assistant/config.py tests/test_config.py tests/test_main.py tests/test_backend_service.py
git commit -m "fix(configurazione): AGENT_URL malformato dà «Configurazione non valida» (R-B9)"
```

---

### Task 2: tempo massimo di MCP dentro `/status` (R-B4)

**Files:**
- Modify: `assistant/mcp_client.py` (`list_tools`, `_submit`), `assistant/api.py` (`_mcp_status`,
  costante), `assistant/api_client.py` (`STATUS_TIMEOUT`)
- Modify: `tests/conftest.py` (`FakeMcpClient.list_tools`), le sottoclassi di test che ridefiniscono
  `list_tools` (per esempio `ToolListFails` in `tests/test_api.py`: cercarle tutte con
  `grep -rn "def list_tools" tests`)
- Test: `tests/test_mcp_client.py`, `tests/test_api.py`, `tests/test_api_client.py`

**Interfaces:**
- Produces: `McpClient.list_tools(timeout: float | None = None) -> list[ToolSpec]`;
  `McpClient._submit(request, timeout: float | None = None)` (con `None` l'attesa resta
  `self._timeout + 5` e il messaggio resta `nessuna risposta entro {self._timeout:g} s`; con un
  valore, attesa e messaggio usano quel valore); `assistant.api.STATUS_MCP_TIMEOUT = 5.0`;
  `FakeMcpClient.list_timeouts: list[float | None]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_mcp_client.py
def test_list_tools_with_its_own_timeout(client, monkeypatch):
    async def slow(self):
        await asyncio.sleep(5)
    monkeypatch.setattr(Client, "list_tools", slow)  # fastmcp.Client
    started = time.monotonic()
    with pytest.raises(ToolUnavailableError, match=r"^nessuna risposta entro 0\.2 s$"):
        client.list_tools(timeout=0.2)
    assert time.monotonic() - started < 2
```

```python
# tests/test_api.py
def test_status_gives_mcp_a_short_timeout():
    client = FakeMcpClient(MCP_SPECS)
    api(client=client).get("/status")
    assert client.list_timeouts == [5.0] and STATUS_MCP_TIMEOUT == 5.0
```

In `tests/test_api_client.py`, riga 138: `(STATUS_TIMEOUT, CHAT_TIMEOUT) == (20, 600)`.

- [ ] **Step 2: Run them, they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mcp_client.py tests/test_api.py tests/test_api_client.py -q`
Expected: FAIL (`timeout` non accettato, `STATUS_MCP_TIMEOUT` non definito, 10 invece di 20).

- [ ] **Step 3: Implement**

Le firme sono quelle del blocco Interfaces. `FakeMcpClient.list_tools(timeout=None)` registra il
valore in `self.list_timeouts`. Le sottoclassi di test accettano `timeout=None`. `_mcp_status`
chiama `client.list_tools(timeout=STATUS_MCP_TIMEOUT)`. Va aggiornato il commento di
`STATUS_TIMEOUT`: 5 s per MCP, 5 s per il modello, più il margine per un riavvio. `_submit_as`
continua a chiamare `self._submit(request)` senza `timeout`: alcuni test esistenti sostituiscono
`_submit` con `lambda request: …`. Import nei test: `from fastmcp import Client` e `asyncio`, `time`
in `tests/test_mcp_client.py`; `STATUS_MCP_TIMEOUT` da `assistant.api` in `tests/test_api.py`.

- [ ] **Step 4: Run them, they pass; then the whole suite**

Run: il comando dello Step 2 → PASS; poi `.\.venv\Scripts\python.exe -m pytest -q` → tutto verde.

- [ ] **Step 5: Commit**

```bash
git add assistant/mcp_client.py assistant/api.py assistant/api_client.py tests/
git commit -m "fix(servizio): /status dà a MCP 5 s, la CLI aspetta 20 s (R-B4)"
```

---

### Task 3: riconnessione automatica del server MCP (R-B3)

**Files:**
- Create: `tests/mcp_test_server.py`
- Modify: `assistant/mcp_client.py` (`McpClient`)
- Test: `tests/test_mcp_client.py` (nuova sezione `# --- reconnection (R-B3) ---`)

**Interfaces:**
- Consumes: `_submit(request, timeout=None)` del Task 2.
- Produces: nessun metodo pubblico nuovo. Metodi privati che il piano fissa:
  - `_open() -> None`: il corpo dell'attuale `__enter__` (loop, thread, `_serve`, attesa di
    `ready` con `self._timeout`, `McpStartupError` in caso di errore). `__enter__` chiama
    `_open()` e segna il client come aperto, `__exit__` lo segna come chiuso e chiama
    `_shutdown()`.
  - `_restart(seen_generation: int, reason: str) -> None`: sotto `self._lock`; se
    `self._generation != seen_generation` e la sessione non è segnata da riavviare, non fa niente,
    perché un altro thread ha già riavviato. Altrimenti scrive il log `mcp_restart`, chiama
    `_shutdown()` e poi `_open()`, incrementa `_generation`, toglie il segno e scrive il log
    `mcp_restarted`. Se `_open()` solleva `McpStartupError`, scrive il log `mcp_restart_failed`,
    lascia il segno e solleva `ToolUnavailableError(f"server MCP non riavviato: {motivo}")`.
  - `_submit`: client chiuso → `ToolUnavailableError("sessione MCP chiusa")`; sessione segnata
    → `_restart` prima di partire; connessione chiusa → `_restart` e **una** ripetizione (se
    anche questa trova la connessione chiusa, `ToolUnavailableError` con il motivo); tempo
    scaduto → segno «da riavviare» (con il messaggio come motivo) e `ToolUnavailableError`,
    senza ripetizione; altri errori → `ToolUnavailableError(_reason(error))` come oggi.

`tests/mcp_test_server.py`: server FastMCP di prova con uno strumento `pid` che restituisce
`{"pid": os.getpid()}`. Con l'opzione `--fail-if PATH`, all'avvio esce con codice 1 se `PATH`
esiste. Va avviato come `assistant/mcp_server.py`:
`run(transport="stdio", show_banner=False)`.

- [ ] **Step 1: Write the failing tests**

```python
TEST_SERVER = Path(__file__).with_name("mcp_test_server.py")


@pytest.fixture
def restartable(tmp_path):
    flag = tmp_path / "fail-on-start"
    with McpClient(sys.executable, [str(TEST_SERVER), "--fail-if", str(flag)], timeout=5) as c:
        yield c, flag


def server_pid(client) -> int:
    return client.call_tool("pid", {})["pid"]


def kill_server(client) -> int:
    pid = server_pid(client)
    os.kill(pid, signal.SIGTERM)  # TerminateProcess su Windows
    time.sleep(0.5)  # il client vede chiudersi la pipe
    return pid


def restart_logs(caplog) -> list[tuple[int, str]]:
    return [(r.levelno, r.getMessage()) for r in caplog.records
            if r.name == "assistant.mcp_client" and r.getMessage().startswith("mcp_restart")]


def test_dead_server_is_restarted_and_the_request_repeated(restartable, caplog):
    client, _ = restartable
    caplog.set_level(logging.INFO, "assistant.mcp_client")
    old = kill_server(client)
    assert [spec.name for spec in client.list_tools()] == ["pid"]
    assert server_pid(client) != old
    (level, first), (info, second) = restart_logs(caplog)
    assert (level, first) == (logging.WARNING, 'mcp_restart reason="Connection closed"')
    assert info == logging.INFO and re.fullmatch(r"mcp_restarted duration_ms=\d+", second)


def test_call_tool_is_repeated_on_the_new_server(restartable):
    client, _ = restartable
    old = kill_server(client)
    assert client.call_tool("pid", {})["pid"] != old


def test_server_errors_do_not_restart(client, caplog):  # server vero
    caplog.set_level(logging.INFO, "assistant.mcp_client")
    with pytest.raises(PromptUnavailableError):
        client.get_prompt("nessuno", {})
    with pytest.raises(ResourceUnavailableError):
        client.read_resource("utente://niente")
    assert "error" in client.call_tool("nessuno", {})
    assert restart_logs(caplog) == []


def test_failed_restart_is_reported_and_retried(restartable, caplog):
    client, flag = restartable
    flag.touch()
    kill_server(client)
    with pytest.raises(ToolUnavailableError, match=r"^server MCP non riavviato: "):
        client.list_tools()
    assert any(level == logging.WARNING and text.startswith("mcp_restart_failed error=")
               for level, text in restart_logs(caplog))
    flag.unlink()
    assert server_pid(client) > 0


def test_timeout_is_not_repeated_but_restarts_before_the_next_request(restartable, monkeypatch):
    client, _ = restartable
    old, calls = server_pid(client), []

    async def slow(self):
        calls.append(1)
        await asyncio.sleep(5)
    monkeypatch.setattr(Client, "list_tools", slow)
    with pytest.raises(ToolUnavailableError, match=r"^nessuna risposta entro 0\.2 s$"):
        client.list_tools(timeout=0.2)
    assert calls == [1]
    monkeypatch.undo()
    assert server_pid(client) != old


def test_library_timeout_counts_as_timeout(restartable, monkeypatch):
    client, _ = restartable
    old, calls = server_pid(client), []

    async def timed_out(self, *args, **kwargs):
        calls.append(1)
        raise MCPError(code=REQUEST_TIMEOUT, message="Timed out")
    monkeypatch.setattr(Client, "call_tool", timed_out)
    with pytest.raises(ToolUnavailableError):
        client.call_tool("pid", {})
    assert calls == [1]
    monkeypatch.undo()
    assert server_pid(client) != old


def test_concurrent_requests_restart_once(restartable, caplog):
    client, _ = restartable
    caplog.set_level(logging.INFO, "assistant.mcp_client")
    kill_server(client)
    barrier, results = threading.Barrier(2), []

    def work():
        barrier.wait()
        results.append(len(client.list_tools()))
    threads = [threading.Thread(target=work) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert results == [1, 1]
    assert sum(text.startswith("mcp_restart reason=") for _, text in restart_logs(caplog)) == 1


def test_no_restart_after_close(tmp_path, caplog):
    caplog.set_level(logging.INFO, "assistant.mcp_client")
    with McpClient(sys.executable, [str(TEST_SERVER)], timeout=5) as c:
        pass
    with pytest.raises(ToolUnavailableError, match="^sessione MCP chiusa$"):
        c.list_tools()
    assert restart_logs(caplog) == []
```

Import da aggiungere: `MCPError` da `mcp.shared.exceptions`, `REQUEST_TIMEOUT` da `mcp.types`,
più `os`, `re`, `signal`, `threading`, `time`, `asyncio` e `pathlib.Path` se mancano.

- [ ] **Step 2: Run them, they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mcp_client.py -q -k "restart or repeated or timeout or close"`
Expected: FAIL su `Connection closed`, nessun riavvio.

- [ ] **Step 3: Implement** la riconnessione con i metodi del blocco Interfaces. `_lock` è un
  `threading.Lock`, `_generation` parte da 0. Il segno «da riavviare» e il motivo da registrare
  sono attributi del client. Il motivo nel log è il testo dell'errore (`_reason(error)`).
  `duration_ms` misura `_shutdown()` più `_open()`.

- [ ] **Step 4: Run the new tests, then the whole suite**

Run: il comando dello Step 2 → PASS; ripetere `tests/test_mcp_client.py` tre volte di seguito per
scoprire eventuali instabilità; poi `.\.venv\Scripts\python.exe -m pytest -q` → tutto verde.

- [ ] **Step 5: Commit**

```bash
git add assistant/mcp_client.py tests/mcp_test_server.py tests/test_mcp_client.py
git commit -m "fix(mcp): riavvio automatico del server MCP quando la connessione si chiude (R-B3)"
```

---

### Task 4: controllo di salute di `agent` e testo per il modello (R-B3)

**Files:**
- Modify: `compose.yaml` (healthcheck di `agent` e il suo commento), `assistant/graph.py`
  (messaggio dell'errore di trasporto in `run_tool`)
- Test: `tests/test_docker.py`, `tests/test_graph.py:192`

**Interfaces:**
- Produces: il comando del controllo di salute, esattamente:
  `["CMD", "python", "-c", "import httpx, sys; sys.exit(httpx.get('http://127.0.0.1:8000/status', timeout=10).json()['mcp']['status'] != 'ok')"]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_docker.py
@pytest.mark.parametrize(("mcp", "model", "code"), [
    ("ok", "ok", 0), ("ok", "unavailable", 0), ("unavailable", "ok", 1),
])
def test_agent_healthcheck_follows_mcp(compose, monkeypatch, mcp, model, code):
    test = compose["services"]["agent"]["healthcheck"]["test"]
    assert test[:3] == ["CMD", "python", "-c"]
    body = {"mcp": {"status": mcp}, "model": {"status": model}}
    fake = types.SimpleNamespace(get=lambda url, timeout: types.SimpleNamespace(json=lambda: body))
    monkeypatch.setitem(sys.modules, "httpx", fake)
    with pytest.raises(SystemExit) as stopped:
        exec(test[3], {})
    assert int(stopped.value.code) == code
```

Import da aggiungere in `tests/test_docker.py`: `sys`, `types`.

In `tests/test_graph.py:192` il testo atteso diventa
`"Strumento non raggiungibile: server terminato. Riprova o riavvia il servizio dell'agente."`.

- [ ] **Step 2: Run them, they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_docker.py tests/test_graph.py -q`
Expected: FAIL (oggi il controllo non chiama `sys.exit`, testo vecchio). Senza la CLI di Docker
il test di Compose viene saltato: annotarlo nel resoconto.

- [ ] **Step 3: Implement** il comando esatto del blocco Interfaces e il testo dei Global
  Constraints. Il commento sopra il controllo dice che il container è sano quando MCP risponde,
  anche con LM Studio spento, e che il controllo ogni 30 s riavvia un server MCP morto. Gli altri
  parametri del controllo non cambiano.

- [ ] **Step 4: Run them, they pass**

Run: il comando dello Step 2 → PASS; `docker compose config --quiet` con un `.env` valido →
nessun errore.

- [ ] **Step 5: Commit**

```bash
git add compose.yaml assistant/graph.py tests/test_docker.py tests/test_graph.py
git commit -m "fix(compose): agent sano solo se MCP risponde; testo «riavvia il servizio dell'agente» (R-B3)"
```

---

### Task 5: prove manuali e documentazione

**Files:**
- Modify: `README.md` (righe 740–744 sul collegamento MCP interrotto, 806–810 sul controllo di
  salute, «Diagnosi» con «AGENT_URL non è un indirizzo valido», conteggi dei test), `TODO.md`,
  `PROGRESS.md`

- [ ] **Step 1: Prova locale.** Avviare il servizio (`.\.venv\Scripts\python.exe -m assistant.service`
  con le variabili di LM Studio), poi uccidere il server MCP:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object CommandLine -like '*assistant.mcp_server*' | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
curl.exe -s http://127.0.0.1:8000/status
```

Expected: `"mcp":{"status":"ok"…}` e, nel log del servizio, `mcp_restart` seguito da
`mcp_restarted`. Poi, dalla CLI, «Quanto fa 17 * 23?» deve usare `calculate`.

- [ ] **Step 2: Prova in Docker.** `docker compose up -d --build`, poi:

```powershell
docker compose exec -T agent python -c "import os, signal; [os.kill(int(p), signal.SIGTERM) for p in os.listdir('/proc') if p.isdigit() and b'assistant.mcp_server' in open(f'/proc/{p}/cmdline', 'rb').read()]"
```

Expected: entro circa 30 s `docker compose logs agent` mostra `mcp_restarted`;
`docker compose ps` mostra `agent` `healthy`; dalla pagina su `http://127.0.0.1:8080` una domanda
che usa `calculate` riesce. Alla fine `docker compose down`.

- [ ] **Step 3: Suite completa.** `.\.venv\Scripts\python.exe -m pytest` e annotare i conteggi.

- [ ] **Step 4: Documentazione.** README con i comportamenti nuovi e i conteggi dello Step 3;
  `TODO.md` con R-B3, R-B4 e R-B9 tolti dai «Debiti noti» e una riga in «Già fatto»;
  `PROGRESS.md` con una sezione del lavoro (prove eseguite ed esiti) e la voce «Prossimo»
  aggiornata in «Stato attuale».

- [ ] **Step 5: Commit**

```bash
git add README.md TODO.md PROGRESS.md
git commit -m "docs: riavvio del server MCP, controllo di salute e AGENT_URL nel README e nel diario"
```
