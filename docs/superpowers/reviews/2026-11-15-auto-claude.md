# Rapporto — revisione di `auto-claude` rispetto a `dev` (2026-11-15)

Specifica: [`../specs/2026-11-15-revisione-integrazione-design.md`](../specs/2026-11-15-revisione-integrazione-design.md),
piano: [`../plans/2026-11-15-revisione-integrazione.md`](../plans/2026-11-15-revisione-integrazione.md).
Codice rivisto: `auto-claude` a `30bad78` (step 4–9 della lezione 6 e streaming facoltativo,
commit `290ce59..c53cc0a`).

## 1. Sintesi

Quattro revisori con contesto pulito, in sola lettura, uno per gruppo: A (Step 4 e 5),
B (Step 6), C (Step 7 e 9), D (Step 8 e streaming). Ogni problema è stato verificato da Claude
sul codice; i problemi gravi e importanti uno per uno (lettura, riproduzione o comando), i minori
a campione sulle righe indicate.

| Gravità | Confermati | Di cui «da decidere» | Falsi positivi |
|---------|-----------:|---------------------:|---------------:|
| Grave | 3 | 0 | 0 |
| Importante | 4 | 1 | 0 |
| Minore | 29 | 10 | 0 |

Problemi uniti perché visti da più gruppi: A6 = B8, A9 = C11, B10 = C7 (identificativo tenuto: il
primo). Nessun problema in codice già pubblicato che blocchi l'integrazione (§4).

Prove del 2026-11-15 (dettaglio in §7):
- **modello simulato:** `pytest` 1003 passed; pagina con Chrome `-m browser` 25 passed;
- **modello vero (LM Studio, `google/gemma-4-e2b`):** suite reale completa 64 passed, 1 skipped
  (atteso), 0 failed in 45:56; pagina con Chrome `-k frontend` 2 passed; streaming dalla pagina
  servita da Compose riuscito.

Criterio di uscita (specifica §7): **non soddisfatto**. Vanno corretti R-C1, R-B1 e R-A1; R-C2,
R-A2, R-A3 e R-D1 vanno corretti o accettati come debito noto.

## 2. Problemi confermati, dal più grave

### Gravi

**R-C1 · PostgreSQL di prova esposto sulla rete, con la password versionata** (gruppo C)
- Dove: `README.md:234` (`docker run … -p 5433:5432 postgres:18.6`), password `labprova` anche in
  `CLAUDE.md` e `README.md:657`; `PROGRESS.md:1225`.
- Scenario: il container `assistente-postgres` delle prove degli Step 7–8 ascolta su tutte le
  interfacce. Verificato: `docker port assistente-postgres` → `0.0.0.0:5433` e `[::]:5433`. Chi è
  sulla stessa rete può collegarsi con la password scritta nel README e leggere o cancellare le
  chat di prova.
- Riferimento: controlli trasversali (porte solo su `127.0.0.1`); specifica dello Step 7 §9.
- Correzione suggerita: `-p 127.0.0.1:5433:5432` nel README (e nel diario), poi ricreare il
  container (`docker rm -f` elimina le chat di prova).

**R-B1 · L'agente restituisce cronologie che poi rifiuta** (gruppo B; gravità alzata da Claude da
importante a grave)
- Dove: `assistant/agent.py:224-247` (`_check_call`), `assistant/agent.py:293-296` (id ripetuti),
  `assistant/api.py:62-66` (`InvalidToolCall` con `id`/`name` null nello schema di risposta).
- Scenario: un turno con una chiamata a strumento malformata (nome vuoto, `invalid_tool_calls`
  con `name` null, due chiamate con lo stesso id) risponde `200`; la `history` restituita, rimandata
  al turno successivo, dà `400 invalid_history`. Riprodotto da Claude con `messages_to_json` →
  `messages_from_json` sui tre casi (tutti rifiutati). Nella CLI ogni domanda dà errore fino al
  riavvio; **nel back-end la cronologia è salvata e la chat resta inutilizzabile per sempre**
  (`502 agent_error` a ogni invio). Con un modello piccolo le chiamate malformate sono realistiche.
- Motivo della gravità: per chi usa la pagina equivale a perdere la chat.
- Riferimento: specifica del servizio HTTP §3 (andata e ritorno per ogni cronologia valida) e §6.
- Etichette: scelta documentata (diario dello Step 6, punto 3), ma il servizio produce ciò che non
  accetta.
- Correzione suggerita: in ingresso accettare ciò che il grafo produce (nome vuoto o null, id
  ripetuti nello stesso messaggio); test che rimanda al servizio la `history` di ogni risposta
  `200`, compresi questi casi.

**R-A1 · Evidenza dello Step 5 «risposta adeguata» non dimostrata** (gruppo A)
- Dove: `tests/test_real.py:401-411` (CA-58); diario dello Step 5, punto 6; README, sezione «Prompt
  MCP».
- Scenario: il test controlla solo che la risposta contenga «protocol» o «mcp», parole già presenti
  nel prompt. Il diario e il README stessi dicono che la spiegazione del modello era «chiara ma
  sbagliata nel merito». L'evidenza della traccia (`/prompt spiega argomento="Model Context
  Protocol" livello=base` con risposta adeguata) non è dimostrata e il test non se ne accorge.
  Nella suite di oggi CA-58 è passata con lo stesso controllo debole.
- Riferimento: traccia Step 5, «Evidenze» punto 1; specifica dei prompt §9.
- Etichette: scelta documentata (limite del modello annotato).
- Correzione suggerita: controllo di merito nel test (per esempio almeno una parola tra «server»,
  «client», «strumenti», «applicazioni») ed eventualmente un testo del prompt `spiega` più guidato;
  se il modello continua a sbagliare, registrare CA-58 come evidenza non soddisfatta invece che
  passata (anche questa è una correzione accettabile).

### Importanti

**R-C2 · Avvio di Compose: back-end che può fermarsi alla prima esecuzione** (gruppo C)
- Dove: `compose.yaml:80-82` (healthcheck `pg_isready` senza `-h`); servizio `backend` senza
  `restart`; `backend/__main__.py:36` (`init_db` all'avvio, uscita con 1 se fallisce).
- Scenario: con il volume `postgres-data` vuoto l'entrypoint ufficiale avvia un server temporaneo
  solo sul socket Unix; `pg_isready` senza `-h` lo vede pronto, `postgres` diventa `healthy` prima
  che il server vero ascolti in TCP. Se il back-end chiama `init_db` in quella finestra esce con 1 e
  resta fermo, mentre `docker compose up -d` termina con successo. Probabilità bassa (CA-91 è
  passata), ma l'avvio non si riprende da solo.
- Riferimento: traccia Step 9, punto 3 («back-end avviato a database pronto»).
- Correzione suggerita: `pg_isready -h 127.0.0.1 …` e `restart: unless-stopped` per `backend`.

**R-A2 · Prove reali degli Step 4 e 5 solo in processo, non attraverso il servizio HTTP** (gruppo A)
- Dove: `tests/test_real.py:55-80` (`open_session`), `388-398` (`send_prompt`).
- Scenario: CA-50, CA-51, CA-58 e CA-59 chiamano direttamente grafo e `resolve_prompt`. Il percorso
  finale (CLI → `POST /chat` con `prompt`, preferenze caricate in `service._serve`), riscritto dallo
  Step 6, è provato con LM Studio solo in modo indiretto; con il modello simulato è coperto.
- Riferimento: traccia Step 5, «Obiettivo»; `CLAUDE.md`, «Test e verifiche».
- Correzione suggerita: una prova reale con `start_service` e la CLI (`/prompt spiega …`) e una con
  `PREFERENCES_FILE` nell'ambiente del servizio (fuso `America/New_York`).

**R-A3 · Diagnosi del README che mostra il file di preferenze sbagliato** (gruppo A)
- Dove: `README.md:970` (snippet «Le preferenze non hanno effetto»); `assistant/mcp_client.py:80-82`
  (valore predefinito di `preferences_file`).
- Scenario: lo snippet chiama `server_command` senza il file delle preferenze, quindi legge sempre
  il file del pacchetto. Chi ha impostato `PREFERENCES_FILE`, cioè proprio chi sta facendo la
  diagnosi, vede il JSON sbagliato e conclude che il servizio legge il file giusto.
- Riferimento: specifica delle preferenze §5 (parametro obbligatorio).
- Correzione suggerita: passare `PREFERENCES_FILE` nello snippet, oppure rendere il parametro
  obbligatorio.

**R-D1 · Pagina chiusa durante lo streaming: il back-end non se ne accorge** (gruppo D;
**da decidere**)
- Dove: `backend/api.py:474-475` (endpoint sincrono), `_forward` in `backend/api.py:276-324`;
  `README.md:924-927`; specifica dello streaming §1.
- Scenario: se la pagina viene ricaricata quando non arrivano eventi (per esempio mentre lavora il
  revisore), il thread del back-end resta fermo sul prossimo evento dell'agente; all'arrivo di
  `done` salva comunque la risposta e scrive `outcome=done`, non `client_gone`. Specifica e README
  dicono il contrario. La pagina ricaricata non sa che il turno è in corso: se l'utente rimanda la
  domanda, partono due turni nella stessa chat e il secondo sovrascrive lo stato dell'agente del
  primo (vedi anche R-C4). Verificato sulla struttura di `_forward`; `client_gone` è provato solo
  chiamando `_forward` a mano.
- Riferimento: specifica dello streaming §1 e §6; specifica dello Step 7 §13.
- Etichette: scelta documentata (generatore sincrono).
- Da decidere: correggere il comportamento (endpoint asincrono che chiude il flusso alla
  disconnessione, `409` per un secondo invio con un turno in corso) oppure correggere specifica e
  README e accettare il comportamento (salvare la risposta è anche utile).

## 3. Minori

Identificativo, dove, che cosa; «(d)» = da decidere (scelta documentata o di gusto).

| Id | Dove | Che cosa |
|----|------|----------|
| R-A4 (d) | `assistant/service.py:93`; `CLAUDE.md` | Preferenze lette all'avvio del servizio, non a inizio sessione: una modifica vale dal riavvio dell'agente; CLAUDE.md dice ancora «a inizio sessione» |
| R-A5 | `assistant/terminal.py:45`, `assistant/api.py:271-272` | `prompt_unavailable` → «(… avanzato.). Riprova.»: punteggiatura doppia e «Riprova» inutile; manca il suggerimento `/prompts` |
| R-A6 | `assistant/api.py:248` (`_kind`) | Nome del prompt nel log senza escape: un `\n` falsifica righe di log (anche B8) |
| R-A7 | `assistant/commands.py:181-185`, `assistant/api.py:100-102` | `PromptRequest.arguments` senza limite di lunghezza; argomenti interi nel log |
| R-A8 (d) | `assistant/data/scope.txt:7` | Ambito allargato a qualsiasi spiegazione di informatica e IA (scheda 1 della rilettura) |
| R-A9 | `assistant/api_client.py:16`, `assistant/commands.py:19-20` | CLI e back-end importano `mcp_client` (quindi `fastmcp`, `langchain_core`) per due dataclass (anche C11) |
| R-A10 | `backend/api.py`, `frontend/static/app.js` | Nella pagina «/prompt …» va al modello come domanda normale (coerente con la traccia; al più una riga nel README) |
| R-A11 (d) | `tests/test_real.py:367-380` (CA-51) | La prova reale cambia solo la lingua, non lo stile (la traccia dice «lingua o stile») |
| R-B2 | `tests/test_api.py:162-168` | Nessun test di `/chat` con uno strumento MCP irraggiungibile durante il turno (solo a livello di grafo) |
| R-B3 | `assistant/graph.py:255`; healthcheck di `agent` | MCP morto: `/status` 503 per sempre, messaggio «riavvia l'assistente» (serve riavviare il servizio); healthcheck che accetta qualsiasi codice. Codice già pubblicato, reso raggiungibile in modo nuovo dal servizio a lunga vita |
| R-B4 | `assistant/api_client.py:18` vs `assistant/mcp_client.py:235` | `STATUS_TIMEOUT` 10 s, attesa di MCP fino a 35 s: con MCP bloccato la CLI esce invece di avvisare |
| R-B5 (d) | `assistant/api.py:287-288` | Timeout di LM Studio segnalato come «LM Studio non raggiungibile» |
| R-B6 (d) | `tests/test_real.py:523-542` (CA-68) | «Stessa risposta da CLI e API»: l'uguaglianza dei testi è solo stampata (oggi passata con «391» in entrambe) |
| R-B7 | `README.md:209-210`, `263-266` | Risposte JSON senza `charset` (agente e back-end): `Invoke-RestMethod` di PowerShell 5.1 storpia le lettere accentate. **Verificato** il 2026-11-15: `GET /chats/5` → «A Sydney Ã¨ alle…» (`Content-Type: application/json`, PowerShell 5.1.26100) |
| R-B9 | `assistant/config.py:171-173`, `assistant/api_client.py:262` | `AGENT_URL=http://[::1` → traceback `InvalidURL` invece di «Configurazione non valida» |
| R-B10 (d) | `compose.yaml:53,100` | `env_file: .env` passa `POSTGRES_PASSWORD` ai container `agent` e `assistant`, che non la usano (anche C7) |
| R-C3 | `backend/db.py:75-77`, `backend/api.py:217-219` | Carattere NUL nel messaggio → errore di psycopg → `500` e parametri SQL (testo della domanda) nel log; `hide_parameters=True` e rifiuto di `\x00` |
| R-C4 (d) | `backend/store.py:235-243`, `backend/api.py:428-438` | Invii contemporanei nella stessa chat: il secondo sovrascrive lo stato dell'agente (documentato); chat eliminata durante `add_answer` → `500` invece di `404` |
| R-C5 | `backend/store.py:198-216` | `list_chats` e `get_chat` caricano anche la cronologia JSON completa dell'agente |
| R-C6 | `assistant/api_client.py:250-255` | `AgentClient.chat` con `timeout=600` anche per la connessione (`chat_stream` usa 10 s) |
| R-C8 | `tests/test_docker.py:151-153` | Test saltati solo senza l'eseguibile `docker`, non senza il plugin `compose` |
| R-C9 | `CLAUDE.md:73` | Comandi `pytest` delle prove reali del back-end senza `.\.venv\Scripts\python.exe -m` |
| R-C10 (d) | diario, Step 9 punto 3 | Evidenze di Compose (CA-91…CA-93) dimostrate solo con uno script temporaneo non versionato |
| R-D2 | `assistant/api_client.py:213-237` | `chat_stream` restituisce un generatore non avviato: chiuderlo prima del primo `next` lascia aperta la connessione httpx (verificato dal revisore) |
| R-D3 (d) | `frontend/static/api.js:178-181`, `texts.js:94-99` | Tempo scaduto dopo `response.ok`: il testo torna nel campo anche se la domanda è salvata |
| R-D4 | `tests/frontend/contract.test.mjs:15-22` | Il contratto non confronta con l'OpenAPI i campi degli eventi dello streaming |
| R-D5 | `frontend/static/app.js:195-197`, `163-167` | La bozza riporta in fondo chi sta leggendo più in alto; `#waiting` con `role="status"` annunciato ogni secondo |
| R-D6 | `frontend/static/texts.js:48-50`, `backend/api.py:179-181` | «L'assistente ha risposto con un errore: l'agente ha risposto con un errore (model_unavailable): …», ripetitivo e tecnico |
| R-P1 (d) | `frontend/static/app.js` (testo con `textContent`) | Trovato nelle prove reali di oggi: le risposte del modello contengono markdown e LaTeX (`**391**`, `$2^{20}$ è $1,048,576$`) e la pagina li mostra così come sono. Scelta sicura (niente HTML), ma poco leggibile per chi non conosce il progetto |

## 4. Codice già pubblicato (step 1–3, a `428cc8a`)

- R-B3 (testo «riavvia l'assistente» in `assistant/graph.py:255`): già pubblicato, reso
  raggiungibile in modo nuovo dal servizio dell'agente, che resta attivo a lungo. Minore, quindi
  non blocca. Nessun altro problema riguarda codice precedente al loop.

## 5. Falsi positivi

Nessuno. Le scelte documentate nel diario sono segnate «(d)» o «da decidere», non scartate.

## 6. Evidenze della traccia per step

Dai resoconti dei revisori, controllati da Claude; «reale» = con LM Studio.

| Step | Evidenza | Dimostrazione | Stato |
|------|----------|---------------|-------|
| 4 | «Che ore sono?» con fuso predefinito `America/New_York` | CA-50 reale (in processo, R-A2) | dimostrata |
| 4 | Cambio di lingua o stile → risposta della sessione successiva | CA-51 reale, solo lingua (R-A11); nel servizio vale dal riavvio (R-A4) | dimostrata |
| 4 | Lettura della resource nei log, separata dai tool | test senza modello; CA-50 | dimostrata |
| 5 | `/prompt spiega …` con risposta adeguata | CA-58 reale, controllo debole | **non dimostrata** (R-A1) |
| 5 | `riassumi_conversazione` riassume la sessione | CA-59 reale (in processo, R-A2) | dimostrata |
| 5 | Log con prompt, argomenti e messaggi | test senza modello | dimostrata |
| 6 | Chiamata HTTP con uno strumento, traccia nei log | CA-67 reale | dimostrata |
| 6 | Modello o strumenti non disponibili → codice e messaggio comprensibili | CA-69 reale (modello); strumenti solo con finti (R-B2) | dimostrata in parte |
| 6 | Test dell'API con grafo simulato, OpenAPI consultabile | test senza modello; CA-69 | dimostrata |
| 6 | Stessa risposta da CLI e API | CA-68 reale (R-B6) | dimostrata |
| 7 | OpenAPI, agente irraggiungibile, test con agente simulato, chat dopo il riavvio | test senza modello; CA-77, CA-78 reali | dimostrata |
| 8 | Conversazione dal browser con uno strumento, chat dopo il riavvio, agente spento | CA-86, CA-87 reali con Edge e Chrome | dimostrata |
| 9 | Quattro servizi attivi, chat con strumento nei log, chat dopo `down` e `up` | CA-91…CA-93 a mano (14/11); oggi `up`, `ps` e chat con strumento (R-C10) | dimostrata |
| Streaming | Testo mentre arriva, strumento indicato, salvataggio alla fine, decisione sulla bozza | CA-94…CA-102; oggi anche con Compose | dimostrata; avviso del revisore vedi §7 |

## 7. Prove reali del 2026-11-15

Ambiente: LM Studio sull'host con `google/gemma-4-e2b`; PostgreSQL in `assistente-postgres`
(porta 5433); Compose spento durante le prove dei punti 1–2.

| # | Comando | Modello | Esito |
|---|---------|---------|-------|
| 0 | `pytest` | simulato | 1003 passed, 90 deselected (86 s) |
| 1 | `pytest -m real -v` (Edge) | vero | 64 passed, 1 skipped (`test_sqlite_engine_enforces_foreign_keys[postgresql]`, atteso), 0 failed, 45:56 |
| 2a | `BROWSER_CHANNEL=chrome`, `pytest -m browser -v` | simulato | 25 passed (10 s) |
| 2b | `BROWSER_CHANNEL=chrome`, `pytest tests/test_real.py -m real -k frontend -v` | vero | 2 passed (2:36) |
| 3 | Compose: `docker compose up -d --build`, pagina su `127.0.0.1:8080` con Edge (script temporaneo), «Quanto fa 17 * 23?» | vero | bozza visibile e cresciuta in 3 stati, «Uso lo strumento calculate…» durante l'attesa, risposta «391» con `calculate`, nessun errore JavaScript, chat presente dopo il ricaricamento; log di `agent`: `tool=calculate` e `api response=chat_stream status=200 outcome=done tools=calculate` |
| 4 | Avviso del revisore dalla pagina servita da Compose, tre domande in tre parti ciascuna, chat nuove | vero | **non ottenuto**: tre risposte complete e corrette (strumenti `calculate`, `convert_units`, `get_current_time` in tutte), revisore `coherent=true` al primo passaggio in tutti e tre i turni (log di `agent`), nessun avviso nella bozza; 110–119 s per turno, 47–65 eventi di testo, chat presenti dopo il ricaricamento, nessun errore JavaScript |
| 5 | PowerShell 5.1: `Invoke-RestMethod http://127.0.0.1:8001/chats/5` | — | testo accentato storpiato (R-B7) |

Prove instabili: nessuna (nessuna prova ripetuta).
Non dimostrato con il modello vero: l'avviso del revisore nella bozza (reset `review`); resta coperto con il modello simulato da CA-99 (Node) e CA-100 (browser), e il rifiuto del revisore con il modello vero da `test_reviewer_rejects_an_imposed_partial_answer` (risposta parziale imposta, senza la pagina). Non ripetuti oggi: CA-93 (chat dopo `down` e `up` con Compose) e `stream_interrupted` con un server vero.
