# Handoff — Assistente del laboratorio

Data: 2026-11-09
Stato: **lezione 5 implementata, revisionata e pubblicata.** Sono stati eseguiti i 12 task del
piano [`plans/2026-11-09-strumenti-mcp.md`](plans/2026-11-09-strumenti-mcp.md). Dopo la
revisione indipendente finale e le sue correzioni, il push su `origin/main` è arrivato a
`7bff3ec`. Restano alcune prove manuali (vedi «Punti aperti»).
**Lezione 6: traccia letta e riassunta, nessun codice.** Si riparte dallo Step 1 (Router): vedi
la sezione «Lezione 6 — prossimo passo».

**Branch di lavoro dal 2026-11-11: `dev`.** Su richiesta dell'utente i commit si fanno su `dev`.
Il push va prima su `origin/dev`, poi `main` si porta allo stesso commit con avanzamento rapido
(`git push origin dev:main`). Regola completa in `CLAUDE.md`, sezione «Git».

**Struttura cambiata il 2026-11-09, dopo il push.** Su richiesta dell'utente il progetto è
stato spostato da `assistente-laboratorio/` alla radice della repository. Inoltre `lezione3/`
è uscita da Git: resta solo in locale, esclusa con `.gitignore`.
- La `.venv` è stata ricreata in radice, con le stesse versioni.
- `compose.yaml` fissa `name: assistente-laboratorio`: immagine e volume mantengono i nomi
  precedenti, qualunque sia la cartella della repository.
- I documenti precedenti (specifiche, piani, requisiti) citano ancora `assistente-laboratorio/`:
  sono documenti storici e non sono stati riscritti.

## Lezione 6 — prossimo passo (2026-11-09)

**Nessun codice scritto per la lezione 6.** La traccia del docente (`LLM_Lez_6.pdf`, nella radice,
non tracciato) è stata letta per intero e riassunta in [`lezione6.md`](lezione6.md): nove step
in tre blocchi (A: router, revisore, riassunto; B: resource e prompt MCP; C: agente HTTP,
back-end con PostgreSQL, front-end, Docker Compose a quattro container).

Decisioni di metodo già prese:
- **Lavoro architetturale, scomposto:** ogni step è un sotto-progetto con il proprio ciclo
  Superpowers: brainstorming → specifica in `specs/` (approvata) → piano in `plans/` (approvato)
  → esecuzione TDD → verifica (`pytest`, `pytest -m real`, README) → commit.
- **Uno step alla volta, si parte dallo Step 1 (Router).** È l'opzione consigliata; l'utente
  non l'ha ancora confermata esplicitamente (domanda lasciata aperta: uno step alla volta
  oppure step 1–3 insieme).
- Il brainstorming dello Step 1 è appena iniziato: non è stata posta ancora nessuna domanda di
  design.

Da tenere presente per lo Step 1:
- Il grafo attuale (`assistant/graph.py`) ha `START → llm ⇄ tools`, `limit`, funzione `route`;
  il router va inserito tra `START` e `llm`, con un nodo di rifiuto che va a `END`.
- La configurazione si legge solo da variabili d'ambiente (`assistant/config.py`); l'«ambito
  in configurazione» va deciso lì (variabile d'ambiente o file indicato da una variabile).
- `CLAUDE.md`, sezione «Confini», dice di non anticipare le lezioni successive: va aggiornato
  quando lo Step 1 viene concordato, aggiungendo solo quello step.
- Gli step 6–9 introducono framework nuovi (server HTTP, PostgreSQL, front-end): vanno motivati
  e concordati quando ci si arriva.
- **In questa macchina `pdftoppm` non c'è:** il Read dei PDF fallisce. Il testo è stato estratto
  con `pypdf` installato nella scratchpad; non serve rifarlo, basta `lezione6.md`.

Prompt da incollare nella prossima sessione: [`prossimo-prompt.txt`](prossimo-prompt.txt).

## Riprendere da qui (stato della lezione 5)

**`.env` aggiornato (2026-11-09).** L'utente ha cambiato i nomi delle variabili:
`LMSTUDIO_MODELLO` → `LMSTUDIO_MODEL` e `MAX_PASSI` → `MAX_STEPS`.
- Verifica: senza `-e`,
  `"Che ore sono a Tokyo?", "esci" | docker compose run --rm -T assistant` chiama
  `get_current_time` con `Asia/Tokyo` ed esce con codice 0.
- Le prove Docker fatte prima dell'aggiornamento passavano `-e LMSTUDIO_MODEL=…`.
- Un `.env` creato prima della lezione 5 va aggiornato allo stesso modo (vedi README).

Leggere prima, in quest'ordine:
1. `../../CLAUDE.md`: regole del progetto, struttura e comandi aggiornati.
2. [`specs/2026-11-09-strumenti-mcp-design.md`](specs/2026-11-09-strumenti-mcp-design.md): il
   **come** della lezione 5.
3. Questo file, sezioni «Decisioni prese durante l'esecuzione» e «Punti aperti».

Da sapere:
- **In Git Bash `python` apre il REPL di Windows** e blocca il comando. Usare sempre
  `.venv/Scripts/python.exe` (o `py -3.13`).
- **`LLM_Lez_5.pdf`** e **`LLM_Lez_6.pdf`** non sono tracciati: non aggiungerli a Git senza
  chiedere.
- Suite predefinita: `pytest` → `165 passed, 9 deselected`, in circa 20 s. I test MCP avviano il
  server come sottoprocesso, circa 1 s ciascuno.

## Che cosa c'è oggi (lezione 5)

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

## Commit della lezione 5 (solo locali)

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

## Verifiche (2026-11-09)

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

## Decisioni prese durante l'esecuzione

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

## Revisione indipendente finale (2026-11-09)

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

## Punti aperti

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

## Comandi

Da PowerShell nella radice della repository:

```powershell
& "$HOME\.lmstudio\bin\lms.exe" server start
& "$HOME\.lmstudio\bin\lms.exe" load google/gemma-4-e2b --context-length 8192 -y
$env:LMSTUDIO_BASE_URL = "http://localhost:1234/v1"
$env:LMSTUDIO_MODEL = "google/gemma-4-e2b"
.\.venv\Scripts\python.exe -m pytest            # senza modello: 165 passed, 9 deselected
.\.venv\Scripts\python.exe -m pytest -m real -v # 9 prove reali, circa 4 minuti
.\.venv\Scripts\python.exe -m assistant
docker compose build
"Quanto fa 17 * 23?", "esci" | docker compose run --rm -T assistant
```

Le variabili valgono solo nella finestra di PowerShell in cui si impostano. Docker legge `.env`;
nel container `LMSTUDIO_BASE_URL` vale `http://host.docker.internal:1234/v1`, oppure
`LMSTUDIO_BASE_URL_DOCKER` se è impostata.

Documenti precedenti:
- base: [`specs/2026-10-26-assistente-laboratorio-design.md`](specs/2026-10-26-assistente-laboratorio-design.md),
  [`plans/2026-10-26-assistente-laboratorio.md`](plans/2026-10-26-assistente-laboratorio.md);
- audit: [`specs/2026-11-03-correzioni-audit-design.md`](specs/2026-11-03-correzioni-audit-design.md),
  [`plans/2026-11-03-correzioni-audit.md`](plans/2026-11-03-correzioni-audit.md).
