# Handoff — Assistente del laboratorio

Data: 2026-11-13
Stato: **lezione 6, Step 2 (revisore): implementato e verificato su `dev`, non ancora
pubblicato.** Anche lo Step 1 (router) è solo su `dev`.
Step 2: specifica [`specs/2026-11-11-revisore-design.md`](specs/2026-11-11-revisore-design.md),
piano [`plans/2026-11-11-revisore.md`](plans/2026-11-11-revisore.md), requisiti §10 (RF-28…RF-33,
CA-30…CA-37). Step 1: specifica
[`specs/2026-11-11-router-design.md`](specs/2026-11-11-router-design.md), piano
[`plans/2026-11-11-router.md`](plans/2026-11-11-router.md), requisiti §9 (RF-23…RF-27,
CA-23…CA-29). Il push si fa solo su richiesta dell'utente (regola in `CLAUDE.md`, sezione «Git»).
La lezione 5 resta come descritta più sotto.

**Branch di lavoro dal 2026-11-11: `dev`.** I commit si fanno su `dev`; il push va prima su
`origin/dev`, poi `main` si porta allo stesso commit con avanzamento rapido
(`git push origin dev:main`).

**Struttura cambiata il 2026-11-09.** Il progetto è nella radice della repository (prima in
`assistente-laboratorio/`); `lezione3/` è solo locale, esclusa da Git. `compose.yaml` fissa
`name: assistente-laboratorio`. I documenti precedenti citano ancora `assistente-laboratorio/`: sono
storici e non sono stati riscritti.

## Lezione 6 — prossimo passo (2026-11-13)

**Prossimo: Step 3 · Riassunto**, da avviare con un nuovo brainstorming
(`superpowers:brainstorming`): requisiti, specifica, piano, come per gli Step 1 e 2. Il prompt
[`prossimo-prompt.txt`](prossimo-prompt.txt) si riferisce ancora al piano dello Step 2: va
riscritto per lo Step 3. Traccia completa: [`lezione6.md`](lezione6.md); lo schema del grafo dei tre
step è la slide 3 di `LLM_Lez_6.pdf` (non tracciato). In questa macchina manca `pdftoppm`: le slide
si leggono come immagini con PyMuPDF installato nella scratchpad (`pip install --target`), non nel
progetto.

## Lezione 6, Step 2 — revisore (2026-11-13)

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

### Verifiche (2026-11-13)

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

### Decisioni prese durante l'esecuzione

- **Worktree:** nessuno, come chiede `CLAUDE.md`; lavoro direttamente su `dev`.
- **Prove rapide da terminale con `NOTES_DB` in una cartella temporanea**, per non toccare `data/`
  del repository.
- **LM Studio e Docker Desktop** sono stati avviati durante la sessione (`lms server start`,
  `lms load google/gemma-4-e2b --context-length 8192 -y`, Docker Desktop dal menu Start).

### Revisione indipendente finale (2026-11-13)

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

### Punti aperti (Step 2)

- **Durata delle prove reali:** da circa 10 a circa 32 minuti (ogni turno ha almeno una chiamata in
  più; la prova con la risposta imposta da sola dura circa 4 minuti).
- **Risposte con LaTeX:** l'agente scrive `$17 \times 23$` (visto in locale e in Docker); il
  terminale lo mostra così com'è. Non riguarda il revisore, non toccato.
- **Contesto:** bozze e indicazioni restano nella cronologia e occupano contesto (8192 token);
  il riassunto è lo Step 3.
- Con il modello reale non sono stati osservati il limite delle revisioni, il ripiego e i falsi
  rifiuti su domande brevi di continuazione («E a Roma?» è stata approvata).

## Lezione 6, Step 1 — router (2026-11-11)

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

### Verifiche (2026-11-11)

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

### Decisioni prese durante l'esecuzione

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

### Revisione indipendente finale (2026-11-11)

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

### Punti aperti (Step 1)

- Il motivo del router comincia spesso con la maiuscola, quindi il rifiuto si legge «…fuori dal
  mio ambito: La richiesta…». Solo estetica, non toccata.
- Nei log rediretti su file in Windows le lettere accentate possono uscire in cp1252 (già noto
  dalla lezione 5).

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
- Suite predefinita: `pytest` → `249 passed, 14 deselected` (Step 2 della lezione 6), in circa 45–85 s. I test MCP avviano il
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
.\.venv\Scripts\python.exe -m pytest            # senza modello: 249 passed, 14 deselected
.\.venv\Scripts\python.exe -m pytest -m real -v # 14 prove reali, circa 32 minuti
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
