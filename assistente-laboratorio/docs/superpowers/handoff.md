# Handoff — Assistente del laboratorio

Data: 2026-11-09
Stato: **lezione 5 implementata.** Sono stati eseguiti i 12 task del piano
[`plans/2026-11-09-strumenti-mcp.md`](plans/2026-11-09-strumenti-mcp.md), tutti con commit
locali; nessun push. Restano alcune prove manuali e la revisione indipendente finale (vedi
«Punti aperti»).

## Riprendere da qui

**Prima di tutto, il `.env` va aggiornato a mano:** `LMSTUDIO_MODELLO` → `LMSTUDIO_MODEL`,
`MAX_PASSI` → `MAX_STEPS`. Il 2026-11-09 il `.env` dell'utente aveva ancora i nomi vecchi.
L'agente non lo modifica. Senza l'aggiornamento `docker compose run` esce con
«Configurazione non valida: Manca LMSTUDIO_MODEL.». Le prove Docker di questa sessione hanno
aggirato il problema passando `-e LMSTUDIO_MODEL=google/gemma-4-e2b`.

Leggere prima, in quest'ordine:
1. `../../../CLAUDE.md`: regole del progetto, struttura e comandi aggiornati.
2. [`specs/2026-11-09-strumenti-mcp-design.md`](specs/2026-11-09-strumenti-mcp-design.md): il
   **come** della lezione 5.
3. Questo file, sezioni «Decisioni prese durante l'esecuzione» e «Punti aperti».

Da sapere:
- **In Git Bash `python` apre il REPL di Windows** e blocca il comando. Usare sempre
  `.venv/Scripts/python.exe` (o `py -3.13`).
- **`LLM_Lez_5.pdf`** è nella cartella, non tracciato: non aggiungerlo a Git senza chiedere.
- Suite predefinita: `pytest` → `159 passed, 9 deselected`, in circa 15 s. I test MCP avviano il
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

`origin/main` è fermo a `5854213`.

## Verifiche (2026-11-09)

Comandi da PowerShell in `assistente-laboratorio/`. Per le prove reali: LM Studio con
`google/gemma-4-e2b` (contesto 8192) e
`$env:LMSTUDIO_BASE_URL="http://localhost:1234/v1"; $env:LMSTUDIO_MODEL="google/gemma-4-e2b"`.

| CA | Comando | Esito |
|----|---------|-------|
| CA-1 | `.\.venv\Scripts\python.exe -m pytest` | ✅ 159 passed, 9 deselected (LM Studio non usato) |
| CA-2, CA-3, CA-4 | `pytest -m real -v` | ✅ passate, insieme alle altre prove reali (9 passed in 226 s) |
| CA-5 | LM Studio fermato e riavviato durante una sessione | ⏳ non ripetuta dopo la lezione 5 (✅ il 26–28/10); il comportamento del terminale è invariato e coperto dai test |
| CA-6 | `pytest` (`test_limit`, `test_session_continues_after_the_limit`) | ✅ |
| CA-7 | `python -m assistant` senza `LMSTUDIO_MODEL`; `docker compose run --rm -T -e LMSTUDIO_MODEL= assistant` | ✅ «Configurazione non valida: Manca LMSTUDIO_MODEL.», exit 1, in locale e nel container |
| CA-8 | `docker compose build`; `"Che ore sono a Tokyo?", "esci" \| docker compose run --rm -T -e LMSTUDIO_MODEL=google/gemma-4-e2b assistant` | ✅ `get_current_time` con `Asia/Tokyo`, risposta «Attualmente a Tokyo sono le 23:27 (9 novembre 2026).» |
| CA-9 | `pytest` (test del terminale); prova a mano con i tasti reali | ✅ automatica; ⏳ manuale non ripetuta: `esci`, Ctrl+Z e Ctrl+C, in locale e con `docker compose run --rm assistant` |
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

## Punti aperti

- **Revisione indipendente finale** del diff `84ec958..HEAD`: prevista da `executing-plans`, vedi
  l'esito nella sezione seguente quando c'è.
- **Prove manuali non ripetute:**
  - CA-9 con i tasti reali (`esci`, Ctrl+Z, Ctrl+C), in locale e con
    `docker compose run --rm assistant`, verificando con `Get-Process python` e `docker ps` che il
    server non resti attivo;
  - CA-5, LM Studio fermato e riavviato.
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

Da PowerShell in `assistente-laboratorio/`:

```powershell
& "$HOME\.lmstudio\bin\lms.exe" server start
& "$HOME\.lmstudio\bin\lms.exe" load google/gemma-4-e2b --context-length 8192 -y
$env:LMSTUDIO_BASE_URL = "http://localhost:1234/v1"
$env:LMSTUDIO_MODEL = "google/gemma-4-e2b"
.\.venv\Scripts\python.exe -m pytest            # senza modello: 159 passed, 9 deselected
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
