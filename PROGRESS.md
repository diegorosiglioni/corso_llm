# Diario di lavoro

## Stato attuale (2026-11-15)

- Step 4–9 e streaming fatti dal loop autonomo il 2026-11-14 su `auto-claude` (commit
  `320c881`…`c53cc0a`); nessun push. `dev` locale a `428cc8a` (un commit avanti a `origin/dev`),
  `main`, `origin/dev` e `origin/main` a `d3b511e`.
- In corso: **revisione e integrazione di `auto-claude`** (specifica e piano del 2026-11-15, sezione
  «Revisione e integrazione» più sotto). Fatte le fasi F1 (revisione), F2 (prove reali) e F3
  (rilettura con l'utente): rapporto in `docs/superpowers/reviews/2026-11-15-auto-claude.md`, 3
  problemi gravi, 4 importanti, 29 minori; decisioni dell'utente nella sezione F3.
- Specifica e piano delle correzioni (F4, con F5 e F6) approvati dall'utente il 2026-11-15:
  `docs/superpowers/specs/2026-11-15-correzioni-auto-claude-design.md`,
  `docs/superpowers/plans/2026-11-15-correzioni-auto-claude.md` (Task 0–16).
- Prossimo: eseguire il piano dal Task 0 in una sessione nuova (prompt in
  `docs/superpowers/prossimo-prompt.txt`). Push solo su richiesta dell'utente.
- I messaggi dei commit del loop (33 su 35) non seguono i Conventional Commits: restano come sono
  (decisione dell'utente del 2026-11-15), perché riscriverli cambierebbe gli hash citati qui.

## Stato iniziale (2026-11-14)

- Branch `auto-claude`, creato da `dev` a `428cc8a`; `origin/dev` e `origin/main` allineati allo
  Step 3.
- Fatto: base delle lezioni 3–4, correzioni dell'audit, lezione 5 (MCP e quattro strumenti),
  lezione 6 Step 1 (router), Step 2 (revisore) e Step 3 (riassunto). Prossimo: Step 4 · Resource
  `utente://preferenze` (primo punto `[ ]` di `TODO.md`).
- Test senza modello, da PowerShell nella radice: `.\.venv\Scripts\python.exe -m pytest`
  (da Git Bash: `.venv/Scripts/python.exe -m pytest`). Esito al 2026-11-14:
  `297 passed, 15 deselected in 21.21s`.
- Prove reali (LM Studio attivo, variabili impostate, circa 30 minuti):
  `.\.venv\Scripts\python.exe -m pytest -m real -v`.

Dove si trova il lavoro già fatto (punti `[x]` di `TODO.md`):
- Base (lezioni 3–4): specifica `docs/superpowers/specs/2026-10-26-assistente-laboratorio-design.md`,
  piano `docs/superpowers/plans/2026-10-26-assistente-laboratorio.md`; commit `d7d0d38`…`68ceec8`
  (`assistant/graph.py`, `config.py`, `session.py`, `terminal.py`, `model.py`, `tools.py`,
  `Dockerfile`, `compose.yaml`).
- Correzioni dell'audit: specifica e piano del 2026-11-03; commit `708b40a`…`be631ef`
  (`constraints.txt`, `compose.yaml`, `.dockerignore`).
- Lezione 5: specifica e piano del 2026-11-09; commit `8ed2849`…`edcb005` (`units.py`,
  `calculator.py`, `catalog.py`, `notes.py`, `mcp_server.py`, `mcp_client.py`, `tests/test_real.py`).
- Progetto nella radice: commit `83a5fc7`.
- Step 1 · Router: specifica e piano del 2026-11-11; commit `c1f110f`…`d0bc81c` (`router.py`,
  `assistant/data/scope.txt`).
- Step 2 · Revisore: specifica e piano del 2026-11-11; commit `595c59a`…`f53b67a` (`reviewer.py`).
- Step 3 · Riassunto: specifica e piano del 2026-11-13; commit `32bdf67`…`428cc8a` (`summary.py`).
- Dettagli, verifiche e punti aperti di ogni fase: sezione «Storico» più sotto.

## Riorganizzazione iniziale (2026-11-14)

- `docs/superpowers/handoff.md` → `PROGRESS.md` (`git mv`): stesso scopo (stato, verifiche,
  decisioni). Contenuto conservato per intero nella sezione «Storico», con i titoli abbassati di un
  livello e i link relativi corretti per la nuova posizione (`docs/superpowers/...`).
- `docs/superpowers/prossimo-prompt.txt` → `_archivio/prossimo-prompt.txt` (`git mv`): prompt per
  la sessione successiva, superato (riguardava lo Step 3, già fatto) e sostituito da `PROMPT.md`.
- Creati `TODO.md` (punti fatti `[x]` e step 4–9 della lezione 6 più lo streaming facoltativo,
  dalla traccia `docs/superpowers/lezione6.md`), `PROMPT.md` e `loop.sh`.
- `CLAUDE.md`: puntatore a `PROGRESS.md` e `TODO.md` al posto di `handoff.md`; nuova sezione
  «Modalità autonoma (branch `auto-claude`)» che adatta al loop le regole su approvazioni, branch e
  commit (scelta: senza questa sezione ogni sessione del loop si fermerebbe in attesa di
  un'approvazione che non arriva).
- `docs/superpowers/requisiti.md`: i due rimandi a `handoff.md` ora indicano `PROGRESS.md`.
- `.gitignore`: aggiunti `/LLM_Lez_*.pdf` (le slide restano non tracciate, come deciso in
  precedenza, e il loop fa `git add -A`). `_archivio/` invece è versionato.
- Non toccati: `.superpowers/` (stato locale delle skill, già escluso dal suo `.gitignore`),
  `assistente-laboratorio/` (cartella vuota, residuo dello spostamento), `lezione3/` (solo locale).
- `.gitattributes`: `*.sh` sempre con fine riga LF, perché con `core.autocrlf=true` un checkout darebbe a `loop.sh` fine riga CRLF che bash non accetta.
- Nessun file cancellato.

## Step 4 · Resource MCP: preferenze dell'utente (2026-11-14)

Specifica: [`docs/superpowers/specs/2026-11-14-preferenze-design.md`](docs/superpowers/specs/2026-11-14-preferenze-design.md);
requisiti §12 (RF-39…RF-44, CA-46…CA-52). Questo piano sostituisce l'approvazione (modalità
autonoma); i punti successivi dello step seguono la specifica.

### Piano dello step (un punto di `TODO.md` per riga)

1. Specifica e requisiti §12. Verifica: `pytest` invariato (solo documenti).
2. Server: `assistant/preferences.py` (`PREFERENCES_URI`, `read_preferences_file`),
   `assistant/data/preferenze.json`, resource in `mcp_server.py` con `--preferences-file`,
   `server_command(..., preferences_file)`, `PREFERENCES_FILE` in `config.py` e `__main__.py` (per
   non lasciare la suite rossa). Test: `test_preferences.py` (lettura del file),
   `test_mcp_server.py` (`resources/list` sì, `tools/list` no, lettura, file mancante),
   `test_config.py`.
3. Client: `ResourceUnavailableError`, `McpClient.read_resource`, `FakeMcpClient.read_resource` in
   `conftest.py`. Test: `test_mcp_client.py` via stdio (leggibile, URI inesistente, file mancante,
   sessione chiusa).
4. Host: `Preferences`, `parse_preferences`, `preferences_prompt`, `with_preferences`,
   `load_preferences` in `preferences.py`; `SYSTEM_PROMPT` e parametro `preferences` di
   `build_graph`; lettura in `_converse`, riga di avvio. Test: `test_preferences.py`,
   `test_graph.py`, `test_main.py` con client e modello finti.
5. Prove reali CA-50…CA-52 (`test_real.py`), README (sezione preferenze e diagnosi), `CLAUDE.md`
   (struttura), esiti in requisiti §12 e qui. LM Studio non raggiungibile → `[!]`.

### Decisioni (scelte del progettista, dettagli nella specifica §1)

- Chiavi JSON in inglese (`language`, `timezone`, `style`), valori in italiano come nella traccia:
  regola di `CLAUDE.md` sulle chiavi JSON.
- Predefiniti `italiano`, `Europe/Rome`, `sintetico`: coincidono con il comportamento attuale.
- File di esempio nel pacchetto (`assistant/data/preferenze.json`) con `PREFERENCES_FILE`: stesso
  schema già usato per `scope.txt`/`SCOPE_FILE`.
- Il server controlla solo che sia un oggetto JSON, l'host valida campo per campo: un campo sbagliato
  non fa perdere gli altri.
- Testo italiano costruito dai valori, non il JSON grezzo, in cima al prompt: istruzioni esplicite
  per un modello piccolo.
- Solo l'agente riceve le preferenze: la traccia parla del suo prompt di sistema.
- `SYSTEM_PROMPT` senza «in italiano, in modo breve» né l'esempio `Europe/Rome`: altrimenti
  contraddirebbe le preferenze.
- Eccezione nuova `ResourceUnavailableError`: tiene separati resource e strumenti nel codice e nei log.
- `compose.yaml` e `Dockerfile` invariati: il file di esempio è già nell'immagine.

### Punto 1 · Specifica e requisiti — fatto

- Scritti la specifica e i requisiti §12. API di `fastmcp` 4.1.6 verificata con uno script usa e
  getta fuori dal progetto (`list_resources`, `read_resource`, `ResourceError(log_level=…)`,
  URI inesistente → `MCPError`).
- Test: `pytest` → 297 passed, 15 deselected (nessun codice cambiato).
- Problemi aperti: rischi nella specifica §9 (fuso predefinito ignorato dal modello, revisore con
  risposte non in italiano), da verificare nella prova reale del punto 5.

### Punto 2 · Server MCP: resource `utente://preferenze` — piano

1. `assistant/preferences.py`: `PREFERENCES_URI`, `read_preferences_file(path)` (specifica §4).
2. `assistant/data/preferenze.json` con i tre predefiniti.
3. `config.py`: `DEFAULT_PREFERENCES_FILE`, `Config.preferences_file` da `PREFERENCES_FILE`, non
   letto né validato; `.env.example` con le righe di commento.
4. `mcp_server.py`: `build_server(notes, catalog, preferences_file)`, resource con `ResourceError`
   a livello INFO e log `event=resource_read`; argomento obbligatorio `--preferences-file`.
5. `mcp_client.server_command(notes_db, log_level, preferences_file=DEFAULT_PREFERENCES_FILE)`;
   `__main__.py` passa `Path(config.preferences_file).resolve()`.
6. Test: `test_preferences.py` (file di esempio, BOM, mancante, JSON non valido, lista);
   `test_mcp_server.py` in memoria (`resources/list` con nome e `mimeType`, assente da
   `tools/list`, lettura, file mancante → errore con il messaggio italiano, log) e via stdio con
   `server_command` (argomento `--preferences-file` passato davvero); `test_config.py`;
   `test_main.py` (il server riceve il percorso assoluto). Poi `pytest` completo.

Decisioni:
- `server_command` ha `preferences_file` con default `DEFAULT_PREFERENCES_FILE`: i chiamanti
  esistenti (test del client, `test_real.py`) restano validi e il server riceve sempre l'argomento
  obbligatorio; `__main__.py` lo passa esplicito.
- `test_mcp_server.py` usa il client in memoria come gli altri test del file, più una prova via
  stdio per l'argomento della riga di comando (la specifica chiedeva stdio; così si coprono
  entrambi i percorsi).
- La riga di avvio `preferences_file=…` arriva al punto 4 con la lettura della resource (specifica §5).
- File non UTF-8 → «non leggibile» (non «non valido»): stessa scelta di `SCOPE_FILE` in `config.py`.
- Nei test si legge `mime_type`: `mimeType` in fastmcp 4.1.6 dà `FastMCPDeprecationWarning`.

### Punto 2 · Server MCP — fatto

- Implementati `assistant/preferences.py`, `assistant/data/preferenze.json`, la resource in
  `mcp_server.py` (`--preferences-file` obbligatorio), `server_command` con il file delle
  preferenze, `PREFERENCES_FILE` in `config.py` e `.env.example`, percorso assoluto da
  `__main__.py`.
- Test nuovi: `test_preferences.py` (12), `test_mcp_server.py` (+7: `resources/list` con nome,
  descrizione e `mime_type`, assente da `tools/list` che resta a 7, lettura e log
  `event=resource_read`, rilettura a ogni richiesta, file mancante → `MCPError` con il messaggio
  italiano, via stdio con `server_command`, nessuna riga «Error reading resource» a INFO),
  `test_config.py` (+2), `test_main.py` (+2, percorso predefinito e relativo reso assoluto).
- Verifica: a DEBUG il server scrive «Error reading resource» con traceback; a INFO no (il test
  sulle righe di log quindi distingue).
- `pytest` → 320 passed, 15 deselected.
- Problemi aperti: nessuno nuovo. README e `CLAUDE.md` si aggiornano al punto 5, come da piano.

### Punto 3 · Client MCP: `read_resource` — piano

1. `mcp_client.py`: `ResourceUnavailableError(Exception)`; `McpClient.read_resource(uri) -> str`
   con `_submit(lambda c: c.read_resource(uri))`, `ToolUnavailableError` → `ResourceUnavailableError`
   con lo stesso motivo; concatenazione dei `text` dei contenuti testuali, nessun testo →
   `ResourceUnavailableError("nessun contenuto testuale")` (specifica §5, «Client»).
2. `tests/conftest.py`: `FakeMcpClient(specs, fail_on_enter=False, resources=None)` con
   `read_resource(uri)` (testo registrato oppure `ResourceUnavailableError`) e `resource_reads`.
3. Test in `tests/test_mcp_client.py`: via stdio resource leggibile (JSON del file passato con
   `--preferences-file`), URI inesistente, file mancante, dopo la chiusura →
   `ResourceUnavailableError`; contenuto solo binario → errore (con un finto `_submit`, il server
   non ne espone); `FakeMcpClient.read_resource` registrata e assente. Poi `pytest` completo.

Decisioni:
- `ResourceUnavailableError` non deriva da `ToolUnavailableError`: altrimenti un `except` sugli
  strumenti catturerebbe anche la resource, mentre la specifica le vuole separate.
- Il contenuto binario (`BlobResourceContents`) è ignorato: la resource delle preferenze è testo
  JSON e decodificare base64 sarebbe codice senza uso.

### Punto 3 · Client MCP — fatto

- Implementati `ResourceUnavailableError` e `McpClient.read_resource` in `mcp_client.py`;
  `FakeMcpClient(..., resources=…)` con `read_resource` e `resource_reads` in `conftest.py`.
- Test nuovi in `test_mcp_client.py` (+10): via stdio file passato con `--preferences-file`, file
  di esempio predefinito, URI inesistente (il motivo contiene l'URI), file mancante (messaggio
  italiano del server; la sessione resta usabile per gli strumenti), lettura dopo la chiusura;
  contenuto solo binario e concatenazione dei testi con un `_submit` sostituito; eccezione distinta
  da `ToolUnavailableError`; `FakeMcpClient` con resource registrata e senza.
- `pytest` → 330 passed, 15 deselected.
- Problemi aperti: nessuno nuovo. Il client non è ancora usato dall'host (punto 4).

### Punto 4 · Host: preferenze nel prompt dell'agente — piano

1. `preferences.py`: `Preferences`, `DEFAULT_PREFERENCES`, `STYLES`, `FieldProblem`,
   `parse_preferences`, `preferences_prompt`, `with_preferences`, `load_preferences(client)` con le
   righe `resources/read …` della specifica §5.
2. `graph.py`: `SYSTEM_PROMPT` ritoccato (lingua e stile dalle preferenze, niente esempio
   `Europe/Rome`); `build_graph(..., preferences: str)` obbligatorio per nome; `llm_node` usa
   `with_summary(with_preferences(SYSTEM_PROMPT, preferences), summary)`.
3. `__main__.py`: `load_preferences(client)` dopo la discovery; `preferences=preferences_prompt(...)`;
   riga di avvio con `preferences_file=…`.
4. `conftest.py`: `fake_graph(..., preferences="")`; `test_real.py`: `open_session` passa le
   preferenze lette dalla resource (file predefinito), per non rompere le prove reali.
5. Test: `test_preferences.py` (validazione, testo, `load_preferences` con `FakeMcpClient`),
   `test_graph.py` (ordine preferenze → `SYSTEM_PROMPT` → riassunto; router e revisore senza),
   `test_main.py` (una sola lettura in più turni, strumenti invariati, resource assente →
   predefiniti e WARNING, riga di avvio). Poi `pytest` completo.

Decisioni:
- In `test_real.py` le preferenze arrivano già ora da `load_preferences` sul file predefinito: le
  prove reali restano eseguibili; il parametro del file temporaneo arriva al punto 5 (CA-50, CA-51).
- `FieldProblem` come `NamedTuple`: confrontabile nei test e leggibile nel log.

### Punto 4 · Host — fatto

- Implementati in `preferences.py` `Preferences`, `DEFAULT_PREFERENCES`, `STYLES`, `FieldProblem`,
  `parse_preferences`, `preferences_prompt`, `with_preferences`, `load_preferences`; in `graph.py`
  `SYSTEM_PROMPT` ritoccato e `build_graph(..., preferences=)`; in `__main__.py` lettura una sola
  volta dopo la discovery e riga di avvio con `preferences_file=` (percorso assoluto);
  `fake_graph(..., preferences="")`; `open_session` di `test_real.py` passa le preferenze lette dal
  file predefinito.
- Decisioni prese durante l'esecuzione:
  - `load_preferences` importa `ResourceUnavailableError` dentro la funzione: `mcp_server.py`
    importa `preferences.py` e così il sottoprocesso del server non carica il client né
    `langchain_core` (verificato con `sys.modules`).
  - Riga `problem=missing` senza `value=` (non c'è un valore da mostrare); `fallback=` scrive la
    lingua in JSON come le altre righe.
  - `timezone` confrontato esattamente (spazi non tolti), come lo strumento orologio; `language` e
    `style` dopo aver tolto gli spazi, come da specifica.
  - In `test_main.py` l'import di `langchain_core.messages` è salito prima di `assistant.*`
    (minore rimandato dello Step 2, toccato perché si aggiungeva `SystemMessage`).
- Test nuovi: `test_preferences.py` (+34: validazione campo per campo, testo, ordine, caricamento
  con `FakeMcpClient` e righe di log esatte), `test_graph.py` (+5: preferenze in cima, poi
  `SYSTEM_PROMPT`, poi il riassunto; su ogni chiamata del turno; router, revisore e riassunto senza),
  `test_main.py` (+6: una sola lettura in due turni e prima della prima domanda, strumenti di
  `bind_tools` invariati, testo al grafo, resource assente → predefiniti e un WARNING, riga di avvio).
- `pytest` → 375 passed, 15 deselected; `pytest -m real --collect-only` raccoglie le 15 prove.
- Prova di avvio con il server reale (LM Studio non usato, `esci` in pipe): `event=resource_read`,
  `resources/read … status=ok language="italiano" timezone=Europe/Rome style=sintetico`; con
  `PREFERENCES_FILE` inesistente WARNING `status=unavailable … fallback=defaults`, exit 0.
- Problemi aperti: l'effetto sul modello (fuso, lingua, stile) e le 15 prove reali con il nuovo
  `SYSTEM_PROMPT` restano da verificare al punto 5 con LM Studio. README e `CLAUDE.md` al punto 5.

### Punto 5 · Prova reale e documentazione — piano

LM Studio raggiungibile (`GET /v1/models` → `google/gemma-4-e2b`, contesto 8192).
1. `tests/test_real.py`: `open_session(config, db, wrap_agent=None, preferences_file=…)` passa il
   file a `server_command`; aiuto `write_preferences(tmp_path, **campi)` che scrive un JSON
   temporaneo partendo dai predefiniti.
2. Prove nuove: CA-50 (`timezone="America/New_York"`, «Che ore sono?» → `get_current_time` con
   quel fuso, ora dello strumento nella risposta, nessuna domanda sul fuso) e CA-51 (stessa domanda
   «Ciao, che cosa sai fare?» in due sessioni: predefinite → italiano, `language="inglese"` →
   inglese, conteggio di parole comuni su due elenchi fissi).
3. Esecuzione: prima le due prove nuove, poi l'intera suite reale (CA-52), poi `pytest`.
4. README (sezione preferenze, diagnosi con le righe `resources/read`), `CLAUDE.md` (struttura:
   `preferences.py`, `data/preferenze.json`, `PREFERENCES_FILE`), requisiti §12 con gli esiti.

Decisioni:
- CA-51 verifica la lingua, non lo stile: la specifica §7 lo fissa così (un conteggio di parole è
  oggettivo, la «sinteticità» no); lo stile resta coperto dai test senza modello sul testo del prompt.
- «Non chiede il fuso» = `get_current_time` chiamato già nel primo turno con `America/New_York` e
  ora dello strumento nella risposta: un controllo su «?» o «fuso» darebbe falsi errori (il modello
  può nominare il fuso o chiudere con una domanda di cortesia).

### Punto 5 · Prova reale e documentazione — fatto

Prove reali con LM Studio, `google/gemma-4-e2b`, contesto 8192, `MAX_STEPS=5`, altre variabili non
impostate.

| CA | Comando | Esito |
|----|---------|-------|
| CA-50, CA-51 | `pytest -m real -v -k preferences` | ✅ 2 passed in 298 s: `resources/read … status=ok … timezone=America/New_York`, `get_current_time` con `{'timezone': 'America/New_York'}` al primo passaggio, revisore `coherent=true`; risposta in italiano con i predefiniti e in inglese con `language="inglese"` |
| CA-52 | `pytest -m real -v -o log_cli=true --log-cli-level=INFO` (prima esecuzione) | ❌ 16 passed, 1 failed in 2066 s: `test_calculate_and_convert`, risposta «17 * 23 fa 391.» senza `calculate` |
| — | prova diretta (script usa e getta in `%TEMP%`, solo la prima chiamata dell'agente) | prompt dello Step 3 `calculate` 8/8, prompt dello Step 4 0/8; senza la riga dello stile, con le preferenze in fondo o con stile `dettagliato` 4/4; frasi «usa comunque gli strumenti» 0/4; «breve ed essenziale» senza «, in poche frasi» 4/4 (anche `convert_units` e l'ora con il fuso predefinito 4/4) |
| CA-16, CA-50 | `pytest -m real -k "calculate_and_convert or default_timezone"` dopo la correzione | ✅ 2 passed in 271 s, `calculate` e `convert_units` chiamati |
| CA-52 | `pytest -m real -v -o log_cli=true --log-cli-level=INFO` (dopo la correzione) | ✅ 17 passed in 2054 s (34 min). Due `review_limit_reached` già noti: CA-4 (nome «senza contesto precedente») e la domanda in due parti (orario «non verificabile»); le prove passano |
| — | `docker compose build`, poi `esci` in pipe verso `docker compose run --rm -T assistant` | ✅ `preferences_file=/app/assistant/data/preferenze.json`, `event=resource_read`, `resources/read … status=ok`, exit 0 |
| — | `pytest` | ✅ 375 passed, 17 deselected |
| — | server avviato a mano senza e con `--preferences-file` (comando del README, da Git Bash) | senza: exit 2 («the following arguments are required»); con: exit 0. README corretto |

Decisioni prese durante l'esecuzione:
- **Regressione dello Step 4 corretta** (non fragilità del test): la descrizione dello stile
  sintetico «breve ed essenziale, in poche frasi», in cima al prompt, faceva rispondere ai calcoli
  senza `calculate`. Ora `STYLES["sintetico"] = "breve ed essenziale"`; le preferenze restano in
  cima come chiede la traccia. Dettagli nella specifica §11; README, sezione «Diagnosi».
- Il comando di diagnosi del README che avvia il server a mano era rotto dal punto 2
  (`--preferences-file` obbligatorio): corretto e annotato.
- Il log di esempio nel README per CA-50 viene dalla prima esecuzione (prima della correzione):
  la correzione tocca solo la riga dello stile e CA-50 è ripassata dopo.

Problemi aperti:
- Il modello è sensibile alla formulazione del prompt: un'altra lingua o lo stile `dettagliato`
  potrebbero cambiare l'uso degli strumenti; verificato solo lo stile `dettagliato` su calcolo e
  conversione (4/4) e la lingua inglese su un saluto.
- CA-51 controlla la lingua, non lo stile (scelta della specifica §7).
- Una sola esecuzione della suite dopo la correzione: dimostra il comportamento con quelle domande.
- I falsi rifiuti del revisore (CA-4, orari) restano quelli degli Step 2 e 3, fuori traccia.

## Step 5 · Prompt MCP: comandi riusabili nella CLI (2026-11-14)

Specifica: [`docs/superpowers/specs/2026-11-14-prompt-mcp-design.md`](docs/superpowers/specs/2026-11-14-prompt-mcp-design.md);
requisiti §13 (RF-45…RF-51, CA-53…CA-60). Questo piano sostituisce l'approvazione (modalità
autonoma); i punti successivi dello step seguono la specifica.

### Piano dello step (un punto di `TODO.md` per riga)

1. Specifica e requisiti §13. Verifica: `pytest` invariato (solo documenti).
2. Server: `assistant/prompts.py` (testi, valori ammessi, descrizioni), prompt `spiega` e
   `riassumi_conversazione` in `mcp_server.py` (`PromptError` a livello INFO, log
   `event=prompt_get`). Test: `test_prompts.py`, `test_mcp_server.py`.
3. Client: `PromptArgument`, `PromptSpec`, `PromptMessage`, `PromptUnavailableError`,
   `McpClient.list_prompts` e `get_prompt`; `FakeMcpClient(..., prompts=…)` in `conftest.py`.
   Test: `test_mcp_client.py` via stdio.
4. `assistant/commands.py` (`PromptCommands`, `CommandResult`) con `/prompts` e il comando
   sconosciuto; `terminal.run(..., commands=)`; `__main__.py` (comandi e benvenuto). Test:
   `test_commands.py`, `test_terminal.py`, `test_main.py`.
5. `/prompt`: analisi con `shlex` (solo virgolette doppie, nessun escape), controllo rispetto a
   `prompts/list`, `prompts/get`, conversione dei messaggi, log; `Session.send_messages`;
   `scope.txt` esteso. Test con client e modello finti (`test_commands.py`, `test_session.py`,
   `test_terminal.py`, `test_main.py`, `test_config.py`).
6. Prove reali CA-58…CA-60 (`test_real.py`), README (sezione prompt e diagnosi), `CLAUDE.md`
   (struttura), esiti in requisiti §13 e qui. LM Studio non raggiungibile → `[!]`.

### Decisioni (scelte del progettista, dettagli nella specifica §1)

- Descrizioni degli argomenti con `Field(description=…)` come default e annotazione `str`: con
  `Annotated` `fastmcp` 4.1.6 aggiunge una nota in inglese sullo schema (verificato).
- Valori ammessi controllati dal server (`livello`: base/intermedio/avanzato; `stile`:
  sintetico/dettagliato); nome, obbligatori e sconosciuti dall'host: il server ignora in silenzio gli
  argomenti sconosciuti (verificato), quindi il controllo della traccia deve stare nell'host.
- `prompts/list` a ogni comando, nessuna cache: nei log i prompt compaiono solo quando l'utente li
  attiva, come nella tabella della traccia.
- Solo virgolette doppie e nessun escape nel comando: l'apostrofo italiano (`l'IA`) resta un
  carattere normale.
- Testo con `/` che non è un comando → «Comando sconosciuto», niente modello: un errore di battitura
  non diventa una domanda.
- `scope.txt` esteso a spiegazioni di concetti di informatica/IA e ai riassunti della
  conversazione: il prompt deve passare dal router (traccia), e aggirarlo la contraddirebbe.
- Moduli separati `prompts.py` (testi, lato server, come `units.py`) e `commands.py` (comandi, lato
  host): il server non importa codice dell'host e `terminal.py` resta piccolo.

### Punto 1 · Specifica e requisiti — fatto

- Scritti la specifica e i requisiti §13. API dei prompt di `fastmcp` 4.1.6 verificata con script usa
  e getta in `%TEMP%\step5probe` (fuori dal progetto): `list_prompts` con `required`, `get_prompt` con
  un messaggio `user`, `PromptError(log_level=…)`, errori come `MCPError`, argomenti sconosciuti
  ignorati, descrizioni degli argomenti da `Field` senza nota in inglese.
- Test: `pytest` → 375 passed, 17 deselected (nessun codice cambiato).
- Problemi aperti: rischi nella specifica §11 (ambito più largo, revisore sul riassunto), da
  verificare nella prova reale del punto 6.

### Punto 2 · Server MCP: prompt `spiega` e `riassumi_conversazione` — piano

1. `assistant/prompts.py` (logica pura, specifica §3): `LEVELS`, `SUMMARY_STYLES`,
   `MAX_TOPIC_LENGTH`, le cinque costanti delle descrizioni, `explain_prompt(topic, level)` e
   `summary_prompt(style)` con i `ValueError` in italiano.
2. `mcp_server.py`: prompt `spiega` e `riassumi_conversazione` con `Field(description=…)` come
   default; `ValueError` → `PromptError(…, log_level=INFO)`; log `event=prompt_get name=<nome>`.
3. Test: `tests/test_prompts.py` (testi per ogni livello e stile, spazi tolti, ogni errore);
   `tests/test_mcp_server.py` in memoria (`prompts/list` con descrizioni, argomenti e `required`;
   prompt assenti da `tools/list`; `prompts/get` col testo atteso e default `base`; valore non
   ammesso, obbligatorio mancante, prompt inesistente → `MCPError`; log) e via stdio con
   `server_command`. Poi `pytest` completo.

Decisioni:
- Un aiuto `_prompt(function, *args)` accanto a `_run`, invece di generalizzare `_run` con il tipo
  d'errore: due funzioni da tre righe restano più leggibili di un parametro in più.
- Log `event=prompt_get` scritto solo dopo un testo valido, come `event=resource_read`.

### Punto 2 · Server MCP — fatto

- Implementati `assistant/prompts.py` (testi, valori ammessi, descrizioni, `explain_prompt`,
  `summary_prompt`) e i prompt `spiega` e `riassumi_conversazione` in `mcp_server.py` (`_prompt`:
  `ValueError` → `PromptError` a livello INFO, log `event=prompt_get name=…`).
- Test nuovi: `test_prompts.py` (21: ogni livello e stile, spazi tolti, apostrofo, lunghezza
  massima, argomento vuoto/lungo/su più righe, livello e stile non ammessi anche con la maiuscola),
  `test_mcp_server.py` (+12: `prompts/list` con descrizioni, argomenti e `required`, `livello`
  facoltativo; prompt assenti da `tools/list` che resta a 7; `prompts/get` → un messaggio `user`
  col testo della logica pura, default `base`, log; valori non ammessi → `MCPError` col messaggio
  italiano e nessun log `prompt_get`; obbligatorio mancante e prompt inesistente → `MCPError`; via
  stdio con `server_command`: elenco, lettura, valore rifiutato, `event=prompt_get` su stderr e
  nessun traceback).
- `pytest` → 408 passed, 17 deselected.
- Problemi aperti: nessuno nuovo. I prompt non sono ancora usati dal client né dalla CLI (punti
  3–5); README e `CLAUDE.md` si aggiornano al punto 6, come da piano dello step.

### Punto 3 · Client MCP: `list_prompts` e `get_prompt` — piano

1. `mcp_client.py` (specifica §4): dataclass `PromptArgument`, `PromptSpec`, `PromptMessage`;
   `PromptUnavailableError(Exception)`; `McpClient.list_prompts()` (descrizioni assenti → `""`,
   argomenti assenti → `()`, `required` assente → `False`) e `get_prompt(name, arguments)`
   (contenuto non `TextContent` → `PromptUnavailableError("contenuto non testuale nel messaggio
   <n>")`); `ToolUnavailableError` di `_submit` → `PromptUnavailableError` con lo stesso motivo.
2. `tests/conftest.py`: `FakeMcpClient(..., prompts=None)` con nome → (`PromptSpec`, funzione
   `arguments → list[PromptMessage]`); `list_prompts`/`get_prompt` registrati in `prompt_lists` e
   `prompt_gets`; nome sconosciuto o `ValueError` della funzione → `PromptUnavailableError`.
3. Test in `tests/test_mcp_client.py`: via stdio `list_prompts` (i due prompt, descrizioni,
   argomenti, `livello` facoltativo), `get_prompt` (`spiega` col testo di `explain_prompt`, default
   `base`; `riassumi_conversazione`), valore rifiutato (messaggio italiano del server), prompt
   inesistente, dopo la chiusura → `PromptUnavailableError`; la sessione resta usabile dopo un
   errore; contenuto non testuale e campi assenti con `_submit` sostituito; eccezione distinta da
   `ToolUnavailableError` e `ResourceUnavailableError`; `FakeMcpClient` con e senza prompt. Poi
   `pytest` completo.

Decisioni:
- Numerazione dei messaggi in «contenuto non testuale nel messaggio <n>» a partire da 1: è un
  messaggio per l'utente, come `message=1/1` nei log della specifica §5.
- `FakeMcpClient.get_prompt` registra la chiamata anche quando fallisce (come `resource_reads`):
  i test dei comandi devono poter dire se `prompts/get` è stato tentato.
- Un `required=None` del server diventa `False` (`bool(...)`), come chiede la specifica per il campo
  assente.

### Punto 3 · Client MCP — fatto

- Implementati in `mcp_client.py` `PromptArgument`, `PromptSpec`, `PromptMessage`,
  `PromptUnavailableError`, `McpClient.list_prompts` e `get_prompt`; in `conftest.py`
  `FakeMcpClient(..., prompts=…)` con `list_prompts`, `get_prompt`, `prompt_lists` e `prompt_gets`.
- Miglioramento: aiuto `_submit_as(error_type, request)` che converte `ToolUnavailableError`
  nell'eccezione di resource o prompt; ora lo usano anche `read_resource`, `list_prompts` e
  `get_prompt` (il blocco `try/except` era ripetuto tre volte). `_submit` invariato: i test lo
  sostituiscono con un `lambda request: …`.
- Test nuovi in `test_mcp_client.py` (+15): via stdio `list_prompts` (due prompt con descrizioni e
  argomenti, `livello` facoltativo), `get_prompt` di `spiega` (testo di `explain_prompt`, default
  `base`) e di `riassumi_conversazione`, valore rifiutato col messaggio italiano del server (la
  sessione resta usabile per prompt e strumenti), prompt inesistente, obbligatorio mancante, dopo la
  chiusura; campi assenti → `""`, `()`, `False`, contenuto non testuale nel messaggio 2, ruoli e
  ordine conservati (con `_submit` sostituito); eccezioni distinte; `FakeMcpClient` con prompt
  registrati, nome sconosciuto, `ValueError`, senza prompt.
- `pytest` → 423 passed, 17 deselected.
- Problemi aperti: nessuno nuovo. I prompt non sono ancora usati dalla CLI (punti 4–5).

### Punto 4 · Terminale: comando `/prompts` — piano

1. `assistant/commands.py` (specifica §5): `CommandResult(output)`, `PromptCommands(client)` con
   `handle(text)`; `/prompts` (parola senza distinzione di maiuscole) → `client.list_prompts()`,
   elenco nel formato della specifica, `Il server MCP non offre prompt.` se vuoto; con altre parole →
   `Errore nel comando: il comando /prompts non ha argomenti.`; `PromptUnavailableError` →
   `Errore: prompt non disponibili (<motivo>).`; ogni altro testo con `/` → `Comando sconosciuto`.
   Log `prompts/list count=… names=…`, `prompts/list status=unavailable error="…"`,
   `prompt_command status=rejected reason="…"`.
2. `terminal.run(session, read, write, commands=None)`: testo con `/` → `commands.handle`, output
   scritto; `commands=None` → `Comandi non disponibili.`
3. `__main__._converse`: `run(session, commands=PromptCommands(client))`; benvenuto con `/prompts`.
4. Test: `tests/test_commands.py` (elenco con e senza argomenti, nessun prompt, non disponibile,
   maiuscole, argomenti in più, comando sconosciuto, righe di log esatte, nessuna chiamata
   `prompts/get`); `test_terminal.py` (comando ai comandi, sessione mai chiamata, `commands=None`);
   `test_main.py` (comandi sul client della sessione, benvenuto, `prompts/list` solo dopo il
   comando). Poi `pytest` completo.

Decisioni:
- `/prompt` resta «Comando sconosciuto» fino al punto 5, che lo aggiunge con `send_messages`;
  `CommandResult` riceve il campo `messages` al punto 5, quando serve (niente codice senza uso).
- Messaggio del comando sconosciuto: `Comando sconosciuto: '<parola>'. Scrivi /prompts per l'elenco
  dei prompt.` (la specifica fissa solo «Comando sconosciuto»; il rimando vale anche dopo il punto 5).
- Il comando sconosciuto non scrive righe di log: la specifica elenca solo le righe dei prompt, e
  non è una richiesta di prompt.
- Il rifiuto di `/prompts` con argomenti scrive `prompt_command status=rejected`, come gli altri
  errori di comando della specifica §5.

### Punto 4 · Terminale: comando `/prompts` — fatto

- Implementati `assistant/commands.py` (`CommandResult`, `format_prompts`, `PromptCommands`),
  `terminal.run(..., commands=None)` (testo con `/` mai al modello) e in `__main__.py` i comandi sul
  client della sessione e il nuovo benvenuto; README, sezione d'avvio, con una riga sui comandi.
- Decisioni prese durante l'esecuzione: un prompt o un argomento senza descrizione si mostra senza
  «: » finale; `/` solo o un testo con `/` dentro la frase («quanto fa 6 / 3?») seguono la regola
  «comincia con `/`» (il primo è un comando sconosciuto, il secondo una domanda); in `test_main.py`
  i `run` finti accettano `**kw` (`commands=` passato da `_converse`).
- Test nuovi: `test_commands.py` (15: elenco con descrizioni e argomenti, senza argomenti né
  descrizioni, nessun prompt, maiuscole, `prompts/list` non disponibile con WARNING, righe di log
  esatte, `/prompts` con argomenti rifiutato senza chiamare il client, comando sconosciuto senza
  chiamate né log, `prompts/get` mai chiamato), `test_terminal.py` (+5), `test_main.py` (+1:
  `prompts/list` solo dopo il comando, sul client della sessione; benvenuto e `PromptCommands`
  controllati in `test_startup_wires_the_modules`).
- `pytest` → 444 passed, 17 deselected.
- Prova di avvio con il server MCP reale (LM Studio non usato: nessuna domanda al modello),
  `/prompts`, `/PROMPTS altro`, `/promt`, `esci` in pipe: elenco dei due prompt come nella specifica
  §5, `prompts/list count=2 names=spiega,riassumi_conversazione`, rifiuto con `prompt_command
  status=rejected`, «Comando sconosciuto: '/promt'…», exit 0.
- Problemi aperti: `/prompt` dà ancora «Comando sconosciuto» (arriva al punto 5); la riga d'uso
  dell'elenco lo cita già.

### Punto 5 · Terminale: comando `/prompt` — piano

1. `assistant/commands.py` (specifica §5): `CommandSyntaxError`, `parse_prompt_command(text)` con
   `shlex.shlex(posix=True)`, `quotes='"'`, `escape=''`, `commenters=''`, `whitespace_split=True`;
   `check_request(specs, name, arguments)` (prompt sconosciuto, argomenti sconosciuti, obbligatori
   mancanti) e `to_messages(received)` (`user` → `HumanMessage`, `assistant` → `AIMessage`, elenco
   non vuoto, ultimo `user`); `CommandResult.messages`; `PromptCommands.handle` riconosce `/prompt`
   (senza distinzione di maiuscole) e scrive le righe `prompts/list`, `prompts/get`,
   `prompt_command` della specifica.
2. `assistant/session.py`: `Session.send_messages(messages)`; `send(text)` la richiama.
3. `assistant/terminal.py`: risultato con `messages` → `"Assistente> " + session.send_messages(…)`,
   dentro lo stesso `try` (errori di LM Studio gestiti come per le domande).
4. `assistant/data/scope.txt`: riga delle spiegazioni di concetti e riassunti della conversazione
   (specifica §7).
5. Test: `test_commands.py` (analisi, ogni errore di sintassi senza chiamate, controllo rispetto a
   `prompts/list` senza `prompts/get`, conversione e messaggi non utilizzabili, errori del client,
   righe di log esatte), `test_session.py` (`send_messages`, turno fallito), `test_terminal.py`
   (messaggi alla sessione, comando bloccato senza modello, errore di LM Studio), `test_main.py`
   (`/prompt spiega …` con client e modello finti: messaggio nella cronologia, righe di riassunto,
   router, agente, revisore), `test_config.py` (ambito predefinito). Poi `pytest` completo.

Decisioni:
- Gli errori di sintassi di `/prompt` aggiungono la riga d'uso (`Uso: /prompt nome chiave=valore …`)
  invece del rimando a `/prompts`: l'errore riguarda la forma del comando, non l'elenco dei prompt.
- `commenters=''` nell'analisi: con il default di `shlex` un `#` in un valore aprirebbe un commento
  e taglierebbe il resto del comando.
- Anche `/prompt` scrive la riga `prompts/list count=… names=…` dopo l'elenco: stesso evento MCP di
  `/prompts`, utile nella diagnosi.
- Messaggi del prompt non utilizzabili → `WARNING prompt_command status=unusable name=… reason="…"`,
  dopo le righe `prompts/get … status=ok` e dei messaggi ricevuti (la specifica non fissa la riga;
  così il log mostra che cosa ha mandato il server).
- Elenchi vuoti nei motivi: `(disponibili: nessuno)`, `(attesi: nessuno)`.

### Punto 5 · Terminale: comando `/prompt` — fatto

- Implementati in `commands.py` `CommandSyntaxError`, `parse_prompt_command`, `check_request`,
  `to_messages`, `CommandResult.messages` e il comando `/prompt` in `PromptCommands`;
  `Session.send_messages` (ora `send` la richiama); in `terminal.py` i messaggi di un comando vanno
  alla sessione dentro lo stesso `try` delle domande; `scope.txt` con le spiegazioni di concetti e i
  riassunti della conversazione; README, sezione d'avvio, con una riga su `/prompt`.
- Decisioni prese durante l'esecuzione: `_specs()` scrive la riga `prompts/list` in entrambi gli
  esiti e rilancia `PromptUnavailableError` (niente stato nell'oggetto); l'ordine dei controlli di
  sintassi segue le parole del comando (la prima parola sbagliata decide il motivo); un nome di
  prompt vuoto (`/prompt ""`) → «manca il nome del prompt».
- Test nuovi: `test_commands.py` (+38: analisi con virgolette, apostrofo, `=` e `#` nel valore,
  maiuscole del comando; dieci errori di sintassi senza chiamate al client; prompt sconosciuto,
  argomenti sconosciuti, obbligatori mancanti senza `prompts/get`; conversione `user`/`assistant`;
  nessun messaggio, ruolo non ammesso, ultimo non `user`; valore rifiutato dal server; elenco non
  disponibile; righe di log esatte e su una riga), `test_session.py` (+3), `test_terminal.py` (+3,
  compreso un comando bloccato con grafo vero e modello che non deve essere chiamato),
  `test_main.py` (+1: `/prompt spiega …` da `main` con client e modelli finti, messaggio in
  cronologia, ricevuto da router, agente e revisore, righe `prompts/get` seguite da `node=summary`,
  `node=router`, `node=llm`, `node=reviewer`), `test_config.py` (+1, ambito).
- `pytest` → 490 passed, 17 deselected.
- Prova d'avvio con il server MCP reale e LM Studio volutamente irraggiungibile
  (`LMSTUDIO_BASE_URL=http://localhost:1/v1`): obbligatorio mancante, argomento sconosciuto,
  virgolette non chiuse, prompt sconosciuto → rifiuti con `prompt_command status=rejected`;
  `livello=esperto` → `prompts/get … status=unavailable` col messaggio del server; richiesta valida
  → `event=prompt_get`, `prompts/get … status=ok messages=1`, `node=summary`, poi «Errore: LM
  Studio non ha risposto correttamente» e la sessione continua; exit 0.
- Problemi aperti: risposta del modello a un prompt, router con l'ambito esteso e suite reale
  completa (CA-58…CA-60) da verificare al punto 6 con LM Studio.

### Punto 6 · Prova reale e documentazione — piano

LM Studio raggiungibile (`GET /v1/models` → `google/gemma-4-e2b`).
1. `tests/test_real.py`: aiuto `send_prompt(session, client, text)` che passa il comando a
   `PromptCommands(client)` (come `terminal.run`) e manda i messaggi con `session.send_messages`.
2. Prove nuove: CA-58 (`/prompt spiega argomento="Model Context Protocol" livello=base`: riga
   `prompts/get name=spiega … status=ok`, router `category=conversation`, riga `node=reviewer`,
   risposta non vuota, non un rifiuto, con «protocol» o «MCP») e CA-59 («Mi chiamo Paolo», «Quanto
   fa 17 * 23?», `/prompt riassumi_conversazione stile=sintetico`: router `conversation`, «Paolo» e
   «391» nella risposta).
3. Esecuzione: prima le due prove nuove, poi l'intera suite reale (CA-60), poi `pytest`; prova da
   terminale con `python -m assistant` e `/prompt` in pipe.
4. README (sezione prompt e diagnosi con le righe `prompts/list`/`prompts/get`), `CLAUDE.md`
   (struttura: `prompts.py`), requisiti §13 con gli esiti.

Decisioni:
- `open_session` resta `(session, client)` e i comandi si costruiscono in `send_prompt` (la
  specifica §9 diceva «`open_session` restituisce anche i comandi»): un terzo elemento obbligherebbe
  a cambiare tutte le prove esistenti per nulla; il comportamento provato è lo stesso.

### Punto 6 · Prova reale e documentazione — fatto

Prove reali con LM Studio, `google/gemma-4-e2b`, `MAX_STEPS=5`, altre variabili non impostate
(da Git Bash, `LMSTUDIO_BASE_URL=http://localhost:1234/v1`).

| CA | Comando | Esito |
|----|---------|-------|
| CA-58, CA-59 | `pytest -m real -v -k "explain_prompt or summary_prompt"` (prima esecuzione) | CA-58 ✅: `prompts/get name=spiega … status=ok messages=1`, router `conversation`, revisore `coherent=true`. CA-59 ❌: «L'utente ha chiesto il risultato della moltiplicazione di 17 per 23.», senza «391» |
| CA-59 | `pytest -m real -k summary_prompt` (ripetuta) | ❌ stessa risposta senza risultato |
| — | prova diretta (`%TEMP%\step5probe2\probe.py`, stessa cronologia, prompt dell'agente con le preferenze, 4 chiamate per variante) | stile `sintetico` attuale 0/4; «…, con le richieste e i risultati ottenuti» 4/4; «…, con le domande e le risposte principali» 4/4 |
| CA-59 | `pytest -m real -k summary_prompt` dopo la correzione | ✅ 1 passed in 224 s, router `conversation`, revisore `coherent=true`, «Paolo» e «391» |
| CA-60 | `pytest -m real -v -o log_cli=true --log-cli-level=INFO` | ❌ 18 passed, 1 failed in 2256 s (38 min): CA-43, il router ha rifiutato «Come mi chiamo?» (`out_of_scope`) pur con il riassunto «L'utente si è presentato come Paolo.»; CA-27 (rifiuto fuori ambito), CA-58 e CA-59 passate |
| — | prova diretta sul router (`router_probe.py`, riassunto e cronologia di CA-43 dopo la compressione, 8 chiamate per ambito) | ambito dello Step 4 8/8 `conversation`, ambito dello Step 5 8/8 `conversation` |
| CA-43 | `pytest -m real -k survives_compression`, due volte | ✅ 2 passed (225 s e 239 s), router `conversation`, «Paolo» nella risposta |
| — | `/prompts`, `/prompt spiega argomento="Model Context Protocol"`, `/prompt riassumi_conversazione stile=sintetico`, `esci` in pipe verso `python -m assistant` | ✅ elenco dei due prompt, spiegazione e riassunto (con richiesta e risultato), righe `prompts/list`, `prompts/get … status=ok`, router `conversation`, revisore `coherent=true`, exit 0 |
| — | `docker compose build`, poi `/prompts`, `/prompt spiega livello=base`, `esci` in pipe verso `docker compose run --rm -T assistant` | ✅ elenco, rifiuto «argomenti obbligatori mancanti per 'spiega': 'argomento'» con `prompt_command status=rejected`, exit 0 |
| — | `pytest` | ✅ 490 passed, 19 deselected; `pytest -m real --collect-only` raccoglie 19 prove |

Decisioni prese durante l'esecuzione:
- **Testo dello stile `sintetico` corretto** (non fragilità del test): «in pochi punti essenziali»
  faceva riassumere solo le richieste dell'utente. Ora «in pochi punti essenziali, con le richieste e
  i risultati ottenuti» (riprende le parole dello stile `dettagliato`). Specifica §13, README
  («Diagnosi»).
- **CA-43 trattata come errore intermittente del modello, non regressione dello Step 5**: con
  l'ingresso del router ricostruito, l'ambito vecchio e quello nuovo danno entrambi 8/8
  `conversation`, e la prova ripetuta passa 2 volte su 2. Nella prova fallita il revisore aveva
  rifiutato una prima risposta sull'ora (una riscrittura in più), ma il router non vede bozze né
  indicazioni. Nessuna modifica al codice o al test.

Problemi aperti:
- Router: «Come mi chiamo?» dopo la compressione è stato rifiutato 1 volta su 3 esecuzioni di CA-43
  (dopo lo Step 3 la suite era passata). Non riprodotto con la prova diretta.
- La spiegazione del Model Context Protocol data dal modello è chiara ma sbagliata nel merito (lo
  descrive come gestione del contesto); CA-58 controlla solo che nomini il protocollo, e il revisore
  giudica la coerenza, non la correttezza. Limite del modello, annotato nel README.
- Due esecuzioni per CA-58 e due per CA-59 dopo la correzione (prova singola e suite): dimostrano il
  comportamento con quelle domande, non che il modello risponda sempre così.

## Step 6 · L'agente come servizio HTTP (2026-11-14)

Specifica: [`docs/superpowers/specs/2026-11-14-servizio-http-design.md`](docs/superpowers/specs/2026-11-14-servizio-http-design.md);
requisiti §14 (RF-52…RF-59, CA-61…CA-69). Questo piano sostituisce l'approvazione (modalità
autonoma); i punti successivi dello step seguono la specifica.

### Piano dello step (un punto di `TODO.md` per riga)

1. Specifica, requisiti §14, dipendenze (`fastapi`, `uvicorn`, `httpx` in `requirements.txt`,
   `constraints.txt` rigenerato). Verifica: `pip check`, `pytest` invariato.
2. `assistant/agent.py`: `run_turn`, `TurnResult`, `messages_to_json`, `messages_from_json`;
   `Session` delega a `run_turn`. Test: `test_agent.py`, `test_session.py`.
3. `assistant/api.py`: `create_app`, `POST /chat` (messaggio o prompt), OpenAPI; `resolve_prompt` in
   `commands.py`. Test: `test_api.py` con `TestClient`, grafo e `FakeMcpClient` finti.
4. `GET /status`, `GET /prompts`, tabella degli errori (specifica §6), `check_model` in `model.py`,
   `assistant/service.py`, `AGENT_HOST`/`AGENT_PORT` in `config.py`. Test: `test_api.py`,
   `test_service.py`, `test_model.py`, `test_config.py`.
5. `assistant/api_client.py` (`AgentClient`, `AgentError`, `RemoteSession`), CLI client
   (`__main__.py`, `commands.py`, `terminal.py`), `AGENT_URL`, `compose.yaml`; README e `CLAUDE.md`.
   Test: `test_api_client.py`, `test_commands.py`, `test_terminal.py`, `test_main.py`.
6. Prove reali CA-67…CA-69 (`test_real.py`), esiti in requisiti §14 e qui. LM Studio non
   raggiungibile → `[!]`.

### Decisioni (scelte del progettista, dettagli nella specifica §1)

- FastAPI + uvicorn: standard per API Python con OpenAPI generata da `pydantic`; endpoint sincroni.
- `httpx` 0.28.1 per la CLI e il controllo del modello: già installata e richiesta da `TestClient`.
- Formato JSON proprio simile a OpenAI (`role` `user`/`assistant`/`tool`): leggibile e documentato
  nell'OpenAPI, indipendente da LangChain, pronto per il salvataggio dello Step 7.
- Prompt MCP dentro `POST /chat` (`prompt: {name, arguments}`): il controllo dell'host resta accanto
  al client MCP, che vive nel servizio; la sintassi del comando resta nella CLI.
- Errore di uno strumento durante il turno → turno `200` con `ok: false`; MCP spento → `503` in
  `/status` e `/prompts`: lo Step 5 già passa al modello l'errore di trasporto.
- Corpo d'errore `{"error", "detail"}` con codici `400`/`502`/`503`/`500` (tranne il `422` di FastAPI).
- `AGENT_HOST` predefinito `127.0.0.1`: in locale il servizio non è raggiungibile da altri computer.
- `python -m assistant` resta il comando della CLI (ora client, `AGENT_URL`); il servizio è
  `python -m assistant.service`.
- Compose con due servizi dalla stessa immagine (`agent` e `assistant`), così `docker compose run
  --rm assistant` continua a funzionare; i quattro container restano allo Step 9.
- `Session` in processo resta e delega a `run_turn`: la usano prove reali e test.

### Punto 1 · Specifica e requisiti — fatto

- Scritti la specifica e i requisiti §14 (intestazione di `requisiti.md` aggiornata).
- Dipendenze: `fastapi==0.162.7` (nuova), `uvicorn==0.54.0` e `httpx==0.28.1` (già indirette) in
  `requirements.txt`; `constraints.txt` rigenerato con `pip freeze` (righe nuove solo
  `annotated-doc==0.0.6` e `fastapi==0.162.7`). `pip check` senza problemi.
- Prova usa e getta in `%TEMP%\step6probe` (fuori dal progetto): FastAPI 0.162.7 con starlette
  1.10.0, `TestClient` con httpx 0.28.1, risposta `400` personalizzata, `422` di validazione,
  `/openapi.json` (OpenAPI 3.1.0) e `/docs` raggiungibili.
- Test: `pytest` → 490 passed, 19 deselected (nessun codice cambiato).
- Problemi aperti: rischi nella specifica §14 (due processi in locale, cronologia dal chiamante,
  turni lunghi); il README cambierà al punto 5, quando cambiano i comandi d'avvio.

### Punto 2 · Modulo dell'agente — piano

1. `assistant/agent.py` (specifica §3–§4): `EMPTY_REPLY` (spostato da `session.py`), `TurnResult`,
   `run_turn(graph, history, summary, messages)` (copie dei messaggi, `id` nuovi a quelli
   d'apertura, messaggi del turno dopo l'ultimo d'apertura, `tools_used`), `messages_to_json`,
   `messages_from_json` (campi, ruoli, niente `system`, ordine chiamate/risposte; `ValueError`
   «messaggio N: …»).
2. `assistant/session.py`: `Session.send_messages` delega a `run_turn`.
3. Test: `tests/test_agent.py` con `fake_graph` (senza stato e argomenti invariati, risposta e
   `EMPTY_REPLY`, `tools_used` con strumento riuscito, errore, chiamata non interpretabile e limite,
   compressione, rifiuto del router, eccezioni al chiamante; andata e ritorno JSON per ogni ruolo e
   campo; ogni errore di `messages_from_json`; cronologia di un turno vero → JSON → di nuovo al
   grafo); `test_session.py` invariato deve restare verde. Poi `pytest` completo.

Decisioni:
- `run_turn` lavora su copie (`model_copy`) di cronologia e messaggi d'apertura: `add_messages`
  assegna gli `id` mancanti modificando gli oggetti ricevuti, e la specifica vuole gli argomenti
  invariati.
- `messages_from_json` rifiuta i campi sconosciuti e richiede `id` e `name` anche nelle chiamate non
  interpretabili: il nodo degli strumenti risponde con `tool_call_id=id`, quindi senza `id` la
  cronologia non sarebbe utilizzabile.
- `ok` di `tools_used` è `false` solo se il risultato è un oggetto con `error` (un testo non JSON
  non viene esaminato per sottostringhe).
- `messages_to_json` rifiuta con `ValueError` i messaggi di tipo non previsto (per esempio
  `SystemMessage`): il grafo non ne mette nella cronologia.

### Punto 2 · Modulo dell'agente — fatto

- Implementati `assistant/agent.py` (`EMPTY_REPLY`, `TurnResult`, `run_turn`, `messages_to_json`,
  `messages_from_json`) e `Session.send_messages` che delega a `run_turn` (`EMPTY_REPLY` non è più
  in `session.py`); `CLAUDE.md`, struttura, con `agent.py`.
- Decisioni prese durante l'esecuzione: `tool_calls`/`invalid_tool_calls` `null` equivalgono ad
  assenti come gli elenchi vuoti; gli `id` di chiamata possono ripetersi tra messaggi diversi
  (succede col modello finto e il controllo dell'ordine resta corretto) ma non nello stesso
  messaggio; `name` vuoto in ingresso = assente.
- Test nuovi: `tests/test_agent.py` (52: turno con strumento, cronologia e riassunto in ingresso,
  senza stato con argomenti invariati e senza `id` aggiunti, `id` nuovi ai messaggi d'apertura,
  turno aperto da più messaggi, nessun messaggio → `ValueError`, `EMPTY_REPLY`, errore dello
  strumento, chiamata non interpretabile con il testo ricevuto, chiamata non eseguita per il
  limite, strumenti dei turni precedenti esclusi, rifiuto del router, compressione (anche con gli
  strumenti del turno), eccezioni al chiamante, indicazione del revisore; andata e ritorno JSON con
  ogni ruolo e campo, contenuto a blocchi, `SystemMessage` rifiutato, cronologia di un turno vero →
  JSON → di nuovo al grafo; 26 cronologie non valide col loro messaggio). `test_session.py`
  invariato e verde.
- `pytest` → 542 passed, 19 deselected.
- Problemi aperti: nessuno nuovo. Il modulo non è ancora esposto via HTTP (punto 3); README
  invariato (comportamento della CLI uguale), si aggiorna al punto 5.

### Punto 3 · Endpoint `POST /chat` — piano

1. `assistant/commands.py`: `PromptRequestError` con le sottoclassi `PromptRejectedError`
   (controllo dell'host), `PromptListError` (`prompts/list` fallito), `PromptGetError` (`prompts/get`
   fallito o messaggi non utilizzabili); `resolve_prompt(client, name, arguments)` con le righe di
   log dello Step 5; `PromptCommands._prompt` la usa (testi e log della CLI invariati).
2. `assistant/api.py` (specifica §4–§7): modelli `pydantic` dei messaggi (`role` come
   discriminatore), di richiesta, risposta ed errore; `ApiError`; `create_app(*, graph, client)` con
   `POST /chat` (messaggio o prompt), corpo d'errore `{"error", "detail"}`, righe `api request=chat …`
   e `api response=chat …`; titolo e descrizioni dell'OpenAPI in italiano.
3. Test: `tests/test_api.py` con `TestClient`, `fake_graph` e `FakeMcpClient` (messaggio, strumento
   usato, cronologia e riassunto di un turno precedente, compressione, prompt valido e rifiutato senza
   `prompts/get` né modello, ogni errore di richiesta, cronologia e prompt, cronologia del chiamante
   invariata, `/openapi.json` e `/docs`, righe di log); `test_commands.py` con `resolve_prompt`. Poi
   `pytest` completo.

Decisioni:
- In questo punto gli errori della richiesta di `/chat` (`400` `invalid_request`, `invalid_history`,
  `prompt_rejected`; `502` `prompt_unavailable`; `503` `mcp_unavailable` di `prompts/list`): il ramo
  dei prompt non si prova senza. Errori di LM Studio (`model_unavailable`, `model_error`), `500`,
  `/status`, `/prompts` e i parametri `model_id`/`model_status` di `create_app` al punto 4 (niente
  codice senza uso).
- Cronologia descritta con modelli `pydantic` (unione discriminata da `role`, `extra="forbid"`): il
  formato compare nell'OpenAPI; forma sbagliata (ruolo sconosciuto o `system`, campo in più, tipo
  sbagliato) → `422` come nella tabella §6; ordine e testi vuoti → `messages_from_json` → `400
  invalid_history`.
- Risposta con `response_model_exclude_unset=True`: la cronologia esce esattamente come da
  `messages_to_json` (campi assenti omessi, `args: null` delle chiamate non interpretabili conservato).
- Il `422` lo produce FastAPI prima dell'endpoint: nessuna riga `api` (annotato nella specifica §7).

### Punto 3 · Endpoint `POST /chat` — fatto

- Implementati `assistant/api.py` (modelli `pydantic` dei messaggi con `role` discriminatore,
  `ChatRequest`, `ChatResponse`, `ToolUse`, `ErrorBody`, `ApiError`, `create_app(*, graph, client)`
  con `POST /chat`, righe `api request=chat …`/`api response=chat …`) e in `commands.py`
  `resolve_prompt` con `PromptRequestError` e le sottoclassi `PromptRejectedError`,
  `PromptListError`, `PromptGetError`; `PromptCommands._prompt` la usa (`_specs` e il log del
  rifiuto sono ora funzioni del modulo: niente codice duplicato tra CLI e servizio). `CLAUDE.md`,
  struttura, con `api.py`; specifica §7 con le aggiunte del punto.
- Decisioni prese durante l'esecuzione: `message` senza spazi iniziali e finali, come nel terminale
  (stessa domanda da CLI e API, CA-68); riga di richiesta con `kind=none`/`kind=both` per le
  richieste senza o con entrambi i campi; `InvalidToolCall` con `id` e `name` testo o `null` nello
  schema (la risposta non deve fallire se LM Studio manda una chiamata senza `id`; il rifiuto in
  ingresso resta di `messages_from_json`, `400`); `PromptListFails` spostato in `conftest.py` (lo
  useranno anche i test di `/prompts` e `/status`).
- Test nuovi: `tests/test_api.py` (45: messaggio con strumento e cronologia JSON attesa, spazi tolti,
  turno successivo con cronologia e riassunto del precedente, servizio senza conversazioni,
  riassunto del chiamante all'agente, compressione, cronologia con ogni ruolo e campo restituita
  uguale, errore di uno strumento nel turno `200`; prompt valido e senza argomenti, tre rifiuti
  dell'host senza `prompts/get` né modello, `prompts/list` fallito `503`, valore rifiutato dal server
  e messaggi non utilizzabili `502`; cinque `invalid_request`, quattro `invalid_history` anche con un
  prompt e senza `prompts/list`, tredici corpi non conformi `422` senza righe `api`; righe di log
  esatte e livelli; `/openapi.json` con `/chat`, codici, schemi e discriminatore; `/docs`),
  `test_commands.py` (+6, `resolve_prompt`). Test esistenti della CLI invariati e verdi.
- `pytest` → 593 passed, 19 deselected.
- Problemi aperti: errori di LM Studio (`503`/`502`) e `500` non ancora tradotti (un'eccezione del
  grafo dà il `500` predefinito di FastAPI); `/status`, `/prompts` e l'avvio con
  `python -m assistant.service` al punto 4; README invariato (il servizio non si avvia ancora da riga
  di comando), si aggiorna al punto 5.

### Punto 4 · Stato, prompt, errori e avvio del servizio — piano

1. `assistant/model.py`: `check_model(config, http=None) -> (ok, detail)` con `GET <base_url>/models`
   (timeout 5 s): non raggiungibile, codice diverso da 200, risposta non valida, modello assente.
2. `assistant/commands.py`: `available_prompts(client)` (ex `_specs`, ora pubblica) che dà
   `PromptListError("prompt non disponibili (…)")`; la usano `resolve_prompt`, `/prompts` della CLI
   e `GET /prompts`.
3. `assistant/api.py`: `create_app(*, graph, client, model_id, model_status)`; `GET /status`
   (`tools/list` per MCP, `model_status()` per il modello, `200`/`503` con lo stesso corpo, riga
   `api response=status …`); `GET /prompts` (`200` elenco, `503 mcp_unavailable`); in `/chat`
   `APIConnectionError` → `503 model_unavailable`, altro `openai.APIError` → `502 model_error`;
   qualsiasi altra eccezione in ogni endpoint → `500 internal_error` con traceback a ERROR.
4. `assistant/config.py`: `AGENT_HOST` (predefinito `127.0.0.1`, non vuoto) e `AGENT_PORT`
   (predefinita `8000`, intero 1…65535).
5. `assistant/service.py`: configurazione, logging, client MCP, strumenti, preferenze, modelli,
   grafo, `create_app`, riga `api listening=…`, `uvicorn.run(..., access_log=False,
   log_config=None)`; errori di configurazione e di MCP → stderr ed exit 1.
6. Test: `test_model.py` (`check_model` con `httpx.MockTransport`), `test_commands.py`,
   `test_api.py` (ogni riga della tabella §6, `/status` in tutte le combinazioni, `/prompts`,
   OpenAPI con i tre percorsi, righe di log), `test_config.py`, `test_service.py` (nuovo, MCP e
   `uvicorn.run` sostituiti). Poi `pytest` completo.

Decisioni:
- `service.py` ripete per ora l'avvio di `__main__.py` (logging, strumenti, modelli, grafo): al
  punto 5 `__main__.py` diventa il client HTTP e quel codice esce da lì; spostarlo ora avrebbe
  obbligato a riscrivere due volte `test_main.py`.
- Stato MCP con `tools/list` (come la specifica §1): `detail` «N strumenti» con il numero pubblicato
  dal server.
- `GET /status` e `GET /prompts` scrivono solo la riga di risposta (come l'esempio della specifica
  §7); `/status` a INFO con `200`, a WARNING con `503`.
- `APITimeoutError` deriva da `APIConnectionError` in `openai`: un solo `except` per il `503`.

### Punto 4 · Stato, prompt, errori e avvio del servizio — fatto

- Implementati `check_model` in `model.py`; `available_prompts` in `commands.py` (al posto di
  `_specs`, usata da `resolve_prompt`, dal `/prompts` della CLI e da `GET /prompts`); in `api.py`
  `create_app(*, graph, client, model_id, model_status)`, `GET /prompts`, `GET /status`, gli errori
  `model_unavailable` (`503`), `model_error` (`502`) e `internal_error` (`500`, aiuto `_answer`
  comune ai tre endpoint), modelli `PromptInfo`, `PromptArgumentInfo`, `StatusBody`, `McpStatus`,
  `ModelStatus` nell'OpenAPI; `AGENT_HOST`/`AGENT_PORT` in `config.py` e `.env.example`;
  `assistant/service.py` (`python -m assistant.service`). README (variabili e breve sezione «Servizio
  HTTP dell'agente»), `CLAUDE.md` (struttura), specifica §7 con le aggiunte del punto.
- Decisioni prese durante l'esecuzione (sostituiscono la terza decisione del piano): le righe di
  risposta di `/status` e `/prompts` hanno anche `duration_ms=` (un controllo del modello può durare
  secondi); `/prompts` riuscito → `api response=prompts status=200 count=N`; un `500` usa la stessa
  riga degli altri errori a ERROR con traceback; la riga d'avvio aggiunge `model=` e `base_url=` e
  usa il logger `assistant.service` (con `python -m` `__name__` sarebbe `__main__`).
- Test nuovi: `test_api.py` (+18: quattro errori di LM Studio con codice, `detail` e riga WARNING,
  errore di LM Studio in un turno da prompt, `500` senza dettagli nella risposta e con traceback nel
  log; `/prompts` con elenco, vuoto, `503` e `500`; `/status` nelle quattro combinazioni con righe e
  livelli, nuovo controllo a ogni richiesta, nessuna chiamata a modello e prompt, `500`; OpenAPI con i
  tre percorsi e gli schemi), `test_model.py` (+12, `check_model` con `httpx.MockTransport` e su
  una porta chiusa), `test_config.py` (+9), `test_commands.py` (+2), `test_service.py` (nuovo, 11:
  indirizzo predefinito e da ambiente, configurazione non valida, MCP non avviato, discovery fallita,
  nomi doppi, percorsi assoluti al server MCP, librerie silenziose, LM Studio non contattato
  all'avvio, app passata a uvicorn che risponde a `/status`, `/prompts` e `/chat` con le preferenze
  lette una sola volta). Test esistenti invariati tranne l'aiuto `api()` e i codici attesi
  dall'OpenAPI di `/chat` (ora con `500`).
- `pytest` → 645 passed, 19 deselected.
- Prova d'avvio da Git Bash con il server MCP reale e LM Studio volutamente irraggiungibile
  (`LMSTUDIO_BASE_URL=http://127.0.0.1:1/v1`, `AGENT_PORT=8765`, note in `%TEMP%`): righe `tools=…`,
  `resources/read … status=ok`, `api listening=…`, avvio di uvicorn; `GET /status` → `503`
  `degraded`, MCP `ok` «7 strumenti», modello `unavailable` «LM Studio non raggiungibile su
  http://127.0.0.1:1/v1»; `GET /prompts` → `200` con i due prompt; `POST /chat` → `503
  model_unavailable` «LM Studio non raggiungibile: Connection error.»; `/openapi.json` con `/chat`,
  `/prompts`, `/status`. Servizio fermato con `taskkill`.
- Problemi aperti: `__main__.py` ripete ancora l'avvio di `service.py` fino al punto 5 (CLI client);
  `/status` con LM Studio attivo e la sezione completa del README (due processi, Docker) ai punti 5 e
  6; su Windows una porta chiusa fa durare `/status` circa 2,5 s (tentativi di connessione di httpx).

### Punto 5 · CLI come client dell'API HTTP — piano

1. `assistant/config.py`: `ClientConfig(agent_url, log_level)` e `load_client_config(env)`
   (`AGENT_URL` predefinito `http://127.0.0.1:8000`, `http://`/`https://`, senza `/` finale;
   `LOG_LEVEL` come oggi); `configure_logging` spostata qui da `service.py` (la usano servizio e CLI).
2. `assistant/api_client.py` (specifica §9): `AgentError(code, detail)`, `AgentClient(base_url,
   http=None)` con `status()`, `prompts()`, `chat(history, summary, *, message=None, prompt=None)`,
   `close()`/context manager; `RemoteSession(agent)` con `send`, `send_prompt`, `history`, `summary`.
3. `assistant/commands.py`: `CommandResult(output, prompt)` (al posto di `messages`); `PromptCommands(agent)`
   con `/prompts` → `agent.prompts()` + `format_prompts`, `/prompt` → `parse_prompt_command` e
   `CommandResult(prompt=(name, arguments))`. `resolve_prompt` e il resto restano per il servizio.
4. `assistant/terminal.py`: `result.prompt` → `session.send_prompt`; `AgentError` al posto di
   `openai.APIError` (`prompt_rejected` → «Errore nel comando: … Scrivi /prompts …»).
5. `assistant/__main__.py`: CLI client (configurazione, logging, `GET /status`, avvisi, benvenuto,
   `run(RemoteSession, PromptCommands)`); il codice d'avvio del grafo esce da qui (resta in `service.py`).
6. Docker: `EXPOSE 8000`; `compose.yaml` con `agent` (servizio, healthcheck) e `assistant` (CLI,
   `AGENT_URL=http://agent:8000`, `depends_on: service_healthy`); `.env.example` con `AGENT_URL`.
7. Test: `test_api_client.py` (nuovo: `TestClient` dell'app con grafo finto e `httpx.MockTransport`),
   `test_commands.py`, `test_terminal.py`, `test_main.py` riscritto per la CLI client (CA-66),
   `test_config.py`; i test di cablaggio del grafo di `test_main.py` (router, revisore, riassunto,
   preferenze, prompt nel grafo) passano a `test_service.py`; `test_real.py` usa `resolve_prompt` per
   i prompt (stesso percorso del servizio). Poi `pytest` completo, prova a mano servizio + CLI con LM
   Studio e `docker compose config`/avvio dei due servizi.
8. README (avvio in due terminali, Docker, diagnosi, variabili) e `CLAUDE.md` (struttura e comandi).

Decisioni:
- `configure_logging` in `config.py`: la CLI non deve importare `service.py` (FastAPI, uvicorn, grafo)
  solo per il logging; un modulo in più per una funzione non serve.
- Errori del client: trasporto (connessione rifiutata, nome sconosciuto) → `agent_unreachable`
  «agente non raggiungibile su <url>»; tempo scaduto → `agent_timeout` «l'agente non ha risposto
  entro N s»; risposta d'errore con `{"error", "detail"}` → quei valori; altra risposta inattesa →
  `bad_response` «risposta inattesa dell'agente (HTTP N)».
- `GET /status` con `503` e corpo di stato non è un errore per il client: `status()` restituisce il
  corpo e la CLI mostra gli avvisi.
- Nel terminale ogni `AgentError` diverso da `prompt_rejected` dà «Errore: <detail>. Riprova.» (un
  solo formato; la specifica §9 ometteva «Riprova.» per gli errori del prompt, che però si possono
  davvero riprovare). Il punto finale del `detail` non si raddoppia.
- All'avvio un `AgentError` qualsiasi su `/status` (anche `500`) → messaggio su stderr ed exit 1; per
  l'agente non raggiungibile si aggiunge come avviarlo.

### Punto 5 · CLI come client dell'API HTTP — fatto

- Implementati `assistant/api_client.py` (`AgentClient`, `AgentError` con `phrase`, `RemoteSession`);
  in `config.py` `ClientConfig`, `load_client_config`, `DEFAULT_AGENT_URL`, `configure_logging` e
  `QUIET_LIBRARIES` (tolti da `service.py`); `commands.py` con `CommandResult(output, prompt)` e
  `PromptCommands(agent)` (solo sintassi nella CLI); `terminal.py` con `send_prompt` e `AgentError`;
  `__main__.py` riscritto come client (nessun grafo, MCP o modello nella CLI). Docker: `EXPOSE 8000`,
  `compose.yaml` con `agent` (healthcheck su `/status`, porta `127.0.0.1:8000`, volume delle note) e
  `assistant` (CLI, `depends_on: service_healthy`); `.env.example` con `AGENT_URL`. README (avvio in
  due terminali, API, Docker, diagnosi), `CLAUDE.md` (struttura e comandi), specifica §10 con le
  aggiunte del punto.
- Decisioni prese durante l'esecuzione: `healthcheck` con `start_interval: 2s` e `interval: 30s` (con
  5 s fissi il log dell'agente si riempiva di righe `/status`); `fake_service` in `conftest.py` (app
  vera su grafo finto, usata da `test_api.py`, `test_api_client.py`, `test_commands.py`,
  `test_terminal.py`, `test_main.py`); avviso di Starlette sul `timeout` col `TestClient` filtrato in
  `pytest.ini`; in `test_real.py` i prompt passano da `parse_prompt_command` + `resolve_prompt`, lo
  stesso percorso di CLI e servizio.
- Test: `test_api_client.py` (nuovo, 34: stato `200`/`503`/`500`/inattesi, agente non raggiungibile
  anche su porta chiusa, tempo scaduto, timeout per endpoint, prompt e forme sbagliate, chat con
  messaggio, prompt, rifiuto, LM Studio spento, corpo inviato, `RemoteSession` che conserva cronologia
  e riassunto solo dopo un `200`); `test_main.py` riscritto (12, CA-66: configurazione, URL, benvenuto,
  cronologia nella CLI, `/prompts` e `/prompt` attraverso il servizio, agente non raggiungibile ed
  errore `500` all'avvio → exit 1, avvisi con stato `degraded`); i test di cablaggio del grafo
  spostati da `test_main.py` a `test_service.py` (+12: strumenti, router, revisore, riassunto,
  preferenze anche non disponibili, riga di configurazione, turno e prompt attraverso i quattro nodi);
  `test_commands.py` (i rifiuti dell'host ora su `resolve_prompt`, +1 agente non raggiungibile),
  `test_terminal.py` (+5), `test_config.py` (+10).
- `pytest` → 689 passed, 19 deselected; `pip check` senza problemi; prove reali `test_explain_prompt`
  e `test_summary_prompt` (aiuto cambiato) → 2 passed in 6 min con LM Studio.
- Prove a mano con LM Studio (`google/gemma-4-e2b`): servizio + CLI da Git Bash su porta 8765
  («Quanto fa 17 * 23?» → «17 * 23 fa 391.» con `calculate` nel log del servizio, `/prompts`,
  `/prompt spiega livello=base` rifiutato dal servizio con `400 prompt_rejected`, cronologia
  mantenuta; CLI senza servizio → exit 1); da PowerShell i comandi del README (`Invoke-RestMethod`
  di `/status` e `/chat` con `tools_used` di `calculate`, `curl.exe`, CLI con domande in ingresso,
  CLI senza servizio → exit 1); Docker: `docker compose build`, `docker compose run --rm -T
  assistant` («391» con `calculate` nei log di `agent`), `docker compose ps` con `agent (healthy)`,
  `/status` `200` e `/openapi.json` dall'host, `docker compose run --rm -T -e LMSTUDIO_MODEL= agent`
  → «Manca LMSTUDIO_MODEL.» ed exit 1, LM Studio raggiungibile dal container; poi `docker compose
  down`.
- Problemi aperti: prove reali formali CA-67…CA-69 al punto 6; `/status` in locale dura circa 3 s
  anche con LM Studio attivo (`localhost` su Windows prova prima `::1`; in Docker 10–40 ms); le
  prove del README precedenti allo Step 6 mostrano ancora `__main__` nei log (annotato nel testo).

### Punto 6 · Prova reale Step 6 — piano

LM Studio raggiungibile (`GET /v1/models` → `google/gemma-4-e2b`).
1. `tests/test_real.py`: aiuto `start_service(config, tmp_path, **env)` (context manager) che avvia
   `python -m assistant.service` come sottoprocesso su una porta libera, note in `tmp_path`, log
   (stderr) in un file, attende `GET /status` e alla fine termina il processo.
2. Prove nuove (specifica §12): CA-67 (`POST /chat` «Quanto fa 17 * 23?» → `200`, `calculate` in
   `tools_used`, «391», righe `api response=chat status=200 tools=calculate` e `tool=calculate` nel
   log), CA-68 (stessa domanda dalla CLI `python -m assistant` con `AGENT_URL` del servizio e
   dall'API: `calculate` e «391» in entrambe; testi confrontati e annotati), CA-69 (`/openapi.json`
   con i tre percorsi, `/status` `200`; servizio con `LMSTUDIO_BASE_URL=http://127.0.0.1:1/v1` →
   `/status` `503` `model.status=unavailable`, `/chat` `503 model_unavailable`).
3. Esecuzione: le tre prove nuove, poi `pytest`; esiti in requisiti §14, qui e nel README se cambia.

Decisioni:
- Servizio come sottoprocesso vero (non `TestClient` in processo): la prova riguarda l'avvio reale
  con `python -m assistant.service`, la porta e il log del processo, come chiede la specifica §12.
- Porta libera scelta dal sistema (`socket.bind(("127.0.0.1", 0))`): le prove non urtano un servizio
  già attivo su 8000.

### Punto 6 · Prova reale Step 6 — fatto

Prove reali con LM Studio, `google/gemma-4-e2b`, `MAX_STEPS=5`, altre variabili non impostate (da
Git Bash, `LMSTUDIO_BASE_URL=http://localhost:1234/v1`). Aiuti nuovi in `tests/test_real.py`:
`start_service` (servizio come sottoprocesso, log in un file di `tmp_path`), `post_chat`,
`cli_replies`.

| CA | Prova | Esito |
|----|-------|-------|
| CA-69 | `test_openapi_and_status`, `test_service_without_lm_studio` | ✅ 2 passed in 23 s: `/openapi.json` con `/chat`, `/prompts`, `/status`, `/docs` `200`, `/status` `200` `ok`; con `LMSTUDIO_BASE_URL=http://127.0.0.1:1/v1` `/status` `503` (MCP `ok`, modello `unavailable`), `/chat` `503 model_unavailable` con la riga `api response=chat status=503 error=model_unavailable` |
| CA-67, CA-68 | `test_http_chat_with_a_tool`, `test_same_answer_from_cli_and_api` | ✅ 2 passed in 238 s: `200`, `tools_used` = `calculate` con `ok: true`, «391», righe `api request=chat kind=message history=0`, `api response=chat status=200 tools=calculate …` e `tool=calculate call_id=…`; CLI (`python -m assistant`, `AGENT_URL` del servizio, domanda ed `esci` in ingresso) e API: due righe `status=200 tools=calculate` e risposta «17 * 23 fa 391.» uguale alla lettera |
| — | `pytest` | ✅ 689 passed, 23 deselected; `pytest -m real --collect-only` raccoglie 23 prove |

- Documenti: README («Prove reali con LM Studio»: le prove del servizio, esiti e comando per eseguire
  solo quelle, verificato con `--collect-only`), requisiti §14 con gli esiti di CA-61…CA-69.
- Problemi aperti: la suite reale completa (23 prove, circa 40 minuti) non è stata rieseguita in
  questo punto: nessun codice dell'applicazione è cambiato dal punto 5, e le prove di prompt erano
  passate al punto 5. Una sola esecuzione per prova: dimostra il comportamento con quella domanda,
  non che il modello risponda sempre uguale da CLI e API.

## Step 7 · Back-end: API e salvataggio delle chat (2026-11-14)

Specifica: [`docs/superpowers/specs/2026-11-14-backend-chat-design.md`](docs/superpowers/specs/2026-11-14-backend-chat-design.md);
requisiti §15 (RF-60…RF-67, CA-70…CA-78). Questo piano sostituisce l'approvazione (modalità
autonoma); i punti successivi dello step seguono la specifica.

### Piano dello step (un punto di `TODO.md` per riga)

1. Specifica, requisiti §15, dipendenze (`SQLAlchemy`, `psycopg[binary]` in `requirements.txt`,
   righe nuove in `constraints.txt`). Verifica: `pip check`, prova usa e getta fuori dal progetto,
   `pytest` invariato.
2. `backend/__init__.py`, `backend/db.py` (schema `chats`/`chat_messages`, `create_db_engine`,
   `init_db`), `backend/store.py` (`ChatStore`, `ChatRecord`, `MessageRecord`, `AgentState`,
   `ChatNotFoundError`). Test: `test_backend_store.py` su SQLite in memoria con orologio fisso;
   `CLAUDE.md` (struttura).
3. `backend/api.py` (`create_app(*, store, agent)`: `POST/GET /chats`, `GET/DELETE /chats/{id}`,
   errori `400`/`404`/`422`/`503 database_unavailable`/`500`, OpenAPI), `backend/config.py`,
   `backend/__main__.py`, `.env.example`. Test: `test_backend_api.py`, `test_backend_config.py`,
   `test_backend_service.py`.
4. `POST /chats/{id}/messages` con `AgentClient.chat`, errori `503 agent_unavailable`,
   `504 agent_timeout`, `502 agent_error`, righe di log dell'invio. Test con l'agente dello Step 6 su
   grafo finto (`fake_service`) e con agenti finti.
5. Prove reali CA-77 (archivio su PostgreSQL con `TEST_DATABASE_URL`) e CA-78 (back-end, agente,
   PostgreSQL in Docker, LM Studio; riavvio del back-end; agente fermato); README e `CLAUDE.md`;
   esiti in requisiti §15 e qui. PostgreSQL o LM Studio non raggiungibili → `[!]`.

### Decisioni (scelte del progettista, dettagli nella specifica §1)

- Pacchetto `backend/` separato da `assistant/`: è un altro servizio (un container allo Step 9).
- SQLAlchemy 2.1.8 + psycopg 3.3.9 (binario): standard Python; lo stesso codice gira su PostgreSQL e
  su SQLite in memoria, così i test non richiedono PostgreSQL.
- `create_all` all'avvio, niente Alembic: schema nuovo, nessuna migrazione da gestire.
- Il back-end riusa `AgentClient` di `assistant/api_client.py`: un solo client dell'agente con gli
  stessi errori; l'immagine del back-end (Step 9) conterrà quindi il pacchetto `assistant`.
- Messaggi visibili (tabella `chat_messages`) separati dallo stato dell'agente (cronologia JSON e
  riassunto nella riga della chat): la cronologia dell'agente ha bozze e chiamate e perde i turni
  riassunti, l'utente deve rileggere tutto.
- Identificativi interi: leggibili, e senza autenticazione un UUID non proteggerebbe nulla.
- Titolo facoltativo, altrimenti dalla prima domanda (60 caratteri): l'elenco ha un titolo utile.
- Domanda salvata prima di chiamare l'agente, come dice la traccia: con l'agente spento resta nella
  chat senza risposta e lo stato dell'agente non cambia.
- Errori `{"error", "detail"}`: `404 chat_not_found`, `400 invalid_request`, `503 agent_unavailable`,
  `504 agent_timeout`, `502 agent_error`, `503 database_unavailable`, `500 internal_error`.
- `DATABASE_URL` obbligatoria e solo PostgreSQL; porta predefinita `8001` (l'agente usa `8000`).
- PostgreSQL per le prove di questo step in un container avviato a mano (`postgres:18`); Compose a
  quattro servizi resta allo Step 9.

### Punto 1 · Specifica e requisiti — fatto

- Scritti la specifica e i requisiti §15 (intestazione di `requisiti.md` aggiornata).
- Dipendenze: `SQLAlchemy==2.1.8` e `psycopg[binary]==3.3.9` in `requirements.txt`; in
  `constraints.txt` le righe nuove `psycopg==3.3.9`, `psycopg-binary==3.3.9`, `SQLAlchemy==2.1.8`
  (confrontato con `pip freeze` dopo l'installazione: nessun'altra differenza). `pip check` senza
  problemi; `pip install --dry-run -r requirements-dev.txt` risolve.
- Prova usa e getta in `%TEMP%\step7probe` (fuori dal progetto): tabelle su SQLite in memoria con
  `StaticPool`, colonna JSON, `ON DELETE CASCADE` con `PRAGMA foreign_keys=ON`, `max(created_at)` con
  `outer join` (su SQLite l'orario torna senza fuso: l'archivio lo considererà UTC), DDL PostgreSQL
  generato, porta chiusa → `OperationalError`. Docker disponibile (server 29.9.1) per le prove reali.
- Test: `pytest` → 689 passed, 23 deselected (nessun codice cambiato).
- Problemi aperti: rischi nella specifica §13 (invii contemporanei, SQLite nei test, domande senza
  risposta); README e `CLAUDE.md` cambiano dal punto 2 in poi, quando c'è codice da descrivere.

### Punto 2 · Modello dati e archivio — piano

1. `backend/__init__.py`; `backend/db.py` (specifica §3): `Base`, `Chat`, `ChatMessage` (ORM
   dichiarativo, `ON DELETE CASCADE`, `cascade="all, delete-orphan"` con `passive_deletes=True`),
   `create_db_engine(url)` (SQLite: `StaticPool` per il database in memoria e
   `PRAGMA foreign_keys=ON`; PostgreSQL: `pool_pre_ping=True`), `init_db(engine)` con `create_all`.
2. `backend/store.py` (specifica §4): `ChatNotFoundError`, `InvalidInputError`, `MessageRecord`,
   `ChatRecord`, `AgentState`, `ChatStore` (una sessione e una transazione per metodo, orari in UTC
   anche se SQLite li restituisce senza fuso), `title_from_question`.
3. Test `tests/test_backend_store.py` su SQLite in memoria con orologio fisso e avanzabile:
   schema (tabelle, colonne, chiave esterna con `CASCADE`), creazione con e senza titolo, elenco con
   titolo, data dell'ultimo messaggio e ordine, lettura in ordine, eliminazione con i messaggi
   contati nella tabella, titolo dalla prima domanda (taglio, prima riga) e non dalle successive,
   `add_question`/`add_answer` con lo stato dell'agente, chat inesistente, chat eliminata durante il
   turno, errori di SQLAlchemy che arrivano al chiamante. Poi `pytest` completo.
4. `CLAUDE.md` (struttura: pacchetto `backend/`).

Decisioni:
- L'archivio normalizza titolo e testo (spazi tolti, titolo vuoto = assente) e solleva
  `InvalidInputError` per titolo oltre 200 caratteri o messaggio vuoto: un solo punto di controllo,
  che l'API del punto 3 trasforma in `400 invalid_request`. Un'eccezione propria e non `ValueError`,
  così un `ValueError` imprevisto non diventa un `400`.
- Titolo dalla prima domanda: prima riga senza spazi ai lati; se supera 60 caratteri, i primi 59
  (spazi finali tolti) più «…», così il titolo resta entro 60 caratteri.
- `create_db_engine` accetta anche SQLite (solo i test lo usano): i test passano dallo stesso
  `create_db_engine` e `init_db` dell'esercizio; il rifiuto degli schemi diversi da PostgreSQL sta
  nella configurazione (punto 3).
- `pool_pre_ping=True` su PostgreSQL: dopo un riavvio del database la prima richiesta non fallisce
  per una connessione morta nel pool (opzione standard di SQLAlchemy).

### Punto 2 · Modello dati e archivio — fatto

- Implementati `backend/__init__.py`, `backend/db.py` (`Chat`, `ChatMessage`, `create_db_engine`,
  `init_db`) e `backend/store.py` (`ChatStore`, `ChatRecord`, `MessageRecord`, `AgentState`,
  `ChatNotFoundError`, `InvalidInputError`, `title_from_question`, `MAX_TITLE_LENGTH`,
  `TITLE_LENGTH`); `CLAUDE.md` (struttura e test del back-end).
- Decisioni prese durante l'esecuzione:
  - `last_message_at` di `get_chat` calcolato dai messaggi già letti (niente seconda query);
    `list_chats` usa `max(created_at)` con `outer join` e `group_by(chats.id)` (ammesso da
    PostgreSQL perché `id` è la chiave primaria).
  - L'eliminazione lascia la cancellazione dei messaggi al database (`passive_deletes=True`): un
    test cancella la chat con SQL diretto e controlla che i messaggi spariscano.
- Test nuovi: `test_backend_store.py` (44: schema e chiave esterna con `CASCADE`, `create_all` che
  non tocca i dati, `PRAGMA foreign_keys`; creazione con e senza titolo, spazi, titolo di 200 e 201
  caratteri; elenco vuoto, titolo e data dell'ultimo messaggio, ordine per attività e a parità per
  id; orari in UTC da un altro fuso; lettura in ordine anche con orari uguali, chat vuota, chat
  separate, chat inesistente; eliminazione con i messaggi contati nella tabella, cascata del
  database, nuova chat che non eredita messaggi né stato; titolo dalla prima domanda, prima riga,
  taglio con «…», non dalle successive né sopra un titolo dato; stato dell'agente vuoto, sostituito
  con la risposta, invariato con la sola domanda, separato per chat, copiato; messaggio vuoto e chat
  inesistente senza righe salvate; chat eliminata durante il turno; errori di SQLAlchemy al
  chiamante).
- Verifiche: tre mutazioni temporanee (senza `PRAGMA`, orario non convertito in UTC, titolo
  sovrascritto a ogni domanda) fanno fallire 5, 1 e 3 test; DDL PostgreSQL compilato senza database
  (`SERIAL`, `TIMESTAMP WITH TIME ZONE`, `JSON DEFAULT '[]'`, `ON DELETE CASCADE`, indice su
  `chat_id`), conforme alla specifica §3.
- `pytest` → 733 passed, 23 deselected (`-W error` sul file nuovo: nessun avviso).
- Problemi aperti: l'archivio su PostgreSQL vero (CA-77) resta da provare al punto 5; API, avvio e
  README arrivano ai punti 3–5. README non cambiato: nessun comportamento visibile all'utente.

### Punto 3 · Endpoint delle chat, configurazione e avvio — piano

1. `backend/config.py` (specifica §8): `BackendConfig(database_url, agent_url, host, port,
   log_level)`, `load_backend_config(env)` con `ConfigError` di `assistant.config`; `AGENT_URL` e
   `LOG_LEVEL` letti da `load_client_config` (stesse regole della CLI, messaggio aggiunto agli altri
   problemi); `postgresql://` → `postgresql+psycopg://`; `display_url(url)` con la password nascosta.
2. `backend/api.py` (specifica §5–§7): `create_app(*, store, agent)` con `POST /chats` (corpo
   facoltativo), `GET /chats`, `GET /chats/{chat_id}`, `DELETE /chats/{chat_id}`; modelli pydantic con
   descrizioni italiane; errori `400 invalid_request`, `404 chat_not_found`, `503
   database_unavailable`, `500 internal_error` mappati in un solo punto; righe di log `backend
   response=…`. L'invio (`POST /chats/{id}/messages`) arriva al punto 4.
3. `backend/__main__.py`: `main(env)` → configurazione (errore → stderr, exit 1), logging,
   `create_db_engine`, `init_db` (`OperationalError` → «Database non raggiungibile: …», exit 1),
   `AgentClient(AGENT_URL)`, riga d'avvio senza password, `uvicorn.run(...)`.
4. `.env.example` (righe di commento `DATABASE_URL`, `BACKEND_HOST`, `BACKEND_PORT`), `CLAUDE.md`
   (struttura del pacchetto `backend/`).
5. Test: `test_backend_config.py` (CA-70), `test_backend_api.py` (CA-72, righe CRUD di CA-74 e
   CA-76: le quattro operazioni con `TestClient` su SQLite in memoria e orologio fisso, OpenAPI,
   404/400/422/503/500, righe di log e livelli), `test_backend_service.py` (CA-75: `uvicorn.run`
   sostituito, indirizzo, configurazione non valida, database su porta chiusa → exit 1, password
   assente). Poi `pytest` completo.

Decisioni:
- `create_app(*, store, agent)` ha già la firma della specifica: `agent` resta inutilizzato fino al
  punto 4, così avvio e test non cambiano firma al punto successivo.
- `ApiError` e la mappatura degli errori scritte di nuovo in `backend/api.py` invece di importarle da
  `assistant/api.py`: la specifica §2 limita gli import da `assistant` a client dell'agente e
  configurazione, e `assistant.api` porta con sé grafo, LangChain e openai.
- Errore su `DATABASE_URL` che riporta solo lo schema ricevuto, mai l'indirizzo: potrebbe contenere
  la password.
- Il messaggio del driver di un `OperationalError` va nel log come `cause="…"` sulla riga della
  risposta `503`, non nel corpo (specifica §6).
- Nessuna riga di log del back-end per il `422` di FastAPI (validazione prima dell'endpoint), come
  nell'agente dello Step 6.
- README rimandato al punto 5 come da piano dello step: i comandi d'avvio si documentano dopo averli
  provati con PostgreSQL vero.

### Punto 3 · Endpoint delle chat, configurazione e avvio — fatto

- Implementati `backend/config.py` (`BackendConfig`, `load_backend_config`, `display_url`),
  `backend/api.py` (`create_app(*, store, agent)` con `POST /chats`, `GET /chats`,
  `GET /chats/{chat_id}`, `DELETE /chats/{chat_id}`, modelli `CreateChatRequest`, `ChatInfo`,
  `ChatDetail`, `ChatMessageInfo`, `ErrorBody`, errori e righe di log), `backend/__main__.py`
  (`python -m backend`); `.env.example` e `CLAUDE.md` (struttura) aggiornati; `Clock` spostato da
  `test_backend_store.py` a `conftest.py` per usarlo anche nei test dell'API.
- Decisioni prese durante l'esecuzione:
  - **`connect_timeout=10` s nel motore PostgreSQL** (`create_db_engine(url, connect_timeout=…)`):
    su questo computer una porta chiusa non viene rifiutata e psycopg aspettava 130 s («connection
    timeout expired»), sia all'avvio sia prima di un `503`. Annotato nella specifica §8.
  - Le righe di log di lettura ed eliminazione mettono `chat=` prima di `status=` (come l'invio
    nella specifica §7); la creazione dopo, perché l'id nasce con la risposta. Lettura con
    `messages=<n>`.
  - Corpo di `POST /chats` facoltativo (anche assente): un front-end può creare una chat senza titolo
    con una richiesta vuota.
  - `history` e `summary` dell'agente non compaiono nelle risposte (specifica §1, stato interno).
- Test nuovi: `test_backend_config.py` (16: predefiniti, valori dall'ambiente, `postgresql://` →
  `postgresql+psycopg://`, `DATABASE_URL` mancante, altri schemi e testo senza schema rifiutati senza
  mostrare la password, URL non interpretabile, porta non valida, problemi in un solo messaggio,
  password nascosta), `test_backend_api.py` (34: creazione con e senza corpo e titolo, titolo di 200 e
  201 caratteri, `422` per corpo fuori schema; elenco vuoto e con titolo, ultimo messaggio e ordine;
  lettura con messaggi e strumenti in ordine, chat vuota, stato dell'agente non esposto; `404` e `422`
  su lettura ed eliminazione; eliminazione con i messaggi contati; OpenAPI con percorsi, schemi e
  codici d'errore, `/docs`; `503 database_unavailable` con `cause=` nel log e `500 internal_error` con
  traceback per ognuna delle quattro operazioni; righe di log esatte e livelli; titoli e messaggi
  assenti dal log), `test_backend_service.py` (12: indirizzo predefinito e dall'ambiente, riga d'avvio
  con la password nascosta, password mai nel log anche a DEBUG, tabelle create prima di servire,
  configurazione non valida → exit 1, psycopg vero su porta chiusa → exit 1 senza password, timeout
  del motore, agente spento che non blocca l'avvio, app servita che usa il database).
- `pytest` → 795 passed, 23 deselected; i tre file nuovi anche con `-W error::DeprecationWarning`.
- Prova d'avvio da Git Bash: senza `DATABASE_URL` → «Configurazione non valida: Manca
  DATABASE_URL.», exit 1; `DATABASE_URL=postgresql://lab:segreta@127.0.0.1:1/assistente` →
  «Database non raggiungibile: connection timeout expired» in 12 s, exit 1, password assente.
- Problemi aperti: avvio con PostgreSQL vero e README al punto 5; invio dei messaggi al punto 4
  (`agent` di `create_app` ancora inutilizzato). Il `422` di FastAPI non scrive una riga di log del
  back-end (come nell'agente).

### Punto 4 · Invio di un messaggio — piano

1. `backend/api.py` (specifica §5–§7): `SendMessageRequest(content)` (`extra="forbid"`),
   `SendMessageResponse(question, answer)`; `POST /chats/{chat_id}/messages` → `add_question`,
   riga `backend agent_call`, `agent.chat(history, summary, message=…)`, `add_answer` → `201`;
   `AgentError` in `_api_error`: `agent_unreachable` → `503 agent_unavailable`, `agent_timeout` →
   `504 agent_timeout`, ogni altro codice → `502 agent_error` («l'agente ha risposto con un errore
   (<codice>): <detail>»); risposte `502`/`503`/`504` documentate nell'OpenAPI.
2. `assistant/api_client.py`: `AgentClient.chat` controlla anche i tipi del corpo `200` (`reply` e
   `summary` testo, `tools_used` e `history` elenchi), altrimenti `bad_response`.
3. Test in `tests/test_backend_api.py`: invio con l'`AgentClient` collegato all'agente dello Step 6
   su grafo finto (`fake_service`): domanda e risposta salvate e restituite, strumento usato
   salvato, titolo dalla prima domanda, al secondo invio l'agente riceve la cronologia salvata
   (CA-73); agente finto per cronologia e riassunto passati e salvati; agente su porta chiusa →
   `503`, tempo scaduto → `504`, errore del servizio (LM Studio spento nel grafo finto) → `502`,
   risposta inattesa → `502`; dopo ogni errore domanda salvata e stato invariato (CA-74); `404`,
   `400`, `422`, `503 database_unavailable`, `500`, chat eliminata durante il turno; OpenAPI; righe
   di log esatte (CA-76). `tests/test_api_client.py`: tipi sbagliati → `bad_response`. Poi `pytest`.

Decisioni:
- `chars=` della riga di richiesta conta il testo ricevuto e la riga si scrive prima di ogni
  controllo: così anche un `400` o un `404` dell'invio ha la sua riga di richiesta.
- Controllo dei tipi nel client e non nel back-end: un solo client dell'agente (specifica §1), e la
  CLI ne beneficia; senza, un corpo malformato diventerebbe un errore di validazione della risposta
  fuori dalla mappatura degli errori (o finirebbe nel database).
- `tools=` con i nomi separati da virgola, vuoto senza strumenti: stesso formato della riga
  `api response=chat` dell'agente.

### Punto 4 · Invio di un messaggio — fatto

- Implementati in `backend/api.py` `SendMessageRequest`, `SendMessageResponse`,
  `POST /chats/{chat_id}/messages` (domanda salvata, riga `agent_call`, `agent.chat`, risposta e
  stato dell'agente salvati, `201`), la conversione di `AgentError` (`_agent_error`: `503
  agent_unavailable`, `504 agent_timeout`, `502 agent_error`) e le risposte `502`/`503`/`504`
  nell'OpenAPI; in `assistant/api_client.py` il controllo dei tipi del corpo di `POST /chat`
  (`CHAT_FIELDS`, `_is_chat`). `CLAUDE.md` (struttura) aggiornato.
- Decisioni prese durante l'esecuzione:
  - La risposta `503` dell'invio nell'OpenAPI descrive entrambi i casi (agente non raggiungibile,
    database non disponibile): un codice HTTP ha una sola voce per operazione.
  - Il messaggio mandato all'agente è il testo salvato (spazi tolti dall'archivio), non quello
    ricevuto: l'agente vede esattamente la domanda che compare nella chat.
  - Chat eliminata mentre l'agente risponde → `404 chat_not_found` dopo la chiamata (la risposta
    non si salva), come da specifica §4.
- Test nuovi: `test_backend_api.py` (+25: invio con l'agente dello Step 6 su grafo finto, con
  domanda, risposta, `get_current_time` negli strumenti, titolo dalla prima domanda e cronologia
  salvati; secondo invio con la cronologia salvata, ricevuta anche dal modello; riassunto salvato e
  rimandato; testo senza spazi salvato e mandato; titolo dato non sostituito; `422` per corpo fuori
  schema e id non intero, `400` messaggio vuoto e `404` senza chiamare l'agente; porta chiusa → `503`,
  tempo scaduto → `504`, LM Studio spento nel grafo finto → `502 (model_unavailable)`, risposta non
  JSON → `502 (bad_response)`, con la domanda salvata, lo stato invariato e la riga a WARNING;
  cronologia salvata rifiutata dall'agente → `502 (invalid_history)`; chat eliminata durante il
  turno → `404`; archivio con `OperationalError` → `503 database_unavailable`, eccezione imprevista →
  `500` a ERROR; righe di log esatte; testi assenti dal log; OpenAPI dell'invio),
  `test_api_client.py` (+5: tipi sbagliati nel corpo `200` → `bad_response`).
- `pytest` → 825 passed, 23 deselected; `test_backend_api.py` anche con
  `-W error::DeprecationWarning`.
- Problemi aperti: prova con PostgreSQL, agente e LM Studio veri (CA-77, CA-78), README (avvio del
  back-end, PostgreSQL in un container, diagnosi) ed esiti in requisiti §15 al punto 5, come da piano
  dello step. Invii contemporanei nella stessa chat non bloccati (rischio della specifica §13).

### Punto 5 · Prova reale Step 7 — piano

Servizi verificati: Docker 29.9.1 con l'immagine `postgres:18.6`, LM Studio con `google/gemma-4-e2b`.
1. PostgreSQL in un container avviato a mano (`docker run -d --name assistente-postgres -e
   POSTGRES_USER=lab -e POSTGRES_PASSWORD=… -e POSTGRES_DB=assistente -p 5432:5432
   postgres:18.6`), comando da riportare nel README.
   *Nota del 2026-11-16 (R-C1): questo comando pubblicava la porta su tutte le interfacce; il comando
   corretto, con `-p 127.0.0.1:5433:5432`, è nel README (sezione del back-end).*
2. CA-77, `tests/test_backend_store.py`: fixture `engine` parametrizzata (`sqlite` e `postgresql`
   con marcatore `real`); su PostgreSQL ogni test usa uno schema temporaneo (`search_path` alla
   connessione) eliminato alla fine; `TEST_DATABASE_URL` mancante → `pytest.fail` come per LM
   Studio. Test solo SQLite (`PRAGMA`) saltato su PostgreSQL; `DELETE` diretto con `text()` e
   parametro con nome (lo stile `?` è solo di SQLite).
3. CA-78, `tests/test_real.py`: agente (`start_service`) e back-end (`python -m backend`) come
   sottoprocessi su porte libere, database in uno schema temporaneo; chat creata, «Quanto fa
   17 * 23?» → `201`, `calculate`, «391»; back-end fermato e riavviato → chat e due messaggi
   presenti, secondo messaggio con la cronologia salvata (riga `agent_call` con `history>0`);
   agente fermato → `503 agent_unavailable`, domanda salvata.
4. `pytest` completo; README (PostgreSQL nel container, avvio del back-end, prove reali, diagnosi),
   `CLAUDE.md` (comandi), esiti in requisiti §15 e qui. Servizio non raggiungibile → `[!]`.

Decisioni:
- Schema temporaneo per test invece di un database apposito: chiede solo `TEST_DATABASE_URL` (anche
  quello di esercizio) e non tocca le tabelle di `public` (specifica §11).
- Il back-end della prova CA-78 usa lo schema temporaneo tramite `PGOPTIONS=-csearch_path=…`
  (variabile standard di libpq, letta da psycopg): nessun codice del back-end cambia per la prova.

### Punto 5 · Prova reale Step 7 — fatto

- Container `assistente-postgres` (`postgres:18.6`, utente `lab`, database `assistente`) pubblicato
  sulla **porta 5433**: sulla 5432 ascolta un PostgreSQL installato come servizio di Windows
  (`postgres.exe`, non toccato), che rifiutava la password («password authentication failed»).
  Scelta annotata nella specifica §9 e nel README (anche in «Diagnosi»). A fine punto il container è
  fermato con `docker stop` (dati conservati; `docker start assistente-postgres` per lo Step 8).
- Test: `conftest.py` ha `postgres_schema(prefix)` (schema nuovo in `TEST_DATABASE_URL`, eliminato
  con `DROP SCHEMA … CASCADE`; variabile mancante o database spento → `pytest.fail` col motivo) ed
  `engine_on_schema(url, schema)` (`search_path` a ogni connessione); in `test_backend_store.py` la
  fixture `engine` è parametrizzata `sqlite`/`postgresql` (`real`), il test del `PRAGMA` si salta su
  PostgreSQL e il `DELETE` diretto usa `text()` con parametro con nome. In `test_real.py`
  `start_process` generico (agente e back-end), `start_backend`, `send_message` e la prova
  `test_backend_keeps_chats_across_restarts`.

| CA | Prova | Esito |
|----|-------|-------|
| CA-77 | `TEST_DATABASE_URL=postgresql://lab:…@127.0.0.1:5433/assistente pytest tests/test_backend_store.py -m real` | ✅ 37 passed, 1 skipped (`PRAGMA`) in 2 s; dopo la prova `\dn` mostra solo `public` e `public` non ha tabelle |
| CA-78 | `pytest tests/test_real.py -m real -k backend` (LM Studio `google/gemma-4-e2b`, `MAX_STEPS=5`) | ✅ 1 passed in 295 s: chat creata, «Quanto fa 17 * 23?» → `201`, `calculate`, «17 * 23 fa 391.», `agent_call … history=0`; back-end riavviato sulla stessa porta → elenco con la chat e titolo dalla domanda, due messaggi con lo strumento; «Moltiplica per 2 il risultato di prima.» → `agent_call` con `history>0`, ricevuta dall'agente (`api request=chat … history=N`), risposta con «782»; agente fermato → `503 agent_unavailable`, quinta riga della chat = la domanda |
| — | Comandi del README eseguiti a mano (PowerShell con `-File`, agente e back-end avviati come nel README) | ✅ riga d'avvio con `lab:***`, `POST /chats`, invio con `calculate` e «391» (71 s), elenco, messaggi; back-end riavviato → chat e messaggi presenti; `404 chat_not_found`; `DATABASE_URL` sulla 5432 → «Database non raggiungibile: … password authentication failed for user "lab"», exit 1; `docker stop`/`docker start` → la chat resta (verificato con `psql`) |
| — | `pytest` | ✅ 825 passed, 62 deselected; `pytest -m real --collect-only` raccoglie 62 prove |

- Documenti: README (introduzione, requisiti dell'host, conteggio dei test, nuova sezione «Back-end:
  chat salvate su PostgreSQL» con variabili, container, avvio, endpoint ed errori; prove reali del
  back-end; due voci di «Diagnosi»), `CLAUDE.md` (comandi), requisiti §15 (esiti di CA-70…CA-78),
  specifica §9–§10.
- Problemi aperti: una sola esecuzione di CA-78 (dimostra il comportamento con quelle domande, non
  che il modello usi sempre `calculate` o la cronologia); la suite reale completa non è stata
  rieseguita (nessun codice dell'agente cambiato dallo Step 6). Invii contemporanei nella stessa
  chat non bloccati (specifica §13). Nei log rediretti su file le lettere accentate della risposta
  possono uscire in cp1252 (già noto).

## Step 8 · Front-end: interfaccia di chat (2026-11-14)

Specifica: [`docs/superpowers/specs/2026-11-14-frontend-chat-design.md`](docs/superpowers/specs/2026-11-14-frontend-chat-design.md);
requisiti §16 (RF-68…RF-75, CA-79…CA-87). Questo piano sostituisce l'approvazione (modalità
autonoma); i punti successivi dello step seguono la specifica.

### Piano dello step (un punto di `TODO.md` per riga)

1. Specifica, requisiti §16, dipendenza di test `playwright==1.65.2` (`requirements-dev.txt`;
   `playwright` e `greenlet` in `constraints.txt`). Verifica: `pip check`, `pip freeze` confrontato
   con `constraints.txt`, prova usa e getta fuori dal progetto (Edge/Chrome con Playwright,
   `node --test`), `pytest` invariato.
2. Pacchetto `frontend/` (`config.py`, `app.py` con `/config.js` e file statici, `__main__.py`),
   contratto `frontend/backend-openapi.json`, `CORS_ORIGINS` e `CORSMiddleware` nel back-end; pagina
   con elenco, creazione ed eliminazione (`index.html`, `style.css`, `api.js`, `texts.js`, `app.js`);
   marcatore `browser` in `pytest.ini`. Test: `test_frontend_config.py`, `test_frontend_app.py`,
   `test_frontend_service.py`, `test_frontend_contract.py`, CORS in `test_backend_api.py` e
   `test_backend_config.py`, `test_frontend_js.py` (`node --test`), `test_frontend_browser.py`
   (Edge senza finestra, back-end vero su SQLite e agente finto).
3. Vista dei messaggi, invio, stato di attesa, strumenti usati ed errori della specifica §5; test
   con Node (`errorMessage`, `toolsSummary`, `formatDate`, client) e nel browser (attesa, pagina
   usabile, agente e back-end spenti, HTML mostrato come testo).
4. Prova reale dal browser (CA-86, CA-87: PostgreSQL nel container sulla 5433, LM Studio, agente,
   back-end e front-end come sottoprocessi, Edge con Playwright); README e `CLAUDE.md`; esiti in
   requisiti §16 e qui. Servizio non raggiungibile → `[!]`.

### Decisioni (scelte del progettista, dettagli nella specifica §1)

- HTML, CSS e JavaScript standard (moduli ES) senza framework né build: cinque operazioni e una vista
  di messaggi non giustificano React/Vue né `npm`; `CLAUDE.md` vieta framework non concordati.
- Pacchetto `frontend/` con un piccolo servizio FastAPI + uvicorn (già fissati): componente a sé per
  lo Step 9, nessuna dipendenza nuova in esercizio.
- `BACKEND_URL` consegnato al browser da `GET /config.js`: modo standard di configurare una pagina
  statica senza ricostruirla.
- Il browser chiama direttamente il back-end con CORS (`CORS_ORIGINS`, elenco esplicito, niente `*`):
  niente proxy da scrivere; la traccia ammette entrambe le strade.
- Contratto: OpenAPI del back-end salvato in `frontend/backend-openapi.json`, controllato dai test.
- Testi come testo (`textContent`), niente Markdown: nessuna libreria e nessuna iniezione di HTML.
- Test del JavaScript con `node --test` lanciato da `pytest` (Node 24.15.0, nessun pacchetto npm);
  pagina nel browser con Playwright e Edge già installato, marcatore `browser` a parte.

### Punto 1 · Specifica e requisiti — fatto

- Scritti la specifica e i requisiti §16 (intestazione di `requisiti.md` aggiornata).
- Dipendenza: `playwright==1.65.2` in `requirements-dev.txt` (solo test, non nell'immagine); in
  `constraints.txt` le righe nuove `greenlet==3.5.6` e `playwright==1.65.2` (confronto tra
  `pip freeze` e `constraints.txt`: sono le sole differenze). `pip check` senza problemi;
  `pip install --dry-run -r requirements-dev.txt` risolve.
- Prova usa e getta in `%TEMP%\step8probe` (fuori dal progetto): `node --test` importa un modulo ES
  `.js` senza `package.json` (Node 24.15.0); Playwright pilota Edge 157.0.4341.46 e Chrome
  157.0.8103.78 senza finestra (`channel`), senza scaricare browser; porta 8080 libera.
- Test: `pytest` → 825 passed, 62 deselected (nessun codice cambiato).
- Problemi aperti: README e `CLAUDE.md` cambiano dal punto 2, quando c'è codice da descrivere;
  immagine del front-end e porta pubblicata del back-end restano allo Step 9 (specifica §11).

### Punto 2 · Front-end: elenco, creazione ed eliminazione — piano

1. Back-end: `CORS_ORIGINS` in `backend/config.py` (`BackendConfig.cors_origins`, specifica §4),
   `create_app(..., cors_origins=())` con `CORSMiddleware` (§6), riga d'avvio con `cors_origins=`;
   `.env.example`.
2. `frontend/`: `config.py` (`FrontendConfig`, `load_frontend_config`), `app.py` (`create_app`:
   `/config.js` e `StaticFiles`), `__main__.py` (avvio con uvicorn), `backend-openapi.json`.
3. Pagina: `static/index.html`, `style.css`, `api.js` (`BackendClient` con `listChats`,
   `createChat`, `getChat`, `deleteChat`; `BackendError`), `texts.js` (`errorMessage`,
   `formatDate`, testi), `app.js` (elenco, nuova chat, selezione con `#/chats/<id>`, eliminazione
   con `confirm`, riquadro d'errore). Vista dei messaggi e invio al punto 3.
4. `pytest.ini`: marcatore `browser` escluso dalla suite predefinita.
5. Test: `test_frontend_config.py`, `test_frontend_app.py`, `test_frontend_service.py`,
   `test_frontend_contract.py`, CORS in `test_backend_config.py`, `test_backend_api.py` e
   `test_backend_service.py`; `tests/frontend/*.test.mjs` lanciati da `test_frontend_js.py`;
   `test_frontend_browser.py` (Edge senza finestra, back-end vero su SQLite, CA-84). Poi `pytest`
   e `pytest -m browser`.

Decisioni:
- `_log_level` di `assistant/config.py` diventa pubblico (`read_log_level`): il front-end valida
  `LOG_LEVEL` con le stesse regole senza copiare il codice né importare un nome privato.
- `errorMessage` copre già tutta la tabella della specifica §5 (funzione pura, una riga per caso);
  `sendMessage`, `toolsSummary` e la vista dei messaggi arrivano al punto 3 con il loro uso.
- Selezionare una chat la legge con `GET /chats/{id}` (titolo e `404`), anche se i messaggi si
  mostrano dal punto 3: così ricarica e chat inesistente funzionano già.
- Campi letti dalla pagina elencati nel test del contratto con Node (`contract.test.mjs`): il
  JavaScript della pagina non è importabile senza DOM.

### Punto 2 · Front-end: elenco, creazione ed eliminazione — fatto

- Back-end: `CORS_ORIGINS` (`BackendConfig.cors_origins`), `create_app(..., cors_origins=())` con
  `CORSMiddleware` (metodi `GET`/`POST`/`DELETE`, intestazione `Content-Type`, niente credenziali),
  riga d'avvio con `cors_origins=…`. OpenAPI invariato.
- `frontend/`: `config.py`, `app.py` (`/config.js` con `no-store`, `StaticFiles(html=True)`, niente
  `/docs` né `/openapi.json`), `__main__.py`, `backend-openapi.json`; pagina `static/index.html`,
  `style.css`, `api.js` (`BackendClient`: `listChats`, `createChat`, `getChat`, `deleteChat`;
  `BackendError`), `texts.js` (`TEXTS`, `errorMessage` con tutta la tabella §5, `formatDate`,
  `chatSubtitle`), `app.js` (elenco, nuova chat in cima e aperta, selezione con `#/chats/<id>`,
  ricarica, chat inesistente → errore e nessuna selezione, eliminazione con `confirm`, riquadro
  d'errore chiudibile). `assistant.config._log_level` → `read_log_level` (pubblico).
- `pytest.ini`: marcatore `browser`, escluso come `real`. README (sezione front-end, variabili,
  test nel browser, diagnosi CORS), `.env.example`, `CLAUDE.md` (struttura e comandi).
- Decisioni prese durante l'esecuzione:
  - Una voce non valida di `CORS_ORIGINS` si cita com'era scritta (prima di togliere la `/`
    finale): `http://` diventerebbe `http:` nel messaggio.
  - Ogni azione dell'utente (nuova chat, selezione, eliminazione) chiude il riquadro d'errore
    precedente: altrimenti un errore vecchio resterebbe dopo che il back-end è tornato.
  - Il client chiama `fetch` globale senza sé stesso come `this` (i browser rifiutano
    `client.fetch(...)` con «Illegal invocation»); il tempo massimo copre anche la lettura del corpo.
  - Risposta `2xx` non JSON → `BackendError(status, null, "risposta non in formato JSON")`.
  - Nel browser, ogni test controlla anche che la pagina non abbia avuto errori JavaScript non
    gestiti (`pageerror`).
  - Il test «back-end spento» (CA-85 per elenco e creazione) è già qui, perché tocca il flusso
    dell'elenco; quelli dell'invio restano al punto 3.
- Test nuovi: `test_frontend_config.py` (13), `test_frontend_app.py` (15), `test_frontend_service.py`
  (5), `test_frontend_contract.py` (1), `test_frontend_js.py` (1 → 35 test Node: client 16, testi
  14, contratto 5), `test_backend_config.py` (+15 CORS), `test_backend_api.py` (+12 CORS: richiesta
  preliminare per le quattro operazioni, risposte e errori 404/422/503 con l'intestazione, altra
  origine senza, nessun CORS senza origini, OpenAPI invariato), `test_backend_service.py` (+1, riga
  d'avvio aggiornata); `test_frontend_browser.py` (12, marcatore `browser`).
- Verifiche:
  - `pytest` → 888 passed, 74 deselected (62 reali, 12 browser).
  - `pytest -m browser` → 12 passed in circa 5 s con Edge, 12 passed anche con
    `BROWSER_CHANNEL=chrome`.
  - `python -m frontend` avviato davvero (porta 8089, da Git Bash): riga d'avvio, `/config.js` con
    l'indirizzo predefinito, `/` HTML, `/docs` 404; `BACKEND_URL=backend:8001` → «Configurazione non
    valida: …», exit 1.
  - Rigenerazione del contratto verificata da Git Bash (`UPDATE_CONTRACT=1 … pytest
    tests/test_frontend_contract.py`); la forma PowerShell del README non è stata eseguita (comando
    bloccato dai permessi della sessione: imposta una variabile d'ambiente).
- Problemi aperti: vista dei messaggi, invio, attesa ed errori dell'agente al punto 3; il back-end
  con CORS non è stato avviato su PostgreSQL in questo punto (coperto da `TestClient` e dai test nel
  browser su SQLite), la prova reale è il punto 4.

### Punto 3 · Vista dei messaggi, invio, attesa ed errori — piano

1. `api.js`: `sendMessage(id, text)` → `POST /chats/{id}/messages` `{"content"}` con
   `sendTimeoutMs` (predefinito 660 s, specifica §1 e §7).
2. `texts.js`: testi del campo, del pulsante e dell'attesa (`waiting(secondi)`), `toolsSummary`
   («Strumenti usati: calculate, convert_units (errore)»), `toolDetail` (argomenti e risultato in
   JSON), `questionSaved(error)` (errori dell'agente: la domanda è nel back-end),
   `visibleMessages(messages, pendingText)` (toglie la domanda già salvata che è anche in attesa).
3. `index.html`, `style.css`: elenco dei messaggi `#messages` (domande a destra, risposte a sinistra,
   ora, strumenti in `<details>`), riga d'attesa, modulo `#composer` (`textarea` e «Invia»).
4. `app.js`: vista dei messaggi; invio con Invio o pulsante (Maiusc+Invio va a capo, testo vuoto
   ignorato); invii in attesa per chat (`Map`), contatore dei secondi, campo e pulsante disattivati
   solo per quella chat; bozze per chat; `201` → messaggi aggiunti ed elenco riletto; errore →
   messaggio, chat riletta, testo rimesso nel campo se la domanda non è salvata.
5. Test: Node (`api.test.mjs`: `sendMessage`, tempo massimo dell'invio separato; `texts.test.mjs`:
   nuove funzioni; `contract.test.mjs`: invio, `ChatMessageInfo`, `SendMessageResponse`, errori
   dell'invio); browser (`test_frontend_browser.py`, agente finto controllabile al posto di
   `NoAgent`: messaggi salvati con ora e strumenti, invio con attesa e strumenti, Maiusc+Invio e
   testo vuoto, altra chat durante l'attesa, agente spento `503`, errore `502`, back-end spento
   durante l'invio, HTML nei messaggi come testo). Poi `pytest` e `pytest -m browser`.

Decisioni:
- Il testo torna nel campo per ogni errore che non sia dell'agente (`503 agent_unavailable`,
  `504`, `502`): in quei casi la domanda è salvata e la chat riletta la mostra; negli altri
  (rete, `400`, `422`, `404`, database, `500`, tempo scaduto) restituire il testo non fa danni e
  la chat riletta dice se era stato salvato. Il testo non sovrascrive una bozza nel frattempo scritta.
- Un errore dell'invio si mostra solo se quella chat è ancora aperta (come la risposta, specifica
  §5); altrimenti si aggiorna solo l'elenco e la chat, riaperta, mostra la domanda senza risposta.
- Il titolo della chat aperta si aggiorna dall'elenco riletto (la prima domanda dà il titolo; la
  risposta di `POST …/messages` non contiene `ChatInfo`).

### Punto 3 · Vista dei messaggi, invio, attesa ed errori — fatto

- `api.js`: `sendMessage(id, text)` con `sendTimeoutMs` (660 s). `texts.js`: `TEXTS.waiting`,
  `questionSaved`, `toolsSummary`, `toolDetail`, `visibleMessages`. `index.html`: `#messages` e
  modulo `#composer` (`textarea` «Scrivi una domanda…», «Invia»); `style.css` per messaggi,
  strumenti, attesa e campo.
- `app.js`: messaggi con ora (`<time>`), strumenti in `<details>`, tutto con `textContent`; invio
  con Invio o «Invia» (Maiusc+Invio a capo, testo vuoto ignorato, testo inviato senza spazi ai
  lati); invii in attesa per chat con contatore dei secondi; campo e pulsante disattivati solo nella
  chat che aspetta; bozze per chat; `201` → domanda e risposta al posto di quella in attesa, elenco
  riletto e titolo della chat aperta preso dall'elenco; errore → riquadro (solo se la chat è ancora
  aperta), chat riletta, testo rimesso nel campo se la domanda non è salvata. `openFromAddress`
  divisa in `openFromAddress` e `readOpenChat` (rilettura senza svuotare la vista).
- Decisioni prese durante l'esecuzione:
  - Rileggere l'elenco non ridisegna i messaggi (aggiorna solo il titolo): altrimenti si
    chiuderebbero i `<details>` degli strumenti aperti dall'utente.
  - Etichette fisse del campo e del pulsante scritte in `index.html` (non in `TEXTS`): non cambiano.
  - Il campo riceve il fuoco quando una chat si apre e dopo una risposta (specifica §5: «campo di
    testo pronto»).
- Test: Node 47 (client 21: +5 su `sendMessage` e i due tempi massimi; testi 19: +5; contratto 7:
  invio, `ChatMessageInfo`, `SendMessageRequest`/`SendMessageResponse`, errori `400/404/502/503/504`
  dell'invio); browser 21 (+9: messaggi con ora e strumenti, invio con attesa e strumenti, testo
  vuoto e Maiusc+Invio, altre chat durante l'attesa con bozza e risposta arrivata altrove, agente
  spento `503`, errore `502` con il motivo, chat eliminata prima dell'invio, back-end spento durante
  l'invio con il testo restituito, HTML in domanda, risposta e strumenti come testo). `NoAgent`
  sostituito da `FakeAgent` controllabile (risposta, strumenti, errore, attesa).
- Verifiche: `pytest` → 888 passed, 83 deselected (62 reali, 21 browser); `pytest -m browser` →
  21 passed in circa 9 s con Edge (tre esecuzioni di seguito) e 21 passed con
  `BROWSER_CHANNEL=chrome`.
- Problemi aperti: prova reale dal browser con LM Studio, PostgreSQL e agente veri al punto 4;
  una lettura della chat partita prima che arrivi la risposta e conclusa dopo potrebbe mostrare la
  domanda senza risposta fino alla prossima apertura (finestra stretta, non osservata nei test).

### Punto 4 · Prova reale Step 8 dal browser — piano

Servizi verificati all'inizio: LM Studio con `google/gemma-4-e2b` (`GET /v1/models`), container
`assistente-postgres` riavviato con `docker start` (porta 5433), Edge per Playwright.
1. `tests/test_real.py`: `start_frontend` (`python -m frontend` come sottoprocesso con
   `BACKEND_URL`), `start_backend` con `CORS_ORIGINS` facoltativo; prova
   `test_frontend_chat_from_the_browser` (CA-86, CA-87): schema temporaneo in `TEST_DATABASE_URL`,
   agente, back-end e front-end come sottoprocessi, Edge senza finestra. Nuova chat, «Quanto fa
   17 * 23?» → attesa, risposta con «391», «Strumenti usati: calculate», `tool=calculate` nel log
   dell'agente; back-end fermato e riavviato sulla stessa porta, pagina ricaricata → chat e messaggi;
   agente fermato → messaggio d'errore, domanda salvata visibile, «Nuova chat» funziona. Schermate in
   `tmp_path`.
2. Esecuzione con `pytest tests/test_real.py -m real -k frontend`; poi `pytest` e `pytest -m browser`.
3. README (prova reale del front-end, avvio dei quattro processi), `CLAUDE.md` (comando), esiti in
   requisiti §16 (CA-86, CA-87) e qui. Servizio non raggiungibile → `[!]`.

Decisioni:
- Una sola prova con le tre fasi (come CA-78): agente, schema e pagina si avviano una volta, e la
  fase «agente fermato» usa la chat creata prima, come chiede CA-87 («domanda salvata visibile»).
- Solo marcatore `real` (quello del modulo), non `browser`: `pytest -m browser` resta senza LM Studio.

### Punto 4 · Prova reale Step 8 dal browser — fatto

- `tests/test_real.py`: `start_backend(..., cors_origins="")` (imposta `CORS_ORIGINS` se dato),
  `start_frontend`, `open_browser_page` (Edge o `BROWSER_CHANNEL`, senza finestra, errori JavaScript
  raccolti), prova `test_frontend_chat_from_the_browser`. Playwright importato dentro le funzioni:
  il modulo resta raccoglibile anche senza la dipendenza di test del browser. Nessun codice
  dell'applicazione cambiato.
- Prima esecuzione fallita per l'ambiente, non per il codice: senza `LMSTUDIO_BASE_URL` e
  `LMSTUDIO_MODEL` nell'ambiente l'agente esce con «Configurazione non valida» (come documentato).

| CA | Prova | Esito |
|----|-------|-------|
| CA-86, CA-87 | `LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1 LMSTUDIO_MODEL=google/gemma-4-e2b MAX_STEPS=5 TEST_DATABASE_URL=postgresql://lab:…@127.0.0.1:5433/assistente pytest tests/test_real.py -m real -k frontend -s` (Edge) | ✅ 1 passed in 92 s. Pagina: «Nuova chat», «Quanto fa 17 * 23?» con l'attesa (schermata), risposta «391» dopo 74 s con «Strumenti usati: calculate» (argomenti `{"expression":"17 * 23"}`, risultato 391), titolo dalla domanda. Log dell'agente: `variant=mcp tool=calculate`, `api response=chat status=200 tools=calculate`; back-end: `agent_call chat=1 history=0`, `send_message … status=201 tools=calculate`, `cors_origins=` con la porta del front-end. Back-end riavviato, pagina ricaricata → stessa chat e due messaggi con gli strumenti. Agente fermato → riquadro «L'assistente non è raggiungibile… riprova più tardi», domanda «Quanto fa 2 + 2?» visibile (`get_chat … messages=3`), `503 agent_unavailable` nel log; «Nuova chat» → seconda chat creata e aperta; nessun errore JavaScript. Dopo la prova `\dn` mostra solo `public` |
| — | `pytest` | ✅ 888 passed, 84 deselected; `pytest -m real --collect-only` raccoglie 63 prove |
| — | `pytest -m browser` | ✅ 21 passed in 9 s (Edge) |

- Schermate controllate a vista (`1-attesa.png`, `2-risposta.png`, `4-agente-fermato.png`): attesa
  con il contatore, risposta con il dettaglio dello strumento aperto, riquadro d'errore con la
  domanda salvata.
- Documenti: README (introduzione con il front-end, titolo della sezione senza «in corso», prova
  reale `-k frontend` con le fasi e le schermate, conteggio dei test), `CLAUDE.md` (comando della
  prova; «in corso» tolto da back-end e front-end), requisiti §16 (esiti di CA-79…CA-87).
- Container `assistente-postgres` lasciato attivo per lo Step 9 (dati conservati; `docker stop
  assistente-postgres` per fermarlo).
- Problemi aperti: una sola esecuzione (dimostra il comportamento con quella domanda, non che il
  modello usi sempre `calculate`); prova solo con Edge, non con Chrome; i comandi del README per i
  quattro terminali non sono stati rieseguiti a mano (la prova avvia gli stessi `python -m …` con le
  stesse variabili). La finestra stretta del punto 3 (lettura della chat partita prima della risposta)
  non si è vista.

## Step 9 · Docker Compose: un container per componente (2026-11-14)

Specifica: [`docs/superpowers/specs/2026-11-14-compose-design.md`](docs/superpowers/specs/2026-11-14-compose-design.md);
requisiti §17 (RF-76…RF-80, CA-88…CA-93). Questo piano sostituisce l'approvazione (modalità
autonoma); i punti successivi dello step seguono la specifica.

### Piano dello step (un punto di `TODO.md` per riga)

1. Specifica e requisiti §17; `Dockerfile` → `docker/agent.Dockerfile` (`git mv`, comando = servizio
   HTTP), nuovi `docker/backend.Dockerfile` e `docker/frontend.Dockerfile`; `compose.yaml` solo nei
   percorsi dei Dockerfile (la CLI imposta `command: python -m assistant`). Test:
   `tests/test_docker.py` (controlli statici dei tre Dockerfile, CA-88). Prove a mano CA-89: tre
   immagini costruite e avviate una per una (agente con LM Studio, back-end col PostgreSQL del
   container sulla 5433, front-end). README (paragrafo dell'immagine) e `CLAUDE.md` (struttura).
2. `compose.yaml` a quattro servizi più la CLI nel profilo `cli`; `.env.example` con `POSTGRES_*`;
   test con `docker compose config --format json` (CA-90).
3. Prova reale con Compose (CA-91…CA-93, pagina in Edge con Playwright); README (sezione Docker,
   diagnosi) e `CLAUDE.md` (comandi Docker); esiti in requisiti §17 e qui. Docker o LM Studio non
   raggiungibili → `[!]`.

### Decisioni (scelte del progettista, dettagli nella specifica §1)

- Dockerfile in `docker/<servizio>.Dockerfile` con contesto la radice: back-end e front-end importano
  `assistant`, e la convenzione `<nome>.Dockerfile` è riconosciuta da Docker.
- Stessa base fissata e stesse prime istruzioni (`requirements.txt` con `constraints.txt`) nei tre
  file: livello delle dipendenze costruito una volta e condiviso (decisione dello Step 7: stesse
  dipendenze nel back-end).
- `assistant/` copiato intero anche in back-end e front-end: è la libreria comune, più robusto che
  elencarne i moduli.
- Utente `app` con uid 1000 (come il vecchio `assistant`): il volume `notes-data` esistente resta
  scrivibile.
- `*_HOST=0.0.0.0` nell'immagine e anche in Compose (`environment` vince su un `.env` locale).
- Back-end raggiunto dal browser sulla porta pubblicata `127.0.0.1:8001` (decisione dello Step 8,
  niente proxy); agente e PostgreSQL senza porte.
- CLI nel profilo `cli`: `docker compose up` avvia solo i quattro servizi, `docker compose run --rm
  assistant` continua a funzionare.
- Credenziali `POSTGRES_*` nel `.env`, `DATABASE_URL` costruita in Compose; password obbligatoria.
- Prove Docker a mano con esiti nel diario, come nelle lezioni precedenti; test automatici solo
  statici (e `docker compose config`, che non usa il demone).

### Punto 1 · Dockerfile dei tre servizi — piano

1. Specifica e requisiti §17 (fatti, vedi sopra).
2. `git mv Dockerfile docker/agent.Dockerfile`; forma comune della specifica §3 (utente `app`,
   `ENV AGENT_HOST=0.0.0.0`, `CMD python -m assistant.service`); `docker/backend.Dockerfile`
   (`assistant/`, `backend/`, `BACKEND_HOST`, 8001, `python -m backend`);
   `docker/frontend.Dockerfile` (`assistant/`, `frontend/`, `FRONTEND_HOST`, 8080,
   `python -m frontend`).
3. `compose.yaml`: `build` con `dockerfile: docker/agent.Dockerfile` per `agent` e `assistant`;
   `agent` senza `command` (è il predefinito dell'immagine), `assistant` con
   `command: ["python", "-m", "assistant"]`. Il resto al punto 2.
4. `tests/test_docker.py` (CA-88): istruzioni lette dal testo dei Dockerfile; porte confrontate con
   `DEFAULT_*_PORT`; moduli di `CMD` trovati con `importlib.util.find_spec`.
5. Prove a mano (CA-89): `docker build -f docker/<servizio>.Dockerfile .` per i tre; agente con
   `LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1` → `/status`; back-end con
   `DATABASE_URL=postgresql://lab:…@host.docker.internal:5433/assistente` → `GET /chats`;
   front-end → `/` e `/config.js`; `whoami` = `app`; `docker compose build` e `docker compose run
   --rm -T assistant` ancora funzionanti.
6. README (paragrafo dell'immagine nella sezione Docker), `CLAUDE.md` (struttura: `docker/`).

### Punto 1 · Dockerfile dei tre servizi — fatto

- Scritti la specifica e i requisiti §17 (intestazione di `requisiti.md` aggiornata).
- `Dockerfile` → `docker/agent.Dockerfile` (`git mv`): utente `app` (uid 1000), `ENV
  AGENT_HOST=0.0.0.0`, `CMD python -m assistant.service`. Nuovi `docker/backend.Dockerfile`
  (`assistant/` e `backend/`, `BACKEND_HOST=0.0.0.0`, 8001, `python -m backend`) e
  `docker/frontend.Dockerfile` (`assistant/` e `frontend/`, `FRONTEND_HOST=0.0.0.0`, 8080,
  `python -m frontend`). `compose.yaml`: `build` con `dockerfile: docker/agent.Dockerfile` per
  `agent` (senza `command`) e `assistant` (`command: python -m assistant`); il resto al punto 2.
- Test nuovi: `tests/test_docker.py` (21: un Dockerfile per servizio e nessuno nella radice,
  lettore delle istruzioni, prime sei istruzioni identiche nei tre file, base fissata per digest,
  `-c constraints.txt` in `requirements.txt`, pacchetti copiati, `*_HOST=0.0.0.0` ed `EXPOSE` uguale a
  `DEFAULT_*_PORT`, utente `app` e nulla dopo `USER` tranne `EXPOSE`/`CMD`, `CMD` col modulo del
  servizio trovato da `find_spec`, cartella delle note prima di `USER`, `.dockerignore`). Mutazione
  temporanea (`EXPOSE 8000` e `USER root` nel back-end) → 2 test falliti.

| CA | Prova | Esito |
|----|-------|-------|
| CA-88 | `pytest tests/test_docker.py` | ✅ 21 passed |
| CA-89 | `docker build -q -f docker/<servizio>.Dockerfile -t step9-<servizio>:prova .` per i tre | ✅ tre immagini da 486 MB; l'ottavo livello (dipendenze) ha lo stesso digest nelle tre: condiviso |
| CA-89 | front-end: `docker run -p 127.0.0.1:8090:8080 step9-frontend:prova` | ✅ `/config.js` → `window.APP_CONFIG = {"backendUrl": "http://127.0.0.1:8001"};`, `/` `200 text/html`, `whoami` → `app`, riga d'avvio `frontend listening=http://0.0.0.0:8080` |
| CA-89 | back-end: `DATABASE_URL=postgresql://lab:…@host.docker.internal:5433/assistente`, `PGOPTIONS=-csearch_path=prova_step9` (schema temporaneo), `AGENT_URL` su una porta chiusa | ✅ `POST /chats` `201`, `GET /chats` `200` con la chat, invio → `503 agent_unavailable` con la domanda salvata (1 riga in `chat_messages`); riga d'avvio con `lab:***`; `whoami` → `app`; schema eliminato, `\dn` mostra solo `public` |
| CA-89 | agente: `LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1`, `LMSTUDIO_MODEL=google/gemma-4-e2b` | ✅ `/status` `200` (`mcp: 7 strumenti`, modello `ok`); processi del container: `python -m assistant.service` e il server `python -m assistant.mcp_server --notes-db /app/data/notes.sqlite3 …` (stdio nello stesso container); `/app/data` di `app`; `POST /chat` «Quanto fa 17 * 23?» → «17 * 23 fa 391.» con `calculate` (`variant=mcp tool=calculate` nel log, 74 s) |
| — | `docker compose build`; `printf 'Quanto fa 2 + 2?\nesci\n' \| docker compose run --rm -T assistant`; `docker compose down` | ✅ CLI dalla nuova immagine: agente `(healthy)`, «2 + 2 fa 4.», «Arrivederci!» (volume `notes-data` esistente usato senza errori di permessi) |
| — | `pytest` | ✅ 909 passed, 84 deselected |

- Decisione presa durante l'esecuzione: nelle prove a mano da Git Bash un valore come
  `-e NOTES_DB=/tmp/…` viene convertito in un percorso Windows (`/app/C:`, errore di permessi
  all'avvio): la prova dell'agente usa il predefinito `data/notes.sqlite3` (`/app/data`), che è anche
  il caso di Compose. Nessun cambiamento al codice.
- Immagini di prova `step9-*:prova` eliminate dopo le prove; container `assistente-postgres`
  lasciato attivo.
- Documenti: README (paragrafo delle immagini nella sezione Docker, test di `test_docker.py`, conteggio
  dei test), `CLAUDE.md` (struttura: `docker/` e `test_docker.py`), requisiti §17 (esiti di CA-88 e
  CA-89).
- Problemi aperti: `compose.yaml` a quattro servizi, credenziali di PostgreSQL in `.env` e test con
  `docker compose config` al punto 2; il README descrive ancora Compose con due servizi (agente e CLI),
  da riscrivere al punto 3 insieme alla prova reale. L'agente resta pubblicato su `127.0.0.1:8000`
  fino al punto 2.

### Punto 2 · `compose.yaml` a quattro servizi — piano

1. `compose.yaml` (specifica §4): `frontend` (`docker/frontend.Dockerfile`, `127.0.0.1:8080:8080`,
   `FRONTEND_HOST=0.0.0.0`, `BACKEND_URL=${BACKEND_URL:-}`, `LOG_LEVEL`), `backend`
   (`docker/backend.Dockerfile`, `127.0.0.1:8001:8001`, `DATABASE_URL` costruita da `POSTGRES_*` verso
   `postgres:5432`, `AGENT_URL=http://agent:8000`, `BACKEND_HOST=0.0.0.0`, `CORS_ORIGINS`,
   `LOG_LEVEL`; `depends_on` `postgres` `service_healthy` e `agent` `service_started`), `agent`
   come ora ma **senza `ports`**, `postgres` (`postgres:18.6`, `POSTGRES_*`, `healthcheck`
   `pg_isready`, volume `postgres-data` in `/var/lib/postgresql`, senza porte), `assistant` con
   `profiles: ["cli"]`; volumi `notes-data` e `postgres-data`.
2. `.env.example`: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` con la nota sui caratteri
   della password; `.env` locale (fuori da Git) con le stesse tre righe, perché ora ogni comando
   `docker compose` le richiede.
3. Test in `tests/test_docker.py` (CA-90): `compose.yaml` copiato in `tmp_path` con un `.env` di
   credenziali finte, `docker compose config --format json` (con e senza `--profile cli`) con
   l'ambiente ripulito dalle variabili interpolate; saltato se manca la CLI di Docker. Controlli
   della specifica §7 più password mancante → errore col messaggio. Poi `pytest` completo e
   `docker compose config` sul file vero.

Decisioni:
- Il test copia `compose.yaml` in una cartella temporanea con il suo `.env`: `env_file: .env` è
  relativo al file, e un clone senza `.env` (o con un `.env` vero) non deve cambiare l'esito.
- Ambiente del sottoprocesso senza `POSTGRES_*`, `LOG_LEVEL`, `CORS_ORIGINS`, `BACKEND_URL`,
  `LMSTUDIO_BASE_URL_DOCKER` e `COMPOSE_*`: le variabili della shell vincono sul `.env`
  nell'interpolazione.
- `pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}` (variabili lette nel container): senza
  `-U`/`-d` `pg_isready` userebbe l'utente `root` e la riga «FATAL: role "root"» nel log.

### Punto 2 · `compose.yaml` a quattro servizi — fatto

- `compose.yaml`: `frontend`, `backend`, `agent` (senza `ports`), `postgres` (`postgres:18.6`,
  `healthcheck` `pg_isready`, volume `postgres-data`), CLI `assistant` nel profilo `cli`;
  `DATABASE_URL` del back-end costruita da `POSTGRES_*` con
  `${POSTGRES_PASSWORD:?Manca POSTGRES_PASSWORD nel file .env}`; `BACKEND_URL` e `CORS_ORIGINS`
  vuoti se non impostati (i servizi usano i predefiniti, verificato nel codice di configurazione).
- `.env.example` con `POSTGRES_USER=lab`, `POSTGRES_PASSWORD=cambiami`, `POSTGRES_DB=assistente` e la
  nota sui caratteri; `.env` locale (fuori da Git) con le tre righe (`lab`/`labprova`/`assistente`,
  come il container del README).
- Test nuovi in `tests/test_docker.py` (+18, CA-90): quattro servizi e due volumi senza profilo; CLI
  solo con `--profile cli` (Dockerfile, comando, `AGENT_URL`, `service_healthy`, `stdin_open`/`tty`);
  Dockerfile di ogni servizio; `agent` e `postgres` senza porte; `backend`/`frontend` solo su
  `127.0.0.1` con le porte predefinite; `*_HOST=0.0.0.0`; immagine, credenziali, volume e
  `healthcheck` di `postgres`; `depends_on` e indirizzi interni del back-end; nessuna variabile del
  database nel front-end; facoltative vuote; predefiniti di utente e database; password mancante →
  errore col messaggio; `.env.example` con le tre righe. Mutazione temporanea (profilo tolto,
  `service_started` per `postgres`) → 3 test falliti.
- Decisione presa durante l'esecuzione: le variabili da togliere dall'ambiente del sottoprocesso si
  leggono da `compose.yaml` con un'espressione regolare (`${NOME`, esclusi i `$${…}`), invece di un
  elenco scritto a mano che una variabile nuova renderebbe incompleto.

| CA | Prova | Esito |
|----|-------|-------|
| CA-90 | `pytest tests/test_docker.py` | ✅ 39 passed (Docker Compose v5.6.0, senza demone necessario) |
| — | `POSTGRES_PASSWORD=dallashell pytest` | ✅ 927 passed, 84 deselected (la variabile della shell non cambia l'esito) |
| — | `docker compose config` sul file vero con il `.env` locale | ✅ servizi `agent`, `postgres`, `backend`, `frontend`; `DATABASE_URL` → `postgresql://lab:***@postgres:5432/assistente` |
| — | `printf 'Quanto fa 2 + 2?\nesci\n' \| docker compose run --rm -T assistant` (immagine dell'agente del punto 1, LM Studio attivo) | ✅ agente `(healthy)` con `8000/tcp` non pubblicata, «2 + 2 fa 4.», «Arrivederci!», exit 0; dall'host `127.0.0.1:8000/status` non risponde, da `docker compose exec agent` → `200`; poi `docker compose down` |

- Documenti: README (sezione Docker con i quattro servizi, l'agente non pubblicato e le credenziali;
  test di `compose.yaml`; conteggio dei test; rimando dal container PostgreSQL del back-end),
  `CLAUDE.md` (struttura: `compose.yaml` e test), requisiti §17 (CA-90).
- Problemi aperti: `docker compose up` con i quattro servizi, la chat dal browser e la persistenza
  dopo `down`/`up` (CA-91…CA-93) al punto 3, con la riscrittura dei comandi Docker nel README e in
  `CLAUDE.md` (che dice ancora «non `up`»). Chi ha un `.env` senza `POSTGRES_PASSWORD` deve
  aggiungerla anche solo per la CLI in Docker (detto nel README).

### Punto 3 · Prova reale con Compose — piano

Servizi verificati all'inizio: Docker 29.9.1, LM Studio con `google/gemma-4-e2b` (`GET /v1/models`),
`.env` locale con `POSTGRES_*`.
1. CA-91: porte 8001 e 8080 libere; `docker compose up -d --build`; `docker compose ps` (quattro
   servizi, `healthy` per `agent` e `postgres`); `127.0.0.1:8000/status` dall'host non risponde.
2. CA-92: script usa e getta in `%TEMP%` (fuori dal progetto) con Playwright e Edge sulla pagina
   `http://127.0.0.1:8080`: nuova chat, «Quanto fa 17 * 23?» → «391» con «Strumenti usati:
   calculate»; `docker compose logs agent` (`variant=mcp tool=calculate`) e `logs backend`
   (`send_message … status=201`).
3. CA-93: `docker compose down` e `docker compose up -d`; la pagina ricaricata mostra la stessa chat
   con i due messaggi (e `GET /chats` dall'host).
4. README (sezione Docker: comandi `up`/`ps`/`logs`/`down`, diagnosi delle porte occupate e della
   password del volume) e `CLAUDE.md` (comandi Docker, «non `up`» tolto); esiti in requisiti §17 e
   qui; `pytest`. Docker o LM Studio non raggiungibili → `[!]`.

Decisioni:
- Prova a mano con uno script fuori dal progetto, non una prova in `tests/test_real.py`: la
  specifica §7 tiene le prove con Compose a mano (costruzione delle immagini e `down`/`up` durano
  minuti e toccano volumi condivisi).
- Il volume `postgres-data` non si cancella dopo la prova: contiene solo la chat di prova ed è il
  volume che userebbe l'utente; lo si dice qui, con il comando per eliminarlo. (Cambiata durante
  l'esecuzione, vedi sotto.)

### Punto 3 · Prova reale con Compose — fatto

- Nessun codice dell'applicazione né test cambiati: solo prove con Docker, README, `CLAUDE.md` e
  requisiti. Script di Playwright usa e getta in `%TEMP%\step9compose` (fuori dal progetto), con le
  schermate.

| CA | Prova | Esito |
|----|-------|-------|
| CA-91 | `docker compose up -d --build` (porte 8000/8001/8080 libere prima); `docker compose ps`; `curl http://127.0.0.1:8000/status` dall'host | ✅ volume `postgres-data` e rete creati, `postgres` `Healthy` prima dell'avvio di `backend`; `ps`: `agent` `Up (healthy)` `8000/tcp`, `backend` `127.0.0.1:8001->8001/tcp`, `frontend` `127.0.0.1:8080->8080/tcp`, `postgres` `Up (healthy)` `5432/tcp`; 8000 dall'host: nessuna risposta (curl exit 7); `/config.js` → `backendUrl http://127.0.0.1:8001`; `GET /chats` `200 []` |
| CA-92 | Edge senza finestra su `http://127.0.0.1:8080`: «Nuova chat», «Quanto fa 17 * 23?» | ✅ attesa visibile, risposta dopo 70 s «17 * 23 fa 391.», «Strumenti usati: calculate» (argomenti `{"expression":"17 * 23"}`, risultato 391), titolo dalla domanda, indirizzo `#/chats/1`, nessun errore JavaScript. `docker compose logs agent`: `step=1/5 variant=mcp tool=calculate call_id=… arguments={'expression': '17 * 23'}`, `api response=chat status=200 tools=calculate`; `logs backend`: riga d'avvio con `lab:***@postgres:5432` e `agent_url=http://agent:8000`, `send_message chat=1 status=201 tools=calculate` |
| CA-93 | `docker compose down` (container e rete rimossi, volumi presenti), `docker compose up -d`, pagina riaperta | ✅ quattro servizi di nuovo attivi; `GET /chats` → la chat 1; nella pagina la stessa chat con i due messaggi e «Strumenti usati: calculate» |
| — | `printf 'Quanto fa 2 + 2?\nesci\n' \| docker compose run --rm -T assistant` con i quattro servizi attivi | ✅ CLI sullo stesso `agent` (`Running`, `Healthy`), «2 + 2 fa 4.», «Arrivederci!», exit 0 |
| — | Diagnosi: `python -m http.server 8080` sull'host, poi `docker compose up -d frontend` | ✅ «ports are not available: exposing port TCP 127.0.0.1:8080 … bind: Only one usage of each socket address …», exit 1; processo fermato → `up -d frontend` riparte |
| — | Diagnosi: `POSTGRES_PASSWORD=altrapassword docker compose up -d backend` sul volume già inizializzato | ✅ `postgres` ricreato e `healthy`, `backend` `Exited (1)` con «Database non raggiungibile: … password authentication failed for user "lab"»; `docker compose up -d` con il `.env` → di nuovo attivo, chat presente |
| — | `docker compose down`, `docker volume rm assistente-laboratorio_postgres-data`, `docker compose up -d` (comando del README) | ✅ `GET /chats` → `[]`; `notes-data` intatto; poi `docker compose down` |
| — | `pytest` | ✅ 927 passed, 84 deselected |

- Decisione cambiata durante l'esecuzione: il volume `postgres-data` è stato eliminato per verificare
  il comando del README; ricreato vuoto dall'`up -d` successivo (la chat di prova non c'è più, gli
  esiti restano qui). Lo stack è fermo (`docker compose down`); volumi `notes-data` e
  `postgres-data` presenti. Container `assistente-postgres` dello Step 7 non toccato.
- Nel README niente `docker compose down -v` (scritto in una prima stesura e tolto): cancellerebbe
  anche `notes-data`; per le chat si indica `docker volume rm …_postgres-data`.
- Documenti: README (introduzione con Compose; sezione Docker divisa in «Avvio dei quattro servizi e
  chat dal browser», «CLI in Docker», «Immagini e volumi»; «in corso» tolto; due voci di «Diagnosi»:
  porta occupata e password cambiata dopo la creazione del volume), `CLAUDE.md` (comandi Docker con
  `up -d --build`, `ps`, `logs`, `down`), requisiti §17 (esiti di CA-91…CA-93).
- Problemi aperti: una sola esecuzione con il modello (dimostra il comportamento con quella domanda);
  pagina provata solo con Edge; `docker compose up` senza `-d` (log in primo piano) e
  `docker compose build --no-cache` non provati; i comandi del README sono stati eseguiti da Git
  Bash, non da PowerShell (sono gli stessi comandi `docker`); la frase di `CLAUDE.md` «Confini» che
  elenca gli step successivi come da non anticipare non è stata cambiata (regola dell'utente,
  superata dalla sezione «Modalità autonoma»).

## Facoltativo · Streaming della risposta (2026-11-14)

Specifica: [`docs/superpowers/specs/2026-11-14-streaming-design.md`](docs/superpowers/specs/2026-11-14-streaming-design.md);
requisiti §18 (RF-81…RF-87, CA-94…CA-104). Questo piano sostituisce l'approvazione (modalità
autonoma); i punti successivi seguono la specifica.

### Piano (un punto di `TODO.md` per riga)

1. Specifica e requisiti §18 (solo documenti). Verifica: `pytest` invariato.
2. Agente e back-end: `stream_turn` in `assistant/agent.py` (funzione comune con `run_turn` per il
   risultato), `disable_streaming=True` per router, revisore e riassunto in `model.py`,
   `POST /chat/stream` in `assistant/api.py` (controlli in una dipendenza, eventi con
   `EventSourceResponse` di FastAPI), `iter_sse` e `AgentClient.chat_stream` in `api_client.py`,
   `POST /chats/{chat_id}/messages/stream` in `backend/api.py`; modello finto in streaming in
   `conftest.py`; test in `test_agent.py`, `test_model.py`, `test_api.py`, `test_api_client.py`,
   `test_backend_api.py` (CA-94…CA-98, CA-103); contratto rigenerato.
3. Front-end e prova reale: `readEvents` e `sendMessageStream` in `api.js`, testi in `texts.js`,
   bozza e strumenti in `app.js` e CSS; test con `node --test` e nel browser (CA-99, CA-100); prove
   reali CA-101 e CA-102 in `test_real.py` (LM Studio, PostgreSQL, Edge); README (CA-104). Servizi
   non raggiungibili o LM Studio che non fa streaming con gli strumenti → `[!]`.

### Decisioni (scelte del progettista, dettagli nella specifica §1)

- **Bozza mostrata** mentre viene scritta, segnata come provvisoria; rifiuto del revisore → evento
  `reset` `review` con il motivo e avviso nella pagina; si salva solo la risposta finale. Motivo: con
  il modello locale mostrare solo la risposta approvata significherebbe non mostrare testo fino alla
  fine del turno.
- Server-Sent Events con `POST`, dal supporto SSE già incluso in FastAPI 0.162.7: nessuna dipendenza
  nuova.
- Endpoint nuovi accanto a quelli esistenti (`/chat/stream`, `/chats/{id}/messages/stream`); CLI
  invariata (la traccia non la nomina).
- Solo il nodo `llm` produce testo; router, revisore e riassunto con `disable_streaming=True`, così le
  loro richieste a LM Studio restano identiche (verificato con un modello finto che i pezzi arrivano
  con `langgraph_node`).
- Errori prima del flusso in JSON come oggi, durante il flusso come evento `error` con gli stessi
  codici; browser che chiude → il back-end chiude il flusso dell'agente, domanda senza risposta.
- Back-end → agente: 60 s al massimo senza dati (FastAPI manda `: ping` ogni 15 s), 600 s per il
  turno; nessuna ripresa di un flusso interrotto.

### Punto 1 · Specifica e requisiti — fatto

- Scritti la specifica `docs/superpowers/specs/2026-11-14-streaming-design.md` (decisioni, eventi,
  agente, client, back-end, front-end, test, rischi) e i requisiti §18 (RF-81…RF-87, CA-94…CA-104;
  intestazione di `requisiti.md` aggiornata).
- Verifiche preliminari per la specifica: `fastapi/sse.py` (0.162.7) offre `EventSourceResponse` e il
  `ping` ogni 15 s, anche con generatori sincroni; uno script usa e getta in `%TEMP%` (eliminato) con
  `GenericFakeChatModel` ha mostrato che `graph.stream(stream_mode=["messages", "updates",
  "values"])` dà i pezzi del nodo `llm` come `AIMessageChunk` con `langgraph_node="llm"`, mentre un
  modello con `disable_streaming=True` dà un solo messaggio intero.
- Test: `pytest` → 927 passed, 84 deselected (nessun codice cambiato).
- Problemi aperti: non è ancora verificato che LM Studio con `google/gemma-4-e2b` restituisca le
  chiamate a strumenti in streaming (prova reale al punto 3, CA-101); README e `CLAUDE.md` cambiano
  dal punto 2, quando c'è codice da descrivere.

### Punto 2 · Streaming nell'agente e nel back-end — piano

1. `assistant/model.py`: `_chat(config, streaming=…)`; router, revisore e riassunto con
   `disable_streaming=True` (CA-96, test in `test_model.py` con una sottoclasse di `ChatOpenAI` che
   registra le istanze).
2. `assistant/agent.py`: `_turn_result` estratta da `run_turn` (stato finale → `TurnResult`),
   `_tool_use` comune a `tools_used` e `tool_end`; `stream_turn` generatore su
   `graph.stream(stream_mode=["messages", "updates", "values"])` con gli eventi della specifica §3–4.
   `StreamingFakeModel` (sottoclasse di `BaseChatModel` con `_generate` e `_stream` a pezzi, chiamate
   comprese) in `conftest.py`; test in `test_agent.py` (CA-94).
3. `assistant/api.py`: controlli di `/chat` estratti (`_prepare`, `_model_error`), `POST /chat/stream`
   con `EventSourceResponse`, controlli in una dipendenza (errore → `ApiError` → gestore che risponde
   JSON), eventi da `_stream_events`; log d'inizio e fine (`done`, `error`, `client_gone`). Test in
   `test_api.py` (CA-95).
4. `assistant/api_client.py`: `iter_sse`, `AgentClient.chat_stream` (tempi 10 s connessione, 60 s
   tra due dati, 600 s per il turno). Test in `test_api_client.py` (CA-97).
5. `backend/api.py`: `POST /chats/{chat_id}/messages/stream` (dipendenza: domanda salvata e flusso
   dell'agente aperto; poi `question`, eventi inoltrati, `add_answer` al `done`, `done`
   `{question, answer}`). Test in `test_backend_api.py` (CA-98); contratto rigenerato con
   `UPDATE_CONTRACT=1`.
6. `pytest` completo (CA-103: i test esistenti non cambiano), README e `CLAUDE.md` (endpoint nuovi),
   requisiti §18.

Decisioni:
- `chat_stream` apre la richiesta e controlla la risposta subito (errori prima del flusso sollevati
  dalla chiamata) e restituisce il generatore degli eventi: il back-end può rispondere in JSON prima
  del flusso senza consumare il primo evento, che con il modello locale arriva dopo decine di secondi.
- L'endpoint dell'agente è un generatore asincrono che legge gli eventi in un thread e, se il client
  chiude, chiude il generatore in un thread (protetto dalla cancellazione): con `stream_mode`
  `messages` LangGraph esegue i nodi in thread separati e chiudere `graph.stream` aspetta il nodo in
  corso, che non deve bloccare il ciclo degli eventi del servizio. Il back-end resta con un generatore
  sincrono (chiudere il flusso dell'agente chiude solo una connessione).
- `iter_sse` segue lo standard SSE: un evento senza la riga vuota finale (flusso troncato) si scarta,
  ed è quindi un flusso interrotto per `chat_stream`.
- Il punto è stato svolto in due sessioni: la prima ha scritto il codice e i test di agente, servizio
  e client senza arrivare al commit; la seconda ha ripreso dal diff (`pytest` già verde, 984 passed),
  scritto i test del back-end e i documenti.
- `sse` (lettore dei corpi `text/event-stream` nei test) spostato da `test_api.py` a `conftest.py`:
  lo usano anche i test del back-end.
- Il caso «client che chiude» del back-end si prova chiamando `_forward` direttamente (generatore
  chiuso dopo due eventi), non con `TestClient`, che non garantisce quando chiude il generatore:
  stesso approccio dei test di `_stream_events` nel servizio.

### Punto 2 · Streaming nell'agente e nel back-end — fatto

- Codice: `assistant/model.py` (`disable_streaming` per router, revisore e riassunto),
  `assistant/agent.py` (`stream_turn`, `_turn_input`/`_turn_result` comuni con `run_turn`,
  `_tool_use`), `assistant/api.py` (`POST /chat/stream`, controlli in una dipendenza, gestore di
  `ApiError`, `_stream_events` e `_in_thread`), `assistant/api_client.py` (`iter_sse`,
  `AgentClient.chat_stream`), `backend/api.py` (`POST /chats/{chat_id}/messages/stream`,
  `open_stream` come dipendenza, `_forward`); contratto `frontend/backend-openapi.json` rigenerato.
- Test: `StreamingFakeModel` e `sse` in `conftest.py`; nuovi test in `test_model.py` (CA-96),
  `test_agent.py` (CA-94), `test_api.py` (CA-95), `test_api_client.py` (CA-97),
  `test_backend_api.py` (CA-98: eventi inoltrati e salvataggio uguale a `/messages`, cronologia e
  riassunto rimandati, errori prima del flusso in JSON — 400, 404, 422, 503, 504, 502, archivio
  guasto —, `error` durante il flusso con LM Studio spento, flusso troncato ed errore imprevisto,
  chat eliminata durante il turno, righe di log, `client_gone`, OpenAPI, preflight CORS).
- CA-103: i test esistenti non sono cambiati (solo import e un parametro facoltativo in più
  nell'aiuto `invalid_call` di `test_agent.py`).
- `pytest` → 1003 passed, 84 deselected.
- Documenti: README (sezione «Streaming della risposta (Server-Sent Events)»: endpoint, eventi,
  decisione sulla bozza, errori e tempi; nessun comando nuovo, perché non ancora provato con i
  servizi reali), `CLAUDE.md` (struttura: endpoint e funzioni nuove, `StreamingFakeModel`).
- Problemi aperti: nessuna prova reale ancora (LM Studio con `stream=true` e strumenti, CA-101);
  la chiusura del flusso da parte del browser è provata solo su `_forward` e non con un server
  vero; front-end, prove reali e voce di diagnosi del README al punto 3.

### Punto 3 · Streaming nel front-end e prova reale — piano

Servizi verificati all'inizio: LM Studio con `google/gemma-4-e2b` (`GET /v1/models`), container
`assistente-postgres` attivo (porta 5433), Node 24.15.0, Edge per Playwright.
1. `frontend/static/api.js`: `readEvents(chunks)` (generatore asincrono, lettore SSE su pezzi di
   testo qualsiasi, stesse regole di `iter_sse`, `data` decodificato da JSON) e
   `BackendClient.sendMessageStream(id, text, onEvent)` (specifica §7).
2. `texts.js`: `TEXTS.draftLabel`, `TEXTS.toolRunning`, `reviewNotice`, `applyEvent` (funzione pura:
   stato della risposta in arrivo `{text, tools, notice}` dopo un evento), `draftToolLine`,
   `errorMessage` per gli errori dentro il flusso (`status` 200, compreso `stream_interrupted`),
   `questionSaved` vero per ogni errore dopo l'inizio del flusso.
3. `app.js`: invio con `sendMessageStream`; eventi nello stato della chat che aspetta
   (`pending.stream`); bozza `#draft` (classe `draft`, etichetta, avviso del revisore, strumenti,
   testo) aggiornata da sola, senza ridisegnare i messaggi; `done` ed errori come oggi. CSS della bozza.
4. Test Node: `readEvents` (pezzi a metà riga, `\r\n`, commenti, più righe di `data`, evento senza
   fine), `sendMessageStream` (eventi, `done`, `error`, interruzione, dati non validi, errore JSON,
   rete, tempo), testi e `applyEvent`; contratto con l'endpoint `/messages/stream`.
5. Browser (`test_frontend_browser.py`): `FakeAgent.chat_stream` con eventi scritti dal test e
   pause (`threading.Event`); test nuovi: testo a pezzi e strumento durante l'attesa, ritorno alla
   chat con la bozza conservata, `reset` `tools` e `review` con l'avviso, errore durante il flusso
   con la domanda salvata, errore imprevisto del back-end (CA-100). I test esistenti restano.
6. Prove reali (`test_real.py`): CA-101 (`AgentClient.chat_stream` sul servizio vero), CA-102 (dal
   browser con agente, back-end e front-end come processi: almeno due aggiornamenti della bozza
   registrati da un `MutationObserver`, «Uso lo strumento calculate…» visto, risposta dopo la
   ricarica); CA-86 aggiornata alle righe di log del flusso. Poi `pytest`, `pytest -m browser`.
7. README (pagina con lo streaming, prove, diagnosi), `CLAUDE.md`, requisiti §18 con gli esiti.

Decisioni:
- La pagina usa solo l'endpoint con lo streaming; `sendMessage` resta nel client (endpoint del
  contratto ancora valido, già provato) ma la pagina non lo chiama più.
- Un errore dentro un flusso (`status` 200) vuol dire che la domanda è salvata (il back-end manda
  `question` solo dopo averla salvata): niente testo rimesso nel campo, chat riletta.
- Flusso chiuso senza evento finale o con dati non validi → un solo codice `stream_interrupted`:
  per l'utente l'effetto è lo stesso (risposta mancante, domanda salvata).
- Errore di rete o tempo scaduto durante la lettura del flusso → `BackendError(0, …)` come
  chiede la specifica §7 (stesso messaggio di oggi).
- La bozza si mostra solo quando ha qualcosa (testo, strumenti o avviso): durante l'elaborazione
  del prompt resta la riga d'attesa come nello Step 8.
- La prova CA-86 (Step 8) cambia solo nelle righe di log attese (`chat_stream`,
  `send_message_stream … outcome=done`): la pagina ora usa l'endpoint con lo streaming. CA-103
  riguarda `/chat`, `/messages` e la CLI, che non cambiano.

### Punto 3 · Streaming nel front-end e prova reale — fatto

- Codice: `frontend/static/api.js` (`readEvents`, `bodyText`, `BackendClient.sendMessageStream`,
  `errorFromBody` estratta da `errorFrom`), `texts.js` (`TEXTS.draftLabel`, `TEXTS.toolRunning`,
  `reviewNotice`, `EMPTY_DRAFT`, `applyEvent`, `draftVisible`, `draftToolLine`; `errorMessage` e
  `questionSaved` con gli errori dentro il flusso), `app.js` (invio con lo streaming, `draftItem`,
  `renderDraft`, bozza nello stato `pending.draft`), `style.css` (bozza tratteggiata, avviso,
  strumenti). Nessun cambiamento a Python, contratto, Docker.
- Decisioni prese durante l'esecuzione:
  - Un errore lanciato da `onEvent` (errore della pagina) arriva al chiamante così com'è: la lettura
    del flusso usa `next()` esplicito e solo gli errori di lettura diventano `stream_interrupted`
    o `timeout`.
  - Un errore dentro il flusso si riconosce da `status` 200 **con** un codice: `BackendError(200,
    null, …)` resta la risposta 2xx non JSON dello Step 8 (test esistente invariato).
  - Avviso del revisore con il punto finale («…: <motivo>.»): il motivo arriva senza punto da
    `clean`.
  - **Testo della bozza con la classe `draft-text`, non `message-text`**: la prima esecuzione delle
    prove reali è fallita (2 su 2) perché `#messages .message-text` contava anche la bozza, e «due
    messaggi» risultava vero prima della fine del turno. La bozza non è ancora un messaggio; test
    nel browser con un controllo in più (solo la domanda ha `message-text` durante la bozza),
    verificato con una mutazione temporanea (classe rimessa a `message-text` → test fallito).
  - `FakeAgent` di `test_frontend_browser.py` ha ora solo `chat_stream` (la pagina non chiama più
    `/messages`): `error` prima del flusso (risposta JSON), `stream_error` durante, `events` con
    pause `threading.Event`; senza `events` produce `tool_start`/`tool_end` per strumento e la
    risposta in due pezzi, così i 21 test esistenti restano invariati.
- Test: Node 79 (+32: `readEvents` su pezzi da 1 a N caratteri, CRLF, commenti, più righe,
  evento senza fine; `sendMessageStream` con eventi, `done` che chiude il corpo, `error`, sei casi
  di `stream_interrupted`, corpo tagliato dalla rete, errore JSON prima del flusso, rete, tempo,
  errore di `onEvent`; testi, `applyEvent`, `draftVisible`; contratto con `/messages/stream`);
  browser 25 (+4: testo a pezzi e strumento durante l'attesa con ritorno alla chat, `reset`
  `tools` e `review` con l'avviso, errore durante il flusso con la domanda salvata, errore
  imprevisto del back-end); `test_real.py` +2 (CA-101, CA-102) e CA-86 aggiornata.

| CA | Prova | Esito |
|----|-------|-------|
| CA-99 | `node --test tests/frontend/*.test.mjs` (anche da `pytest`) | ✅ 79 passed |
| CA-100 | `pytest -m browser` (Edge, due volte; Chrome con `BROWSER_CHANNEL=chrome`) | ✅ 25 passed in circa 10 s ogni volta |
| CA-101 | `LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1 LMSTUDIO_MODEL=google/gemma-4-e2b MAX_STEPS=5 pytest tests/test_real.py -m real -k agent_stream_with_a_tool -s` | ✅ 1 passed in 78 s: `tool_start` e `tool_end` di `calculate` a 44,9 s, 12 eventi `text` tra 50,9 e 51,8 s («1», «7», « *» … «.»), `done` a 73,3 s con «17 * 23 fa 391.» (tra testo e `done` il revisore). LM Studio accetta `stream=true` con gli strumenti di `google/gemma-4-e2b` |
| CA-86, CA-102 | stesse variabili e `TEST_DATABASE_URL=postgresql://lab:…@127.0.0.1:5433/assistente`, `pytest tests/test_real.py -m real -k frontend -s` (prima esecuzione) | ❌ 2 failed: `#messages .message-text` contava il testo della bozza (vedi sopra); le schermate mostravano la pagina corretta (bozza con lo strumento durante l'attesa) |
| CA-86, CA-102 | stesso comando dopo la correzione | ✅ 2 passed in 175 s. CA-102: bozza registrata in 12 stati da «1» a «17 * 23 fa 391.», «Uso lo strumento calculate…» visto durante l'attesa, risposta «17 * 23 fa 391.» con «Strumenti usati: calculate» anche dopo la ricarica; agente `api response=chat_stream status=200 outcome=done tools=calculate reply_chars=15 history=4 text_events=12 resets=0 duration_ms=74128`; back-end `agent_call … stream=true` e `send_message_stream chat=1 status=200 outcome=done tools=calculate`. CA-86: stesso esito dello Step 8 con le righe del flusso, back-end riavviato, agente fermato → `503 agent_unavailable` |
| CA-103 | `pytest` | ✅ 1003 passed, 90 deselected (65 reali, 25 browser); i test di `/chat`, `/messages` e CLI non cambiati |

- Schermate controllate a vista (`1-bozza.png`: domanda, riga d'attesa a 46 s, bozza tratteggiata con
  etichetta e strumento; `2-risposta.png`: risposta salvata); cartella temporanea eliminata.
- `-k stream` (comando del README) verificato con `--collect-only`: seleziona le due prove dello
  streaming, eseguite prima con `-k agent_stream_with_a_tool` e `-k frontend`.
- Documenti: README (introduzione, pagina con lo streaming, test nel browser, prove reali,
  diagnosi «La bozza non compare…», conteggio dei test, che diceva ancora 927 dal punto 2),
  `CLAUDE.md` (struttura del front-end, comando `-k stream`), requisiti §18 (esiti).
- Problemi aperti: una sola esecuzione riuscita per CA-101 e CA-102 (dimostrano il comportamento con
  quella domanda); `reset` `review` mostrato solo con l'agente finto (il revisore reale ha approvato);
  interruzione del flusso (`stream_interrupted`) provata solo in Node, non con un back-end vero
  fermato a metà turno; streaming non provato con Compose (Docker invariato, specifica §10); pagina
  provata con Edge nelle prove reali e con Edge e Chrome nei test con l'agente finto.

## Revisione e integrazione di `auto-claude` (2026-11-15)

Specifica [`docs/superpowers/specs/2026-11-15-revisione-integrazione-design.md`](docs/superpowers/specs/2026-11-15-revisione-integrazione-design.md),
piano [`docs/superpowers/plans/2026-11-15-revisione-integrazione.md`](docs/superpowers/plans/2026-11-15-revisione-integrazione.md)
(approvati dall'utente il 2026-11-15; commit `3dc9feb`). Obiettivo dell'utente: pubblicare su
`main` in sicurezza, senza scadenze.

Decisioni dell'utente: approccio «revisione per step con controlli trasversali»; correzioni fatte da
Claude in sessione con il via libera dell'utente, niente loop; messaggi dei commit del loop lasciati
come sono; un problema grave si corregge sempre, uno importante si corregge o si accetta come
debito noto; revisione indipendente anche delle correzioni e problemi del codice già pubblicato
fuori dal criterio di uscita (scelte delegate a Claude).

### F1 · Revisione — fatto

- Quattro revisori con contesto pulito, in sola lettura: A (Step 4 e 5), B (Step 6), C (Step 7 e 9),
  D (Step 8 e streaming). Ognuno ha eseguito test senza modello sulla propria parte (317, 446, 217
  e 1003 passed).
- Verifica di Claude: gravi e importanti uno per uno (R-B1 riprodotto con
  `messages_to_json`/`messages_from_json` su tre casi; R-C1 con `docker port`), minori a campione.
  Gravità di R-B1 alzata da importante a grave (chat salvata inutilizzabile per sempre).
- Esito: **3 gravi** (R-C1 PostgreSQL di prova esposto sulla rete con password versionata, R-B1
  cronologie restituite e poi rifiutate, R-A1 evidenza «risposta adeguata» dello Step 5 non
  dimostrata), **4 importanti** (R-C2 avvio di Compose, R-A2 prove reali degli Step 4–5 non
  attraverso il servizio, R-A3 diagnosi delle preferenze nel README, R-D1 pagina chiusa durante lo
  streaming, da decidere), **29 minori** (10 da decidere). Nessun falso positivo. Dettagli nel
  rapporto.

### F2 · Prove reali — fatto

- Modello simulato: `pytest` 1003 passed; `BROWSER_CHANNEL=chrome`, `pytest -m browser` 25 passed.
- Modello vero (LM Studio, `google/gemma-4-e2b`; PostgreSQL in `assistente-postgres`):
  `pytest -m real -v` con Edge 64 passed, 1 skipped (atteso), 0 failed in 45:56; con Chrome
  `-k frontend` 2 passed in 2:36; streaming dalla pagina servita da Compose riuscito («391» con
  `calculate`, bozza in 3 stati, chat dopo il ricaricamento, log di `agent`).
- Avviso del revisore con il modello vero: tre tentativi, revisore sempre `coherent=true`;
  **non dimostrato con il modello vero** (coperto da CA-99 e CA-100 con il modello simulato).
- Nessuna prova instabile. Trovati nelle prove: R-B7 confermato (PowerShell 5.1 storpia «è»), R-P1
  (la pagina mostra markdown e LaTeX così come sono).
- Container `assistente-postgres` fermato a fine prove (`docker stop`); Compose spento.

### F3 · Rilettura guidata — fatto

Decisioni dell'utente, una per scheda:
1. **Ambito del router (`scope.txt`)**: tenere la riga dei riassunti della conversazione;
   **restringere** quella delle spiegazioni ai temi del laboratorio («spiegazioni dei concetti
   trattati nel laboratorio: modelli linguistici, agenti, strumenti, Model Context Protocol»), così
   `/prompt spiega` passa dal router per i temi del corso e l'ambito non diventa «qualsiasi domanda
   di informatica». Da fare in F4 con una prova reale del router (spiegazione di MCP accettata,
   domanda generica di informatica rifiutata).
2. **Testi dei prompt cambiati dal loop** (prompt di sistema dell'agente con le preferenze, stile
   `sintetico` «breve ed essenziale», stile `sintetico` del riassunto «con le richieste e i
   risultati ottenuti»): **tenuti** così (l'utente ha chiesto di proseguire senza obiezioni al
   consiglio). Limite noto: messi a punto su 4–8 chiamate con `gemma-4-e2b`.

Schede 3–5 presentate insieme e approvate dall'utente con «ok a tutto», tutte come consigliato:
3. **Dipendenze nuove** (`fastapi`, `uvicorn`, `httpx`, `SQLAlchemy`, `psycopg[binary]`,
   `playwright`, più le indirette `greenlet` e `annotated-doc`): **tenute**.
4. **`POSTGRES_PASSWORD` obbligatoria** per ogni comando `docker compose`: **tenuta** (un valore
   predefinito sarebbe una password nota nel file versionato).
5. **Bozza mostrata durante lo streaming**: **tenuta**; avviso del revisore nella bozza dimostrato
   solo con il modello simulato (limite noto).

Problemi del rapporto:
- Da correggere in F4: i gravi **R-C1, R-B1, R-A1**; gli importanti **R-C2** (healthcheck con
  `-h 127.0.0.1` e `restart: unless-stopped` per `backend`), **R-A2** (prove reali degli Step 4 e 5
  attraverso il servizio, insieme alla prova di R-A1), **R-A3** (diagnosi delle preferenze nel
  README); la scheda 1 (**R-A8**, ambito ristretto); i minori «da decidere» **R-B5** (tempo scaduto
  segnalato come «non raggiungibile»), **R-B10** (password ai container che non la usano),
  **R-A4** (`CLAUDE.md`: preferenze lette all'avvio del servizio).
- Accettati come debito noto (in `TODO.md` in F5, motivi nel rapporto §8): **R-D1** (specifica e
  README corretti in F4 per descrivere il comportamento vero), **R-A11**, **R-B6**, **R-C4**,
  **R-C10**, **R-D3**, **R-P1**.
- Gli altri 19 minori confermati: divisi nella specifica delle correzioni tra «correggere» e
  «debito noto», da approvare con la specifica.

### F4 · Correzioni — approcci approvati, specifica da scrivere

Approvati dall'utente il 2026-11-15 (la specifica si scrive in una sessione nuova):
- **R-B1, approccio A**: normalizzare all'uscita, nel nodo `llm`, le chiamate a strumento del
  modello (id non vuoto e unico per ogni chiamata, nome segnaposto per quelle senza nome, a cui lo
  strumento risponde «Strumento sconosciuto»); il controllo d'ingresso di `agent.py` resta severo.
  Test: ogni `history` di una risposta `200` rimandata al servizio è accettata, compresi nome
  vuoto o null, id vuoto o null e id ripetuti. Scartato l'approccio B (allargare il controllo
  d'ingresso): lascerebbe nella cronologia chiamate che LM Studio potrebbe rifiutare.
- **R-A1, approccio A, a tre gradini**: (1) controllo di merito in CA-58 (la risposta parla di
  server, client, strumenti o simili); (2) se il modello sbaglia, una sola modifica generale al
  testo di `spiega` (per esempio «se non conosci bene l'argomento dillo, invece di inventare»),
  niente suggerimenti su MCP; (3) se sbaglia ancora, evidenza registrata come **non soddisfatta per
  limite del modello**, test come fallimento atteso documentato. Scartato l'approccio B (solo
  registro, senza tentativi).
- **Minori da correggere**: R-B7 (`charset=utf-8` nelle risposte JSON di agente e back-end), R-C3
  (NUL rifiutato con errore chiaro, `hide_parameters=True`), R-C6 (connessione di `chat` con 10 s),
  R-A5 e R-D6 (messaggi d'errore), R-A6 (nome del prompt con escape nel log), R-A7 (limite di
  lunghezza agli argomenti dei prompt), R-A10 e R-C9 (documentazione).
- **Minori come debito noto** (in `TODO.md` in F5): R-A9, R-B2, R-B3, R-B4, R-B9, R-C5, R-C8, R-D2,
  R-D4, R-D5.

Specifica delle correzioni (con F5 e F6)
[`docs/superpowers/specs/2026-11-15-correzioni-auto-claude-design.md`](docs/superpowers/specs/2026-11-15-correzioni-auto-claude-design.md)
approvata dall'utente il 2026-11-15, con le scelte del progettista del §11. Piano
[`docs/superpowers/plans/2026-11-15-correzioni-auto-claude.md`](docs/superpowers/plans/2026-11-15-correzioni-auto-claude.md)
(Task 0–16) approvato dall'utente il 2026-11-15; esecuzione in una sessione nuova, consigliata in
sessione (superpowers:executing-plans) con il revisore indipendente del Task 13.

### F4 · Correzioni — esecuzione del piano (2026-11-15)

In sessione con superpowers:executing-plans, un task alla volta. «Modello simulato» = test senza
LM Studio; «modello vero» = LM Studio con `google/gemma-4-e2b`.

- **Task 0 · Ambiente — fatto.** `auto-claude`, albero pulito, ultimo commit `b60e6cc` (piano);
  Compose spento, porte 8000/8001/8080 libere; LM Studio avviato e `google/gemma-4-e2b` caricato
  (contesto 8192, elencato da `/v1/models`); `docker start assistente-postgres`; modello simulato:
  `pytest` 1003 passed, 90 deselected (68 s).
- **Task 1 · R-B1 — fatto.** `normalize_tool_calls` e `UNNAMED_TOOL` in `assistant/graph.py`,
  chiamata in `llm_node` con una riga WARNING `tool_call_normalized` per ogni chiamata cambiata.
  Modello simulato: i 15 test nuovi (grafo, servizio `/chat` e `/chat/stream` sui cinque casi,
  richiesta di `langchain-openai` con `_get_request_payload`) visti fallire (`ImportError`, poi
  `400 invalid_history` e un `500` nello streaming con nome null), poi verdi; `pytest` 1017 passed.
  Modello vero: `test_lm_studio_accepts_a_normalized_history` (prima risposta imposta con una
  chiamata senza nome e un id ripetuto) 1 passed in 111 s al primo tentativo: LM Studio accetta la
  cronologia normalizzata, «391», secondo turno con «400». L'origine delle chiamate malformate resta
  provata solo con il modello simulato.
- **Task 2 · R-A6 e R-A7 — fatto.** `kind=prompt name="…"` in JSON e troncato a 64 caratteri;
  `_check_prompt_size` in `assistant/api.py` (nome 64, 10 argomenti, nome di argomento 64, valore
  1000) prima di cronologia e `prompts/list`. Modello simulato: 11 test visti fallire (riga senza
  virgolette, `
` che spezza la riga, nome intero nel log, nessun limite); il test ai limiti esatti
  passava già (comportamento da conservare); poi tutti verdi, `pytest` 1028 passed. README
  allineato.
- **Task 3 · R-B5 e R-A5 — fatto.** `APITimeoutError` → `503 model_unavailable` con «LM Studio non
  ha risposto in tempo: …»; motivo tra parentesi di `PromptGetError` senza punto finale; la CLI
  scrive «Errore nel prompt: … Scrivi /prompts per l'elenco dei prompt.» per `prompt_unavailable`.
  Modello simulato: 7 test visti fallire, compreso `test_unusable_reason_loses_its_final_period`
  (aggiunto per il caso «non è utilizzabile», che con i motivi esistenti non aveva un punto finale;
  rosso rivisto con la correzione tolta), poi verdi; `pytest` 1030 passed. README allineato.
- **Task 4 · R-B7 — fatto.** `Utf8JsonMiddleware` (ASGI puro) in `assistant/api.py` e
  `backend/api.py`: `application/json` diventa `application/json; charset=utf-8`. Modello
  simulato: 20 test visti fallire (successi, errori `ApiError`, `422`, errori prima del flusso), poi
  verdi; i due test dei flussi (`text/event-stream`, CORS) passavano già e restano come guardia;
  `test_frontend_contract.py` verde senza rigenerare il contratto; `pytest` 1041 passed. La prova
  con `Invoke-RestMethod` di PowerShell 5.1 è nel Task 15.
- **Task 5 · R-C3 — fatto.** `ChatStore` rifiuta il carattere NUL nel titolo e nel messaggio
  (`InvalidInputError` → `400 invalid_request`, anche prima del flusso); `create_db_engine` con
  `hide_parameters=True` per SQLite e PostgreSQL. Modello simulato: 6 test visti fallire (SQLite
  accettava il NUL, `201` per il titolo, `500` per la domanda, motore senza `hide_parameters`), poi
  verdi; `test_postgresql_engine_has_a_connect_timeout`, che confronta le opzioni esatte del
  motore, aggiornato con `hide_parameters`; `pytest` 1047 passed. I test dell'archivio su
  PostgreSQL girano nel Task 11.
- **Task 6 · R-D6 — fatto.** `_agent_error` mette nel `502 agent_error` solo il detail
  dell'agente e il suo codice nella riga di log (`cause="model_unavailable"`); la pagina scrive
  «L'assistente non è riuscito a rispondere (…). La domanda è salvata nella chat: riprova.», senza
  parentesi con un detail vuoto. Modello simulato: 6 test del back-end e i test Node visti fallire,
  poi verdi; `pytest` 1047 passed; browser vero con modello simulato: `pytest -m browser` con Edge
  25 passed. README allineato.
- **Task 7 · R-C6 — fatto.** `CONNECT_TIMEOUT` (10 s) al posto di `STREAM_CONNECT_TIMEOUT`, usato
  da `_request` e da `chat_stream`. Modello simulato: `test_timeouts` visto fallire (`ImportError`;
  controllo diretto del comportamento: `chat` aveva `connect=600.0`), poi verde (`connect=10.0`,
  il resto 600); `pytest` 1047 passed.
- **Task 8 · R-A3 — fatto.** `server_command` senza valore predefinito per il file delle
  preferenze (import non più usato tolto); le chiamate a due argomenti dei test passano
  `DEFAULT_PREFERENCES_FILE`. Modello simulato: `test_server_command_needs_the_preferences_file`
  visto fallire (`DID NOT RAISE TypeError`), poi verde; `pytest` 1047 passed. Prova senza modello
  dello snippet nuovo del README da PowerShell: con `PREFERENCES_FILE` su un file della scratchpad
  stampa `{"language": "italiano", "timezone": "America/New_York", "style": "sintetico"}`, senza la
  variabile il file del pacchetto (`Europe/Rome`).
- **Task 9 · R-A8 — non corretto: debito noto (decisione dell'utente del 2026-11-16).** Provata la
  riga nuova di `scope.txt` («spiegazioni dei concetti trattati nel laboratorio: modelli
  linguistici, agenti, strumenti, Model Context Protocol»). Modello simulato: il test della riga
  visto fallire e poi verde, `pytest` 1047 passed. Modello vero: `pytest tests/test_real.py -m real
  -v -k "lab_topics or router"` → 3 passed (prove del router esistenti) e 1 failed in 364 s;
  ripetizione `-k lab_topics` → failed in 192 s. In entrambe la spiegazione del MCP è
  `category=conversation` (giusto), ma anche «Spiegami la differenza tra memoria RAM e disco rigido»
  è `category=conversation` («spiegazione di un concetto tecnico che rientra nella capacità
  esplicativa dell'assistente»). Causa probabile: `ROUTER_PROMPT` chiede di giudicare la richiesta
  e non l'argomento, e di scegliere `conversation` nel dubbio. Come da specifica §5.3, fermato e
  chiesto all'utente, che ha scelto di **tornare alla riga vecchia** (ambito largo
  «informatica, programmazione e intelligenza artificiale») e di registrare R-A8 come debito noto
  in `TODO.md` (F5). Annullati `scope.txt`, il test della riga, la prova reale nuova, RF-51 e README:
  nessun cambio al codice. Il Task 10 usa l'ambito di prima, che comprende già le spiegazioni del
  MCP.
- **Task 10 · R-A2 e R-A1 — fatto, R-A1 al gradino 3.** In `tests/test_real.py` CA-50 e CA-58
  passano dal servizio: `test_default_timezone_from_preferences_in_the_service` (`PREFERENCES_FILE`
  con `America/New_York`, `POST /chat`) e `test_explain_prompt_from_the_cli` (CLI con `AGENT_URL`,
  controllo di merito `MERIT`: server, client, tool, strumenti esterni, fonti di dati, dati esterni);
  le versioni in processo sono state sostituite. Modello vero:
  - gradino 1: CA-50 **passed** al primo tentativo (in 234 s insieme a CA-58); CA-58 **failed** due
    volte (147 s), stessa risposta: il MCP è «il set di regole o il "protocollo" che stabilisce come
    tu gli dai queste informazioni di sfondo (il contesto)», con un esempio sulle piante. Letta:
    **sbagliata nel merito** (nessun server, client, strumento o dato esterno);
  - gradino 2: test del testo di `spiega` aggiornati e visti fallire (4), frase «Se non conosci bene
    l'argomento, dillo invece di inventare.» aggiunta (`beb25e5`), `pytest` 1047 passed; CA-58
    **failed** due volte (147 e 145 s), stessa spiegazione sbagliata («il sistema che organizza
    tutte le informazioni rilevanti…»);
  - gradino 3: frase tolta con un revert (`1f39857`, messaggio riscritto in Conventional Commits);
    `xfail(strict=False)` con il motivo «limite del modello»; con il modello vero `1 xfailed` in
    147 s. CA-58 registrata come **non soddisfatta per limite del modello** in `requisiti.md`, nel
    rapporto (§6) e nel README («Prompt MCP»); CA-50 in `requisiti.md` e nel rapporto dal servizio.
  Modello simulato: `pytest` 1047 passed dopo il revert.
- **Task 11 · R-C1, R-C2, R-B10 — fatto.** README: `docker run … -p 127.0.0.1:5433:5432` e la frase
  sulla password di prova; `compose.yaml`: healthcheck `pg_isready -h 127.0.0.1 …`, `restart:
  unless-stopped` per `backend`, `POSTGRES_PASSWORD: ""` in `agent` e `assistant`; nota accanto al
  comando storico del diario (Step 7, punto 5). Modello simulato: 3 test di `test_docker.py` visti
  fallire (README, healthcheck e `restart`, password nell'agente e nella CLI);
  `test_every_published_port_is_on_localhost` passava già (Compose pubblicava già solo su
  `127.0.0.1`) e resta come guardia; poi 43 passed, `pytest` 1051 passed. Docker vero:
  `docker rm -f assistente-postgres` (solo chat di prova), nuovo `docker run` del README,
  `pg_isready` «accepting connections», `docker port assistente-postgres` → solo
  `5432/tcp -> 127.0.0.1:5433`. PostgreSQL vero: `pytest tests/test_backend_store.py -m real` →
  39 passed, 1 skipped (`PRAGMA`), compresi i test del NUL del Task 5.
- **Task 12 · R-D1, R-A4, R-A10, R-C9 — fatto (solo documentazione).**
  - R-D1, osservazione con uno script nella scratchpad (back-end vero `create_app` su SQLite in
    memoria servito da uvicorn in un thread, agente finto con pause, client httpx che chiude il
    flusso dopo `question` e `text`):
    1. chiusura durante una pausa di 5 s, poi altro testo e `done`: `outcome=client_gone` dopo
       circa 9 s, alla scrittura dell'evento successivo; risposta **non** salvata (solo la domanda);
    2. chiusura mentre arrivano eventi ogni 0,2 s: `outcome=client_gone`, risposta non salvata;
    3. chiusura durante una pausa di 20 s seguita subito da `done`: `outcome=done` a 20 s, risposta
       **salvata** (il `ping` dei 15 s non si è accorto della chiusura).
    Specifica dello streaming (§1 e righe di log), README (diagnosi dello streaming) e RF-84
    descrivono ora questo comportamento, con «comportamento corretto il 2026-11-15, debito R-D1».
  - R-A4: `CLAUDE.md` (Obiettivo, Step 4), RF-41 e l'introduzione del README: preferenze lette
    all'avvio del servizio dell'agente, una modifica vale dal riavvio (la sezione delle preferenze
    del README lo diceva già).
  - R-A10: README, sezione del front-end: `/prompts` e `/prompt` esistono solo nella CLI.
  - R-C9: `CLAUDE.md`, prove reali del back-end con `.\.venv\Scripts\python.exe -m pytest …`.

## Storico (ex `docs/superpowers/handoff.md`, fino al 2026-11-13)

Data: 2026-11-13
Stato: **lezione 6, Step 1 (router), Step 2 (revisore) e Step 3 (riassunto): implementati e
verificati e pubblicati.**
Il 2026-11-13 `origin/dev` e `origin/main` sono stati portati a `f53b67a` (Step 2) e poi, con lo
Step 3, al commit che contiene questa riga (avanzamento rapido).
Step 3: specifica [`specs/2026-11-13-riassunto-design.md`](docs/superpowers/specs/2026-11-13-riassunto-design.md),
piano [`plans/2026-11-13-riassunto.md`](docs/superpowers/plans/2026-11-13-riassunto.md), requisiti §11 (RF-34…RF-38,
CA-38…CA-45). Step 2: specifica [`specs/2026-11-11-revisore-design.md`](docs/superpowers/specs/2026-11-11-revisore-design.md),
piano [`plans/2026-11-11-revisore.md`](docs/superpowers/plans/2026-11-11-revisore.md), requisiti §10 (RF-28…RF-33,
CA-30…CA-37). Step 1: specifica
[`specs/2026-11-11-router-design.md`](docs/superpowers/specs/2026-11-11-router-design.md), piano
[`plans/2026-11-11-router.md`](docs/superpowers/plans/2026-11-11-router.md), requisiti §9 (RF-23…RF-27,
CA-23…CA-29). Il push si fa solo su richiesta dell'utente (regola in `CLAUDE.md`, sezione «Git»).
La lezione 5 resta come descritta più sotto.

**Branch di lavoro dal 2026-11-11: `dev`.** I commit si fanno su `dev`; il push va prima su
`origin/dev`, poi `main` si porta allo stesso commit con avanzamento rapido
(`git push origin dev:main`).

**Struttura cambiata il 2026-11-09.** Il progetto è nella radice della repository (prima in
`assistente-laboratorio/`); `lezione3/` è solo locale, esclusa da Git. `compose.yaml` fissa
`name: assistente-laboratorio`. I documenti precedenti citano ancora `assistente-laboratorio/`: sono
storici e non sono stati riscritti.

### Lezione 6 — prossimo passo (2026-11-13)

**Step 3 · Riassunto della cronologia: fatto** (sezione seguente). Prossimo: Step 4 · Resource
`utente://preferenze` (traccia in [`lezione6.md`](docs/superpowers/lezione6.md)), da avviare con un nuovo
brainstorming. I commit dello Step 3 sono pubblicati su `origin/dev` e `origin/main`.

### Lezione 6, Step 3 — riassunto (2026-11-13)

All'inizio di ogni turno il nodo `summary` (prima del router) conta i messaggi della cronologia,
domanda appena arrivata compresa. Fino a `SUMMARY_MAX_MESSAGES` (default 20) non chiama il modello
(`skipped=below_threshold`). Oltre, `cut_index` conserva almeno gli ultimi
`SUMMARY_KEEP_MESSAGES` (default 6) e arretra fino alla domanda che apre il turno; se arriva a 0,
`skipped=nothing_to_compress`. Altrimenti lo stesso modello, senza strumenti, riceve il riassunto
precedente e la trascrizione «Utente: … / Assistente: …» dei messaggi tolti (filtrati con
`router_messages`); il testo **sostituisce** il campo `summary` e i messaggi vecchi escono con
`RemoveMessage` (log `messages_before=… messages_after=… removed=…`). Riassunto vuoto → WARNING
`fallback=empty_summary`, nulla compresso. Agente, router e revisore ricevono il riassunto in fondo
al loro prompt di sistema (`with_summary`); `Session` lo conserva tra i turni e non cambia nulla se
il turno fallisce. Riga di avvio: `scope_file=… max_reviews=… summary_max_messages=…
summary_keep_messages=…`.

Commit: `32bdf67` (specifica e requisiti), `8d5796a` (piano), `c09ec34` (Task 1, soglie),
`f85242e` (Task 2, `summary.py`), `01062db` (Task 3, modello), `bf84c55` (Task 4: grafo, sessione,
avvio, `conftest.py`, fixture reale), `b85f9d9` (router con il riassunto), `4277c9e` (revisore con
il riassunto e frase in `REVIEWER_PROMPT`), `bde496a` (Task 5, prova reale), poi la
documentazione (Task 6).

#### Verifiche (2026-11-13)

Prove reali con LM Studio, `google/gemma-4-e2b`, contesto 8192, soglie non impostate (20 e 6) salvo
dove indicato.

| CA | Comando | Esito |
|----|---------|-------|
| CA-38 | `pytest tests/test_config.py` | ✅ default 20 e 6; `abc`, `0`, `-1`, `2.5` rifiutati per entrambe; `keep ≥ max` rifiutato anche con un default; tutti nel messaggio unico |
| CA-39 | `pytest tests/test_graph.py tests/test_main.py` | ✅ con `n = max` nessuna chiamata e `messages=5/5 skipped=below_threshold`; con `n = max + 1` una chiamata; da `main`: `messages=1/20 skipped=below_threshold` |
| CA-40 | `pytest tests/test_graph.py tests/test_session.py` | ✅ `messages_before=7 messages_after=5 removed=2`, chi riassume riceve esattamente `summary_input("", messages[:2])`, `summary` sostituito; al quarto turno chi riassume riceve il riassunto del terzo; agente, router e revisore lo ricevono |
| CA-41 | `pytest tests/test_summary.py tests/test_graph.py` | ✅ taglio su tool_call, `ToolMessage`, bozza, indicazione e risposta → arretra alla domanda; turno unico → `skipped=nothing_to_compress`, nessuna chiamata |
| CA-42 | `pytest tests/test_graph.py tests/test_session.py` | ✅ riassunto `""` e di soli spazi → WARNING `fallback=empty_summary`; `APIConnectionError` di chi riassume, e dell'agente dopo una compressione → cronologia e riassunto invariati |
| — | `pytest` | ✅ 297 passed, 15 deselected |
| CA-43 | `pytest -m real -v -k survives_compression` (soglie 4 e 2 nel test) | prime 4 esecuzioni ❌ (vedi «Decisioni prese durante l'esecuzione»); dopo le due modifiche ✅ 1 passed in 270 s |
| CA-43, CA-44 | `pytest -m real -v -o log_cli=true --log-cli-level=INFO` | ✅ 15 passed in 1756 s (29 min). CA-43: `messages_before=11 messages_after=9 removed=2`, risposta con «Paolo» dopo una riscrittura chiesta dal revisore. Nelle altre prove solo `skipped=below_threshold` |
| CA-45 | `"Mi chiamo Paolo", "Che ore sono a Tokyo?", "Come mi chiamo?", "esci"` in pipe verso `python -m assistant` con `SUMMARY_MAX_MESSAGES=4`, `SUMMARY_KEEP_MESSAGES=2` e `NOTES_DB` temporaneo | ✅ `summary_max_messages=4 summary_keep_messages=2`, due `skipped=below_threshold`, poi `messages_before=11 messages_after=9 removed=2`, router `conversation`, revisore `coherent=true`, «Ti chiami Paolo.», exit 0 |
| CA-45 | la stessa pipe verso `docker compose run --rm -T -e SUMMARY_MAX_MESSAGES=4 -e SUMMARY_KEEP_MESSAGES=2 assistant` (dopo `docker compose build`) | ✅ stesse righe, `scope_file=/app/assistant/data/scope.txt`, «Ti chiami Paolo.», exit 0 |

Limite: dopo le modifiche, una sola esecuzione della suite reale e una prova da terminale per
ambiente. Dimostrano il comportamento con quelle domande, non che il modello riassuma e giudichi
sempre così. Con il modello reale non si sono visti `nothing_to_compress` né `empty_summary`:
sono verificati solo con il modello simulato.

#### Decisioni prese durante l'esecuzione

- **Worktree:** nessuno (`CLAUDE.md`); lavoro direttamente su `dev`. LM Studio e Docker Desktop
  avviati durante la sessione.
- **Lettura delle soglie** con un aiuto locale `read_positive` in `config.py` (stessa logica e
  stessi messaggi di `MAX_STEPS`, che non è stato toccato).
- **Selettore di un test del router:** `test_router_reason_is_logged_on_one_line` sceglieva la
  prima riga che contiene `node=router`, e ora anche la riga del riassunto contiene
  `next_node=router`; il test usa `startswith("node=router")`.
- **CA-43 fallita, router (decisione dell'utente).** La compressione e il riassunto («L'utente si
  è presentato come Paolo.») erano corretti, ma il router, senza riassunto, rifiutava «Come mi
  chiamo?» («informazioni personali»). Una frase in `ROUTER_PROMPT` non è bastata (3 rifiuti su
  4). Prova diretta, 4 chiamate per variante: senza riassunto `out_of_scope` 4/4, con il riassunto
  `conversation` 4/4. Ora il router riceve il riassunto; la frase è stata tolta. Specifica §16,
  RF-36.
- **CA-43 fallita, revisore (decisione dell'utente).** Con il router corretto, il revisore (solo
  domanda e risposta) bocciava «Ti chiami Paolo.» («l'utente non ha fornito il proprio nome») e
  l'agente riscriveva «Non mi hai fornito il tuo nome.». Prova diretta: revisore attuale 0/4,
  frase nel prompt 3/4, riassunto 4/4, entrambi 4/4. Ora il revisore riceve il riassunto e
  `REVIEWER_PROMPT` non giudica i dati «da strumenti o dalla conversazione precedente».
- Le prove dirette sono script usa e getta nella scratchpad, non nel progetto.

#### Revisione indipendente finale (2026-11-13)

Un revisore con contesto pulito ha esaminato `8d5796a..4e511f1`. Esito: «Ready to merge: Yes»,
nessun problema critico o importante; i cinque punti della Review Focus hanno test dedicati;
`pytest` rieseguito dal revisore: 297 passed.

Rimandati (minori):
- la docstring di `reviewer.py` dice ancora che il revisore vede solo domanda e risposta, e quella
  di `with_summary` parla solo del prompt dell'agente;
- `reviewer_node` scompone il `SystemMessage` di `review_messages` per aggiungere il riassunto (un
  parametro `summary` di `review_messages` sarebbe più diretto);
- `REVIEWER_PROMPT` dice «conversazione precedente, che tu non vedi» anche quando il revisore
  riceve il riassunto (formulazione validata 4/4 nella prova diretta);
- `test_threshold_boundary` non controlla la riga `messages_before` nel caso con compressione
  (la copre `test_compression_over_the_threshold`).

Messi da parte dal revisore, con la decisione presa: il riassunto sta nel prompt di sistema senza
la cornice «dati, non istruzioni» (app locale a un solo utente, specifica §1); nessun messaggio a
terminale durante la chiamata di riassunto (circa 20 s, visibile nei log); soglia in messaggi,
turno unico mai compresso, nessun limite rigido alla lunghezza del riassunto, dati solo negli
strumenti persi (specifica §1, §5, §14, §15); CA-43 che può fallire senza difetto se la risposta
del secondo turno usa il nome (specifica §11); falsi rifiuti «timestamp futuro» del revisore dello
Step 2 (fuori traccia).

#### Punti aperti (Step 3)

- **Revisore senza compressione:** in CA-4 (nome e domanda in due turni, nessun riassunto) il
  revisore ha bocciato due volte la risposta con il nome (`review_limit_reached`); la prova è
  passata perché anche l'ultima risposta conteneva «Paolo». La frase nel prompt riduce il problema
  (3/4 nella prova diretta), non lo elimina.
- **Falsi rifiuti sull'ora di Tokyo** («timestamp futuro», quando a Tokyo è già il giorno dopo):
  3 nella suite reale e 1 per prova da terminale; la riscrittura viene poi approvata. È del
  revisore dello Step 2, fuori dalla traccia dello Step 3: non toccato.
- **Durata delle prove reali:** 15 prove in circa 29 minuti; la CA-43 da sola 3–5 minuti.
- Dati presenti solo nei risultati degli strumenti e non ripetuti nella risposta non entrano nel
  riassunto (rischio accettato, specifica §14).

**Decisione dell'utente (2026-11-13): si fa solo ciò che chiede la traccia di `LLM_Lez_6.pdf`.**
Non si fanno i punti che stanno fuori dalla traccia: le correzioni minori rimandate degli Step 1 e
2, le prove manuali mai ripetute delle lezioni precedenti (CA-5, Ctrl+Z), i minori aperti della
lezione 5 e la prova mirata di una riscrittura dopo `add_note`. Restano annotati più sotto solo
come memoria. Traccia completa: [`lezione6.md`](docs/superpowers/lezione6.md); lo schema del grafo dei tre
step è la slide 3 di `LLM_Lez_6.pdf` (non tracciato). In questa macchina manca `pdftoppm`: le slide
si leggono come immagini con PyMuPDF installato nella scratchpad (`pip install --target`), non nel
progetto.

### Lezione 6, Step 2 — revisore (2026-11-13)

Dopo la risposta finale dell'agente (nessuna tool_call) il nodo `reviewer` (stesso modello, prompt
`REVIEWER_PROMPT`, nessuno strumento, output `json_schema` con `reason` e `coherent`) riceve solo
la domanda dell'utente e la risposta proposta. Coerente → END. Non coerente e `reviews <
MAX_REVIEWS` → l'indicazione `HumanMessage(name="reviewer")` con il motivo entra nella cronologia e
il turno torna a `llm`. Non coerente al limite → END con l'ultima risposta e WARNING
`review_limit_reached`. Output non valido o `None` → risposta approvata con WARNING
`fallback=invalid_output`. Rifiuto del router e avviso di `limit` non sono rivisti; il revisore non
consuma `MAX_STEPS`, che non si azzera. `router_messages` scarta indicazioni e bozze rifiutate.
`MAX_REVIEWS` (default 2) in `config.py` e `.env.example`; all'avvio il log scrive
`scope_file=… max_reviews=…`.

Commit: `8498085` (piano), `51e9216` (Task 1, `MAX_REVIEWS`), `5e46842` (Task 2, `reviewer.py` e
`router_messages`), `1506282` (Task 3, `guard_structured_output` e `create_reviewer_model`),
`0f54a2d` (Task 4: grafo, sessione, avvio, `conftest.py` e fixture reale in un solo commit),
`6dfd2b9` (Task 5, prove reali), poi la documentazione (Task 6).

#### Verifiche (2026-11-13)

Prove reali con LM Studio, `google/gemma-4-e2b`, contesto 8192, `MAX_REVIEWS` non impostata (2).

| CA | Comando | Esito |
|----|---------|-------|
| CA-30 | `pytest tests/test_config.py tests/test_graph.py` | ✅ default 2; `abc`, `0`, `-1`, `2.5` rifiutati nel messaggio unico; il revisore riceve esattamente `review_messages(domanda, risposta)` dopo un ciclo di strumenti e alla seconda revisione |
| CA-31 | `pytest tests/test_graph.py` | ✅ una chiamata all'agente e una al revisore; `review=1/2 coherent=true reason="test" next_node=end`; nessuna indicazione |
| CA-32 | `pytest tests/test_graph.py` | ✅ bozza parziale → `coherent=false … next_node=llm`, indicazione all'agente, risposta completa → `review=2/2 coherent=true` |
| CA-33 | `pytest tests/test_graph.py` (`max_reviews` 1, 2, 3) | ✅ agente e revisore chiamati `max_reviews` volte, `max_reviews - 1` indicazioni, ultima bozza restituita, WARNING `review_limit_reached` |
| CA-34 | `pytest tests/test_graph.py tests/test_session.py` | ✅ `ReviewerOutputError` e `None` → `fallback=invalid_output … coherent=true`; `APIConnectionError` del revisore → cronologia invariata |
| CA-35 | `pytest tests/test_graph.py` | ✅ rifiuto e avviso di `limit` non rivisti; `steps` invariato dal revisore; limite dei passaggi durante una riscrittura → `limit` |
| — | `pytest` | ✅ 247 passed, 14 deselected; dopo la correzione della revisione finale 249 passed, 14 deselected |
| — | LM Studio non raggiungibile (`LMSTUDIO_BASE_URL=http://localhost:9/v1`) | ✅ `scope_file=… max_reviews=2`, «Errore: LM Studio non ha risposto correttamente (Connection error.). Riprova.», «Arrivederci!», exit 0 |
| CA-36 | `pytest -m real -v -k imposed_partial` (prima risposta dell'agente **imposta**) | ✅ 1 passed in 263 s: `review=1/2 coherent=false reason="La risposta proposta ignora la richiesta di calcolare 17 * 23…"`, poi l'agente reale chiama `get_current_time` e `calculate`, `review=2/2 coherent=true`; risposta con «391». Il campo `name` del messaggio utente è accettato da LM Studio |
| CA-36, CA-37 | `pytest -m real -v` | ✅ 14 passed in 1940 s (32 min). 17 righe `node=reviewer`: 16 `coherent=true` al primo passaggio, l'unico `coherent=false` è quello sulla risposta imposta. Nessun falso rifiuto; CA-17 con una sola `add_note` |
| CA-37 | `"Che ore sono a Tokyo e quanto fa 17 * 23?", "esci"` in pipe verso `python -m assistant` e verso `docker compose run --rm -T assistant` (dopo `docker compose build`) | ✅ in locale e in Docker: `get_current_time` e `calculate` nello stesso passaggio, `review=1/2 coherent=true`, risposta con l'ora e 391, exit 0; in Docker `scope_file=/app/assistant/data/scope.txt max_reviews=2` |

Limite: una sola esecuzione delle prove reali. Dimostra il comportamento con quelle domande, non che
il revisore giudichi sempre così. Con il modello reale non si sono visti né il limite delle
revisioni né il ripiego: sono verificati solo con il revisore simulato.

#### Decisioni prese durante l'esecuzione

- **Worktree:** nessuno, come chiede `CLAUDE.md`; lavoro direttamente su `dev`.
- **Prove rapide da terminale con `NOTES_DB` in una cartella temporanea**, per non toccare `data/`
  del repository.
- **LM Studio e Docker Desktop** sono stati avviati durante la sessione (`lms server start`,
  `lms load google/gemma-4-e2b --context-length 8192 -y`, Docker Desktop dal menu Start).

#### Revisione indipendente finale (2026-11-13)

Un revisore con contesto pulito ha esaminato `595c59a..e518505`. Esito: «With fixes», nessun
problema critico; i cinque punti della Review Focus hanno test precisi.

Corretto (problema importante, lacuna della specifica e del piano, non dell'esecuzione), con test
che prima fallivano: una risposta rifiutata all'ultimo passaggio rimandava il turno all'agente
oltre `MAX_STEPS` (con `MAX_STEPS=1` il log mostrava `step=2/1 node=llm`; nel caso peggiore
`max_steps + max_reviews - 1` chiamate), contro RF-31. Ora `route_after_reviewer(state,
max_reviews, max_steps)` chiude il turno anche quando `steps ≥ max_steps`, con WARNING
`step_limit_reached` e l'ultima risposta (`test_rejection_at_the_last_step_ends_the_turn`,
`test_rewrite_never_exceeds_max_steps`, nuovo caso di `test_route_after_reviewer_cases`).
Specifica §8, RF-31 e README allineati. Le prove reali non sono state ripetute: il percorso
corretto non compare in nessuna di esse (nessun rifiuto all'ultimo passaggio).

Rimandati (minori):
- `graph.py`, nodo `reviewer`: `state["reviews"]` dà `KeyError` se il grafo è invocato senza
  `reviews` (solo `Session` lo invoca e lo passa sempre; `steps` segue lo stesso schema);
- `tests/test_main.py`: l'import di `langchain_core.messages` sta dopo quelli di `assistant.*`;
- `CLAUDE.md`, riga sui finti di `conftest.py`: più lunga delle altre.

Messi da parte dal revisore, con la decisione presa: falsi rifiuti su domande brevi di
continuazione (rischio accettato dalla specifica §14, documentato nel README); contesto occupato da
bozze e indicazioni (Step 3); possibili azioni ripetute in una riscrittura dopo `add_note` (affidate
al testo dell'indicazione; mai osservate, perché nessuna prova reale ha prodotto un rifiuto dopo uno
strumento con effetti: da controllare in una prova futura); `error="None"` nel ripiego (come da
specifica); esattezza dei dati non giudicata (RF-28); eccezioni diverse da quelle previste che
arrivano al terminale (come per il router).

#### Punti aperti (Step 2)

- **Durata delle prove reali:** da circa 10 a circa 32 minuti (ogni turno ha almeno una chiamata in
  più; la prova con la risposta imposta da sola dura circa 4 minuti).
- **Risposte con LaTeX:** l'agente scrive `$17 \times 23$` (visto in locale e in Docker); il
  terminale lo mostra così com'è. Non riguarda il revisore, non toccato.
- **Contesto:** bozze e indicazioni restano nella cronologia e occupano contesto (8192 token);
  il riassunto è lo Step 3.
- Con il modello reale non sono stati osservati il limite delle revisioni, il ripiego e i falsi
  rifiuti su domande brevi di continuazione («E a Roma?» è stata approvata).

### Lezione 6, Step 1 — router (2026-11-11)

Prima dell'agente il nodo `router` (stesso modello, prompt diverso, nessuno strumento, output
`json_schema` con `category` e `reason`) classifica l'ultimo messaggio leggendo l'ambito di
`assistant/data/scope.txt` (o `SCOPE_FILE`) e la cronologia senza tool_call né `ToolMessage`.
`conversation` → `llm` come prima; `out_of_scope` → `refusal` → END, con il testo «Mi dispiace,
questa domanda è fuori dal mio ambito: <motivo>. Chiedimi pure che cosa so fare.». Output non
valido → WARNING `fallback=invalid_output` e il turno va all'agente. Il router non consuma
`MAX_STEPS`.

Commit: `69ff4cc` (Task 1, ambito), `0c6c070` (Task 2, `router.py`), `5d5bf61` (Task 3 e 4
insieme: grafo, modello del router, avvio), `c8f0eb4` (Task 5, prove reali e ritocco dei testi),
poi la documentazione (Task 6).

#### Verifiche (2026-11-11)

| CA | Comando | Esito |
|----|---------|-------|
| CA-23 | `pytest tests/test_config.py tests/test_main.py` | ✅ ambito predefinito, `SCOPE_FILE`, file mancante, cartella, file vuoto, BOM; exit 1 all'avvio |
| CA-24, CA-25 | `pytest tests/test_graph.py` | ✅ in ambito: log con categoria, motivo, `next_node=llm`; fuori ambito: rifiuto con motivo, `model.calls == []`, nessun `node=llm` |
| CA-26 | `pytest tests/test_graph.py tests/test_session.py tests/test_model.py` | ✅ ripiego su errore di output e su `None`; `APIConnectionError` del router → cronologia invariata |
| — | `pytest` | ✅ 201 passed, 12 deselected |
| CA-27, CA-28 | `pytest -m real -v` (LM Studio, `google/gemma-4-e2b`, contesto 8192) | prima esecuzione 9 passed, 3 failed (falsi rifiuti, vedi sotto); dopo il ritocco dei testi ✅ 12 passed in 601 s |
| CA-29 | `"Che ore sono a Tokyo?", "Chi ha vinto i Mondiali del 2006?", "esci"` in pipe verso `python -m assistant` e verso `docker compose run --rm -T assistant` (dopo `docker compose build`) | ✅ in locale e in Docker: `category=conversation … next_node=llm` e `get_current_time`; poi `category=out_of_scope … next_node=refusal`, `node=refusal`, nessun `node=llm`; in Docker `scope_file=/app/assistant/data/scope.txt` |
| — | LM Studio non raggiungibile (`LMSTUDIO_BASE_URL=http://localhost:9/v1`) | ✅ «Errore: LM Studio non ha risposto correttamente (Connection error.). Riprova.», poi «Arrivederci!», exit 0 |

Limite: una sola esecuzione delle prove reali dopo il ritocco. Dimostra il comportamento con
quelle domande, non che il router classifichi sempre così.

#### Decisioni prese durante l'esecuzione

- **Falsi rifiuti alla prima prova reale** («Mi chiamo Paolo», «Come mi chiamo?», «Ci sono corsi
  di astrologia?», «Ricordami di comprare il latte»): il modello giudicava l'argomento delle
  parole. Con l'accordo dell'utente sono cambiati solo i testi: `scope.txt` descrive le richieste
  (promemoria su qualsiasi argomento, ricerca di corsi su qualsiasi argomento, l'utente che si
  presenta) e `ROUTER_PROMPT` dice di giudicare la richiesta e, nel dubbio, scegliere
  `conversation`. Specifica §4–§5 allineata. Costo: più domande di confine arrivano all'agente.
- **Task 3 e 4 in un solo commit:** a fine Task 3 `__main__.py` chiamava ancora `build_graph` senza
  router (4 test di `test_main` rossi); per non lasciare un commit con la suite rossa i due task
  sono stati registrati insieme.
- **Eccezioni di output del router** (decisione rimandata dalla specifica al piano): `model.py`
  converte `ValueError` (anche `pydantic.ValidationError`), `OpenAIRefusalError`,
  `openai.LengthFinishReasonError` e `openai.ContentFilterFinishReasonError` in
  `RouterOutputError`; `openai.APIError` passa fino al terminale.

#### Revisione indipendente finale (2026-11-11)

Un revisore con contesto pulito ha esaminato `2b13342..7fa0149`. Esito: «Ready to merge: Yes»,
nessun problema critico o importante. Due punti segnalati come minori sono stati rivalutati come
importanti per il loro effetto e corretti, ciascuno con un test che prima falliva:
- la prova reale `test_router_in_scope_reaches_the_agent` controllava `"node=llm"`, che compare
  anche nella riga del router (`next_node=llm`): ora cerca `step=N/M node=llm` (rieseguita: le due
  prove reali del router passano, 72 s);
- `router_messages` scartava le risposte vuote dell'agente: il router avrebbe ricevuto due
  messaggi utente di seguito, che alcuni template di chat rifiutano (ogni turno successivo
  sarebbe fallito). Ora tiene le risposte senza tool_call anche se vuote
  (`test_router_messages_keep_alternation_after_an_empty_answer`); specifica §5 allineata.

Rimandati (minori):
- il rifiuto si legge «…fuori dal mio ambito: La richiesta…» (motivo con la maiuscola);
- il WARNING di ripiego per un risultato `None` scrive `error="None"`, poco informativo;
- `INVALID_OUTPUT_ERRORS` comprende tutto `ValueError`: anche un errore diverso dall'output
  diventerebbe un ripiego (visibile nei log); il testo dell'errore del parser è lungo;
- `SCOPE_FILE` nel `.env` vale solo per Docker e deve indicare un percorso dentro l'immagine
  (relativo a `/app`): il README non lo dice;
- `test_create_router_model_needs_no_server` non verifica `json_schema` né l'assenza di
  strumenti; manca un test per `scope.txt` non UTF-8 (il codice lo gestisce).

#### Punti aperti (Step 1)

- Il motivo del router comincia spesso con la maiuscola, quindi il rifiuto si legge «…fuori dal
  mio ambito: La richiesta…». Solo estetica, non toccata.
- Nei log rediretti su file in Windows le lettere accentate possono uscire in cp1252 (già noto
  dalla lezione 5).

### Riprendere da qui (stato della lezione 5)

**`.env` aggiornato (2026-11-09).** L'utente ha cambiato i nomi delle variabili:
`LMSTUDIO_MODELLO` → `LMSTUDIO_MODEL` e `MAX_PASSI` → `MAX_STEPS`.
- Verifica: senza `-e`,
  `"Che ore sono a Tokyo?", "esci" | docker compose run --rm -T assistant` chiama
  `get_current_time` con `Asia/Tokyo` ed esce con codice 0.
- Le prove Docker fatte prima dell'aggiornamento passavano `-e LMSTUDIO_MODEL=…`.
- Un `.env` creato prima della lezione 5 va aggiornato allo stesso modo (vedi README).

Leggere prima, in quest'ordine:
1. `CLAUDE.md`: regole del progetto, struttura e comandi aggiornati.
2. [`specs/2026-11-09-strumenti-mcp-design.md`](docs/superpowers/specs/2026-11-09-strumenti-mcp-design.md): il
   **come** della lezione 5.
3. Questo file, sezioni «Decisioni prese durante l'esecuzione» e «Punti aperti».

Da sapere:
- **In Git Bash `python` apre il REPL di Windows** e blocca il comando. Usare sempre
  `.venv/Scripts/python.exe` (o `py -3.13`).
- **`LLM_Lez_5.pdf`** e **`LLM_Lez_6.pdf`** non sono tracciati: non aggiungerli a Git senza
  chiedere.
- Suite predefinita: `pytest` → `297 passed, 15 deselected` (Step 3 della lezione 6), in circa 20–50 s. I test MCP avviano il
  server come sottoprocesso, circa 1 s ciascuno.

### Che cosa c'è oggi (lezione 5)

È un'applicazione Python da terminale. Conversa con `google/gemma-4-e2b`, servito da LM Studio
sull'host, attraverso un grafo LangGraph esplicito: nodi `llm`, `tools`, `limit` e funzione
`route`.

Strumenti a disposizione del modello:
- **locale:** `get_current_time(timezone)`;
- **MCP:** sette strumenti offerti da un server FastMCP locale (stdio), che l'applicazione avvia
  come sottoprocesso e scopre con `tools/list`: `convert_units`, `calculate`, `search_catalog`,
  `get_item`, `add_note`, `list_notes`, `delete_note`.

Il codice è in inglese; prompt, testi del terminale, descrizioni degli strumenti e messaggi d'errore
sono in italiano.

- Moduli in `assistant/`:
  - `config.py`, `model.py`, `tools.py`, `graph.py`, `session.py`, `terminal.py`;
  - logica pura: `units.py`, `calculator.py`, `catalog.py`, `notes.py`;
  - MCP: `mcp_server.py` e `mcp_client.py` (`McpClient` sincrono e adattatore
    `create_mcp_tools`);
  - dati: `data/catalog.json`.
  Solo `__main__.py` collega i moduli.
- Le note sono in SQLite: in locale in `NOTES_DB` (default `data/notes.sqlite3`, ignorato da Git),
  in Docker nel volume `notes-data`.
- Log nel formato della slide 26:
  `step=…`, `variant=…`, `call_id=…`, `execution=ok|tool_error|transport_error`,
  `tool_message.call_id=…`; il server scrive `event=note_added|note_deleted`.
- Dipendenza nuova `fastmcp==4.1.6`. `constraints.txt` ha 47 righe aggiunte e nessuna versione
  esistente cambiata. `pywin32` vi compare perché il venv è su Windows, ma non viene installato
  nell'immagine.

### Commit della lezione 5 (solo locali)

| Commit | Contenuto |
|--------|-----------|
| `8ed2849` | Task 1: traduzione in inglese (pacchetto `assistant`, `LMSTUDIO_MODEL`, `MAX_STEPS`, marcatore `real`, servizio `assistant`) |
| `8f5da86` | Task 2: log della slide 26 e `ToolUnavailableError` → `transport_error` |
| `71d38ed` | Task 3: `units.py` |
| `49460db` | Task 4: `calculator.py` |
| `989dd69` | Task 5: `catalog.py` e `catalog.json` |
| `9e49e92` | Task 6: `notes.py` e `NOTES_DB` |
| `f969775` | Task 7: `fastmcp`, `mcp_server.py`, `constraints.txt` |
| `05a246a` | Task 8: `McpClient` |
| `41907eb` | Task 9: adattatore, avvio, prompt di sistema, log del server |
| `07290b9` | Task 10: prove reali |
| `4cb78f6` | Task 11: Docker con il volume delle note |
| (successivo) | Task 12: README, handoff, `CLAUDE.md`, note nella specifica di base |

Prima di questi commit `origin/main` era fermo a `5854213`; il push del 2026-11-09 lo ha portato a `7bff3ec`.

### Verifiche (2026-11-09)

Comandi da PowerShell nella cartella del progetto (allora `assistente-laboratorio/`, oggi la radice). Per le prove reali: LM Studio con
`google/gemma-4-e2b` (contesto 8192) e
`$env:LMSTUDIO_BASE_URL="http://localhost:1234/v1"; $env:LMSTUDIO_MODEL="google/gemma-4-e2b"`.

| CA | Comando | Esito |
|----|---------|-------|
| CA-1 | `.\.venv\Scripts\python.exe -m pytest` | ✅ 165 passed, 9 deselected dopo le correzioni della revisione (LM Studio non usato) |
| CA-2, CA-3, CA-4 | `pytest -m real -v` | ✅ passate, insieme alle altre prove reali (9 passed in 226 s) |
| CA-5 | LM Studio fermato e riavviato durante una sessione | ⏳ non ripetuta dopo la lezione 5 (✅ il 26–28/10); il comportamento del terminale è invariato e coperto dai test |
| CA-6 | `pytest` (`test_limit`, `test_session_continues_after_the_limit`) | ✅ |
| CA-7 | `python -m assistant` senza `LMSTUDIO_MODEL`; `docker compose run --rm -T -e LMSTUDIO_MODEL= assistant` | ✅ «Configurazione non valida: Manca LMSTUDIO_MODEL.», exit 1, in locale e nel container |
| CA-8 | `docker compose build`; `"Che ore sono a Tokyo?", "esci" \| docker compose run --rm -T -e LMSTUDIO_MODEL=google/gemma-4-e2b assistant` | ✅ `get_current_time` con `Asia/Tokyo`, risposta «Attualmente a Tokyo sono le 23:27 (9 novembre 2026).» |
| CA-9 | `pytest` (test del terminale); prova a mano con i tasti reali | ✅ automatica; ✅ manuale (utente, 2026-11-09): `esci` e Ctrl+C con i tasti reali, in locale e con `docker compose run --rm assistant`; dopo: 0 processi `python`, 0 container. Ctrl+Z non provato a mano |
| CA-10 | `git status --ignored` | ✅ vedi Task 12 |
| CA-11 | `pytest tests/test_mcp_server.py tests/test_mcp_client.py tests/test_main.py` | ✅ sette nomi, descrizioni e schemi dal server; `shell` scartato; collisione → exit 1 |
| CA-12 | `pytest tests/test_mcp_server.py tests/test_mcp_client.py` | ✅ ogni strumento via stdio; errori → `{"error": …}` senza `structured_content` |
| CA-13 | `pytest` (`test_startup_failure_raises`, `test_call_after_close_is_unavailable`, `test_mcp_startup_failure_exits_1`, `test_unavailable_tool_is_transport_error`) | ✅ |
| CA-14 | `pytest tests/test_calculator.py` | ✅ `__import__('os')`, `2 ^ 3` con il suggerimento `**`, `9 ** 9 ** 9` rifiutati |
| CA-15 | `pytest tests/test_notes.py` | ✅ persistenza dopo la riapertura, id non riusati |
| CA-16 | `pytest -m real` (`test_calculate_and_convert`) | ✅ 391; `convert_units` km→mi, 6,21 |
| CA-17 | `pytest -m real` (`test_remember_creates_one_note`) | ✅ una sola `add_note` |
| CA-18 | `pytest -m real` (`test_delete_unknown_note`) | ✅ `delete_note` 99 → errore; note invariate |
| CA-19 | `pytest -m real` (`test_notes_survive_restart`) | ✅ nota ritrovata da `list_notes` dopo il riavvio del server |
| CA-20 | `pytest -m real` (`test_catalog_search_then_detail`, `test_catalog_no_results`) | ✅ `search_catalog` → `get_item DL-201`, «32»; astrologia → `total 0`, nessun codice inventato |
| CA-21 | `pytest -m real` (`test_logs_correlate_call_ids`) | ✅ |
| CA-22 | `docker compose run --rm -T -e LMSTUDIO_MODEL=google/gemma-4-e2b assistant`, tre esecuzioni via pipe | ✅ `calculate` → 391; «Ricordami di comprare il latte» in un `run`, `list_notes` la ritrova nel successivo |

Altre verifiche:
- **Prova locale via pipe** con `NOTES_DB` in una cartella temporanea: `calculate`, `add_note` e
  `list_notes`; «venerdì» arriva integro; i `call_id` coincidono con `tool_message.call_id`.
- **Processi:** dopo l'uscita dell'app locale (input da pipe) non restano processi `python`
  (`Get-Process python`: 0 prima e dopo).
- **Immagine:** contiene `/app/assistant/data/catalog.json`; `/app/data` appartiene all'utente
  `assistant`; la cartella `data/` dell'host non viene copiata.
- **Pulizia:** il volume `notes-data`, creato nelle prove con la nota «comprare il latte», è stato
  eliminato con `docker volume rm assistente-laboratorio_notes-data` (comando verificato per il
  README).

Limite delle prove reali: una sola esecuzione. Dimostra che `gemma-4-e2b` usa gli strumenti con
quelle domande, non che lo faccia sempre.

### Decisioni prese durante l'esecuzione

Si aggiungono a quelle del piano («Scostamenti dalla specifica»).

- **Task 1:**
  - `tools.py` usa `datetime.UTC`, perché il parametro `timezone` oscurerebbe `datetime.timezone`.
  - Prove Docker con `-e LMSTUDIO_MODEL=…`, per non toccare il `.env`.
- **Task 2:** il README è stato aggiornato già qui, con un esempio di log reale; altrimenti avrebbe
  descritto log non più esistenti.
- **Task 4:** due rifiuti in più nella calcolatrice:
  - `OverflowError` dei float → «Numero troppo grande: oltre 1e100.»;
  - risultato complesso (`(-8) ** 0.5`) → «Risultato non reale: …».
- **Task 8:** `McpStartupError` con un modulo inesistente dice solo «Connection closed»; il motivo
  dettagliato arriva su stderr dal sottoprocesso.
- **Task 9:**
  - **Collisione di nomi:** `main` passa esplicitamente `ALLOWED_MCP_TOOLS` all'adattatore. Una
    collisione può nascere solo da un elenco consentito che contiene un nome locale; il test lo
    simula.
  - **Fixture dei test di `main`:** usano `monkeypatch.chdir(tmp_path)`, così nessun test crea
    `data/` nel repository.
  - **Log del server** (difetto trovato nella prova manuale): il logger ha nome esplicito
    `assistant.mcp_server` (con `python -m` sarebbe `__main__`), e anche nel sottoprocesso
    `mcp`/`fastmcp` restano a WARNING salvo DEBUG. Test `test_server_logs_use_module_name_and_hide_library_info`.
- **Task 10:**
  - In CA-19 la nota della prima sessione si aggiunge con `client.call_tool`: la prova riguarda la
    persistenza.
  - In CA-20 il codice di `get_item` si confronta senza distinzione di maiuscole, come lo accetta il
    server.

### Revisione indipendente finale (2026-11-09)

Un revisore con contesto pulito ha esaminato il diff `84ec958..178466b`. Esito: «With fixes»,
nessun problema critico. Tutti e cinque i punti della Review Focus sono stati verificati anche
lungo il percorso adattatore → grafo. Il revisore ha anche provato il server terminato a metà
sessione e Ctrl+C durante una chiamata lenta: nessun processo orfano, archivio rilasciato.

Corretti nel commit successivo, ciascuno con un test che prima falliva:
- discovery fallita dopo l'handshake → «Server MCP non avviato: …» ed exit 1, non un traceback
  (`test_discovery_failure_exits_1`);
- errori di validazione degli argomenti MCP (in inglese, con URL di pydantic) → messaggio italiano
  con gli argomenti attesi e la descrizione dello strumento
  (`test_invalid_arguments_reach_the_model_in_italian`);
- il server non stampa più nel terminale, in formato Rich, le righe di fastmcp per ogni errore
  atteso; a DEBUG restano, nel formato dell'app (`test_expected_tool_errors_add_no_server_log_lines`);
- `convert_units` con risultato infinito → errore invece di un falso successo
  (`test_overflowing_result_is_rejected`).

Dopo queste correzioni le prove reali non sono state ripetute. Toccano solo percorsi d'errore che
le prove reali non attraversano.

Rimandati (minori):
- con Windows, Ctrl+C durante una chiamata MCP bloccata arriva solo alla fine della chiamata
  (fino a 35 s); con strumenti normali dura millisecondi;
- manca un test che termini il server a metà sessione (il comportamento, verificato dal revisore,
  è corretto);
- `NOTES_DB` con una cartella padre non creabile (per esempio un file) → traceback invece di un
  messaggio;
- in `_shutdown`, se la chiusura supera 10 s, l'annullamento del task può non essere eseguito (il
  Job Object di Windows termina comunque il server);
- il log di avvio `tools=[…]` usa il nome `__main__`.

### Punti aperti

- **Prove manuali non ripetute:** CA-5, LM Studio fermato e riavviato; Ctrl+Z con i tasti reali.
- **Audit del 2026-11-03, punti M4–M13:** non affrontati. La descrizione non è nel repository.
- **Minori ancora aperti:**
  - con `MAX_STEPS=1` il testo dice «il limite di 1 passaggi»;
  - con `MAX_STEPS` oltre ~5000 si avrebbe un errore di LangGraph invece del messaggio di RF-10;
  - il container non ha init (`docker stop` attende 10 s); possibile `init: true`;
  - su Windows con stdout rediretto, caratteri fuori da cp1252 potrebbero dare
    `UnicodeEncodeError`. Nelle prove via pipe di questa sessione «venerdì» è passato senza
    errori, ma «€» non è stato provato in uscita dal terminale.
- **Mai provati:**
  - LM Studio su un'altra porta tramite `LMSTUDIO_BASE_URL_DOCKER`;
  - `docker compose build --no-cache`.

### Comandi

Da PowerShell nella radice della repository:

```powershell
& "$HOME\.lmstudio\bin\lms.exe" server start
& "$HOME\.lmstudio\bin\lms.exe" load google/gemma-4-e2b --context-length 8192 -y
$env:LMSTUDIO_BASE_URL = "http://localhost:1234/v1"
$env:LMSTUDIO_MODEL = "google/gemma-4-e2b"
.\.venv\Scripts\python.exe -m pytest            # senza modello: 297 passed, 15 deselected
.\.venv\Scripts\python.exe -m pytest -m real -v # 15 prove reali, circa 30 minuti
.\.venv\Scripts\python.exe -m assistant
docker compose build
"Quanto fa 17 * 23?", "esci" | docker compose run --rm -T assistant
```

Le variabili valgono solo nella finestra di PowerShell in cui si impostano. Docker legge `.env`;
nel container `LMSTUDIO_BASE_URL` vale `http://host.docker.internal:1234/v1`, oppure
`LMSTUDIO_BASE_URL_DOCKER` se è impostata.

Documenti precedenti:
- base: [`specs/2026-10-26-assistente-laboratorio-design.md`](docs/superpowers/specs/2026-10-26-assistente-laboratorio-design.md),
  [`plans/2026-10-26-assistente-laboratorio.md`](docs/superpowers/plans/2026-10-26-assistente-laboratorio.md);
- audit: [`specs/2026-11-03-correzioni-audit-design.md`](docs/superpowers/specs/2026-11-03-correzioni-audit-design.md),
  [`plans/2026-11-03-correzioni-audit.md`](docs/superpowers/plans/2026-11-03-correzioni-audit.md).
