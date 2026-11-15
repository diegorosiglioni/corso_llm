# Specifica — Correzioni di `auto-claude` (F4), sistemazione (F5) e integrazione (F6)

Data: 2026-11-15
Stato: approvata dall'utente il 2026-11-15
Riferimenti: [`2026-11-15-revisione-integrazione-design.md`](2026-11-15-revisione-integrazione-design.md)
(fasi, regole del §5, criteri di uscita del §7), rapporto
[`../reviews/2026-11-15-auto-claude.md`](../reviews/2026-11-15-auto-claude.md) (problemi, §8 debiti),
`PROGRESS.md`, sezione «Revisione e integrazione di `auto-claude`» (decisioni F3 e approcci F4).

## 1. Scopo

La revisione (F1), le prove reali (F2) e la rilettura con l'utente (F3) hanno deciso che cosa
correggere prima di pubblicare `auto-claude` su `main`. Questa specifica descrive, per ogni
correzione approvata, il problema, il comportamento atteso, il test che lo dimostra e l'eventuale
prova reale; poi la revisione delle correzioni, la sistemazione dei file del loop (F5) e la verifica
finale con l'integrazione (F6). Obiettivo dell'utente: **pubblicare su `main` in sicurezza**, senza
scadenze.

## 2. Obiettivi, non obiettivi, anti-obiettivi

Obiettivi:
- correggere i 3 gravi (R-C1, R-B1, R-A1), i 3 importanti approvati (R-C2, R-A2, R-A3), la scelta
  R-A8 e i 12 minori approvati (R-B5, R-B10, R-A4, R-B7, R-C3, R-C6, R-A5, R-D6, R-A6, R-A7, R-A10,
  R-C9); correggere specifica e README per R-D1;
- ogni correzione di comportamento con un test che prima fallisce;
- registrare in `TODO.md` i debiti noti con il loro motivo (§6);
- arrivare ai criteri di uscita (§10) e a `dev` portato su `auto-claude` con avanzamento rapido.

Non obiettivi:
- riaprire le decisioni di F3 e F4 (che cosa si corregge e con quale approccio);
- correggere i debiti noti, aggiungere funzioni oltre la traccia, refactoring non legati a un
  problema;
- riparare cronologie già salvate e rese inutilizzabili da R-B1 (esistono solo nei database di
  prova);
- riscrivere la storia di `auto-claude`.

Anti-obiettivi (il lavoro fallisce anche se «funziona»):
- una correzione senza il test che la dimostra, o un test scritto dopo la correzione e mai visto
  fallire;
- contare come superata una prova reale fallita o simularne l'esito;
- cambiare un testo di prompt oltre a quanto deciso (solo il gradino 2 di R-A1 e la riga di R-A8);
- merge non in avanzamento rapido, `--force`, push non richiesti.

## 3. Vincoli

- Tutto su `auto-claude`: un commit su `dev` prima dell'integrazione impedirebbe l'avanzamento
  rapido.
- Conventional Commits in italiano; prima di ogni commit `git status`, controllo del diff, staging
  selettivo; nessuna credenziale versionata.
- TDD per ogni correzione di comportamento: test che fallisce, correzione minima, test verde, suite
  senza modello verde, commit. Per le correzioni solo di documentazione non c'è test.
- Prove reali attivate esplicitamente; regola del §5 della specifica di revisione: una prova reale
  fallita si ripete una volta; se passa è «instabile» e si annota, se fallisce di nuovo è un problema.
- Nel resoconto si distingue sempre il modello simulato (test senza LM Studio) dal modello vero.
- Comandi da PowerShell nella radice, Python da `.\.venv\Scripts\python.exe`.

## 4. Approcci (decisi dall'utente il 2026-11-15)

| Problema | Approccio scelto | Scartato e perché |
|---|---|---|
| R-B1 | **A**: normalizzare all'uscita, nel nodo `llm`, le chiamate a strumento del modello; il controllo d'ingresso di `agent.py` resta severo | **B**, allargare il controllo d'ingresso: lascerebbe nella cronologia chiamate che LM Studio potrebbe rifiutare |
| R-A1 | **A a tre gradini**: controllo di merito; poi una sola modifica generale a `spiega`; poi evidenza registrata come non soddisfatta | **B**, solo registro senza tentativi |
| Minori e scelte «da decidere» | 12 da correggere; 17 problemi come debito noto (§6), R-D1 con la documentazione corretta | — |

## 5. Correzioni

Per ognuna: **problema**, **atteso**, **test** (modello simulato, scritto prima e visto fallire),
**prova reale** (con LM Studio, Docker, PostgreSQL o browser, se serve). Le prove reali indicate qui
si eseguono nel punto del piano della correzione quando sono brevi; la suite completa si ripete in
F6 (§9).

### 5.1 Gravi

**R-C1 · PostgreSQL di prova esposto sulla rete**
- Problema: il `docker run` del README pubblica la porta 5433 su tutte le interfacce, con la
  password `labprova` scritta nel README e in `CLAUDE.md`.
- Atteso: il comando del README pubblica solo `127.0.0.1:5433:5432`; il container
  `assistente-postgres` viene ricreato con quel comando (`docker rm -f` elimina le chat di prova, che
  sono solo dati di prova). La password `labprova` resta nei documenti: vale solo per un container
  di prova raggiungibile da questo computer, e il README lo dice. Nel diario, accanto al comando
  storico, una nota che rimanda al comando corretto (la riga storica non si riscrive).
- Test: un test sul testo (in `tests/test_docker.py`) che ogni `-p` dei `docker run` del README e
  ogni porta di `compose.yaml` comincino con `127.0.0.1:`. Oggi fallisce sul README.
- Prova reale: `docker port assistente-postgres` → solo `127.0.0.1:5433`; poi le prove reali del
  back-end in F6 girano su questo container.

**R-B1 · L'agente restituisce cronologie che poi rifiuta**
- Problema: una chiamata a strumento malformata del modello (id vuoto o null, nome vuoto o null,
  due chiamate con lo stesso id) passa nel turno, finisce nella `history` della risposta `200` e al
  turno successivo dà `400 invalid_history`; nel back-end la chat resta inutilizzabile per sempre.
- Atteso: il nodo `llm`, subito dopo la risposta del modello, normalizza `tool_calls` e
  `invalid_tool_calls` prima di metterle nello stato:
  - ogni chiamata ha un id non vuoto e unico nel messaggio: si tiene il primo id valido, mentre
    quelli vuoti, null o già usati diventano un id nuovo generato dal programma;
  - una chiamata senza nome (vuoto o null) riceve il nome segnaposto `unnamed_tool`, che non è uno
    strumento: il nodo `tools` risponde con l'errore «Strumento sconosciuto: 'unnamed_tool'.» come
    per ogni nome sconosciuto, e il turno continua;
  - per ogni chiamata cambiata, una riga WARNING con l'id nuovo e l'id e il nome originali (in JSON);
  - il messaggio rimandato a LM Studio nello stesso turno porta gli id normalizzati, così le
    risposte degli strumenti corrispondono alle chiamate;
  - `messages_from_json` non cambia: resta severo.
- Test: con un modello finto che restituisce, una per caso, chiamate con id vuoto, id null, id
  ripetuto, nome vuoto in `tool_calls` e nome null in `invalid_tool_calls`:
  - a livello di grafo: messaggio nello stato con id unici e non vuoti, nome segnaposto, risposta
    dello strumento «Strumento sconosciuto», riga WARNING; la seconda chiamata al modello riceve gli
    id normalizzati;
  - a livello di servizio (`fake_service`): `POST /chat` dà `200` e la sua `history`, rimandata a
    `POST /chat`, dà `200` (oggi `400`); lo stesso con la `history` dell'evento `done` di
    `POST /chat/stream`;
  - gli eventi `tool_start` e `tool_end` dello streaming usano gli id normalizzati;
  - la richiesta che `langchain-openai` costruirebbe per LM Studio con quel messaggio usa gli id
    normalizzati (senza server; il modo esatto lo sceglie il piano).
- Prova reale (nuova, in processo, come `test_reviewer_rejects_an_imposed_partial_answer`): la prima
  risposta dell'agente è **imposta** con una chiamata senza nome e due chiamate con lo stesso id; poi
  il modello vero continua. Atteso: LM Studio accetta la cronologia normalizzata (nessun errore
  `400`), il turno finisce con una risposta, la cronologia supera `messages_to_json` →
  `messages_from_json`, e un secondo turno sulla stessa cronologia con il modello vero riesce. La
  chiamata malformata non si può provocare a comando dal modello vero: la sua origine resta provata
  solo con il modello simulato.

**R-A1 · Evidenza «risposta adeguata» dello Step 5 non dimostrata**
- Problema: CA-58 controlla solo che la risposta contenga «protocol» o «mcp», parole già presenti
  nella richiesta; la spiegazione del modello era sbagliata nel merito.
- Atteso, a tre gradini, ciascuno con la regola di ripetizione del §3:
  1. CA-58 (che passa ora dal servizio, vedi R-A2) aggiunge un controllo di merito: la risposta
     nomina almeno uno tra «server», «client», «strumenti esterni / tool», «fonti di dati / dati
     esterni» (l'elenco esatto lo fissa il piano, senza parole generiche come «contesto»,
     «protocollo» o «modello»). Il test stampa la risposta; Claude la legge e annota nel diario se
     la spiegazione è corretta. Se passa, l'evidenza è dimostrata.
  2. Se fallisce: una sola modifica generale al testo di `spiega` in `assistant/prompts.py`, la
     frase «Se non conosci bene l'argomento, dillo invece di inventare.» (nessun suggerimento su
     MCP); i test senza modello del testo del prompt si aggiornano prima della modifica. Si ripete
     CA-58.
  3. Se fallisce ancora: la modifica del gradino 2 si toglie (non ha dimostrato di servire); CA-58
     diventa un fallimento atteso documentato (`xfail` non stretto, motivo «limite del modello»,
     controllo di merito invariato); l'evidenza è registrata come **non soddisfatta per limite del
     modello** in `requisiti.md` (CA-58), nel rapporto (§6) e nel README (sezione «Prompt MCP»).
- Test: il controllo di merito è esso stesso una prova reale; con il modello simulato restano i test
  attuali del prompt.
- Prova reale: CA-58, una o due esecuzioni per gradino.

### 5.2 Importanti

**R-C2 · Back-end che può fermarsi al primo avvio di Compose**
- Problema: `pg_isready` senza `-h` vede pronto il server temporaneo dell'inizializzazione (solo
  socket Unix); il back-end può chiamare `init_db` troppo presto, uscire con 1 e restare fermo.
- Atteso: healthcheck di `postgres` con `pg_isready -h 127.0.0.1 -U … -d …`; servizio `backend` con
  `restart: unless-stopped`.
- Test: in `tests/test_docker.py`, sul risultato di `docker compose config`: healthcheck con
  `-h 127.0.0.1` e `restart: unless-stopped` per `backend` (saltato senza la CLI di Docker, come gli
  altri).
- Prova reale (F6): avvio con volumi vuoti sotto un nome di progetto temporaneo
  (`docker compose -p <temporaneo> up -d --build`, con il progetto normale spento per le porte):
  `postgres` healthy, `backend` attivo, `GET /chats` `200`, nessuna uscita del back-end nei log; poi
  `docker compose -p <temporaneo> down -v` (elimina solo i volumi del progetto temporaneo). La prova
  mostra che l'avvio funziona; la finestra della corsa è rara e non si riproduce a comando.

**R-A2 · Prove reali degli Step 4 e 5 solo in processo**
- Problema: CA-50, CA-51, CA-58 e CA-59 chiamano grafo e `resolve_prompt` direttamente; il percorso
  vero (CLI → `POST /chat` con `prompt`, preferenze lette in `service._serve`) non è provato con
  LM Studio.
- Atteso: due prove reali passano dal servizio avviato con `start_service`:
  - **CA-58** dalla CLI (`python -m assistant` con `AGENT_URL`): `/prompt spiega
    argomento="Model Context Protocol" livello=base`, poi `esci`; nel log del servizio
    `api request=chat kind=prompt`, `prompts/get name=spiega … status=ok`, router
    `category=conversation`, riga del revisore; risposta della CLI non vuota, non un rifiuto, con il
    controllo di merito di R-A1;
  - **CA-50** con `PREFERENCES_FILE` (fuso `America/New_York`) nell'ambiente del servizio:
    `POST /chat` «Che ore sono?» → `get_current_time` con `America/New_York` in `tools_used`,
    risposta con l'ora di quel fuso, riga `resources/read … status=ok` con il fuso nel log.
  Le versioni in processo di CA-50 e CA-58 sono sostituite da queste (stesso grafo, percorso più
  completo, suite non più lunga); CA-51 e CA-59 restano in processo (il percorso del servizio è
  provato dalle due sopra).
- Test: sono prove reali; con il modello simulato il percorso è già coperto.
- Prova reale: le due prove, insieme a R-A1.

**R-A3 · Diagnosi del README che mostra il file di preferenze sbagliato**
- Problema: lo snippet «Le preferenze non hanno effetto» chiama `server_command` senza il file delle
  preferenze, quindi legge sempre quello del pacchetto.
- Atteso: il parametro `preferences_file` di `server_command` diventa obbligatorio (come diceva la
  specifica delle preferenze, §5); lo snippet del README usa `PREFERENCES_FILE` se impostata,
  altrimenti il file del pacchetto, risolto come fa il servizio.
- Test: `server_command` senza `preferences_file` dà `TypeError` (oggi usa il predefinito); i test
  che lo chiamavano senza passano il file.
- Prova reale: lo snippet eseguito da PowerShell con `PREFERENCES_FILE` che indica un file
  temporaneo stampa il JSON di quel file (il README riporta solo comandi verificati).

### 5.3 Scelta cambiata in F3

**R-A8 · Ambito del router ristretto ai temi del laboratorio**
- Problema: la riga di `scope.txt` «spiegazioni di concetti di informatica, programmazione e
  intelligenza artificiale» rende in ambito qualsiasi domanda di informatica.
- Atteso: la riga diventa «spiegazioni dei concetti trattati nel laboratorio: modelli linguistici,
  agenti, strumenti, Model Context Protocol»; la riga dei riassunti resta. Nessun cambio a
  `ROUTER_PROMPT`.
- Test: un test che l'ambito predefinito contiene la riga nuova e non quella vecchia (fallisce prima
  della modifica).
- Prova reale (nuova, in processo): «Spiegami che cos'è il Model Context Protocol» →
  `category=conversation`; «Spiegami la differenza tra memoria RAM e disco rigido» →
  `category=out_of_scope` e rifiuto. Se il rifiuto non avviene nemmeno alla ripetizione, ci si ferma
  e si chiede all'utente (niente ritocchi al prompt del router di propria iniziativa). La suite reale
  completa di F6 controlla che le altre domande in ambito non diventino rifiuti.

### 5.4 Minori

**R-B5 · Tempo scaduto di LM Studio segnalato come «non raggiungibile»**
- Atteso: `openai.APITimeoutError` → stesso stato e codice di oggi (`503 model_unavailable`, per non
  cambiare il contratto), detail «LM Studio non ha risposto in tempo: …»; la connessione fallita
  resta «LM Studio non raggiungibile: …». Vale per `/chat` e per l'evento `error` di
  `/chat/stream`. README (diagnosi) allineato.
- Test: `fake_service` con un modello finto che solleva `APITimeoutError`, nei due endpoint.

**R-B10 · `POSTGRES_PASSWORD` passata ai container che non la usano**
- Atteso: `agent` e `assistant` tengono `env_file: .env` (servono le altre variabili) e impostano
  `POSTGRES_PASSWORD: ""` in `environment`, che ha la precedenza, con un commento; `backend` e
  `postgres` invariati.
- Test: in `tests/test_docker.py`, su `docker compose config` con il `.env` finto: `agent` e
  `assistant` con `POSTGRES_PASSWORD` vuota, `DATABASE_URL` del back-end con la password.
- Prova reale (F6): `docker compose exec agent printenv POSTGRES_PASSWORD` stampa una riga vuota.

**R-A4 · Preferenze lette all'avvio del servizio, non a inizio sessione**
- Atteso: `CLAUDE.md` (obiettivo, Step 4), RF-41 di `requisiti.md` e il README dicono «all'avvio del
  servizio dell'agente; una modifica vale dal riavvio del servizio». Solo documentazione.

**R-B7 · Risposte JSON senza `charset`**
- Problema: `Invoke-RestMethod` di PowerShell 5.1 storpia le lettere accentate («Ã¨»).
- Atteso: ogni risposta JSON di agente e back-end (successi, errori `ApiError`, `422` di FastAPI)
  ha `Content-Type: application/json; charset=utf-8`; le risposte `text/event-stream` non cambiano.
  Il modo (classe di risposta o middleware) lo sceglie il piano, preferendo quello che non cambia
  il contratto `frontend/backend-openapi.json`; se cambia, si rigenera con `UPDATE_CONTRACT=1`.
- Test: con `TestClient`, intestazione esatta su un successo, un errore e un `422`, per ciascun
  servizio.
- Prova reale (F6): da PowerShell 5.1, `Invoke-RestMethod` su `GET /chats/{id}` di una chat con
  lettere accentate mostra «è».

**R-C3 · Carattere NUL nei testi del back-end**
- Problema: un `\x00` nella domanda fa fallire psycopg → `500`, con i parametri SQL (il testo della
  domanda) nel log.
- Atteso: `ChatStore` rifiuta `\x00` nel messaggio e nel titolo con `InvalidInputError` («… contiene
  un carattere non ammesso (NUL)») → `400 invalid_request`, anche nello streaming prima del flusso;
  `create_db_engine` crea il motore con `hide_parameters=True`, così nessun errore del database
  scrive i valori nel log.
- Test: archivio e API su SQLite (oggi SQLite accetta il NUL: il test fallisce); motore con
  `hide_parameters` attivo.
- Prova reale: i test dell'archivio girano anche su PostgreSQL con `TEST_DATABASE_URL` (F6).

**R-C6 · `AgentClient.chat` con 600 s anche per la connessione**
- Atteso: `chat` usa 10 s per la connessione e 600 s per il resto, come `chat_stream`; una sola
  costante per i 10 s di connessione.
- Test: con un trasporto finto di httpx, i timeout della richiesta di `chat` sono
  `connect=10`, gli altri 600.

**R-A5 · Messaggio di `prompt_unavailable` nella CLI**
- Problema: «Errore: il prompt 'spiega' non è disponibile (… avanzato.). Riprova.»: punteggiatura
  doppia, «Riprova» inutile, nessun rimando a `/prompts`.
- Atteso: il motivo tra parentesi perde il punto finale (`PromptGetError`); la CLI scrive per
  `prompt_unavailable` «Errore nel prompt: il prompt 'spiega' non è disponibile (Livello non
  valido: 'esperto'. Valori ammessi: base, intermedio, avanzato). Scrivi /prompts per l'elenco dei
  prompt.».
- Test: `test_commands.py` (testo dell'errore senza punto finale tra parentesi) e `test_terminal.py`
  (riga esatta).

**R-D6 · Messaggio d'errore dell'agente ripetitivo nella pagina**
- Problema: «L'assistente ha risposto con un errore: l'agente ha risposto con un errore
  (model_unavailable): …».
- Atteso: il back-end mette nel detail di `502 agent_error` solo il detail dell'agente e scrive il
  codice dell'agente nella riga di log (causa); la pagina mostra «L'assistente non è riuscito a
  rispondere (LM Studio non raggiungibile: Connection error). La domanda è salvata nella chat:
  riprova.». Stesso testo per l'evento `error` dello streaming. README allineato.
- Test: test del back-end (detail e riga di log, anche nello streaming) e test Node di
  `errorMessage`.

**R-A6 · Nome del prompt nel log senza escape**
- Atteso: la riga `api request=chat|chat_stream kind=prompt name=…` scrive il nome in JSON
  (`name="spiega"`), così un `\n` non crea righe false. README allineato.
- Test: con un nome che contiene `\n`, la riga di log è una sola e contiene `name="a\nb"`.

**R-A7 · Argomenti dei prompt senza limite di lunghezza**
- Atteso: il servizio, prima di cronologia e `prompts/list`, rifiuta con `400 prompt_rejected`
  (che la CLI mostra già come «Errore nel comando: … Scrivi /prompts …») un nome di prompt oltre 64
  caratteri, più di 10 argomenti, un nome di argomento oltre 64 caratteri o un valore oltre 1000
  caratteri; il detail nomina l'argomento e il limite, non il valore. Così nessuna riga di log
  contiene argomenti oltre questi limiti.
- Test: `fake_service`, per ogni limite: `400 prompt_rejected`, nessuna chiamata a `prompts/list` né
  a `prompts/get`, valore assente dal log; ai limiti esatti la richiesta passa. Anche per
  `/chat/stream`.

**R-A10 · `/prompt` nella pagina**
- Atteso: una riga nel README (sezione del front-end): nella pagina «/prompt …» è una domanda
  normale al modello; i comandi esistono solo nella CLI. Solo documentazione.

**R-C9 · Comandi delle prove reali del back-end in `CLAUDE.md`**
- Atteso: `CLAUDE.md` riporta `.\.venv\Scripts\python.exe -m pytest …` anche per le prove reali del
  back-end. Solo documentazione.

### 5.5 Debito con documentazione corretta

**R-D1 · Pagina chiusa durante lo streaming**
- Problema: specifica dello streaming (§1 e §6), README (diagnosi) e requisiti dicono che il
  back-end smette di leggere e chiude il flusso dell'agente; in realtà se ne accorge solo quando
  prova a scrivere l'evento successivo, e se nel frattempo il turno finisce salva la risposta con
  `outcome=done`.
- Atteso: prima di riscrivere i testi, il comportamento vero si osserva con uno script temporaneo
  nella scratchpad (back-end con un agente finto lento, client che chiude il flusso a metà) e si
  annota nel diario; poi specifica dello streaming, README e requisiti descrivono quello osservato
  (risposta salvata se il turno finisce, `client_gone` solo quando la scrittura di un evento
  fallisce, rischio di due turni se l'utente rimanda la domanda: R-C4). Nessuna modifica al codice.
  Il debito va in `TODO.md` (§6).

## 6. Debiti noti (in `TODO.md` in F5, con il motivo)

| Id | Motivo |
|---|---|
| R-D1 | Salvare la risposta anche a pagina chiusa è utile; un endpoint asincrono che chiude il flusso è un lavoro grande (documentazione corretta in F4) |
| R-A11 | La traccia chiede «lingua o stile»: la prova sulla lingua basta |
| R-B6 | Le risposte del modello variano: un'uguaglianza esatta CLI/API sarebbe instabile |
| R-C4 | Invii contemporanei nella stessa chat: raro con un solo utente, documentato; va con R-D1 |
| R-C10 | Evidenze di Compose nel diario; streaming da Compose ripetuto il 2026-11-15 |
| R-D3 | Testo che torna nel campo dopo un tempo scaduto: raro, la domanda non si perde |
| R-P1 | Markdown e LaTeX mostrati così come sono: servirebbe una libreria o un'istruzione nel prompt, che rischia di far perdere l'uso degli strumenti |
| R-A9, R-B2, R-B3, R-B4, R-B9, R-C5, R-C8, R-D2, R-D4, R-D5 | Minori confermati che l'utente ha scelto di non correggere ora (descrizione nel rapporto §3) |

## 7. Revisione delle correzioni

- Alla fine di F4, un revisore con contesto pulito (subagente in sola lettura, che può eseguire i
  test senza modello) legge il diff delle correzioni (dal commit di questa specifica alla fine di
  F4), con questa specifica e il rapporto. Cerca: correzioni che non risolvono il problema, test che
  non lo dimostrano, regressioni, problemi nuovi; stessi livelli di gravità del rapporto.
- Claude verifica ogni problema segnalato sul codice. Un grave o importante confermato si corregge
  (con il suo test) e si rivede solo quella correzione; i minori nuovi si presentano all'utente,
  che decide se correggerli o metterli in `TODO.md`.
- Al massimo due giri: se dopo il secondo resta un grave o importante aperto, ci si ferma e si
  chiede all'utente.
- Esito nel rapporto (sezione nuova «Revisione delle correzioni») e nel diario.

## 8. F5 · Sistemazione dei file del loop

Come la specifica di revisione §6.5, su `auto-claude`:
- `CLAUDE.md`: la sezione «Modalità autonoma» diventa una nota storica di due righe; restano le
  regole normali (lavoro su `dev`, approvazioni); struttura e comandi allineati alle correzioni;
- `loop.sh` e `PROMPT.md` → `_archivio/` con `git mv`;
- `TODO.md`: punti fatti in «Già fatto»; una sezione «Debiti noti» con la tabella del §6; nessun
  altro punto aperto;
- `PROGRESS.md`: sezioni F4–F6, nota sui messaggi dei commit del loop, «Stato attuale» aggiornato;
- `docs/superpowers/prossimo-prompt.txt` aggiornato per la sessione dopo l'integrazione, o archiviato
  se non serve;
- README: `assistente-postgres` descritto come container separato da Compose, usato solo dalle
  prove reali del back-end (porta 5433 su `127.0.0.1`).

## 9. F6 · Verifica finale e integrazione

Il codice è cambiato dopo F2, quindi si ripete tutto (specifica di revisione §6.6, punto 1):
1. **Modello simulato:** `pytest` tutto verde; `pytest -m browser` con Edge e con
   `BROWSER_CHANNEL=chrome`.
2. **Modello vero (LM Studio, `google/gemma-4-e2b`; PostgreSQL in `assistente-postgres` su
   `127.0.0.1:5433`; Compose spento):** `pytest -m real -v` completa con Edge, comprese le prove
   nuove (R-B1, R-A8, CA-50 e CA-58 dal servizio); con Chrome `-k frontend`.
3. **Docker:** `docker port assistente-postgres` (R-C1); avvio con volumi vuoti sotto un progetto
   temporaneo (R-C2); `docker compose up -d --build` del progetto normale, streaming dalla pagina con
   una domanda con strumento (come F2, punto 3), `printenv POSTGRES_PASSWORD` nell'agente (R-B10),
   `Invoke-RestMethod` da PowerShell 5.1 (R-B7).
4. Controllo dei criteri del §10; resoconto all'utente con eseguito, esito, prove instabili e che
   cosa resta non dimostrato.
5. `git switch dev`, `git merge --ff-only auto-claude`, `pytest` su `dev`.
6. Solo su richiesta dell'utente: `git push origin dev`, `git push origin dev:main`,
   `git fetch origin main:main`; se l'avanzamento rapido viene rifiutato, fermarsi e chiedere. Dopo
   il push, su conferma dell'utente, cancellare o tenere `auto-claude`.

## 10. Criteri di uscita

Quelli del §7 della specifica di revisione, con questi dettagli:
1. R-C1, R-B1 e R-A1 chiusi (R-A1 anche al gradino 3, come evidenza registrata non soddisfatta);
   R-C2, R-A2, R-A3, R-A8 e i 12 minori corretti, ciascuno con il suo test o la sua prova; R-D1
   documentato; debiti del §6 in `TODO.md`.
2. Revisione delle correzioni senza gravi o importanti aperti (§7).
3. Dopo l'ultima modifica al codice: test senza modello verdi, suite reale senza fallimenti
   confermati, pagina con Edge e Chrome, streaming con Compose, prove Docker del §9; prove
   instabili elencate.
4. Integrazione solo in avanzamento rapido, test verdi su `dev`, push solo su richiesta.

## 11. Scelte del progettista (da controllare nell'approvazione)

- R-B1: nome segnaposto `unnamed_tool` (identificativo inglese, accettato come nome di funzione);
  id nuovi generati dal programma; WARNING per ogni chiamata cambiata.
- R-A1: elenco delle parole di merito senza termini generici; al gradino 3 si toglie la modifica
  del gradino 2.
- R-A2: le versioni in processo di CA-50 e CA-58 sono sostituite da quelle dal servizio; CA-51 e
  CA-59 restano in processo.
- R-A8: domanda di prova fuori ambito «Spiegami la differenza tra memoria RAM e disco rigido».
- R-A7: limiti 64 caratteri per i nomi, 10 argomenti, 1000 caratteri per un valore; codice
  `prompt_rejected`.
- R-B5: codice e stato invariati, cambia solo il detail.
- R-B10: password svuotata con `environment` invece di sostituire `env_file` con un elenco di
  variabili (ogni altra variabile del `.env` continua ad arrivare all'agente).
- R-C1: `labprova` resta nei documenti, perché il container è raggiungibile solo da questo computer.
- R-D1: comportamento osservato con uno script temporaneo, non con un test versionato.

## 12. Lasciato al costruttore del piano

- Ordine dei task e raggruppamento in commit (un commit per correzione o per piccoli gruppi dello
  stesso file).
- Modo di imporre il charset (R-B7) e di verificare la richiesta di `langchain-openai` (R-B1).
- Elenco esatto delle parole di merito (R-A1) e testi esatti dei detail nuovi.
- Nome del progetto temporaneo per la prova di R-C2.

## 13. Rischi

- **LM Studio rifiuta la cronologia normalizzata** (per esempio il nome `unnamed_tool`): la prova
  reale di R-B1 lo scopre; in quel caso ci si ferma e si chiede all'utente, perché cambierebbe
  l'approccio.
- **Ambito ristretto che produce falsi rifiuti** in altre prove reali: si vedono nella suite di F6 e
  si portano all'utente.
- **Prove reali lunghe:** la suite completa dura circa 50 minuti, più le prove Docker; con le
  ripetizioni di R-A1 si aggiungono 5–15 minuti.
- **NUL nella risposta del modello:** dopo R-C3 resterebbe un `500` su PostgreSQL al salvataggio
  della risposta, senza il testo nel log; caso molto improbabile, non corretto.
- **Revisione delle correzioni che apre altri problemi:** limite di due giri (§7).

## 14. Costi stimati

| Fase | Tempo | Note |
|---|---|---|
| F4 | 3–5 ore di sessione | 20 correzioni, quasi tutte piccole, prove reali brevi di R-A1, R-A2, R-A8, R-B1, R-A3 |
| Revisione delle correzioni | 30–45 min, 200.000–400.000 token | Uno o due giri |
| F5 | 15–30 min | |
| F6 | circa 90 min | Soprattutto attesa del modello e di Docker |
