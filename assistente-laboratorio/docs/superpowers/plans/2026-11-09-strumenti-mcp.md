# Lezione 5 — Strumenti MCP e codice in inglese: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** tradurre in inglese il codice esistente senza cambiarne il comportamento, poi collegare al
grafo un server FastMCP locale (stdio) con convertitore di unità, calcolatrice sicura, catalogo
locale e note persistenti.

**Architecture:**
- La logica di dominio sta in moduli puri (`units.py`, `calculator.py`, `catalog.py`, `notes.py`),
  avvolti da `mcp_server.py`.
- `mcp_client.py` tiene aperta una sessione stdio in un thread con il suo event loop e offre metodi
  sincroni; un adattatore trasforma il catalogo `tools/list` in `StructuredTool`.
- Il grafo LangGraph non cambia forma: riceve strumenti locali e MCP come `BaseTool`, e i log
  seguono il formato della slide 26.

**Tech Stack:** Python 3.13, LangGraph 1.2.17, langchain-core 1.7.0, langchain-openai 1.7.2,
fastmcp 4.1.6 (nuova), SQLite (`sqlite3`), pytest 9.1.1, Docker Compose.

**Spec:** [`../specs/2026-11-09-strumenti-mcp-design.md`](../specs/2026-11-09-strumenti-mcp-design.md),
con i requisiti [`../requisiti.md`](../requisiti.md) §8.

**Stato (2026-11-09):** scritto e committato; nessun task iniziato. Da confermare all'inizio
dell'esecuzione, insieme alla modalità (consigliata: esecuzione nella sessione,
`superpowers:executing-plans`, con revisione indipendente finale).

## Global Constraints

- Comandi da PowerShell in `assistente-laboratorio/`, senza attivare il venv:
  `.\.venv\Scripts\python.exe -m pytest` (in Git Bash: `.venv/Scripts/python.exe -m pytest`).
- Lingua (RNF-10):
  - in inglese: identificatori, moduli, variabili d'ambiente, nomi e argomenti degli strumenti,
    chiavi JSON, chiavi dei log, commenti, docstring, nomi dei test;
  - in italiano: `SYSTEM_PROMPT`, testi del terminale, descrizioni degli strumenti, messaggi
    `error`, messaggi di configurazione, dati del catalogo.
- Codice sincrono; l'asincronia solo dentro `assistant/mcp_client.py`.
- Dipendenze: aggiungere solo `fastmcp==4.1.6`. Le versioni già fissate in `constraints.txt` non
  cambiano; se pip chiede di cambiarle, fermarsi e riferire.
- Risultati degli strumenti: `dict`. Gli errori dello strumento hanno una sola chiave, `"error"`, con
  un messaggio in italiano.
- Variabili d'ambiente:
  - `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL` (obbligatorie);
  - `MAX_STEPS` (default 5), `LOG_LEVEL` (default INFO), `NOTES_DB` (default `data/notes.sqlite3`);
  - `LMSTUDIO_BASE_URL_DOCKER` solo in Compose.
- Git:
  - lavoro su `main`, senza worktree;
  - prima di ogni commit `git status`, controllo del diff e staging selettivo;
  - Conventional Commits in italiano, che terminano con
    `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`;
  - mai push;
  - mai versionare `.env`, `.venv/`, cache, `data/`, `LLM_Lez_5.pdf`.
- Non modificare il file `.env` dell'utente.
- Ogni task termina con la suite predefinita verde (`pytest`, senza LM Studio).

## Review Focus

1. **Accenti e simboli tramite stdio su Windows.** Una nota «Consegnare il report venerdì €» deve
   tornare identica dopo il passaggio tra i due processi. → Task 8, `test_unicode_text_round_trips`.
2. **Numeri passati come stringhe** dal modello (`{"note_id": "3"}`, `{"value": "10"}`). Devono
   funzionare come i numeri, non dare un errore di trasporto. → Task 8,
   `test_numeric_strings_are_coerced`.
3. **Argomenti mancanti o in più per uno strumento MCP.** Devono produrre `{"error": …}` (esito
   `tool_error`), mai un'eccezione che interrompe il turno. → Task 8, `test_missing_argument_is_tool_error`.
4. **Codice del corso scritto in modo diverso** (`" dl-101 "`). Deve trovare `DL-101`. → Task 5,
   `test_get_item_ignores_case_and_spaces`.
5. **Uscita con `esci` o Ctrl+C.** Non deve lasciare attivo il processo del server, né bloccare
   l'archivio. → Task 8, `test_close_releases_the_database` (il file si può cancellare dopo
   l'uscita), più la verifica manuale con `Get-Process` nel Task 9.

## Scostamenti dalla specifica (verificati durante la stesura)

- **`ToolSpec` invece dei tipi MCP.** In `mcp` 2.x il campo si chiama `input_schema`, non
  `inputSchema`. Per questo `McpClient.list_tools()` restituisce `ToolSpec(name, description,
  input_schema)`, e adattatore e client finto non dipendono dai tipi MCP.
- **`McpClient` riceve anche `cwd`.** Serve perché il sottoprocesso trovi il pacchetto `assistant`.
- **Nessun modello Pydantic nell'adattatore.** `StructuredTool` con `args_schema` dizionario passa
  lo schema del server a `bind_tools` senza modificarlo (verificato con langchain-core 1.7.0), quindi
  l'alternativa della spec §7 non serve. La validazione degli argomenti la fa il server.
- **Test del server con il client in memoria di fastmcp** (Task 7). La discovery e le chiamate
  attraverso stdio, con `McpClient`, sono nel Task 8.

---

### Task 1: Traduzione in inglese del codice esistente

Comportamento invariato (spec §4). Nessuna funzionalità nuova.

**Files:**
- Rename (`git mv`):
  - `assistente/` → `assistant/`;
  - `modello.py` → `model.py`, `strumenti.py` → `tools.py`, `grafo.py` → `graph.py`,
    `sessione.py` → `session.py`, `terminale.py` → `terminal.py`;
  - `tests/test_grafo.py` → `test_graph.py`, `test_strumenti.py` → `test_tools.py`,
    `test_sessione.py` → `test_session.py`, `test_terminale.py` → `test_terminal.py`,
    `test_reale.py` → `test_real.py`.
- Modify: tutti i moduli di `assistant/`, tutti i file di `tests/`, `pytest.ini`, `.env.example`,
  `Dockerfile`, `compose.yaml`, `README.md`, `../CLAUDE.md` (sezione «Struttura e comandi»).

**Interfaces:**
- Produces (nomi usati da tutti i task successivi):
  - `assistant.config`: `Config(base_url, model, max_steps=5, log_level="INFO")`, `ConfigError`,
    `load_config(env) -> Config`, `LOG_LEVELS`.
  - `assistant.model`: `create_model(config, tools) -> Runnable`.
  - `assistant.tools`: `create_current_time_tool(now=…) -> BaseTool`, tool
    `get_current_time(timezone)`, `CURRENT_TIME_DESCRIPTION`.
  - `assistant.graph`:
    - `State{messages, steps}`, `SYSTEM_PROMPT`;
    - `route(state, max_steps) -> Literal["tools", "limit", "end"]`;
    - `build_graph(model, tools, max_steps)`, con i nodi `"llm"`, `"tools"`, `"limit"`.
  - `assistant.session`: `Session(graph)`, `.messages`, `.send(text) -> str`, `EMPTY_REPLY`.
  - `assistant.terminal`: `run(session, read=input, write=print)`.
  - `assistant.__main__`: `main(env=os.environ) -> int`.
  - `tests/conftest.py`:
    - `FakeModel(replies)`, con `.calls`;
    - `fake_graph(model, tools=None, max_steps=5)`;
    - `tool_call(timezone="Asia/Tokyo", id="c1", name="get_current_time")`;
    - `lm_studio_error()`, `FIXED_NOW`.
  - Aiuti locali ai test: `start_turn(model, text="salve", **kwargs)` e `tool_messages(messages)`
    in `test_graph.py`; `VALID` in `test_main.py` e `test_config.py`.
  - Marcatore pytest `real`.

- [x] **Step 1: Registrare la base.** Eseguire `pytest -v` e annotare il risultato.
  Expected: `60 passed, 2 deselected`.

- [x] **Step 2: Rinominare i file con `git mv`** come elencato sopra.

- [x] **Step 3: Tradurre identificatori e chiavi** secondo la tabella della spec §4.
  - Comprende i parametri (`adesso` → `now`, `fuso` → `timezone`, `leggi`/`scrivi` → `read`/`write`),
    le variabili locali, i commenti e le docstring.
  - Chiavi dei risultati: `{"timezone", "datetime"}` e `{"error"}`.
  - In `config.py` si leggono `LMSTUDIO_MODEL` e `MAX_STEPS`. I messaggi restano in italiano e
    cambiano solo i nomi: «Manca LMSTUDIO_MODEL.», «MAX_STEPS deve essere un intero ≥ 1,
    ricevuto '…'.».
  - Restano identici (italiano) i testi dei messaggi di log, del terminale, `SYSTEM_PROMPT` (che
    cita `get_current_time` al posto di `ora_corrente`) e i testi d'errore degli strumenti.
  - Descrizione dello strumento: «Restituisce data e ora correnti nel fuso orario indicato.
    `timezone` è un nome IANA, per esempio "Europe/Rome" o "Asia/Tokyo".»

- [x] **Step 4: Tradurre i test.** Nomi delle funzioni di test in inglese (es.
  `test_risposta_fissa_in_un_passo` → `test_fixed_reply_in_one_step`). Stesse asserzioni, con i
  nomi e le chiavi nuovi. Nessun test aggiunto né tolto.

- [x] **Step 5: Aggiornare la configurazione dei file.**
  - `pytest.ini`: `addopts = -m "not real"` e il marcatore
    `real: prove con LM Studio attivo (eseguire con: pytest -m real)`.
  - `.env.example`: `LMSTUDIO_MODEL=google/gemma-4-e2b`, `MAX_STEPS=5`; il resto invariato.
  - `Dockerfile`: utente `assistant`, `COPY assistant/ assistant/`,
    `CMD ["python", "-m", "assistant"]`.
  - `compose.yaml`: servizio `assistant`.

- [x] **Step 6: Verificare che non resti italiano nel codice.**
  Run: `git grep -n -E "assistente|modello|strumenti|grafo|sessione|terminale|fuso|data_ora|errore|passi|MODELLO|MAX_PASSI|reale" -- assistant tests pytest.ini Dockerfile compose.yaml .env.example`
  Expected: solo righe con testi in italiano permessi (messaggi, prompt, descrizioni), nessun
  identificatore.

- [x] **Step 7: Eseguire la suite.**
  Run: `.\.venv\Scripts\python.exe -m pytest -v`
  Expected: `60 passed, 2 deselected`, come allo Step 1.

- [x] **Step 8: Aggiornare README e `CLAUDE.md`.**
  - README: nomi dei comandi (`python -m assistant`, `pytest -m real`, servizio `assistant`),
    tabella delle variabili, esempio dello strumento, esempi di log.
  - Aggiungere al README un avviso: un `.env` con `LMSTUDIO_MODELLO`/`MAX_PASSI` va aggiornato.
  - `CLAUDE.md`, sezione «Struttura e comandi»: cartella `assistant/`, moduli nuovi, `FakeModel`,
    `test_real.py`, marcatore `real`, `python -m assistant`, `pytest -m real`.

- [x] **Step 9: Prove reali e Docker.** Con LM Studio attivo e
  `$env:LMSTUDIO_BASE_URL="http://localhost:1234/v1"; $env:LMSTUDIO_MODEL="google/gemma-4-e2b"`:
  - `.\.venv\Scripts\python.exe -m pytest -m real -v` → `2 passed`;
  - `docker compose build`, poi `"Che ore sono a Tokyo?", "esci" | docker compose run --rm -T assistant`.
    Expected: nel log c'è la chiamata `get_current_time` con `Asia/Tokyo`, e la risposta riporta
    l'orario.
  - Se il `.env` dell'utente usa ancora `LMSTUDIO_MODELLO`, la prova Docker fallisce con
    «Manca LMSTUDIO_MODEL.». È il comportamento atteso: chiedere all'utente di aggiornarlo, non
    modificarlo.

- [x] **Step 10: Commit**
  ```bash
  git add -A assistant tests pytest.ini .env.example Dockerfile compose.yaml README.md ../CLAUDE.md
  git status   # assistente/ risulta rinominata; nessun .env, data/, PDF
  git commit -m "refactor!: traduce in inglese pacchetto, moduli e identificatori" -m "BREAKING CHANGE: variabili LMSTUDIO_MODEL e MAX_STEPS al posto di LMSTUDIO_MODELLO e MAX_PASSI; avvio con python -m assistant."
  ```

---

### Task 2: Log nel formato della slide 26 ed errori di collegamento nel grafo

**Files:**
- Modify: `assistant/tools.py`, `assistant/graph.py`
- Test: `tests/test_graph.py`

**Interfaces:**
- Produces:
  - `assistant.tools.ToolUnavailableError(Exception)`: la solleva uno strumento quando il servizio
    dietro non risponde.
  - La variante di uno strumento si legge da `tool.metadata["variant"]`; senza metadati vale
    `"local"`.
- Consumes: `build_graph`, `FakeModel`, `tool_call` (Task 1).

- [x] **Step 1: Sostituire i test dei log in `tests/test_graph.py`.** I test sui vecchi testi di
  log diventano:

```python
def test_llm_step_log(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    start_turn(FakeModel([AIMessage("Ciao!")]))
    assert "step=1/5 node=llm" in caplog.text

def test_tool_call_logs_follow_slide_26(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    start_turn(FakeModel([tool_call(), tool_call(timezone="Tokio", id="c2"), AIMessage("ok")]))
    assert "step=1/5 variant=local tool=get_current_time call_id=c1 arguments={'timezone': 'Asia/Tokyo'}" in caplog.text
    assert ("step=1/5 execution=ok call_id=c1 result="
            "{'timezone': 'Asia/Tokyo', 'datetime': '2026-10-27T00:47:12+09:00'}") in caplog.text
    assert "tool_message.call_id=c1 next_node=llm" in caplog.text
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(w.startswith("step=2/5 execution=tool_error call_id=c2 result={'error'") for w in warnings)

def test_limit_and_invalid_calls_logs(caplog):
    # stessi scenari del test esistente
    ...
    assert any(w.startswith("step=1/5 invalid_tool_calls=") for w in warnings)
    assert "step=1/1 limit_reached pending=['get_current_time']" in warnings

def test_unavailable_tool_is_transport_error(caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    def down(**_): raise ToolUnavailableError("server terminato")
    remote = StructuredTool.from_function(down, name="add_note", description="d",
                                          args_schema={"type": "object", "properties": {}},
                                          metadata={"variant": "mcp"})
    r = start_turn(FakeModel([tool_call(name="add_note"), AIMessage("ok")]), tools=[remote])
    assert json.loads(tool_messages(r["messages"])[0].content) == {
        "error": "Strumento non raggiungibile: server terminato. Riprova o riavvia l'assistente."}
    assert "variant=mcp tool=add_note call_id=c1" in caplog.text
    assert "step=1/5 execution=transport_error call_id=c1" in caplog.text
```

  (`StructuredTool.from_function` accetta `args_schema` come dizionario: verificato nel venv con
  langchain-core 1.7.0.)

- [x] **Step 2: Eseguire i test.**
  Run: `pytest tests/test_graph.py -v`
  Expected: i quattro test nuovi FAIL (testi di log diversi, `ToolUnavailableError` inesistente).

- [x] **Step 3: Implementare.**
  - In `tools.py`: `class ToolUnavailableError(Exception)`.
  - In `graph.py`:
    - le righe di log della spec §8, nodo `tools`: chiamata, esecuzione, `tool_message`;
    - `step=N/M node=llm` nel nodo `llm`;
    - `step=N/M invalid_tool_calls=[…]` e `step=N/M limit_reached pending=[…]` come WARNING.
  - Esito:
    - `ToolUnavailableError` (intercettata prima di `Exception`) → `transport_error`, con il
      messaggio del test;
    - eccezione generica o risultato con chiave `"error"` → `tool_error`;
    - altrimenti → `ok`.
  - WARNING per ogni esito diverso da `ok`. Il messaggio di RF-10 non cambia.

- [x] **Step 4: Eseguire la suite.**
  Run: `pytest -v`
  Expected: tutto verde (60 + 1 nuovo, 2 deselected).

- [x] **Step 5: Commit** — `feat(grafo): registra call_id, variante ed esito delle chiamate (slide 26)`.

---

### Task 3: Convertitore di unità (`units.py`)

**Files:**
- Create: `assistant/units.py`
- Test: `tests/test_units.py`

**Interfaces:**
- Produces:
  - `convert_units(value: float, from_unit: str, to_unit: str) -> dict`;
  - solleva `ValueError(messaggio_in_italiano)` per input non valido;
  - `UNITS_DESCRIPTION: str`, la descrizione dello strumento (spec §6.1).

Tabelle (spec §6.1):
- **lunghezza**, base m: mm 0.001, cm 0.01, m 1, km 1000, in 0.0254, ft 0.3048, yd 0.9144,
  mi 1609.344;
- **massa**, base kg: mg 1e-6, g 0.001, kg 1, t 1000, oz 0.028349523125, lb 0.45359237;
- **volume**, base l: ml 0.001, l 1, gal 3.785411784;
- **temperatura**: C, F, K, passando per i kelvin (K = C + 273.15; K = (F − 32)·5/9 + 273.15).

Nomi delle grandezze, con l'articolo per i messaggi: `lunghezza`/«una lunghezza»,
`massa`/«una massa», `temperatura`/«una temperatura», `volume`/«un volume».

- [x] **Step 1: Scrivere i test.**

```python
def test_length():
    assert convert_units(10, "km", "mi") == {"value": 10, "from_unit": "km", "to_unit": "mi",
                                             "quantity": "lunghezza", "result": 6.21371}
@pytest.mark.parametrize("v,a,b,expected", [
    (1, "ft", "cm", 30.48), (2.5, "kg", "lb", 5.51156), (1, "gal", "l", 3.78541),
    (100, "C", "F", 212), (32, "F", "C", 0), (0, "K", "C", -273.15), (1500, "mg", "g", 1.5)])
def test_known_conversions(v, a, b, expected):
    assert convert_units(v, a, b)["result"] == pytest.approx(expected)
def test_units_ignore_case_spaces_and_degree():
    r = convert_units(20, " °c ", "f")
    assert (r["from_unit"], r["to_unit"], r["result"]) == ("C", "F", 68)
def test_unknown_unit():
    with pytest.raises(ValueError, match=r"^Unità sconosciuta: 'xyz'\. Unità ammesse: mm, cm, m, km, in, ft, yd, mi, mg, g, kg, t, oz, lb, C, F, K, ml, l, gal\.$"):
        convert_units(1, "xyz", "m")
def test_incompatible_quantities():
    with pytest.raises(ValueError, match=r"^Conversione impossibile: 'km' è una lunghezza, 'kg' è una massa\.$"):
        convert_units(1, "km", "kg")
@pytest.mark.parametrize("v", [float("nan"), float("inf")])
def test_non_finite_value(v):
    with pytest.raises(ValueError, match=r"^Il valore deve essere un numero finito\.$"):
        convert_units(v, "m", "km")
def test_below_absolute_zero():
    with pytest.raises(ValueError, match=r"^Temperatura sotto lo zero assoluto: -500 C\.$"):
        convert_units(-500, "C", "F")
```

- [x] **Step 2: Eseguire i test.** `pytest tests/test_units.py -v` → FAIL (modulo inesistente).

- [x] **Step 3: Implementare `convert_units`.**
  - Il risultato è `float(f"{x:.6g}")`.
  - Le unità vengono normalizzate con `strip()`, rimozione di un `°` iniziale e confronto senza
    distinzione di maiuscole; nel risultato compare la forma canonica.
  - Il valore del messaggio sullo zero assoluto si formatta con `:g`.

- [x] **Step 4: Eseguire i test.** `pytest tests/test_units.py -v` → PASS; poi `pytest` → verde.

- [x] **Step 5: Commit** — `feat(strumenti): aggiunge il convertitore di unità con elenco chiuso`.

---

### Task 4: Calcolatrice sicura (`calculator.py`)

**Files:**
- Create: `assistant/calculator.py`
- Test: `tests/test_calculator.py`

**Interfaces:**
- Produces:
  - `calculate(expression: str) -> dict`, che restituisce `{"expression": <testo senza spazi
    esterni>, "result": n}`;
  - solleva `ValueError` per input non valido;
  - `CALCULATOR_DESCRIPTION: str` (spec §6.2).

- [x] **Step 1: Scrivere i test.**

```python
@pytest.mark.parametrize("expr,expected", [
    ("17 * 23", 391), ("2 + 3 * 4", 14), ("(2 + 3) * 4", 20), ("-3 ** 2", -9), ("+5 - -2", 7),
    ("7 // 2", 3), ("7 % 3", 1), ("2 ** 10", 1024), ("0.1 + 0.2", 0.3), ("1 / 4", 0.25)])
def test_valid(expr, expected):
    assert calculate(expr) == {"expression": expr, "result": expected}
def test_integer_result_stays_int():
    assert type(calculate("6 * 7")["result"]) is int
@pytest.mark.parametrize("expr,message", [
    ("", r"^Espressione vuota\.$"),
    ("1+" * 101 + "1", r"^Espressione troppo lunga: massimo 200 caratteri\.$"),
    ("2 ^ 3", r"usa \*\* per le potenze"),
    ("3,5 + 1", r"usa il punto per i decimali"),
    ("(1 + 2", r"^Espressione non valida"),
    ("x + 1", r"^Elemento non ammesso: nome 'x'\.$"),
    ("__import__('os')", r"^Elemento non ammesso: chiamata di funzione\.$"),
    ("(1).real", r"^Elemento non ammesso: attributo\.$"),
    ("'a' * 3", r"^Elemento non ammesso: valore 'a'\.$"),
    ("True + 1", r"^Elemento non ammesso: valore True\.$"),
    ("1 << 3", r"^Elemento non ammesso: operatore '<<'\.$"),
    ("1 < 2", r"^Elemento non ammesso: confronto\.$"),
    ("1 / 0", r"^Divisione per zero\.$"),
    ("5 % 0", r"^Divisione per zero\.$"),
    ("2 ** 101", r"^Esponente troppo grande: massimo 100 in valore assoluto\.$"),
    ("9 ** 9 ** 9", r"^Esponente troppo grande"),
    ("10 ** 100 * 10", r"^Numero troppo grande: oltre 1e100\.$"),
])
def test_rejected(expr, message):
    with pytest.raises(ValueError, match=message):
        calculate(expr)
def test_no_eval_in_module():
    source = Path(calculator.__file__).read_text(encoding="utf-8")
    assert "eval(" not in source.replace('mode="eval"', "") and "exec(" not in source
```

- [x] **Step 2: Eseguire i test.** `pytest tests/test_calculator.py -v` → FAIL.

- [x] **Step 3: Implementare `calculate`.**
  - Controlli preliminari, nell'ordine: testo vuoto dopo `strip()`; lunghezza > 200; `^` presente →
    «Espressione non valida: usa ** per le potenze.»; regex `\d,\d` → «Espressione non valida: usa
    il punto per i decimali.».
  - `ast.parse(text, mode="eval")`; su `SyntaxError` → «Espressione non valida: controlla parentesi
    e operatori.».
  - Visita ricorsiva che ammette solo i nodi della spec §6.2. Ogni altro nodo produce il messaggio
    «Elemento non ammesso: …» corrispondente (nome, chiamata di funzione, attributo, valore,
    operatore, confronto; per gli altri tipi di nodo «costrutto '<NomeNodo>'»).
  - Per `Pow`: se l'esponente supera 100 in valore assoluto si rifiuta **prima** di calcolare.
  - Dopo ogni operazione: se il valore assoluto supera 1e100 → «Numero troppo grande: oltre 1e100.».
  - `ZeroDivisionError` → «Divisione per zero.».
  - Un risultato `float` viene restituito come `float(f"{x:.12g}")`.

- [x] **Step 4: Eseguire i test.** `pytest tests/test_calculator.py -v` → PASS; `pytest` → verde.

- [x] **Step 5: Commit** — `feat(strumenti): aggiunge la calcolatrice sicura senza eval`.

---

### Task 5: Catalogo locale (`catalog.py`, `assistant/data/catalog.json`)

**Files:**
- Create: `assistant/catalog.py`, `assistant/data/catalog.json`
- Test: `tests/test_catalog.py`

**Interfaces:**
- Produces:
  - `Catalog(items: list[dict])`;
  - `Catalog.load(path: Path = DEFAULT_CATALOG_PATH) -> Catalog`;
  - `.search(query: str, max_results: int = 5) -> dict`, `.get_item(code: str) -> dict`;
  - `ValueError` per input non valido; `SEARCH_DESCRIPTION`, `GET_ITEM_DESCRIPTION` (spec §6.3);
  - `DEFAULT_CATALOG_PATH = Path(__file__).parent / "data" / "catalog.json"`.

`catalog.json`: dati d'esempio inventati, in quest'ordine. Ogni corso ha `code`, `title`,
`location`, `duration_hours` e `description` (una frase in italiano):

| code | title | location | duration_hours |
|------|-------|----------|----------------|
| DL-101 | Deep learning: fondamenti | Pordenone | 40 |
| DL-201 | Deep learning per la visione artificiale | Udine | 32 |
| LLM-101 | LLM: costruire chatbot e agenti | Pordenone | 48 |
| PY-101 | Python per l'analisi dei dati | Trieste | 40 |
| PY-201 | Python avanzato: test e packaging | Online | 24 |
| NET-101 | Reti e sicurezza informatica | Udine | 36 |
| DB-101 | Basi di dati e SQL | Trieste | 30 |
| CLD-101 | Docker e servizi in container | Online | 20 |

- [x] **Step 1: Scrivere i test.**

```python
def test_search_by_word():
    r = Catalog.load().search("python")
    assert r == {"query": "python", "total": 2, "results": [
        {"code": "PY-101", "title": "Python per l'analisi dei dati", "location": "Trieste"},
        {"code": "PY-201", "title": "Python avanzato: test e packaging", "location": "Online"}]}
def test_search_all_words_must_match():
    assert [i["code"] for i in Catalog.load().search("deep UDINE")["results"]] == ["DL-201"]
def test_search_by_code_and_location():
    assert Catalog.load().search("net-101")["total"] == 1
    assert Catalog.load().search("pordenone")["total"] == 2
def test_max_results_limits_results_not_total():
    r = Catalog.load().search("python", max_results=1)
    assert (len(r["results"]), r["total"]) == (1, 2)
def test_no_results_is_declared_empty():
    assert Catalog.load().search("astrologia") == {"query": "astrologia", "results": [], "total": 0}
def test_empty_query():
    with pytest.raises(ValueError, match=r"^Il testo di ricerca è vuoto\.$"): Catalog.load().search("  ")
@pytest.mark.parametrize("n", [0, 11])
def test_max_results_out_of_range(n):
    with pytest.raises(ValueError, match=rf"^max_results deve essere tra 1 e 10, ricevuto {n}\.$"):
        Catalog.load().search("python", max_results=n)
def test_get_item_full_record():
    item = Catalog.load().get_item("LLM-101")
    assert (item["title"], item["location"], item["duration_hours"]) == ("LLM: costruire chatbot e agenti", "Pordenone", 48)
    assert item["description"]
def test_get_item_ignores_case_and_spaces():
    assert Catalog.load().get_item(" dl-101 ")["code"] == "DL-101"
def test_get_item_unknown():
    with pytest.raises(ValueError, match=r"^Nessun corso con codice 'XX-999'\. Usa search_catalog per trovare il codice\.$"):
        Catalog.load().get_item("XX-999")
def test_duplicate_codes_rejected():
    item = {"code": "A-1", "title": "t", "location": "l", "duration_hours": 1, "description": "d"}
    with pytest.raises(ValueError, match="duplicato"): Catalog([item, dict(item)])
def test_missing_field_rejected():
    with pytest.raises(ValueError, match="title"): Catalog([{"code": "A-1"}])
```

- [x] **Step 2: Eseguire i test.** `pytest tests/test_catalog.py -v` → FAIL.

- [x] **Step 3: Implementare `Catalog` e scrivere `catalog.json`.**
  - Ricerca: le parole di `query` (con `split()`, confronto con `casefold()`) devono comparire tutte
    nel testo `code + title + location`. I risultati sono nell'ordine del file.
  - `Catalog.load` legge il file in UTF-8.
  - La validazione nel costruttore produce i messaggi «Campo mancante nel catalogo: 'title' (corso
    'A-1').» e «Codice duplicato nel catalogo: 'A-1'.».

- [x] **Step 4: Eseguire i test.** `pytest tests/test_catalog.py -v` → PASS; `pytest` → verde.
  Verificare con `git status` che `assistant/data/catalog.json` sia fra i file da aggiungere: non
  deve essere ignorato.

- [x] **Step 5: Commit** — `feat(strumenti): aggiunge il catalogo locale dei corsi con ricerca e dettaglio`.

---

### Task 6: Note persistenti (`notes.py`) e `NOTES_DB`

**Files:**
- Create: `assistant/notes.py`
- Modify: `assistant/config.py`, `.env.example`, `.gitignore`
- Test: `tests/test_notes.py`, `tests/test_config.py`

**Interfaces:**
- Produces:
  - `NotesStore(path: str | Path, now: Callable[[], datetime] = lambda: datetime.now(timezone.utc))`;
  - `.add(text: str) -> dict`, `.list(limit: int = 10) -> dict`, `.delete(note_id: int) -> dict`;
  - `ValueError` per input non valido e per l'archivio non accessibile;
  - `ADD_NOTE_DESCRIPTION`, `LIST_NOTES_DESCRIPTION`, `DELETE_NOTE_DESCRIPTION` (spec §6.4);
  - `Config.notes_db: str = "data/notes.sqlite3"` (variabile `NOTES_DB`; vuota → default).

- [x] **Step 1: Scrivere i test** (archivio in `tmp_path`, istante fisso
  `datetime(2026, 11, 9, 14, 2, 11, tzinfo=timezone.utc)`).

```python
def test_add_returns_id_and_date(store):
    assert store.add("  Consegnare il report venerdì  ") == {
        "id": 1, "text": "Consegnare il report venerdì", "created_at": "2026-11-09T14:02:11+00:00"}
def test_list_newest_first_with_limit_and_total(store):
    for t in ("a", "b", "c"): store.add(t)
    r = store.list(limit=2)
    assert [n["text"] for n in r["notes"]] == ["c", "b"] and r["total"] == 3
def test_list_empty(store):
    assert store.list() == {"notes": [], "total": 0}
def test_delete_returns_deleted_note(store):
    store.add("a")
    assert store.delete(1) == {"deleted": {"id": 1, "text": "a", "created_at": "2026-11-09T14:02:11+00:00"}}
    assert store.list()["total"] == 0
def test_delete_unknown_id_deletes_nothing(store):
    store.add("a")
    with pytest.raises(ValueError, match=r"^Nessuna nota con id 99: nessuna nota eliminata\.$"):
        store.delete(99)
    assert store.list()["total"] == 1
@pytest.mark.parametrize("text,message", [("   ", r"^Il testo della nota è vuoto\.$"),
    ("x" * 501, r"^Il testo della nota è troppo lungo: massimo 500 caratteri\.$")])
def test_invalid_text(store, text, message):
    with pytest.raises(ValueError, match=message): store.add(text)
@pytest.mark.parametrize("limit", [0, 51])
def test_limit_out_of_range(store, limit):
    with pytest.raises(ValueError, match=rf"^limit deve essere tra 1 e 50, ricevuto {limit}\.$"):
        store.list(limit)
def test_notes_survive_reopening(tmp_path):
    NotesStore(tmp_path / "n.sqlite3").add("resta")
    assert NotesStore(tmp_path / "n.sqlite3").list()["notes"][0]["text"] == "resta"
def test_deleted_ids_are_not_reused(store):
    store.add("a"); store.add("b"); store.delete(2)
    assert store.add("c")["id"] == 3
def test_inaccessible_store(tmp_path):
    with pytest.raises(ValueError, match=r"^Archivio delle note non accessibile: "):
        NotesStore(tmp_path / "missing" / "n.sqlite3").add("a")
```

  In `tests/test_config.py` aggiungere:
  - `test_notes_db_default_and_override`: default `"data/notes.sqlite3"`, `NOTES_DB=" x.db "` →
    `"x.db"`, `NOTES_DB=""` → default;
  - aggiornare `test_valid_values_and_defaults`, perché `Config` ha un campo in più.

- [x] **Step 2: Eseguire i test.** `pytest tests/test_notes.py tests/test_config.py -v` → FAIL.

- [x] **Step 3: Implementare.**
  - `NotesStore`:
    - una connessione per operazione (`with closing(sqlite3.connect(path))` e transazione), tabella
      della spec §6.4 creata se manca;
    - ogni `sqlite3.Error` diventa `ValueError(f"Archivio delle note non accessibile: {e}.")`;
    - `created_at` è `now().astimezone(timezone.utc).isoformat(timespec="seconds")`.
  - `NotesStore` non crea cartelle: lo fa `__main__.py` (Task 9).
  - `Config.notes_db` e la lettura di `NOTES_DB`.
  - `.env.example`: riga commentata `# NOTES_DB=data/notes.sqlite3`.
  - `.gitignore`: aggiungere `/data/`.

- [x] **Step 4: Eseguire i test.** `pytest -v` → verde.

- [x] **Step 5: Commit** — `feat(strumenti): aggiunge l'archivio SQLite delle note persistenti`.

---

### Task 7: Dipendenza `fastmcp` e server MCP (`mcp_server.py`)

**Files:**
- Create: `assistant/mcp_server.py`
- Modify: `requirements.txt`, `constraints.txt`
- Test: `tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `convert_units`, `calculate`, `Catalog`, `NotesStore` e le rispettive descrizioni
  (Task 3–6).
- Produces:
  - `build_server(notes: NotesStore, catalog: Catalog) -> FastMCP`, con nome
    «Strumenti del laboratorio» e i 7 strumenti `convert_units(value: float, from_unit: str, to_unit: str)`,
    `calculate(expression: str)`, `search_catalog(query: str, max_results: int = 5)`,
    `get_item(code: str)`, `add_note(text: str)`, `list_notes(limit: int = 10)`,
    `delete_note(note_id: int)`, ciascuno `-> dict`;
  - `main(argv: list[str] | None = None) -> int`, avviabile con
    `python -m assistant.mcp_server --notes-db PATH [--log-level INFO]`.

- [x] **Step 1: Installare e fissare la dipendenza.**
  - Aggiungere a `requirements.txt`:
    ```
    # Server FastMCP e client stdio (lezione 5)
    fastmcp==4.1.6
    ```
  - Eseguire `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`.
    Expected: nessun pacchetto già fissato viene cambiato (nessun «Successfully uninstalled» di
    pacchetti presenti in `constraints.txt`). Se compare `ResolutionImpossible`: fermarsi e riferire.
  - Eseguire `.\.venv\Scripts\python.exe -m pip check` → «No broken requirements found.».
  - Eseguire `.\.venv\Scripts\python.exe -c "from fastmcp import FastMCP, Client; from fastmcp.client.transports import StdioTransport; from fastmcp.exceptions import ToolError"` → nessun errore.

- [x] **Step 2: Scrivere i test.** Si usa il client in memoria di fastmcp; la prova su stdio è nel
  Task 8.

```python
def call(server, name, args):
    async def go():
        async with Client(server) as c:
            return await c.call_tool(name, args, raise_on_error=False)
    return asyncio.run(go())

@pytest.fixture
def server(tmp_path):
    return build_server(NotesStore(tmp_path / "n.sqlite3"), Catalog.load())

def test_discovery_lists_the_seven_tools_with_schemas(server):
    async def go():
        async with Client(server) as c: return await c.list_tools()
    tools = {t.name: t for t in asyncio.run(go())}
    assert set(tools) == {"convert_units", "calculate", "search_catalog", "get_item",
                          "add_note", "list_notes", "delete_note"}
    assert tools["add_note"].description == ADD_NOTE_DESCRIPTION
    assert tools["convert_units"].input_schema["required"] == ["value", "from_unit", "to_unit"]
    assert tools["delete_note"].input_schema["properties"]["note_id"]["type"] == "integer"
def test_structured_result(server):
    r = call(server, "calculate", {"expression": "17 * 23"})
    assert (r.is_error, r.structured_content) == (False, {"expression": "17 * 23", "result": 391})
def test_tool_error_has_no_false_success(server):
    r = call(server, "get_item", {"code": "XX-999"})
    assert r.is_error and r.structured_content is None
    assert "Nessun corso con codice 'XX-999'" in r.content[0].text
def test_note_round_trip_and_log(server, caplog):
    caplog.set_level(logging.INFO, logger="assistant.mcp_server")
    assert call(server, "add_note", {"text": "x"}).structured_content["id"] == 1
    assert call(server, "delete_note", {"note_id": 1}).structured_content["deleted"]["id"] == 1
    assert "event=note_added id=1" in caplog.text and "event=note_deleted id=1" in caplog.text
```

- [x] **Step 3: Eseguire i test.** `pytest tests/test_mcp_server.py -v` → FAIL (modulo inesistente).

- [x] **Step 4: Implementare `mcp_server.py`.**
  - Ogni strumento è registrato con `@server.tool(name=…, description=…)` e chiama la logica
    corrispondente; un `ValueError` diventa `ToolError(str(e))`.
  - `add_note` e `delete_note` scrivono `log.info("event=note_added id=%d", …)` /
    `"event=note_deleted id=%d"`.
  - `main`:
    - `argparse` con `--notes-db` (obbligatorio) e `--log-level` (default `INFO`);
    - `logging.basicConfig(stream=sys.stderr, level=…, format="%(asctime)s %(levelname)s %(name)s: %(message)s")`;
    - `build_server(NotesStore(args.notes_db), Catalog.load()).run(transport="stdio")`, senza banner
      sullo stdout. Se `run` ha un'opzione per il banner (`show_banner=False`), usarla e
      verificarla nel codice installato.
  - Blocco `if __name__ == "__main__": sys.exit(main())`.

- [x] **Step 5: Eseguire i test.** `pytest tests/test_mcp_server.py -v` → PASS.
  - Se `structured_content` è annidato (es. `{"result": {...}}`), correggere l'annotazione di
    ritorno in modo che il dizionario arrivi così com'è, come nel test.

- [x] **Step 6: Fissare le versioni.**
  - Eseguire `pytest` → verde.
  - Rigenerare `constraints.txt` con il comando del README («Installazione»):
    `@("# Versioni verificate: rigenerare con il comando del README, sezione Installazione.") + (.\.venv\Scripts\python.exe -m pip freeze) | Out-File -Encoding ascii constraints.txt`.
  - `git diff constraints.txt`: solo righe aggiunte, nessuna versione già presente cambiata.

- [x] **Step 7: Commit** — `feat(mcp): aggiunge il server FastMCP con i quattro strumenti della lezione 5`.

---

### Task 8: Client MCP sincrono (`McpClient`)

**Files:**
- Create: `assistant/mcp_client.py`
- Test: `tests/test_mcp_client.py`

**Interfaces:**
- Consumes: `python -m assistant.mcp_server` (Task 7), `ToolUnavailableError` (Task 2).
- Produces:
  - `ToolSpec(name: str, description: str, input_schema: dict)`, dataclass frozen;
  - `McpStartupError(Exception)`;
  - `McpClient(command: str, args: list[str], cwd: str | None = None, timeout: float = 30.0)`:
    context manager; `.list_tools() -> list[ToolSpec]`; `.call_tool(name: str, arguments: dict) -> dict`;
  - `server_command(notes_db: Path, log_level: str) -> tuple[str, list[str], str]`, che
    restituisce `(sys.executable, ["-m", "assistant.mcp_server", "--notes-db", str(notes_db),
    "--log-level", log_level], <cartella che contiene il pacchetto assistant>)`.

`cwd` serve perché il sottoprocesso trovi il pacchetto `assistant`. Con stdio l'ambiente del
sottoprocesso è ridotto: tutto il necessario passa come argomenti.

- [x] **Step 1: Scrivere i test** (server reale via stdio, archivio in `tmp_path`).

```python
@pytest.fixture
def client(tmp_path):
    command, args, cwd = server_command(tmp_path / "n.sqlite3", "WARNING")
    with McpClient(command, args, cwd=cwd) as c:
        yield c

def test_list_tools_over_stdio(client):
    specs = {s.name: s for s in client.list_tools()}
    assert len(specs) == 7 and specs["calculate"].description == CALCULATOR_DESCRIPTION
    assert specs["search_catalog"].input_schema["properties"]["max_results"]["default"] == 5
def test_call_returns_structured_dict(client):
    assert client.call_tool("convert_units", {"value": 10, "from_unit": "km", "to_unit": "mi"})["result"] == 6.21371
def test_tool_error_becomes_error_dict(client):
    assert client.call_tool("delete_note", {"note_id": 99}) == {
        "error": "Nessuna nota con id 99: nessuna nota eliminata."}
def test_missing_argument_is_tool_error(client):
    assert set(client.call_tool("add_note", {})) == {"error"}
def test_numeric_strings_are_coerced(client):
    assert client.call_tool("convert_units", {"value": "10", "from_unit": "m", "to_unit": "cm"})["result"] == 1000
    client.call_tool("add_note", {"text": "a"})
    assert "deleted" in client.call_tool("delete_note", {"note_id": "1"})
def test_unicode_text_round_trips(client):
    assert client.call_tool("add_note", {"text": "Consegnare il report venerdì €"})["text"] == "Consegnare il report venerdì €"
def test_startup_failure_raises():
    with pytest.raises(McpStartupError):
        with McpClient(sys.executable, ["-m", "assistant.no_such_module"]): pass
def test_call_after_close_is_unavailable(tmp_path):
    command, args, cwd = server_command(tmp_path / "n.sqlite3", "WARNING")
    with McpClient(command, args, cwd=cwd) as c: pass
    with pytest.raises(ToolUnavailableError): c.call_tool("calculate", {"expression": "1+1"})
def test_close_releases_the_database(tmp_path):
    db = tmp_path / "n.sqlite3"
    command, args, cwd = server_command(db, "WARNING")
    with McpClient(command, args, cwd=cwd) as c: c.call_tool("add_note", {"text": "a"})
    db.unlink()   # su Windows fallisce se il processo del server tiene ancora il file
```

- [x] **Step 2: Eseguire i test.** `pytest tests/test_mcp_client.py -v` → FAIL.

- [x] **Step 3: Implementare `McpClient`.** È il punto delicato: entrata e uscita dal contesto del
  client fastmcp devono avvenire nello **stesso task asyncio** (cancel scope di anyio). Per questo
  una coroutine di servizio lunga quanto la sessione tiene aperto il client, e le chiamate arrivano
  come task separati nello stesso loop:

```python
async def _serve(self, ready: concurrent.futures.Future) -> None:
    try:
        transport = StdioTransport(self._command, self._args, cwd=self._cwd,
                                   keep_alive=False, log_file=sys.stderr)
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
```

  - `__enter__`:
    1. crea un loop nuovo, avviato con `run_forever` in un thread demone `mcp-client`;
    2. `self._serving = run_coroutine_threadsafe(self._serve(ready), loop)`;
    3. `ready.result(self._timeout)`; qualsiasi eccezione o timeout → ferma il loop e solleva
       `McpStartupError(<motivo leggibile>)`.
  - `__exit__`:
    1. `loop.call_soon_threadsafe(self._stop.set)`;
    2. attende `self._serving` (al massimo 10 s, ignorando gli errori di chiusura);
    3. ferma il loop, `join` del thread, `loop.close()`.
  - `list_tools`: da `client.list_tools()` costruisce `ToolSpec(t.name, t.description or "", t.input_schema)`.
  - `call_tool`:
    - se il client è `None` → `ToolUnavailableError("sessione MCP chiusa")`;
    - altrimenti `run_coroutine_threadsafe(client.call_tool(name, arguments, timeout=self._timeout, raise_on_error=False), loop).result(self._timeout + 5)`;
    - timeout → `ToolUnavailableError(f"nessuna risposta entro {self._timeout:g} s")`;
    - altra eccezione → `ToolUnavailableError(str(e) or type(e).__name__)`;
    - `is_error` → `{"error": "\n".join(testi dei contenuti)}`;
    - altrimenti → `structured_content or {}`.

- [x] **Step 4: Eseguire i test.** `pytest tests/test_mcp_client.py -v` → PASS. Se un test di
  Review Focus fallisce, correggere il codice, non il test. Esempio: se il testo con «venerdì €» si
  altera, controllare la codifica dei flussi stdio.

- [x] **Step 5: Eseguire la suite.** `pytest -v` → verde. Annotare la durata dei test MCP
  (`--durations=5`).

- [x] **Step 6: Commit** — `feat(mcp): aggiunge il client MCP sincrono con sessione stdio persistente`.

---

### Task 9: Adattatore, avvio e prompt di sistema

**Files:**
- Modify: `assistant/mcp_client.py`, `assistant/__main__.py`, `assistant/graph.py` (`SYSTEM_PROMPT`)
- Test: `tests/test_mcp_client.py`, `tests/test_main.py`, `tests/test_graph.py`, `tests/conftest.py`

**Interfaces:**
- Consumes: `McpClient`, `ToolSpec`, `McpStartupError`, `server_command` (Task 8);
  `Config.notes_db` (Task 6).
- Produces:
  - `ALLOWED_MCP_TOOLS: tuple[str, ...]`, con i 7 nomi;
  - `create_mcp_tools(client, allowed=ALLOWED_MCP_TOOLS) -> list[BaseTool]`;
  - in `tests/conftest.py`: `FakeMcpClient(specs: list[ToolSpec], fail_on_enter: bool = False)`,
    che registra le chiamate in `.calls` e restituisce `{"ok": True}`; `MCP_SPECS`, i 7
    `ToolSpec` d'esempio con schema `{"type": "object", "properties": {}}`.

- [x] **Step 1: Scrivere i test.**

```python
# test_mcp_client.py
def test_adapter_keeps_server_contract():
    spec = ToolSpec("add_note", "Salva una nota", {"type": "object",
           "properties": {"text": {"type": "string"}}, "required": ["text"]})
    fake = FakeMcpClient([spec])
    [t] = create_mcp_tools(fake)
    assert (t.name, t.description, t.metadata) == ("add_note", "Salva una nota", {"variant": "mcp"})
    assert convert_to_openai_tool(t)["function"]["parameters"] == spec.input_schema
    assert t.invoke({"text": "ciao"}) == {"ok": True}
    assert fake.calls == [("add_note", {"text": "ciao"})]
def test_adapter_drops_tools_not_allowed(caplog):
    caplog.set_level(logging.INFO, logger="assistant.mcp_client")
    tools = create_mcp_tools(FakeMcpClient(MCP_SPECS + [ToolSpec("shell", "x", {"type": "object"})]))
    assert [t.name for t in tools] == [s.name for s in MCP_SPECS]
    assert "non consentito" in caplog.text and "shell" in caplog.text
def test_adapter_warns_on_missing_allowed_tool(caplog):
    create_mcp_tools(FakeMcpClient(MCP_SPECS[1:]))
    assert any(r.levelno == logging.WARNING and MCP_SPECS[0].name in r.getMessage() for r in caplog.records)

# test_main.py (FakeMcpClient al posto di McpClient in tutti i test di main)
def test_all_tools_reach_the_model(monkeypatch): ...
    assert names == ["get_current_time", *ALLOWED_MCP_TOOLS]
def test_mcp_startup_failure_exits_1(capsys, monkeypatch):
    # FakeMcpClient(fail_on_enter=True) solleva McpStartupError("comando non trovato")
    assert main(VALID) == 1
    assert "Server MCP non avviato: comando non trovato" in capsys.readouterr().err
def test_name_collision_exits_1(capsys, monkeypatch):
    # specs con un ToolSpec("get_current_time", …)
    assert main(VALID) == 1
    assert "Strumenti con lo stesso nome: 'get_current_time'." in capsys.readouterr().err
def test_notes_folder_is_created(tmp_path, monkeypatch):
    main({**VALID, "NOTES_DB": str(tmp_path / "sub" / "n.sqlite3")})
    assert (tmp_path / "sub").is_dir()
# test_graph.py
def test_system_prompt_mentions_every_tool():
    for name in ["get_current_time", *ALLOWED_MCP_TOOLS]: assert name in SYSTEM_PROMPT
```

  Aggiornare `test_library_http_logs_hidden_at_info` aggiungendo `"mcp"` e `"fastmcp"` alla lista
  dei logger.

  In `test_main.py` una fixture autouse:
  - imposta `monkeypatch.setattr(entry, "McpClient", lambda *a, **k: FakeMcpClient(MCP_SPECS))`,
    dove `entry` è `assistant.__main__`; i test che cambiano specs o `fail_on_enter` la
    risostituiscono;
  - fa partire ogni `main(...)` con `NOTES_DB` in `tmp_path`, così nessun test crea `data/` nel
    repository.

- [x] **Step 2: Eseguire i test.** `pytest tests/test_mcp_client.py tests/test_main.py tests/test_graph.py -v` → FAIL.

- [x] **Step 3: Implementare.**
  - `create_mcp_tools`, come nella spec §7:
    - `StructuredTool(name=…, description=…, args_schema=spec.input_schema, func=…, metadata={"variant": "mcp"})`;
    - `func` creata da una funzione fabbrica (`_caller(client, name)`), per evitare la chiusura
      tardiva sulla variabile del ciclo;
    - log: `strumento MCP non consentito, ignorato: shell` (INFO) e
      `strumento MCP consentito ma assente dal catalogo: <nome>` (WARNING).
  - `__main__.py`:
    1. dopo il logging, `notes_db = Path(config.notes_db).resolve()` e
       `notes_db.parent.mkdir(parents=True, exist_ok=True)`;
    2. `with McpClient(*command, cwd=cwd) as client:`, con i valori di `server_command`;
    3. `McpStartupError` → «Server MCP non avviato: {e}» su stderr, `return 1`;
    4. strumenti `[create_current_time_tool(), *create_mcp_tools(client)]`; nomi duplicati →
       «Strumenti con lo stesso nome: '<nome>'.» su stderr, `return 1`;
    5. log INFO `tools=[get_current_time (local), convert_units (mcp), …]`;
    6. modello, grafo, sessione, riga iniziale e `run(session)` dentro il `with`.
  - Logger `mcp` e `fastmcp` a WARNING insieme a `httpx`, `httpx2`, `openai`.
  - `SYSTEM_PROMPT` con il testo esatto della spec §8.

- [x] **Step 4: Eseguire la suite.** `pytest -v` → verde.

- [x] **Step 5: Prova manuale locale con LM Studio.** Eseguire
  `"Quanto fa 17 * 23?", "Ricordami di consegnare il report venerdì", "Quali note ho?", "esci" | .\.venv\Scripts\python.exe -m assistant`.
  Expected:
  - nel log si vedono `variant=mcp tool=calculate`, `tool=add_note`, `tool=list_notes`, con
    `execution=ok` e `tool_message.call_id` uguale al `call_id`;
  - nelle risposte compaiono 391 e la nota;
  - dopo l'uscita `Get-Process python` non mostra processi del server rimasti attivi.
  - Riportare l'esito così com'è (RT-4).

- [x] **Step 6: Commit** — `feat(mcp): collega gli strumenti scoperti dal server al grafo`.

---

### Task 10: Prove reali della lezione 5

**Files:**
- Modify: `tests/test_real.py`

**Interfaces:**
- Consumes: `load_config`, `create_model`, `build_graph`, `Session`, `McpClient`, `server_command`,
  `create_mcp_tools`, `create_current_time_tool`.

- [x] **Step 1: Riscrivere la fixture `real_session`.**
  - Usa un `McpClient` con l'archivio in `tmp_path` e restituisce la sessione con gli 8 strumenti.
  - Aggiungere la fabbrica `open_session(db)`, per la prova del riavvio.
  - Restano invariati il messaggio di fallimento senza variabili e i test CA-2…CA-4.

- [x] **Step 2: Aggiungere i test** (helper `calls(messages, name)` = argomenti delle chiamate a quello
  strumento).
  - `test_calculate_and_convert` (CA-16):
    - «Quanto fa 17 * 23?» → almeno una `calculate` e `"391"` nella risposta;
    - «Converti 10 km in miglia» → una `convert_units` con `from_unit` `km` e `to_unit` `mi`, e il
      risultato (`6,21` o `6.21`) nella risposta.
  - `test_remember_creates_one_note` (CA-17): «Ricordami di consegnare il report venerdì» →
    `len(calls(..., "add_note")) == 1`.
  - `test_delete_unknown_note` (CA-18): con una nota salvata, «Elimina la nota 99» → `delete_note`
    con `note_id` 99, `ToolMessage` con `error`, e `list_notes` diretto sul client ha ancora
    `total == 1`.
  - `test_notes_survive_restart` (CA-19): aggiunge una nota in una sessione, la chiude, ne apre una
    nuova sullo stesso archivio; «Quali note ho salvato?» → `list_notes` chiamato e `"report"`
    nella risposta.
  - `test_catalog_search_then_detail` (CA-20): «Quante ore dura il corso di visione artificiale?» →
    nell'ordine `search_catalog` e poi `get_item` con `code` `DL-201`, e `"32"` nella risposta.
  - `test_catalog_no_results` (CA-20): «Ci sono corsi di astrologia?» → `search_catalog` con
    `total == 0` e nessun codice del catalogo nella risposta.
  - `test_logs_correlate_call_ids` (CA-21, `caplog`): per una `call_id` di `add_note` ci sono le
    righe `variant=mcp`, `execution=ok` e `tool_message.call_id=<id>`.

- [x] **Step 3: Eseguire le prove reali.** Con LM Studio attivo:
  `.\.venv\Scripts\python.exe -m pytest -m real -v`.
  Expected: tutti PASS. Un fallimento dovuto al modello (strumento non scelto, doppia `add_note`,
  argomenti diversi) **non** si nasconde e il test non si allenta: si annotano la risposta e i
  messaggi per l'handoff.

- [x] **Step 4: Verificare la suite predefinita.** `pytest` → verde, con i test `real` deselezionati.

- [x] **Step 5: Commit** — `test(reale): aggiunge le prove con LM Studio degli strumenti MCP`.

---

### Task 11: Docker con il volume delle note

**Files:**
- Modify: `Dockerfile`, `compose.yaml`, `.dockerignore`

- [x] **Step 1: Modificare i file.**
  - `Dockerfile`: prima di `USER assistant`, `RUN mkdir /app/data && chown assistant /app/data`.
  - `compose.yaml`: nel servizio `volumes: ["notes-data:/app/data"]`; a livello radice
    `volumes: {notes-data: {}}`.
  - `.dockerignore`: aggiungere `data/`.

- [x] **Step 2: Build e contenuto dell'immagine.**
  - `docker compose build` → riuscito.
  - `docker compose run --rm -T assistant ls -A /app/assistant/data` → `catalog.json`.
  - `docker compose run --rm -T assistant ls -A /app` → nessuna cartella `data` del progetto copiata
    dall'host (c'è solo il volume).

- [x] **Step 3: CA-22.**
  - `"Quanto fa 17 * 23?", "esci" | docker compose run --rm -T assistant` → `calculate` nel log,
    391 nella risposta.
  - `"Ricordami di comprare il latte", "esci" | docker compose run --rm -T assistant`, poi
    `"Quali note ho salvato?", "esci" | docker compose run --rm -T assistant` → nel secondo
    `list_notes` restituisce la nota del primo.
  - Senza `LMSTUDIO_MODEL`: `docker compose run --rm -T -e LMSTUDIO_MODEL= assistant` → exit 1 e
    «Manca LMSTUDIO_MODEL.».

- [ ] **Step 4: Interattivo.** `docker compose run --rm assistant`: una domanda, poi `esci`; poi di
  nuovo con Ctrl+C. Expected: saluto, nessuna traccia d'errore, nessun container rimasto
  (`docker ps`).

- [x] **Step 5: Commit** — `build(docker): conserva le note in un volume e include il catalogo`.

---

### Task 12: Documentazione finale

**Files:**
- Modify: `README.md`, `docs/superpowers/handoff.md`,
  `docs/superpowers/specs/2026-10-26-assistente-laboratorio-design.md`, `../CLAUDE.md`

- [ ] **Step 1: README.**
  - Sezione «Strumenti»:
    - l'orologio locale e il server MCP con i 7 strumenti, con un esempio di domanda e di
      risultato per ciascuno;
    - catalogo: dati d'esempio inventati, in `assistant/data/catalog.json`;
    - note: dove stanno (`NOTES_DB`, volume `notes-data`), come azzerarle (cancellare il file o
      `docker volume rm` del volume).
  - Esempio di log nel formato nuovo, preso da una prova reale.
  - Diagnosi per livelli (slide 27): processo non avviato, catalogo assente, strumento elencato ma
    non chiamato, risultato corretto ma risposta sbagliata. Ogni livello con un comando verificato,
    ad esempio `python -m assistant.mcp_server --notes-db data/notes.sqlite3` avviato a mano esce
    in attesa su stdin.
  - Riportare solo comandi eseguiti in questo piano.

- [ ] **Step 2: Specifica di base.** Nei §2, §3, §5, §6, §8, §9 e §10 aggiungere la nota
  «*Rivisto il 2026-11-09: vedi [`2026-11-09-strumenti-mcp-design.md`](2026-11-09-strumenti-mcp-design.md).*».

- [ ] **Step 3: Handoff.**
  - Stato e commit della lezione 5.
  - Tabella delle verifiche: CA-1…CA-22, con il comando e l'esito reale di ciascuna.
  - Decisioni prese durante l'esecuzione.
  - Punti aperti, compresi gli esiti negativi delle prove reali con il messaggio esatto.
  - Avviso sul `.env` da aggiornare.
  - Comandi per riprendere, con i nomi nuovi.

- [ ] **Step 4: `CLAUDE.md`.** Struttura con i moduli nuovi (`units.py`, `calculator.py`,
  `catalog.py`, `notes.py`, `mcp_server.py`, `mcp_client.py`, `assistant/data/`), `FakeMcpClient` in
  `conftest.py`, volume Docker.

- [ ] **Step 5: Verifica finale.**
  - `pytest -v` → verde.
  - `git status --ignored`: `.env`, `.venv/`, `data/` e cache sono solo ignorati; il PDF resta non
    tracciato.
  - Ogni comando del README è stato eseguito in uno dei task.

- [ ] **Step 6: Commit** — `docs: aggiorna README, handoff e CLAUDE.md per la lezione 5`.
