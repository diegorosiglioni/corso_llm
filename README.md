# Assistente del laboratorio

Applicazione Python da terminale che conversa con un modello locale servito da LM Studio,
organizzata in un grafo LangGraph esplicito. Il modello usa un orologio locale e sette strumenti
offerti da un server MCP locale (FastMCP, stdio): convertitore di unità, calcolatrice, catalogo
dei corsi e note persistenti. Prima dell'agente un router LLM controlla che la domanda rientri
nell'ambito dell'assistente: le domande fuori ambito ricevono un rifiuto senza raggiungere l'agente.
Dopo l'agente un revisore LLM controlla che la risposta sia coerente con la domanda; se non lo è,
il motivo torna all'agente, che riscrive la risposta (al più `MAX_REVIEWS` revisioni per turno).
All'inizio di ogni turno, quando la cronologia supera `SUMMARY_MAX_MESSAGES` messaggi, un nodo
riassunto comprime i turni vecchi in un riassunto che agente, router e revisore ricevono nel prompt
di sistema. All'avvio l'applicazione legge dal server MCP la resource `utente://preferenze` (lingua
delle risposte, fuso orario predefinito, stile) e la mette in cima al prompt di sistema dell'agente.
Il server MCP offre anche due prompt riusabili, `spiega` e `riassumi_conversazione`, che l'utente
richiama dal terminale con i comandi `/prompts` e `/prompt`.
Grafo, server MCP e modelli girano in un **servizio HTTP dell'agente** (FastAPI, senza stato,
documentato con OpenAPI); il terminale è un **client** di quel servizio e conserva cronologia e
riassunto della conversazione.
Un **back-end** separato (FastAPI, `python -m backend`) salva chat e messaggi in PostgreSQL e
chiama l'agente con la cronologia salvata: le chat restano dopo il riavvio.
Un **front-end** (`python -m frontend`) serve una pagina di chat per il browser che parla solo con il
back-end: elenco, creazione ed eliminazione delle chat, messaggi con gli strumenti usati, risposta
mostrata mentre arriva (streaming con Server-Sent Events).
Con **Docker Compose** front-end, back-end, agente e PostgreSQL girano ciascuno nel proprio container
(`docker compose up -d --build`, sezione «Docker»).

Requisiti e specifica: [`docs/superpowers/`](docs/superpowers/).

## Requisiti dell'host

- Python 3.13 (con il launcher `py` su Windows)
- LM Studio con il modello caricato e il server avviato
- Docker Desktop (per l'avvio con Docker Compose e per PostgreSQL del back-end)

## Installazione

Tutti i comandi si eseguono in PowerShell dalla radice della repository.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
```

Si usa direttamente `.\.venv\Scripts\python.exe`, senza attivare l'ambiente: così la execution
policy di PowerShell non interferisce. `requirements.txt` contiene le dipendenze
dell'applicazione, `requirements-dev.txt` aggiunge quelle dei test.

`requirements.txt` richiama `constraints.txt`, che fissa tutte le versioni verificate, anche le
indirette: così venv e immagine Docker installano gli stessi pacchetti. Il file si rigenera dal
venv in cui passano test e prove reali:

```powershell
@("# Versioni verificate: rigenerare con il comando del README, sezione Installazione.") + (.\.venv\Scripts\python.exe -m pip freeze) | Out-File -Encoding ascii constraints.txt
```

Per cambiare una versione: aggiornare i requirements, svuotare `constraints.txt`, reinstallare,
ripetere le verifiche e rigenerarlo.

## Test automatici

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Non richiedono LM Studio né la rete: il modello è sostituito da un modello finto con risposte
programmate (anche per router e revisore). I test del server MCP lo avviano davvero come
sottoprocesso stdio, con l'archivio delle note in una cartella temporanea (circa 1 s per test).
Il servizio HTTP si prova con l'app vera su un grafo finto, senza rete (`TestClient`), e la CLI
parla con quella stessa app. Il back-end si prova su SQLite in memoria, con lo stesso schema, senza
PostgreSQL. Il JavaScript della pagina del front-end si prova con Node.js (`node --test`, lanciato
da `pytest`; senza Node il test si salta col motivo). I Dockerfile si controllano come testo, senza
costruire immagini, e `compose.yaml` con `docker compose config` su una copia con un `.env` di
credenziali finte, senza il demone (`tests/test_docker.py`; senza la CLI di Docker questi test si
saltano col motivo). Esito al 2026-11-14: `1003 passed, 90
deselected` (le 90 deselezionate sono le 65 prove reali, 27 con LM Studio e 38 test dell'archivio
ripetuti su PostgreSQL, e i 25 test nel browser).

La pagina vera nel browser installato (Edge; Chrome con `$env:BROWSER_CHANNEL = "chrome"`), pilotato
da Playwright senza finestra, con il back-end vero su SQLite in memoria, un agente finto (risposta con
uno strumento, risposta lenta, agente spento o in errore, eventi dello streaming con pause scelte dal
test: bozza a pezzi, strumento in corso, `reset` del revisore, errore durante il flusso) e nessun
browser da scaricare:

```powershell
.\.venv\Scripts\python.exe -m pytest -m browser
```

Esito al 2026-11-14: `25 passed` in circa 10 s (anche con Chrome).

## Configurazione

L'applicazione legge variabili d'ambiente e il file con l'ambito dell'assistente:

| Variabile | Obbligatoria | Default | Significato |
|-----------|--------------|---------|-------------|
| `LMSTUDIO_BASE_URL` | sì | — | indirizzo dell'API di LM Studio, es. `http://localhost:1234/v1` |
| `LMSTUDIO_MODEL` | sì | — | identificativo del modello restituito da `GET /v1/models` |
| `MAX_STEPS` | no | `5` | chiamate massime al modello dell'agente in un turno (intero ≥ 1), riscritture comprese; router e revisore non contano |
| `MAX_REVIEWS` | no | `2` | chiamate massime al revisore in un turno (intero ≥ 1); con `2` l'agente riscrive al più una volta |
| `SUMMARY_MAX_MESSAGES` | no | `20` | messaggi della cronologia (domanda appena arrivata compresa) oltre i quali si riassume (intero ≥ 1) |
| `SUMMARY_KEEP_MESSAGES` | no | `6` | messaggi recenti conservati come minimo dopo un riassunto (intero ≥ 1, minore di `SUMMARY_MAX_MESSAGES`) |
| `LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING` o `ERROR` |
| `NOTES_DB` | no | `data/notes.sqlite3` | file SQLite delle note, relativo alla cartella di avvio |
| `SCOPE_FILE` | no | `assistant/data/scope.txt` del pacchetto | file di testo (UTF-8) con l'ambito dell'assistente; un percorso relativo vale dalla cartella di avvio |
| `PREFERENCES_FILE` | no | `assistant/data/preferenze.json` del pacchetto | file JSON delle preferenze dell'utente, letto dal server MCP (sezione «Preferenze dell'utente»); un percorso relativo vale dalla cartella di avvio; un file mancante non blocca l'avvio |
| `AGENT_HOST` | no | `127.0.0.1` | indirizzo su cui ascolta il servizio HTTP dell'agente (`0.0.0.0` per accettare connessioni da altri computer o container) |
| `AGENT_PORT` | no | `8000` | porta del servizio HTTP dell'agente (intero tra 1 e 65535) |
| `AGENT_URL` | no | `http://127.0.0.1:8000` | indirizzo del servizio dell'agente per la CLI (`http://` o `https://`) |

Il servizio dell'agente (`python -m assistant.service`) legge tutte le variabili tranne
`AGENT_URL`; la CLI (`python -m assistant`) legge solo `AGENT_URL` e `LOG_LEVEL`.

`.env.example` è il modello versionato; la copia reale `.env` resta fuori da Git ed è letta da
Docker Compose:

```powershell
Copy-Item .env.example .env
```

**Un `.env` creato prima della lezione 5 va aggiornato a mano:** `LMSTUDIO_MODELLO` diventa
`LMSTUDIO_MODEL` e `MAX_PASSI` diventa `MAX_STEPS`. Con i nomi vecchi l'avvio con Docker si ferma
con «Configurazione non valida: Manca LMSTUDIO_MODEL.».

In locale Python non legge `.env`: le variabili si impostano nella sessione di PowerShell.

```powershell
$env:LMSTUDIO_BASE_URL = "http://localhost:1234/v1"
$env:LMSTUDIO_MODEL = "google/gemma-4-e2b"
```

Se manca una variabile obbligatoria, un valore non è valido o il file dell'ambito manca o è vuoto,
il servizio non parte, elenca i problemi su stderr ed esce con codice 1 (lo stesso fa la CLI con
`AGENT_URL` o `LOG_LEVEL` non validi):

```powershell
Remove-Item Env:LMSTUDIO_MODEL
.\.venv\Scripts\python.exe -m assistant.service
$LASTEXITCODE    # 1
```

## Avvio locale

Servono due terminali PowerShell nella radice della repository: uno per il servizio dell'agente,
uno per la CLI.

**1. Servizio dell'agente** (LM Studio avviato, modello caricato, variabili di LM Studio impostate):

```powershell
.\.venv\Scripts\python.exe -m assistant.service
```

La riga `api listening=http://127.0.0.1:8000 docs=/docs …` nel log indica che il servizio è pronto;
si ferma con Ctrl+C. Il servizio avvia il server MCP, legge le preferenze e tiene aperti i modelli,
ma non conserva nessuna conversazione. I log del grafo, degli strumenti e di MCP compaiono qui, con
una riga per ogni richiesta e risposta HTTP (`api request=chat …`, `api response=chat status=200
tools=calculate … duration_ms=…`). LM Studio spento non impedisce l'avvio: lo segnalano `/status` e
le risposte della conversazione.

**2. CLI** (non servono le variabili di LM Studio; `AGENT_URL` solo se il servizio non è su
`http://127.0.0.1:8000`):

```powershell
.\.venv\Scripts\python.exe -m assistant
```

All'avvio la CLI chiede `GET /status`: se il servizio non risponde esce con codice 1 e «Agente non
disponibile: agente non raggiungibile su http://127.0.0.1:8000. Avvia il servizio con: python -m
assistant.service»; se il server MCP o il modello non sono disponibili mostra «Attenzione: …» e apre
comunque la conversazione.

Si conversa al prompt `Tu>`. La sessione termina con `esci`, con Ctrl+Z seguito da Invio
(fine input su Windows) o con Ctrl+C. La cronologia (e l'eventuale riassunto) vive nella CLI e vale
solo per la sessione in corso: a ogni turno la CLI la manda al servizio e riceve quella aggiornata.
La conversazione va su stdout, i log su stderr.
Il testo che comincia con `/` è un comando e non arriva al modello: `/prompts` elenca i prompt del
server MCP (nome, descrizione e argomenti); `/prompt nome chiave=valore` richiama un prompt (valori
con spazi tra virgolette doppie, per esempio
`/prompt spiega argomento="Model Context Protocol" livello=base`): un errore di sintassi lo blocca
la CLI, un argomento obbligatorio mancante o sconosciuto lo blocca il servizio, in entrambi i casi
senza chiamare il modello; altrimenti i messaggi del prompt entrano nella cronologia e passano dal
grafo come una domanda. Un comando sconosciuto dà «Comando sconosciuto». Dettagli nella sezione
«Prompt MCP: comandi della CLI».

Per una prova non interattiva si possono passare le domande in ingresso (con il servizio avviato):

```powershell
"Mi chiamo Paolo", "Come mi chiamo?", "esci" | .\.venv\Scripts\python.exe -m assistant
```

### API HTTP dell'agente

Il documento OpenAPI è su `http://127.0.0.1:8000/openapi.json` e la pagina interattiva su
`http://127.0.0.1:8000/docs`. Endpoint:

- `POST /chat`: un turno, aperto da `message` oppure da `prompt` (`{"name", "arguments"}`), con
  `history` e `summary` ricevuti dal turno precedente; risponde con `reply`, `tools_used` (nome,
  argomenti, risultato ed esito di ogni strumento eseguito), `history` e `summary` aggiornati.
- `GET /prompts`: i prompt MCP (`prompts/list`).
- `GET /status`: `200` se server MCP e modello sono disponibili, `503` con il motivo altrimenti.

Gli errori hanno il corpo `{"error": "<codice>", "detail": "<messaggio>"}`: `400` richiesta,
cronologia o prompt non validi; `502` errore di LM Studio o prompt non ottenibile; `503` LM Studio o
server MCP non raggiungibili; `500` errore imprevisto (dettagli solo nel log). Un errore non cambia
cronologia e riassunto del chiamante. Formato dei messaggi e tabella completa nella
[specifica](docs/superpowers/specs/2026-11-14-servizio-http-design.md) (§4 e §6).

```powershell
Invoke-RestMethod http://127.0.0.1:8000/status
Invoke-RestMethod http://127.0.0.1:8000/chat -Method Post -ContentType "application/json" -Body '{"message": "Quanto fa 17 * 23?"}'
```

### Back-end: chat salvate su PostgreSQL

Il back-end (`python -m backend`) è un servizio distinto dall'agente: salva chat e messaggi in
PostgreSQL e, per ogni messaggio, chiama l'agente via HTTP con la cronologia e il riassunto salvati
nella chat. Le chat restano dopo il riavvio del back-end. Servono tre processi: PostgreSQL (qui in
un container), il servizio dell'agente (punto 1 di «Avvio locale») e il back-end.

| Variabile | Obbligatoria | Default | Significato |
|-----------|--------------|---------|-------------|
| `DATABASE_URL` | sì | — | database PostgreSQL, `postgresql+psycopg://utente:password@host:porta/nome` (anche `postgresql://…`) |
| `AGENT_URL` | no | `http://127.0.0.1:8000` | indirizzo del servizio dell'agente |
| `BACKEND_HOST` | no | `127.0.0.1` | indirizzo su cui ascolta il back-end |
| `BACKEND_PORT` | no | `8001` | porta del back-end (intero tra 1 e 65535) |
| `LOG_LEVEL` | no | `INFO` | come per l'agente |
| `CORS_ORIGINS` | no | `http://127.0.0.1:8080,http://localhost:8080` | origini (`http(s)://host[:porta]`, separate da virgola) delle pagine del front-end che possono chiamare il back-end dal browser |

**PostgreSQL in un container** (immagine ufficiale; utente, password e nome sono d'esempio). Sulla
porta 5432 dell'host può esserci già un PostgreSQL installato: il comando pubblica il container
sulla 5433.

```powershell
docker run -d --name assistente-postgres -e POSTGRES_USER=lab -e POSTGRES_PASSWORD=labprova -e POSTGRES_DB=assistente -p 5433:5432 postgres:18.6
docker exec assistente-postgres pg_isready -U lab -d assistente    # «accepting connections»
```

I dati restano nel container (anche dopo `docker stop assistente-postgres` e
`docker start assistente-postgres`); `docker rm -f assistente-postgres` lo elimina con le chat.
Con Docker Compose PostgreSQL è invece il servizio `postgres`, con i dati nel volume `postgres-data`
(sezione «Docker»); è un database distinto da quello di questo container.

**Avvio del back-end**, in un terzo terminale (servizio dell'agente già avviato):

```powershell
$env:DATABASE_URL = "postgresql://lab:labprova@127.0.0.1:5433/assistente"
.\.venv\Scripts\python.exe -m backend
```

All'avvio crea le tabelle `chats` e `chat_messages` se mancano (i dati esistenti restano) e scrive
`backend listening=http://127.0.0.1:8001 docs=/docs agent_url=… database=postgresql+psycopg://lab:***@… cors_origins=…`
(la password non compare mai nei log). Con il database spento esce con codice 1 e «Database non
raggiungibile: …»; l'agente spento invece non blocca l'avvio.

OpenAPI su `http://127.0.0.1:8001/openapi.json`, pagina interattiva su `http://127.0.0.1:8001/docs`.
Endpoint: `POST /chats` (corpo `{"title": "…"}` facoltativo; senza titolo lo prende dalla prima
domanda), `GET /chats` (titolo e data dell'ultimo messaggio, la più recente prima),
`GET /chats/{chat_id}` (messaggi in ordine, con gli strumenti usati), `DELETE /chats/{chat_id}`
(con i messaggi) e `POST /chats/{chat_id}/messages` (corpo `{"content": "…"}`: salva la domanda,
chiama l'agente, salva e restituisce domanda e risposta).

```powershell
$chat = Invoke-RestMethod http://127.0.0.1:8001/chats -Method Post
Invoke-RestMethod "http://127.0.0.1:8001/chats/$($chat.id)/messages" -Method Post -ContentType "application/json" -Body '{"content": "Quanto fa 17 * 23?"}'
Invoke-RestMethod http://127.0.0.1:8001/chats
(Invoke-RestMethod "http://127.0.0.1:8001/chats/$($chat.id)").messages | Format-Table role, content
```

Gli errori hanno il corpo `{"error", "detail"}`: `400 invalid_request` (titolo oltre 200 caratteri,
messaggio vuoto), `404 chat_not_found`, `503 agent_unavailable` (agente non raggiungibile), `504
agent_timeout`, `502 agent_error` (l'agente ha risposto con un errore, per esempio LM Studio
spento), `503 database_unavailable`, `500 internal_error`. Con un errore dell'agente la domanda
resta nella chat senza risposta e lo stato dell'agente della chat non cambia: si può rimandare il
messaggio. Dettagli nella [specifica](docs/superpowers/specs/2026-11-14-backend-chat-design.md)
(§5–§7).

### Streaming della risposta (Server-Sent Events)

Accanto agli endpoint precedenti, che non cambiano (la CLI usa sempre `POST /chat`), agente e
back-end offrono lo stesso turno in streaming, come `text/event-stream` con lo stesso corpo della
richiesta:

- agente: `POST /chat/stream` (corpo di `POST /chat`);
- back-end: `POST /chats/{chat_id}/messages/stream` (corpo `{"content": "…"}`), che inoltra il
  flusso dell'agente e salva la risposta solo alla fine.

Eventi (nome e oggetto JSON): `question` (solo back-end, primo: la domanda salvata), `text`
`{delta}` (un pezzo del testo dell'agente; router, revisore e riassunto non ne producono), `reset`
`{reason, detail}` (il testo arrivato dall'ultimo reset non sarà la risposta: `tools` se l'agente
chiama strumenti, `review` se il revisore la respinge, con il motivo), `tool_start` `{id, name,
args}`, `tool_end` `{id, name, args, result, ok}`, e per ultimo `done` (agente: il corpo di
`POST /chat`; back-end: `{question, answer}` salvati) oppure `error` `{error, detail}`. Ogni 15 s
senza eventi arriva un commento `: ping`.

**Bozza o sola risposta approvata**: il testo si mostra mentre l'agente lo scrive, come bozza che
può ancora cambiare; se il revisore la respinge arriva `reset` `review` e poi la riscrittura. Nel
database entra solo la risposta finale di `done`. Gli errori scoperti prima del flusso (richiesta,
chat inesistente, database, agente non raggiungibile) restano risposte JSON con gli stessi codici
degli endpoint senza streaming; quelli durante il turno arrivano come evento `error`, con la domanda
salvata senza risposta. Il back-end aspetta l'agente al massimo 60 s senza dati e 600 s per il
turno (`agent_timeout`). Dettagli nella
[specifica](docs/superpowers/specs/2026-11-14-streaming-design.md).

### Front-end: la chat nel browser

Il front-end (`python -m frontend`) serve una pagina in HTML, CSS e JavaScript, senza framework,
che parla solo con il back-end: il browser lo chiama direttamente all'indirizzo `BACKEND_URL`,
ammesso dal back-end con `CORS_ORIGINS`. La pagina elenca le chat (dalla più recente, con la data
dell'ultimo messaggio), ne crea una nuova e la apre, ne elimina una dopo la conferma; la chat aperta
resta nell'indirizzo (`#/chats/3`) e si ritrova ricaricando la pagina.

Nella chat aperta i messaggi compaiono in ordine con l'ora (domande a destra, risposte a sinistra),
come testo semplice: il Markdown del modello non è interpretato. Sotto una risposta, «Strumenti
usati: calculate» (con «(errore)» accanto a uno strumento fallito) si apre con un clic e mostra
argomenti e risultato di ogni strumento. La domanda si scrive nel campo in fondo: Invio o «Invia»
la manda, Maiusc+Invio va a capo. Mentre l'assistente risponde la domanda è già visibile, sotto
compare «L'assistente sta rispondendo… (12 s)» e solo l'invio in quella chat è bloccato: si possono
leggere, creare o aprire altre chat (il testo scritto e non inviato resta nella sua chat). La pagina
aspetta la risposta fino a 660 s (il back-end aspetta l'agente fino a 600 s). Gli errori compaiono
in un riquadro rosso in cima alla vista, chiudibile, senza bloccare la pagina; dopo un errore
dell'agente la chat mostra la domanda salvata, negli altri casi il testo torna nel campo per
riprovare.

La pagina invia con lo **streaming** (`POST /chats/{chat_id}/messages/stream`, sezione precedente):
sotto la riga d'attesa compare la **risposta in arrivo**, con il bordo tratteggiato e l'etichetta
«Bozza: la risposta può ancora cambiare». Quando l'agente chiede uno strumento la bozza mostra «Uso
lo strumento calculate…», che diventa nome, argomenti e risultato quando lo strumento risponde; il
testo cresce man mano che il modello lo scrive. Se il revisore respinge la bozza, il testo sparisce,
compare «Il revisore ha chiesto di riscrivere la risposta: <motivo>» e arriva la riscrittura; il
testo scritto prima di una chiamata a strumenti sparisce senza avviso (non sarà la risposta). Alla
fine domanda e risposta salvate prendono il posto della domanda in attesa e della bozza. La bozza
resta legata alla sua chat: aprendo un'altra chat e tornando, riprende da dove era arrivata. Con il
modello locale la bozza compare solo nella parte finale del turno: prima ci sono l'elaborazione del
prompt, il router e (dopo il testo) il revisore, che non producono testo. Se il flusso si interrompe
compare «La risposta si è interrotta prima della fine. La domanda è salvata nella chat: riprova.»

| Variabile | Default | Significato |
|-----------|---------|-------------|
| `BACKEND_URL` | `http://127.0.0.1:8001` | indirizzo del back-end **visto dal browser** (deve iniziare con `http://` o `https://`) |
| `FRONTEND_HOST` | `127.0.0.1` | indirizzo su cui ascolta il front-end |
| `FRONTEND_PORT` | `8080` | porta del front-end (intero tra 1 e 65535) |
| `LOG_LEVEL` | `INFO` | come per l'agente |

In un quarto terminale (back-end già avviato), poi si apre `http://127.0.0.1:8080` nel browser:

```powershell
.\.venv\Scripts\python.exe -m frontend
```

All'avvio scrive `frontend listening=http://127.0.0.1:8080 backend_url=http://127.0.0.1:8001`; il
back-end spento non blocca l'avvio (lo segnala la pagina). La pagina riceve l'indirizzo del back-end
da `http://127.0.0.1:8080/config.js`. Il contratto con il back-end è il suo documento OpenAPI,
salvato in `frontend/backend-openapi.json`: se il back-end cambia, il test
`tests/test_frontend_contract.py` fallisce e si rigenera con
`$env:UPDATE_CONTRACT = "1"; .\.venv\Scripts\python.exe -m pytest tests/test_frontend_contract.py`
(poi `Remove-Item Env:UPDATE_CONTRACT`), controllando la pagina.

## Router: domande in ambito e fuori ambito

Dopo il nodo `summary` (sezione «Riassunto della cronologia») ogni turno passa dal nodo `router`:
lo stesso modello, con un prompt di sistema diverso e senza
strumenti, classifica l'ultimo messaggio come `conversation` o `out_of_scope`, con un motivo
(output strutturato `json_schema`). Il router legge l'ambito e la cronologia senza le chiamate agli
strumenti; se servono strumenti lo decide poi l'agente. Se c'è un riassunto dei turni vecchi, il
router lo riceve in fondo al suo prompt di sistema.

```
START → summary → router ─ conversation ─→ llm ⇄ tools (o limit → END) → reviewer → END (o di nuovo llm)
                     └──── out_of_scope ─→ refusal → END
```

- `conversation`: il turno prosegue verso l'agente e poi verso il revisore (sezione seguente).
- `out_of_scope`: il nodo `refusal` risponde «Mi dispiace, questa domanda è fuori dal mio ambito:
  <motivo>. Chiedimi pure che cosa so fare.» e l'agente non viene eseguito. Il rifiuto resta nella
  cronologia e la sessione continua.
- Se il router risponde con un output non valido, il turno va all'agente e il log mostra un WARNING
  `node=router fallback=invalid_output`.

L'ambito è in [`assistant/data/scope.txt`](assistant/data/scope.txt): gli argomenti degli
strumenti, i saluti, le domande sull'assistente, le presentazioni dell'utente e le domande su
quanto detto nella conversazione. Per cambiarlo basta modificare il file, oppure indicarne un
altro con `SCOPE_FILE`; il codice non cambia. Con Docker si modifica il file e si ricostruisce
l'immagine (`docker compose build`).

Log di una prova del 2026-11-11 (`"Che ore sono a Tokyo?", "Chi ha vinto i Mondiali del 2006?", "esci" | docker compose run --rm -T assistant`):

```
INFO __main__: scope_file=/app/assistant/data/scope.txt
INFO assistant.graph: node=router category=conversation reason="La richiesta riguarda la data e l'ora attuale in un fuso orario." next_node=llm
INFO assistant.graph: step=1/5 node=llm
INFO assistant.graph: step=1/5 variant=local tool=get_current_time call_id=AXEA5NxqTb7gaiLGVw99URhZuPzpRz7i arguments={'timezone': 'Asia/Tokyo'}
...
INFO assistant.graph: node=router category=out_of_scope reason="La richiesta riguarda informazioni generali che non rientrano nelle funzioni dell'assistente del laboratorio." next_node=refusal
INFO assistant.graph: node=refusal
Tu> Assistente> Mi dispiace, questa domanda è fuori dal mio ambito: La richiesta riguarda informazioni generali che non rientrano nelle funzioni dell'assistente del laboratorio. Chiedimi pure che cosa so fare.
```

Per una domanda fuori ambito nel turno compaiono `next_node=refusal` e `node=refusal`, e nessuna
riga `node=llm`.

## Revisore: la risposta è coerente con la domanda?

Quando l'agente dà una risposta finale (senza chiedere strumenti), il nodo `reviewer` la controlla:
stesso modello, prompt di sistema diverso, nessuno strumento, output strutturato con un motivo e un
verdetto (`coherent`). Il revisore vede **solo** la domanda dell'utente e la risposta proposta (più
il riassunto dei turni vecchi, se c'è): non la cronologia né i risultati degli strumenti. Giudica se
la risposta tocca tutte le parti della domanda senza uscire dal tema; non giudica stile, lunghezza
né esattezza dei dati, che vengono da strumenti o dalla conversazione precedente.

```
llm ── risposta finale ──→ reviewer ─┬─ coerente ─────────────────────────────→ END
 ▲                                   ├─ non coerente, revisioni < MAX_REVIEWS ─→ llm (con il motivo)
 └───────────────────────────────────┘
                                     └─ non coerente, revisioni = MAX_REVIEWS ─→ END (ultima risposta)
```

- Se la risposta non è coerente, il motivo entra nella cronologia come messaggio utente marcato
  `name="reviewer"` («Revisione: la risposta precedente non è coerente con la domanda: <motivo>.
  Scrivi una nuova risposta completa…») e l'agente riscrive. Bozza e indicazione restano nella
  cronologia della sessione; il router non le vede.
- Il rifiuto del router e l'avviso del limite dei passaggi non vengono rivisti.
- Le riscritture consumano passaggi dell'agente (`MAX_STEPS` non si azzera); il revisore no. Se
  la risposta rifiutata arriva all'ultimo passaggio, il turno termina con quella risposta (WARNING
  `step_limit_reached`): l'agente non è mai chiamato più di `MAX_STEPS` volte.
- Se il revisore risponde con un output non valido, la risposta passa e il log mostra un WARNING;
  un errore di collegamento con LM Studio arriva al terminale come per l'agente.

Log della prova reale del 2026-11-13 `test_reviewer_rejects_an_imposed_partial_answer`, con la
domanda «Che ore sono a Tokyo e quanto fa 17 * 23?». **La prima risposta dell'agente è imposta
dalla prova** («A Tokyo sono le 10:00.», solo la prima parte); revisore e riscrittura sono reali:

```
INFO assistant.graph: step=1/5 node=llm
INFO assistant.graph: node=reviewer review=1/2 coherent=false reason="La risposta proposta ignora la richiesta di calcolare 17 * 23 e fornisce solo un'informazione parziale sulla posizione oraria." next_node=llm
INFO assistant.graph: step=2/5 node=llm
INFO assistant.graph: step=2/5 variant=local tool=get_current_time call_id=ODxniM0Myrv7ALCMTTaUKcyUT5fOBoAk arguments={'timezone': 'Asia/Tokyo'}
...
INFO assistant.graph: step=2/5 variant=mcp tool=calculate call_id=1WvGnlIAo0oArH04bE9q85yI5DtZrtsR arguments={'expression': '17 * 23'}
...
INFO assistant.graph: step=3/5 node=llm
INFO assistant.graph: node=reviewer review=2/2 coherent=true reason="La risposta fornisce le risposte a entrambe le domande poste dall'utente." next_node=end
```

La stessa domanda, interamente reale, con `docker compose run --rm -T assistant` (2026-11-13):

```
INFO __main__: scope_file=/app/assistant/data/scope.txt max_reviews=2
...
INFO assistant.graph: step=2/5 node=llm
INFO assistant.graph: node=reviewer review=1/2 coherent=true reason="La risposta fornisce entrambe le informazioni richieste in modo corretto." next_node=end
Tu> Assistente> A Tokyo sono le ore 00:19:49 (il 14 novembre 2026). $17 \times 23$ fa 391.
```

Righe di limite e di ripiego, nel formato verificato dai test automatici (con un revisore simulato,
non osservate con il modello reale):

```
WARNING assistant.graph: node=reviewer review=2/2 coherent=false reason="incompleta" review_limit_reached next_node=end
WARNING assistant.graph: node=reviewer review=1/2 coherent=false reason="incompleta" step_limit_reached next_node=end
WARNING assistant.graph: node=reviewer review=1/2 fallback=invalid_output error="JSON troncato" coherent=true next_node=end
```

## Riassunto della cronologia

Il contesto del modello locale è limitato (8192 token per `google/gemma-4-e2b`). All'inizio di
ogni turno, prima del router, il nodo `summary` conta i messaggi della cronologia, compresa la
domanda appena arrivata:

- fino a `SUMMARY_MAX_MESSAGES` (default 20) non fa nulla e non chiama il modello
  (`skipped=below_threshold`);
- oltre la soglia conserva almeno gli ultimi `SUMMARY_KEEP_MESSAGES` (default 6) e arretra il
  taglio fino alla domanda dell'utente che apre il turno: una richiesta di strumento non resta mai
  senza il suo risultato, né una bozza rifiutata senza l'indicazione del revisore. Se il taglio
  arriva all'inizio, non c'è nulla da comprimere (`skipped=nothing_to_compress`);
- altrimenti lo stesso modello, senza strumenti, scrive un riassunto aggiornato a partire dal
  riassunto precedente e dalle sole domande e risposte finali dei messaggi tolti; il riassunto
  **sostituisce** il precedente e i messaggi vecchi escono dalla cronologia.

Agente, router e revisore ricevono il riassunto in fondo al loro prompt di sistema. Il riassunto
dura quanto la sessione, come la cronologia. Un dato che compare solo nel risultato di uno
strumento, e che la risposta non ha ripetuto, non entra nel riassunto. Se il modello restituisce
un riassunto vuoto, la cronologia resta intatta e il log mostra un WARNING; un errore di LM Studio
arriva al terminale e cronologia e riassunto restano quelli di prima.

Log della prova del 2026-11-13 con soglie piccole (`$env:SUMMARY_MAX_MESSAGES = "4";
$env:SUMMARY_KEEP_MESSAGES = "2"`, poi `"Mi chiamo Paolo", "Che ore sono a Tokyo?", "Come mi
chiamo?", "esci" | .\.venv\Scripts\python.exe -m assistant`):

```
INFO __main__: scope_file=…\assistant\data\scope.txt max_reviews=2 summary_max_messages=4 summary_keep_messages=2
INFO assistant.graph: node=summary messages=1/4 skipped=below_threshold next_node=router
...
Tu> Assistente> Ciao Paolo.
INFO assistant.graph: node=summary messages=3/4 skipped=below_threshold next_node=router
...
Tu> Assistente> L'ora attuale a Tokyo è 04:05:54 del 14 novembre 2026.
INFO assistant.graph: node=summary messages_before=11 messages_after=9 removed=2 next_node=router
INFO assistant.graph: node=router category=conversation reason="La domanda riguarda un'informazione fornita dall'utente precedentemente." next_node=llm
INFO assistant.graph: node=reviewer review=1/2 coherent=true reason="La risposta risponde alla domanda basandosi sul contesto fornito." next_node=end
Tu> Assistente> Ti chiami Paolo.
```

Il primo turno («Mi chiamo Paolo», «Ciao Paolo.») è uscito dalla cronologia: il nome arriva
all'agente solo dal riassunto. Il testo del riassunto compare nel log solo con `LOG_LEVEL=DEBUG`
(`node=summary summary="…"`). Con Docker le soglie sono variabili del servizio `agent`: si
impostano nel `.env` e valgono dopo `docker compose down` e un nuovo `docker compose run --rm
assistant` (sezione «Docker»). Prima dello Step 6 la prova si faceva con
`docker compose run --rm -T -e SUMMARY_MAX_MESSAGES=4 -e SUMMARY_KEEP_MESSAGES=2 assistant`.

Righe senza compressione e di ripiego, nel formato verificato dai test automatici (non osservate
con il modello reale):

```
INFO assistant.graph: node=summary messages=5/4 skipped=nothing_to_compress next_node=router
WARNING assistant.graph: node=summary messages=5/4 fallback=empty_summary next_node=router
```

## Preferenze dell'utente

Oltre ai sette strumenti, il server MCP espone una **resource** `utente://preferenze`
(`application/json`), letta dal file [`assistant/data/preferenze.json`](assistant/data/preferenze.json)
(o da quello indicato con `PREFERENCES_FILE`):

```json
{
  "language": "italiano",
  "timezone": "Europe/Rome",
  "style": "sintetico"
}
```

| Chiave | Valori ammessi | Predefinito |
|--------|----------------|-------------|
| `language` | lingua delle risposte, testo libero su una riga, al più 40 caratteri (es. `"inglese"`) | `"italiano"` |
| `timezone` | nome IANA, lo stesso controllo dello strumento orologio (es. `"America/New_York"`) | `"Europe/Rome"` |
| `style` | `"sintetico"` (breve) o `"dettagliato"` (con spiegazioni ed esempi) | `"sintetico"` |

- Il servizio dell'agente legge la resource **una sola volta**, al suo avvio, prima della prima
  domanda (`resources/read`), e mette in cima al prompt di sistema dell'agente un testo con lingua,
  fuso e stile, uguale per tutte le conversazioni. Una modifica del file vale quindi dal **riavvio
  del servizio**, senza toccare il codice (riavviare solo la CLI non basta).
- Con un fuso predefinito, a «Che ore sono?» senza luogo l'agente chiama `get_current_time` con
  quel fuso invece di chiederlo.
- La resource non è uno strumento: non compare in `tools/list` e il modello non la può chiamare.
  Router, revisore e riassunto non la ricevono.
- Un campo mancante o non valido prende il suo predefinito (WARNING `field=…`) senza far perdere gli
  altri; se la resource non è leggibile (file mancante, JSON non valido), il servizio parte con i tre
  predefiniti e un WARNING `status=unavailable`.
- Con Docker il file di esempio è nell'immagine: dopo averlo modificato serve `docker compose
  build`; in alternativa `PREFERENCES_FILE` indica un percorso dentro il container.

Log della prova reale del 2026-11-14 `test_default_timezone_from_preferences`, con
`"timezone": "America/New_York"` nel file e la domanda «Che ore sono?»:

```
INFO assistant.preferences: resources/read uri=utente://preferenze status=ok language="italiano" timezone=America/New_York style=sintetico
INFO assistant.graph: node=summary messages=1/20 skipped=below_threshold next_node=router
...
INFO assistant.graph: step=1/5 variant=local tool=get_current_time call_id=pRqbbvDb3EVkqZXJW83V2liIxSFClrE1 arguments={'timezone': 'America/New_York'}
...
INFO assistant.graph: node=reviewer review=1/2 coherent=true reason="La risposta fornisce un orario, rispondendo alla domanda dell'utente." next_node=end
```

All'avvio da terminale la riga di configurazione termina con `preferences_file=<percorso
assoluto>`. Le righe delle preferenze cominciano tutte con `resources/read` (logger
`assistant.preferences`) e si distinguono da quelle degli strumenti (`step=… variant=… call_id=…`).
Righe di ripiego, nel formato verificato dai test automatici:

```
WARNING assistant.preferences: resources/read uri=utente://preferenze field=style problem=invalid value="lungo" fallback=sintetico
INFO assistant.preferences: resources/read uri=utente://preferenze status=partial language="italiano" timezone=Europe/Rome style=sintetico
WARNING assistant.preferences: resources/read uri=utente://preferenze status=unavailable error="File delle preferenze non leggibile: '…' (No such file or directory)." fallback=defaults language="italiano" timezone=Europe/Rome style=sintetico
```

## Prompt MCP: comandi della CLI

Il server MCP espone due **prompt**: modelli di messaggio con argomenti, scelti dall'utente (non dal
modello, come invece gli strumenti). Non compaiono in `tools/list` e non entrano in `bind_tools`.

| Prompt | Argomenti | Messaggio prodotto |
|--------|-----------|--------------------|
| `spiega` | `argomento` (obbligatorio, una riga, al più 200 caratteri), `livello` (facoltativo: `base`, `intermedio`, `avanzato`; predefinito `base`) | «Spiegami <argomento> a livello <livello>: …» |
| `riassumi_conversazione` | `stile` (obbligatorio: `sintetico` o `dettagliato`) | «Riassumi la nostra conversazione fino a questo momento, …», senza strumenti |

Dal terminale:

- `/prompts` elenca nome, descrizione e argomenti di ogni prompt (`GET /prompts` del servizio, che
  chiede `prompts/list` a ogni comando):

  ```
  Prompt disponibili:
  - spiega: Spiega un argomento al livello scelto.
      argomento (obbligatorio): Argomento da spiegare (per esempio Model Context Protocol).
      livello (facoltativo): Livello della spiegazione: base, intermedio o avanzato (predefinito: base).
  - riassumi_conversazione: Riassume i turni della conversazione corrente.
      stile (obbligatorio): Stile del riassunto: sintetico o dettagliato.
  Uso: /prompt nome chiave=valore (valori con spazi tra virgolette doppie).
  ```
- `/prompt nome chiave=valore …` richiama un prompt. I valori con spazi vanno tra virgolette doppie;
  l'apostrofo e `=` dentro le virgolette sono caratteri normali. Esempi:
  `/prompt spiega argomento="Model Context Protocol" livello=base`,
  `/prompt riassumi_conversazione stile=sintetico`.
- La CLI controlla solo la sintassi (virgolette, forma `chiave=valore`, argomenti ripetuti o
  vuoti): un errore dà «Errore nel comando: … Uso: …» senza richieste al servizio. Poi manda nome e
  argomenti al servizio (`POST /chat` con `prompt`), che prima di chiedere il prompt controlla la
  richiesta rispetto a `prompts/list`: nome sconosciuto, argomento sconosciuto o obbligatorio
  mancante bloccano il comando con «Errore nel comando: … Scrivi /prompts per l'elenco dei prompt.»
  senza chiamare `prompts/get` né il modello. Un valore non ammesso (per esempio
  `livello=esperto`) lo rifiuta il server MCP: «Errore nel prompt: il prompt 'spiega' non è
  disponibile (Livello non valido: 'esperto'. Valori ammessi: base, intermedio, avanzato). Scrivi
  /prompts per l'elenco dei prompt.».
- I messaggi ottenuti entrano nella cronologia e fanno un turno normale: riassunto, router (l'ambito
  in `scope.txt` comprende spiegazioni di concetti e riassunti della conversazione), agente con gli
  strumenti, revisore.
- Il testo che comincia con `/` non arriva mai al modello; «quanto fa 6 / 3?» invece è una domanda.
- Il revisore controlla che la risposta sia coerente con la richiesta, non che sia corretta: nella
  prova del 2026-11-14 la spiegazione «base» del Model Context Protocol data da `google/gemma-4-e2b`
  era chiara ma sbagliata nel merito (lo descriveva come il modo in cui il modello usa il contesto, non
  come il protocollo che collega applicazioni, strumenti e dati). È un limite del modello piccolo.
- Con Docker i comandi funzionano allo stesso modo (`docker compose run --rm assistant`).

Log della prova reale del 2026-11-14 `test_summary_prompt` («Mi chiamo Paolo», «Quanto fa 17 * 23?»,
poi `/prompt riassumi_conversazione stile=sintetico`):

```
INFO assistant.commands: prompts/list count=2 names=spiega,riassumi_conversazione
INFO assistant.commands: prompts/get name=riassumi_conversazione arguments={"stile": "sintetico"} status=ok messages=1
INFO assistant.commands: prompts/get name=riassumi_conversazione message=1/1 role=user text="Riassumi la nostra conversazione fino a questo momento, in pochi punti essenziali, con le richieste e i risultati ottenuti. Usa solo quanto detto in questa conversazione, compreso l'eventuale riassunto dei turni precedenti, senza chiamare strumenti."
INFO assistant.graph: node=summary messages=5/20 skipped=below_threshold next_node=router
INFO assistant.graph: node=router category=conversation reason="La richiesta rientra nell'ambito dell'assistente, poiché chiede un riassunto della conversazione precedente." next_node=llm
...
INFO assistant.graph: node=reviewer review=1/2 coherent=true reason="La risposta riassume correttamente i punti essenziali della conversazione precedente come richiesto." next_node=end
```

Queste righe (prova del 2026-11-14, prima dello Step 6) oggi compaiono nel log del servizio
dell'agente. Un comando bloccato scrive `prompt_command status=rejected reason="…"` (nel log della
CLI per un errore di sintassi, in quello del servizio per il controllo rispetto a `prompts/list`); un
prompt rifiutato dal server `prompts/get … status=unavailable error="…"` (WARNING).

## Prove reali con LM Studio

Sono separate dai test automatici e partono solo su richiesta, con le variabili impostate:

```powershell
.\.venv\Scripts\python.exe -m pytest -m real -v
```

Senza variabili le prove falliscono con un messaggio esplicito invece di essere saltate.
Una risposta simulata non dimostra che il modello locale sappia usare lo strumento: lo dimostra
solo questa prova.

Le prove del back-end richiedono anche PostgreSQL (il container della sezione «Back-end: chat
salvate su PostgreSQL») e la variabile `TEST_DATABASE_URL`. Ogni prova lavora in uno schema
temporaneo del database, eliminato alla fine: le tabelle di `public` non vengono toccate, quindi va
bene anche il database del back-end.

```powershell
$env:TEST_DATABASE_URL = "postgresql://lab:labprova@127.0.0.1:5433/assistente"
.\.venv\Scripts\python.exe -m pytest tests/test_backend_store.py -m real -v    # archivio su PostgreSQL, senza LM Studio
.\.venv\Scripts\python.exe -m pytest tests/test_real.py -m real -k backend -v  # back-end, agente e LM Studio
.\.venv\Scripts\python.exe -m pytest tests/test_real.py -m real -k frontend -v # pagina nel browser con tutti i servizi
```

La prima riesegue su PostgreSQL i test dell'archivio (di solito su SQLite in memoria); la seconda
avvia agente e back-end come processi, manda «Quanto fa 17 * 23?», riavvia il back-end e controlla
che la chat ci sia ancora e che il messaggio successivo usi la cronologia salvata, poi ferma
l'agente e controlla la risposta `503 agent_unavailable`.

La terza avvia anche il front-end e pilota Edge senza finestra (Chrome con
`$env:BROWSER_CHANNEL = "chrome"`): crea una chat dalla pagina, manda «Quanto fa 17 * 23?» e aspetta
la risposta con «391» e «Strumenti usati: calculate» (strumento presente anche nel log
dell'agente); riavvia il back-end, ricarica la pagina e ritrova chat e messaggi; ferma l'agente,
manda un'altra domanda e controlla il messaggio d'errore, la domanda salvata nella chat e che si
possa ancora creare una chat. Le schermate di ogni fase (`1-attesa.png` … `4-agente-fermato.png`)
restano nella cartella temporanea del test, indicata nell'output con `-s`. Con `-k frontend` parte
anche la prova dello streaming dalla pagina: registra ogni cambiamento della bozza e controlla che
il testo cresca prima della fine del turno, che «Uso lo strumento calculate…» compaia durante
l'attesa e che la risposta resti dopo la ricarica (schermate `1-bozza.png`, `2-risposta.png`).

Solo le due prove dello streaming (la prima chiama `POST /chat/stream` dell'agente e stampa gli
eventi con i secondi, senza PostgreSQL; la seconda è quella dalla pagina, con `TEST_DATABASE_URL`):

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_real.py -m real -k stream -v -s
```

## Strumenti

Il modello richiede gli strumenti tramite tool calling; il programma li esegue davvero e gli
restituisce il risultato. Un errore dello strumento arriva al modello come `{"error": "…"}` con un
messaggio in italiano, così può correggersi.

**Locale** (eseguito nel processo dell'applicazione):

| Strumento | Esempio di domanda | Esempio di risultato |
|-----------|--------------------|----------------------|
| `get_current_time(timezone)` | «Che ore sono a Tokyo?» | `{"timezone": "Asia/Tokyo", "datetime": "2026-11-09T23:29:22+09:00"}` |

**MCP** (server `assistant.mcp_server`, avviato dall'applicazione come sottoprocesso stdio e
scoperto con `tools/list`; l'applicazione espone al modello solo i sette nomi attesi):

| Strumento | Esempio di domanda | Esempio di risultato |
|-----------|--------------------|----------------------|
| `convert_units(value, from_unit, to_unit)` | «Converti 10 km in miglia» | `{"value": 10, "from_unit": "km", "to_unit": "mi", "quantity": "lunghezza", "result": 6.21371}` |
| `calculate(expression)` | «Quanto fa 17 * 23?» | `{"expression": "17 * 23", "result": 391}` |
| `search_catalog(query, max_results=5)` | «Ci sono corsi di Python?» | `{"query": "python", "results": [{"code": "PY-101", …}, {"code": "PY-201", …}], "total": 2}` |
| `get_item(code)` | «Quante ore dura il corso di visione artificiale?» | il record completo di `DL-201`, con `"duration_hours": 32` |
| `add_note(text)` | «Ricordami di consegnare il report venerdì» | `{"id": 1, "text": "Consegnare il report venerdì", "created_at": "2026-11-09T14:41:15+00:00"}` |
| `list_notes(limit=10)` | «Quali note ho?» | `{"notes": [{"id": 1, …}], "total": 1}`, dalla più recente |
| `delete_note(note_id)` | «Elimina la nota 99» | `{"error": "Nessuna nota con id 99: nessuna nota eliminata."}` |

- **Convertitore:** lunghezza (mm, cm, m, km, in, ft, yd, mi), massa (mg, g, kg, t, oz, lb),
  temperatura (C, F, K) e volume (ml, l, gal USA); risultato a 6 cifre significative.
- **Calcolatrice:** solo numeri, `+ - * / // % **` e parentesi, analizzati con `ast` senza `eval`;
  al più 200 caratteri, esponenti fino a 100, numeri fino a 1e100.
- **Catalogo:** 8 corsi d'esempio **inventati**, in `assistant/data/catalog.json`. La ricerca vuole
  tutte le parole in codice, titolo o sede; il dettaglio si chiede con il codice esatto
  (maiuscole e spazi esterni ignorati).
- **Note:** SQLite nel file di `NOTES_DB` (in locale `data/notes.sqlite3`, ignorato da Git; in
  Docker il volume `notes-data`). Le note restano tra un avvio e l'altro; un'eliminazione richiede
  l'id esatto e restituisce la nota eliminata. Ogni modifica compare nel log del server
  (`event=note_added id=1`, `event=note_deleted id=1`). Per azzerarle: cancellare il file
  `data\notes.sqlite3`, oppure in Docker `docker volume rm assistente-laboratorio_notes-data`.
  `created_at` è in UTC.

Se il server MCP non parte, il servizio dell'agente esce con «Server MCP non avviato: <motivo>». Se
il collegamento si interrompe mentre il servizio è attivo, lo strumento risponde «Strumento non
raggiungibile: … Riprova o riavvia l'assistente.» e `GET /status` risponde `503`: non c'è
riconnessione automatica, va riavviato il servizio.

In un turno il modello è chiamato al più `MAX_STEPS` volte; se all'ultimo passaggio chiede ancora
uno strumento, il turno termina con «Ho raggiunto il limite di 5 passaggi senza una risposta
finale.» e la sessione resta utilizzabile.

A livello `INFO` i log del servizio su stderr mostrano all'avvio l'elenco degli strumenti con la
variante (riga `assistant.service: tools=[…]`; nella prova qui sotto, precedente allo Step 6, era
`__main__`), poi
ogni passaggio, ogni chiamata con variante e `call_id`, l'esito (`ok`, `tool_error`,
`transport_error`; WARNING se diverso da `ok`) e il messaggio restituito al modello. Le righe del
server MCP (`assistant.mcp_server`) si intercalano a quelle del grafo. Prova reale del 2026-11-09:

```
INFO __main__: tools=[get_current_time (local), convert_units (mcp), calculate (mcp), search_catalog (mcp), get_item (mcp), add_note (mcp), list_notes (mcp), delete_note (mcp)]
INFO assistant.graph: step=1/5 node=llm
INFO assistant.graph: step=1/5 variant=mcp tool=add_note call_id=WLCQjkfF0ugFhx6llQ79dfhJngEAAbRo arguments={'text': 'comprare il latte'}
INFO assistant.mcp_server: event=note_added id=1
INFO assistant.graph: step=1/5 execution=ok call_id=WLCQjkfF0ugFhx6llQ79dfhJngEAAbRo result={'id': 1, 'text': 'comprare il latte', 'created_at': '2026-11-09T14:49:40+00:00'}
INFO assistant.graph: tool_message.call_id=WLCQjkfF0ugFhx6llQ79dfhJngEAAbRo next_node=llm
INFO assistant.graph: step=2/5 node=llm
Tu> Assistente> Nota aggiunta: Ricordati di comprare il latte.
```

Le prove reali (`pytest -m real`, 17 prove, circa 34 minuti il 2026-11-14) passano tutte da
riassunto, router e revisore, con le preferenze lette dalla resource, e verificano con il modello
locale: con il fuso predefinito `America/New_York` nelle preferenze, «Che ore sono?» risolta con
quel fuso senza chiederlo; la stessa domanda in italiano con le preferenze predefinite e in inglese
con `"language": "inglese"`; l'orario a Tokyo e poi a Roma; un nome ricordato senza strumenti;
`calculate` e `convert_units`; una sola `add_note` per una richiesta di ricordare; `delete_note` su
un id inesistente che non elimina nulla; le note ritrovate dopo il riavvio del server;
`search_catalog` seguito da `get_item`; una ricerca senza risultati; i log correlati dallo stesso
`call_id`; il router che manda all'agente «Che ore sono a Tokyo?» e «Ciao!» e rifiuta «Chi ha
vinto i Mondiali del 2006?» senza eseguire l'agente; il revisore che rifiuta una prima risposta
parziale imposta dalla prova e approva la riscrittura dell'agente reale, e la stessa domanda in due
parti interamente reale («391» e l'ora di Tokyo nella risposta); con soglie 4 e 2, il nome
detto nel primo turno ritrovato dopo la compressione solo attraverso il riassunto.

Le prove dei prompt MCP (`/prompt spiega` e `/prompt riassumi_conversazione`) e quelle del servizio
HTTP si aggiungono alle precedenti (23 prove in tutto). Le quattro del servizio avviano
`python -m assistant.service` come processo separato su una porta libera e sono passate il
2026-11-14 (circa 4 minuti e mezzo): `POST /chat` «Quanto fa 17 * 23?» → `200` con `calculate` in
`tools_used`, «391» e le righe `api response=chat status=200 tools=calculate` e `tool=calculate` nel
log del servizio; la stessa domanda dalla CLI e dall'API con lo stesso strumento e la stessa
risposta («17 * 23 fa 391.» in entrambe, alla lettera); `/openapi.json`, `/docs` e `/status` `200`;
con `LMSTUDIO_BASE_URL` irraggiungibile `/status` `503` (modello `unavailable`) e `/chat` `503
model_unavailable`. Per eseguire solo queste:

```powershell
.\.venv\Scripts\python.exe -m pytest -m real -v -k "http_chat or same_answer or openapi_and_status or without_lm_studio"
```

## Docker

LM Studio resta sull'host. `compose.yaml` definisce quattro servizi, ognuno in un container, più la
CLI:

- `frontend`: la pagina della chat (`python -m frontend`), pubblicata solo su
  `http://127.0.0.1:8080` di questo computer.
- `backend`: il back-end (`python -m backend`), pubblicato su `127.0.0.1:8001` perché la pagina nel
  browser lo chiama direttamente (CORS dello Step 8); salva in `postgres` e chiama l'agente su
  `http://agent:8000`. Parte solo quando PostgreSQL è pronto (`healthcheck` con `pg_isready`).
- `agent`: il servizio HTTP dell'agente (`python -m assistant.service`, con il server MCP come
  sottoprocesso nello stesso container e le note nel volume `notes-data`), **non pubblicato**: lo
  raggiungono solo back-end e CLI sulla rete di Compose. Un `healthcheck` lo dichiara pronto quando
  `GET /status` risponde, con qualsiasi codice (LM Studio spento dà `503`, ma l'agente c'è). Lo stato
  si legge da dentro il container:
  `docker compose exec -T agent python -c "import httpx; print(httpx.get('http://127.0.0.1:8000/status').text)"`.
- `postgres`: PostgreSQL ufficiale (`postgres:18.6`), dati nel volume `postgres-data`, non
  pubblicato.
- `assistant`: la CLI, client dell'agente (`AGENT_URL=http://agent:8000`), nel profilo `cli`: non
  parte con `docker compose up`, si avvia con `docker compose run --rm assistant` quando `agent` è
  pronto.

Compose legge `.env` (vedi «Configurazione») e in `agent` imposta `LMSTUDIO_BASE_URL` a
`http://host.docker.internal:1234/v1`. Se LM Studio usa un'altra porta o un altro host, si imposta
`LMSTUDIO_BASE_URL_DOCKER` nel `.env` (vedi `.env.example`). Le credenziali di PostgreSQL
(`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`) stanno solo nel `.env`, da cui `compose.yaml`
costruisce `DATABASE_URL` del back-end: la password è obbligatoria per **ogni** comando `docker
compose` (senza, si ferma con «Manca POSTGRES_PASSWORD nel file .env»), va scelta senza i caratteri
`@ : / % #` e vale solo alla prima creazione del volume `postgres-data`.

### Avvio dei quattro servizi e chat dal browser

```powershell
Copy-Item .env.example .env      # solo la prima volta; poi cambiare POSTGRES_PASSWORD
docker compose up -d --build     # costruisce le immagini e avvia frontend, backend, agent, postgres
docker compose ps                # quattro servizi Up; agent e postgres (healthy)
```

Poi si apre `http://127.0.0.1:8080` nel browser. `docker compose ps` mostra le porte: `frontend`
`127.0.0.1:8080->8080/tcp`, `backend` `127.0.0.1:8001->8001/tcp`, `agent` solo `8000/tcp` e
`postgres` solo `5432/tcp` (non pubblicati: dall'host `http://127.0.0.1:8000` non risponde). Il
back-end parte dopo che `postgres` è `(healthy)`. I log si leggono servizio per servizio:

```powershell
docker compose logs agent        # step=1/5 variant=mcp tool=calculate …, api response=chat … tools=calculate
docker compose logs backend      # backend response=send_message chat=1 status=201 tools=calculate …
docker compose down              # ferma e rimuove i container; i volumi restano
docker compose up -d             # riparte con le stesse chat e le stesse note
```

Le chat restano nel volume `postgres-data` dopo `docker compose down` (e dopo `up -d` la pagina le
mostra di nuovo); dopo `docker compose down`, `docker volume rm
assistente-laboratorio_postgres-data` le cancella (le note, nel volume `notes-data`, restano). Le
variabili dei servizi valgono dal loro avvio: dopo una modifica del `.env` servono `docker compose
down` e `docker compose up -d`.

### CLI in Docker

```powershell
docker compose run --rm assistant
```

`docker compose run --rm assistant` avvia anche `agent` (se non è già attivo), che resta attivo dopo
l'uscita dalla CLI fino a `docker compose down`; con i quattro servizi avviati la CLI usa lo stesso
`agent` della pagina. La CLI parte solo con `run`, non con `docker compose up` (profilo `cli`), che
non collegherebbe l'input del terminale. Per una prova non interattiva serve `-T`:

```powershell
"Che ore sono a Tokyo?", "esci" | docker compose run --rm -T assistant
docker compose logs agent
docker compose down
```

### Immagini e volumi

Ogni servizio ha il proprio Dockerfile nella cartella `docker/`, con contesto di build la radice
della repository: `agent.Dockerfile` (comando predefinito `python -m assistant.service`; la CLI usa
la stessa immagine con `python -m assistant`), `backend.Dockerfile` (`python -m backend`) e
`frontend.Dockerfile` (`python -m frontend`). Le tre immagini partono da
`python:3.13.18-slim-trixie`, fissata per digest, con le stesse prime istruzioni: il livello delle
dipendenze (`requirements.txt` con `constraints.txt`) si costruisce una volta e si riusa. Ognuna
contiene il pacchetto `assistant` (con `assistant/data/catalog.json`, `assistant/data/scope.txt` e
`assistant/data/preferenze.json`) più quello del proprio servizio, ascolta su `0.0.0.0` nel
container ed esegue come utente non root `app`. Un'immagine si costruisce anche da sola, per
esempio `docker build -f docker/backend.Dockerfile -t assistente-backend .`. Nel container l'orario
dei log è in UTC;
l'orario restituito dallo strumento dipende solo dal fuso richiesto.

Le note stanno nel volume `notes-data`, montato in `/app/data` del servizio `agent`: una nota
salvata resta anche dopo `docker compose down`. Il volume si elimina con
`docker volume rm assistente-laboratorio_notes-data`.

## Diagnosi

**Quali modelli serve LM Studio?** L'identificativo da usare in `LMSTUDIO_MODEL` è quello
restituito dal server:

```powershell
(Invoke-RestMethod http://localhost:1234/v1/models).data.id
```

**Agente non raggiungibile.** La CLI esce subito con «Agente non disponibile: agente non
raggiungibile su http://127.0.0.1:8000. Avvia il servizio con: python -m assistant.service»: avviare
il servizio in un altro terminale (o controllare `AGENT_URL`). Se il servizio si ferma durante la
sessione, ogni domanda dà `Errore: agente non raggiungibile su http://127.0.0.1:8000. Riprova.` e
la cronologia resta nella CLI: si può riprovare dopo averlo riavviato. Lo stato si controlla con
`curl.exe -s http://127.0.0.1:8000/status`, che mostra il corpo anche con `503` (con `503`
`Invoke-RestMethod` dà invece un errore di PowerShell).

**Il back-end non parte.** «Configurazione non valida: Manca DATABASE_URL.» (o lo schema ricevuto, mai
l'indirizzo intero): impostare `DATABASE_URL`. «Database non raggiungibile: …» dopo al più 10 s:
il container di PostgreSQL è fermo (`docker ps`, poi `docker start assistente-postgres`) o la porta
è sbagliata. «password authentication failed for user …» con il container avviato: sulla porta
risponde un altro PostgreSQL (per esempio uno installato sull'host sulla 5432); `netstat -ano |
findstr :5432` mostra chi ascolta.

**Un messaggio del back-end dà `503 agent_unavailable` (o `502 agent_error`).** Il servizio
dell'agente non è avviato o non è su `AGENT_URL` (`503`), oppure ha risposto con un errore, per
esempio LM Studio spento (`502`: il `detail` è quello dell'agente, il suo codice è nella riga di log
`backend response=…` come `cause="model_unavailable"`). La domanda resta nella chat:
dopo aver avviato l'agente si rimanda il messaggio. Nel log del back-end le righe `backend
request=send_message …`, `backend agent_call chat=… history=… summary_chars=…` (cronologia mandata
all'agente) e `backend response=send_message … status=…` seguono ogni invio; il testo dei messaggi
è solo nel log dell'agente.

**La pagina del front-end dice «Il back-end non risponde (…)».** Il back-end non è avviato o non è
all'indirizzo di `BACKEND_URL` (quello che vede il browser). Se il back-end risponde
(`Invoke-RestMethod http://127.0.0.1:8001/chats`), la pagina è aperta da un'origine che non è in
`CORS_ORIGINS` (per esempio `http://localhost:8080` con un elenco che contiene solo
`http://127.0.0.1:8080`): il browser blocca la risposta e la pagina non può distinguere i due casi.
Nella console del browser (F12) compare l'errore CORS; aggiungere l'origine a `CORS_ORIGINS` e
riavviare il back-end.

**La pagina dice «L'assistente non è raggiungibile in questo momento…» o «L'assistente non è
riuscito a rispondere (…)…».** Il back-end funziona ma l'agente è spento (`503`) o ha risposto con un
errore, per esempio LM Studio spento (`502`, il motivo è tra parentesi: «L'assistente non è riuscito a
rispondere (LM Studio non raggiungibile: Connection error). La domanda è salvata nella chat:
riprova.»; lo stesso testo per un errore durante lo streaming). La domanda è salvata e compare nella
chat senza risposta: avviare l'agente (o LM Studio) e scrivere di nuovo la domanda. «L'assistente
non ha risposto in tempo» è il `504` del back-end dopo 600 s.

**La bozza non compare, o la risposta arriva tutta alla fine.** È normale che per decine di secondi
ci sia solo la riga d'attesa: elaborazione del prompt e router non producono testo. Alla fine del
turno il log dell'agente ha `api response=chat_stream status=200 outcome=done tools=… text_events=…
resets=…`: con `text_events=0` il modello non ha scritto testo nel nodo dell'agente (rifiuto del
router, limite di passaggi), con `resets=` maggiore di zero c'è stato un `reset` (strumenti o
revisore). Il log del back-end ha `backend response=send_message_stream chat=… status=200
outcome=…`: `done`, `error` (con `error=` e `detail=`, come per i messaggi senza streaming) o
`client_gone` (pagina chiusa o ricaricata durante il turno: la domanda resta senza risposta e si
rimanda). «La risposta si è interrotta prima della fine» nella pagina vuol dire che la connessione
con il back-end si è chiusa senza l'evento finale (back-end fermato durante il turno).

**LM Studio non raggiungibile.** All'avvio la CLI mostra «Attenzione: modello non disponibile (LM
Studio non raggiungibile su …)»; ogni domanda risponde `Errore: LM Studio non raggiungibile:
Connection error. Riprova.` e la sessione resta attiva: la domanda fallita non entra nella
cronologia, quindi si può riprovare dopo aver avviato il server. Controllare che il server di LM
Studio sia avviato e che `LMSTUDIO_BASE_URL` del servizio termini con `/v1`. Se invece il server
risponde ma non entro il tempo limite (modello che si carica o richiesta molto lunga), il messaggio
è `Errore: LM Studio non ha risposto in tempo: Request timed out. Riprova.`: stesso codice
`503 model_unavailable` nell'API, con un detail diverso.

**Contesto del modello superato.** Se la richiesta supera il contesto caricato in LM Studio
(8192 token per `google/gemma-4-e2b` nella configurazione provata), l'assistente mostra
`Errore: LM Studio non ha risposto correttamente: Error code: 400 - ... exceeds the available context size .... Riprova.`
Se la causa è una sola domanda troppo lunga, basta riformularla: la domanda rifiutata non entra
nella cronologia. Se invece è la cronologia della sessione a essere diventata troppo lunga, ogni
domanda successiva fallirà allo stesso modo: chiudere la CLI con `esci` e riavviarla (la cronologia
vive nella CLI e riparte da zero; il servizio non va riavviato), oppure aumentare in LM Studio la
lunghezza del contesto del modello.

**Una domanda in ambito viene rifiutata (o il contrario).** Il motivo scritto dal router è nella
riga `node=router … reason="…"`. Il router è un modello piccolo e classifica in base al testo di
`assistant/data/scope.txt`: conviene descrivere che cosa può chiedere l'utente, non solo gli
argomenti. Nella prima prova del 2026-11-11 «Ricordami di comprare il latte» e «Ci sono corsi di
astrologia?» erano rifiutate; con l'ambito attuale passano. Dopo una modifica si ripete
`pytest -m real`.

**Il revisore rifiuta una risposta giusta (o ne approva una incompleta).** Il motivo è nella riga
`node=reviewer … reason="…"`. Il revisore vede solo la domanda e la risposta, quindi può sbagliare
con domande brevi che continuano la conversazione («E a Roma?»). Un rifiuto in più costa al più
`MAX_REVIEWS - 1` riscritture, poi passa l'ultima risposta; con `MAX_REVIEWS=1` il revisore controlla
ma non fa mai riscrivere.

**Le preferenze non hanno effetto.** All'avvio cercare la riga `resources/read
uri=utente://preferenze`: `status=ok` con i valori letti; `status=partial` preceduta da un WARNING
`field=<campo> problem=missing|invalid` per ogni campo che ha preso il predefinito;
`status=unavailable … fallback=defaults` se il file manca o non è JSON valido (il motivo è in
`error="…"`, con il percorso). Il file si legge solo all'avvio del servizio dell'agente: dopo una
modifica va riavviato il servizio (con Docker `docker compose down`, e anche `docker compose build`
se si cambia il file dell'immagine). La resource si legge da sola così, con lo stesso file del
servizio (`PREFERENCES_FILE` se è impostata nella finestra, altrimenti quello del pacchetto); deve
stampare il JSON di quel file:

```powershell
@'
import os
from pathlib import Path
from assistant.config import DEFAULT_PREFERENCES_FILE
from assistant.mcp_client import McpClient, server_command
preferences = Path(os.environ.get("PREFERENCES_FILE", "").strip() or DEFAULT_PREFERENCES_FILE).resolve()
command, args, cwd = server_command(Path("data/notes.sqlite3").resolve(), "WARNING", preferences)
with McpClient(command, args, cwd=cwd) as client:
    print(client.read_resource("utente://preferenze"))
'@ | .\.venv\Scripts\python.exe -
```

Se i valori sono letti ma il modello non li segue (risponde in un'altra lingua, chiede il fuso), è un
limite del modello: il testo delle preferenze è in cima al prompt di sistema dell'agente. Vale anche
il contrario: quel testo può cambiare l'uso degli strumenti. Nella prima prova reale del 2026-11-14
la descrizione dello stile sintetico «breve ed essenziale, in poche frasi» faceva rispondere
«Quanto fa 17 * 23?» senza `calculate` (0 volte su 8); senza «in poche frasi» lo strumento è chiamato
(dettagli nella §11 della [specifica](docs/superpowers/specs/2026-11-14-preferenze-design.md)). Dopo
una modifica di `preferences.py` o del prompt si ripete `pytest -m real`.

**Un `/prompt` non funziona.** Le righe del logger `assistant.commands` (nel log della CLI per la
sintassi, in quello del servizio per il resto, dopo `api request=chat kind=prompt name="…"`, con il
nome in JSON e troncato a 64 caratteri) dicono dove si è fermato: `prompt_command status=rejected
reason="…"` se il comando è stato bloccato (sintassi, nome o argomenti rispetto a `prompts/list`: il
modello non è stato chiamato). Prima ancora il servizio rifiuta, senza chiamare il server MCP, un
nome di prompt o di argomento oltre 64 caratteri, più di 10 argomenti o un valore oltre 1000
caratteri: la CLI scrive per esempio «Errore nel comando: il valore dell'argomento 'argomento'
supera 1000 caratteri. Scrivi /prompts per l'elenco dei prompt.»; il valore non entra nel log.
`prompts/list status=unavailable` o `prompts/get … status=unavailable error="…"` se il server non ha risposto o ha
rifiutato un valore; `prompts/get … status=ok` seguita da `message=1/1 … text="…"` con il testo
mandato al grafo. Da lì in poi il turno ha le righe consuete di `summary`, `router`, agente e
`reviewer`. Se la risposta non è quella attesa, conta il testo del prompt in `assistant/prompts.py`:
nella prima prova reale del 2026-11-14 lo stile `sintetico` («in pochi punti essenziali») faceva
riassumere solo le richieste dell'utente, senza i risultati (0 volte su 4); con «…, con le
richieste e i risultati ottenuti» 4 su 4 (dettagli nella §13 della
[specifica](docs/superpowers/specs/2026-11-14-prompt-mcp-design.md)).

**Più dettagli.** Con `$env:LOG_LEVEL = "DEBUG"` i log mostrano la traccia completa degli errori
e le richieste HTTP (del servizio verso LM Studio, della CLI verso il servizio).

### Strumenti MCP, livello per livello

**1. Il processo del server non parte.** Il servizio dell'agente esce con «Server MCP non avviato: …» (per
esempio «Connection closed»); il motivo dettagliato del sottoprocesso compare su stderr. Il server
si può avviare a mano: con l'ingresso chiuso deve uscire subito con codice 0, altrimenti mostra
l'errore (dipendenza mancante, modulo non trovato):

```powershell
$null | .\.venv\Scripts\python.exe -m assistant.mcp_server --notes-db data\notes.sqlite3 --preferences-file assistant\data\preferenze.json
$LASTEXITCODE    # 0
```

Senza `--preferences-file` il server esce con codice 2 («the following arguments are required»).

**2. Il catalogo degli strumenti è vuoto o incompleto.** All'avvio la riga `tools=[…]` deve
elencare otto strumenti; un nome atteso ma assente produce il WARNING «strumento MCP consentito ma
assente dal catalogo». La discovery si prova da sola (deve stampare sette righe):

```powershell
@'
from pathlib import Path
from assistant.mcp_client import McpClient, server_command
command, args, cwd = server_command(Path("data/notes.sqlite3").resolve(), "WARNING")
with McpClient(command, args, cwd=cwd) as client:
    for tool in client.list_tools():
        print(tool.name, "-", tool.description[:50])
'@ | .\.venv\Scripts\python.exe -
```

Il catalogo dei corsi si controlla così:

```powershell
.\.venv\Scripts\python.exe -c "from assistant.catalog import Catalog; print(Catalog.load().search('python'))"
```

**3. Lo strumento è elencato ma il modello non lo chiama.** Nei log manca la riga `tool=<nome>` e
la risposta è inventata (per esempio un orario o un risultato di calcolo). È un limite del modello,
non del programma: con `google/gemma-4-e2b` le 9 prove reali del 2026-11-09 sono passate, ma un
modello piccolo con otto strumenti può sceglierne uno sbagliato. Un altro modello si prova
cambiando solo `LMSTUDIO_MODEL` e ripetendo `pytest -m real`.

**4. Il risultato è corretto ma la risposta è sbagliata.** La riga `execution=ok … result=…` mostra
il valore giusto e la risposta del modello lo riporta male (per esempio l'orario UTC di
`created_at` presentato come ora locale). Anche questo è un limite del modello: il risultato
restituito si legge nel log, con lo stesso `call_id` della chiamata.

**LM Studio non raggiungibile dal container.** Si verifica così:

```powershell
docker compose run --rm -T agent python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:1234/v1/models').read()[:200])"
```

Deve stampare l'elenco dei modelli. Con Docker Desktop su Windows ha funzionato senza modificare
LM Studio; se fallisce, attivare in LM Studio l'opzione per servire anche sulla rete locale.

**`docker compose up` fallisce con «ports are not available: … 127.0.0.1:8080 … bind: Only one usage
of each socket address …».** La porta 8080 (o 8001) è già usata, di solito dallo stesso servizio
avviato a mano con `python -m frontend` (o `python -m backend`): fermarlo, oppure trovare il processo
con `netstat -ano | findstr :8080`. I servizi già partiti restano attivi; un nuovo `docker compose up
-d` avvia quello mancante.

**In Compose il back-end esce con «Database non raggiungibile: … password authentication failed for
user "lab"».** `POSTGRES_PASSWORD` nel `.env` è cambiata dopo la prima creazione del volume
`postgres-data`: PostgreSQL tiene la password con cui il volume è stato inizializzato. Rimettere
quella di prima, oppure eliminare il volume (cancella le chat): `docker compose down`, `docker volume
rm assistente-laboratorio_postgres-data` e di nuovo `docker compose up -d`. Lo stato si vede con `docker compose ps
-a` (`backend` `Exited (1)`) e il motivo con `docker compose logs backend`.

**Configurazione nel container.** Una variabile dell'agente si può sovrascrivere per una sola
esecuzione del servizio, per esempio per verificare il messaggio di configurazione mancante
(«Configurazione non valida: Manca LMSTUDIO_MODEL.», codice 1):

```powershell
docker compose run --rm -T -e LMSTUDIO_MODEL= agent
```
