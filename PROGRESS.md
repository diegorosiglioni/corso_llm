# Diario di lavoro

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
