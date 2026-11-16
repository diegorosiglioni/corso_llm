# Assistente del laboratorio

Progetto del corso «Deep Learning e LLM: costruire chatbot e agenti».
La cartella del progetto è `"C:\Users\diegorosiglioni\Desktop\paolo\test_paolo"`, radice della
repository: il progetto sta direttamente lì (fino al 2026-11-09 stava in `assistente-laboratorio/`).
Requisiti, specifica e piano: `docs/superpowers/`.
Stato corrente e prossimo passo: `PROGRESS.md` (diario di lavoro, ex `docs/superpowers/handoff.md`; leggerlo per primo) e debiti noti in `TODO.md`; prompt per la prossima sessione in `docs/superpowers/prossimo-prompt.txt`.

## Struttura e comandi
- Codice in `assistant/`: `config.py`, `model.py`, `tools.py`, `router.py`, `reviewer.py`,
  `summary.py`, `preferences.py`, `graph.py`, `agent.py` (turno senza stato e messaggi in JSON),
  `api.py` (app FastAPI del servizio HTTP dell'agente: `/chat`, `/chat/stream` in Server-Sent
  Events da `stream_turn` di `agent.py`, `/prompts`, `/status`),
  `service.py` (avvio del servizio con `python -m assistant.service`, `AGENT_HOST`/`AGENT_PORT`),
  `api_client.py` (client HTTP della CLI e del back-end: `AgentClient` con `chat_stream`,
  `iter_sse`, `AgentError`, `RemoteSession`),
  `session.py` (sessione in processo che usa `agent.py`, per prove reali e test), `terminal.py`,
  `commands.py` (comandi della CLI che cominciano con `/`, controllo dell'host dei prompt usato dal
  servizio); `__main__.py` è la CLI, client del servizio (`AGENT_URL`); ambito del router in
  `assistant/data/scope.txt` (sostituibile con `SCOPE_FILE`); preferenze dell'utente (resource MCP
  `utente://preferenze`) in `assistant/data/preferenze.json` (sostituibile con `PREFERENCES_FILE`);
  logica pura degli strumenti MCP in `units.py`,
  `calculator.py`, `catalog.py` (dati in `assistant/data/catalog.json`), `notes.py`; testi dei
  prompt MCP `spiega` e `riassumi_conversazione` in `prompts.py`; server
  FastMCP in `mcp_server.py`, client sincrono e adattatore in `mcp_client.py` (`server_command`
  vuole sempre il file delle preferenze: nessun valore predefinito). Solo
  `service.py` collega grafo, MCP e modelli; `__main__.py` collega client HTTP e terminale.
- Back-end (Step 7) nel pacchetto `backend/`, servizio distinto dall'agente: `db.py`
  (schema SQLAlchemy `chats`/`chat_messages`, `create_db_engine`, `init_db`), `store.py`
  (`ChatStore`: chat, messaggi visibili e stato dell'agente), `api.py` (app FastAPI: `/chats`,
  `/chats/{chat_id}`, `/chats/{chat_id}/messages` che inoltra la domanda all'agente e
  `/chats/{chat_id}/messages/stream` che ne inoltra il flusso SSE), `config.py` (`DATABASE_URL`, `AGENT_URL`, `BACKEND_HOST`/`BACKEND_PORT`),
  `__main__.py` (avvio con `python -m backend`). Da `assistant` importa solo il client dell'agente
  e la configurazione (logging, `AGENT_URL`, `LOG_LEVEL`); `assistant` non importa nulla da
  `backend`. Il back-end ammette il browser dalle origini di `CORS_ORIGINS`.
- Front-end (Step 8) nel pacchetto `frontend/`: `config.py` (`BACKEND_URL`,
  `FRONTEND_HOST`/`FRONTEND_PORT`), `app.py` (file statici e `/config.js`), `__main__.py` (avvio con
  `python -m frontend`), pagina in `frontend/static/` (HTML, CSS, JavaScript senza framework:
  `api.js` client del back-end con il lettore SSE `readEvents` e `sendMessageStream`, `texts.js`
  testi e funzioni pure, compresa `applyEvent` per la bozza in arrivo, `app.js` DOM; la pagina
  invia con lo streaming), contratto
  `frontend/backend-openapi.json` (OpenAPI del back-end, rigenerato con `UPDATE_CONTRACT=1` su
  `tests/test_frontend_contract.py`). Da `assistant` importa solo la configurazione; nulla da
  `backend`.
- Test in `tests/`; il modello finto (`FakeModel`; `StreamingFakeModel` per lo streaming), il router finto (`ConversationRouter`), il
  revisore finto (`ApprovingReviewer`), il client MCP finto (`FakeMcpClient`), il servizio finto
  (`fake_service`: l'app vera su un grafo finto, con `TestClient`) e gli aiuti comuni sono in
  `conftest.py`. I test MCP avviano il server
  reale via stdio. I test del back-end (`test_backend_*.py`) usano SQLite in memoria con lo stesso
  `init_db`, senza PostgreSQL. Le prove con LM Studio stanno in `test_real.py` (marcatore `real`).
  Il JavaScript del front-end si prova con `node --test` (`tests/frontend/*.test.mjs`, lanciati da
  `test_frontend_js.py`); la pagina in Edge con Playwright in `test_frontend_browser.py`
  (marcatore `browser`, escluso dalla suite predefinita). I Dockerfile si controllano come testo
  in `test_docker.py`, e `compose.yaml` con `docker compose config` (copia in una cartella
  temporanea con un `.env` finto; saltato senza la CLI di Docker).
- Immagini Docker (Step 9): un Dockerfile per servizio in `docker/` (`agent.Dockerfile`, che serve
  anche la CLI, `backend.Dockerfile`, `frontend.Dockerfile`), contesto di build la radice; stesse
  prime istruzioni (base fissata e `requirements.txt`) per condividere il livello delle dipendenze.
  `compose.yaml`: `frontend` (`127.0.0.1:8080`), `backend` (`127.0.0.1:8001`), `agent` e `postgres`
  (non pubblicati, volumi `notes-data` e `postgres-data`), CLI `assistant` nel profilo `cli`;
  credenziali `POSTGRES_*` nel `.env` (password obbligatoria per ogni comando `docker compose`).
- Note in SQLite: in locale `NOTES_DB` (default `data/notes.sqlite3`, ignorato da Git), in
  Docker il volume `notes-data`.
- Dipendenze dirette in `requirements.txt` (app) e `requirements-dev.txt` (test); tutte le
  versioni verificate in `constraints.txt`, richiamato da `requirements.txt`.
- Comandi da PowerShell nella radice della repository, senza attivare l'ambiente:
  - ambiente: `py -3.13 -m venv .venv` e `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`
  - test senza modello: `.\.venv\Scripts\python.exe -m pytest`
  - pagina del front-end nel browser (Edge installato; Chrome con `BROWSER_CHANNEL=chrome`):
    `.\.venv\Scripts\python.exe -m pytest -m browser`
  - prove reali (LM Studio attivo, variabili impostate; circa 30 minuti): `.\.venv\Scripts\python.exe -m pytest -m real -v`
  - prove reali del back-end (PostgreSQL nel container del README, porta 5433):
    `$env:TEST_DATABASE_URL = "postgresql://lab:labprova@127.0.0.1:5433/assistente"`, poi
    `.\.venv\Scripts\python.exe -m pytest tests/test_backend_store.py -m real` (solo PostgreSQL),
    `.\.venv\Scripts\python.exe -m pytest tests/test_real.py -m real -k backend` e, dal browser con
    tutti i servizi, `.\.venv\Scripts\python.exe -m pytest tests/test_real.py -m real -k frontend`
    (compreso lo streaming; solo le prove dello streaming con `-k stream`)
  - avvio locale, in due terminali: servizio `.\.venv\Scripts\python.exe -m assistant.service`
    (variabili di LM Studio), poi CLI `.\.venv\Scripts\python.exe -m assistant`; back-end in un
    terzo terminale con `DATABASE_URL` impostata: `.\.venv\Scripts\python.exe -m backend`;
    front-end in un quarto: `.\.venv\Scripts\python.exe -m frontend` (pagina su
    `http://127.0.0.1:8080`)
  - Docker: `docker compose up -d --build` avvia `frontend`, `backend`, `agent` e `postgres`
    (`docker compose ps`, `docker compose logs agent`, pagina su `http://127.0.0.1:8080`);
    `docker compose down` li ferma (i volumi restano). La CLI solo con
    `docker compose run --rm assistant` (profilo `cli`; avvia anche `agent`, che resta attivo fino a
    `docker compose down`)

## Obiettivo
Un'applicazione in Python (terminale e pagina web) che conversa con un modello locale e:
- organizza il flusso in un grafo LangGraph esplicito (stato, nodi, instradamento riconoscibili);
- (lezione 6, Step 1) un router LLM prima dell'agente, con ambito in configurazione, manda le
  domande fuori ambito a un nodo di rifiuto senza eseguire l'agente;
- (lezione 6, Step 2) un revisore LLM dopo la risposta finale dell'agente controlla che sia
  coerente con la domanda e, se non lo è, rimanda all'agente il motivo, fino a `MAX_REVIEWS`;
- (lezione 6, Step 3) un nodo riassunto all'inizio del turno, oltre `SUMMARY_MAX_MESSAGES`,
  sostituisce i turni vecchi con un riassunto nello stato (letto da agente, router e revisore) e
  conserva almeno gli ultimi `SUMMARY_KEEP_MESSAGES`, tagliando sempre all'inizio di un turno;
- (lezione 6, Step 4) legge una volta, all'avvio del servizio dell'agente, la resource MCP
  `utente://preferenze` (lingua, fuso predefinito, stile) e la mette in cima al prompt di sistema
  dell'agente; una modifica vale dal riavvio del servizio;
- (lezione 6, Step 5) i comandi `/prompts` e `/prompt nome chiave=valore` elencano e richiamano i
  prompt MCP `spiega` e `riassumi_conversazione`; i messaggi ottenuti passano dal grafo;
- (lezione 6, Step 6) espone il grafo come servizio HTTP dell'agente (FastAPI, senza stato:
  cronologia e riassunto arrivano dal chiamante e tornano aggiornati); la CLI è un suo client;
- (lezione 6, Step 7) un back-end separato salva chat e messaggi in PostgreSQL e inoltra le
  domande all'agente con la cronologia salvata;
- (lezione 6, Step 8) un front-end web (HTML, CSS e JavaScript senza framework) parla solo con il
  back-end: elenco, creazione ed eliminazione delle chat, messaggi con gli strumenti usati;
- (lezione 6, Step 9) Docker Compose con quattro container: front-end, back-end, agente (non
  esposto, con il server MCP stdio dentro) e PostgreSQL;
- (facoltativo) risposta in streaming con Server-Sent Events, bozza mostrata mentre arriva e
  salvata solo alla fine;
- usa un modello servito da LM Studio, che resta sul computer host;
- conserva la cronologia della conversazione per la durata della sessione nella CLI; nel
  back-end le chat sono persistenti;
- offre uno strumento orologio con fuso orario esplicito, richiesto dal modello tramite tool calling
  ed eseguito davvero dal programma;
- (lezione 5) collega un server MCP locale (FastMCP, stdio) che espone convertitore di unità,
  calcolatrice sicura, catalogo locale e note persistenti su SQLite, scoperti con `tools/list`;
- si avvia anche con Docker Compose.

## Confini
- Implementare solo i requisiti concordati. MCP e i quattro strumenti della lezione 5 e gli
  Step 1–9 della lezione 6 (router, revisore, riassunto, resource delle preferenze, prompt MCP,
  servizio HTTP, back-end, front-end, Compose a quattro container) e lo streaming facoltativo sono
  implementati; i debiti noti rimasti sono in `TODO.md`;
  altri strumenti, altri server MCP, workflow e RAG non vanno anticipati: ognuno avrà il proprio
  ciclo di specifica e piano.
- Niente interfacce grafiche oltre al front-end web dello Step 8, niente servizi cloud o
  framework non concordati.
- La cartella `lezione3/` è una lezione passata: resta solo in locale, esclusa da Git con
  `.gitignore`. Non leggerla per copiarne il codice e non modificarla.
- Lavorare nel branch `dev`; nessun altro branch o worktree se non richiesto.

## Scelte tecniche
- Python, codice sincrono e moduli piccoli, con una separazione semplice tra
  grafo, collegamento al modello, strumenti e interfaccia da terminale. L'asincronia del client
  MCP resta confinata nel suo modulo, che offre metodi sincroni.
- Lingua: codice in inglese (identificatori, moduli, variabili d'ambiente, nomi e argomenti degli
  strumenti, chiavi JSON, commenti); in italiano prompt di sistema, testi del terminale,
  descrizioni degli strumenti e messaggi d'errore; documentazione e commit in italiano.
- LM Studio sull'host, raggiunto tramite la sua API compatibile con OpenAI.
- Indirizzo del server e identificativo del modello solo da variabili d'ambiente.
  L'identificativo è quello restituito dal server (`GET /v1/models`), mai inventato.
- Un file di configurazione di esempio senza credenziali; il file reale resta fuori da Git.
- Docker Compose per l'applicazione; LM Studio non va containerizzato.
- Dipendenze motivate, concordate e con versioni fissate.
- Comandi documentati anche per PowerShell (Windows).

## Metodo: Superpowers
- Usare le skill di Superpowers per brainstorming, specifica, piano, implementazione e verifica.
- Non scrivere codice prima che io abbia approvato la specifica e poi il piano.
- Salvare specifica e piano in `docs/superpowers/`.
- Procedere per incrementi piccoli, ciascuno verificato prima del commit.

## Test e verifiche
- Test automatici ripetibili che non richiedono un modello attivo (grafo, cronologia,
  instradamento, strumento con istante controllato).
- Prove reali con LM Studio e con Docker tenute separate e attivate esplicitamente.
- Una risposta simulata non dimostra che il modello locale sappia usare lo strumento.
- Nel resoconto indicare che cosa è stato eseguito, con quale esito, e che cosa resta da provare.

## Git
- Conventional Commits in italiano, per esempio `feat(grafo): ...`, `test(strumenti): ...`,
  `docs: ...`.
- Prima di ogni commit: `git status`, controllo del diff, staging selettivo dei soli file pertinenti.
- Mai versionare credenziali, `.env`, ambienti virtuali, cache o pesi dei modelli.
- Push soltanto su mia richiesta, e Claude lo esegue per intero, in due passi:
  1. i commit si fanno su `dev`, mai direttamente su `main`; push con `git push origin dev`;
  2. `main` si porta allo stesso commit con un avanzamento rapido: `git push origin dev:main`,
     poi `git fetch origin main:main` per allineare il `main` locale.
  Se l'avanzamento rapido viene rifiutato (`main` ha commit che `dev` non ha), fermarsi e chiedere:
  niente `--force`, niente merge automatici.

## Nota storica: modalità autonoma
Il 2026-11-14 un loop senza nessuno che rispondesse ha fatto gli Step 4–9 e lo streaming sul branch
`auto-claude`; revisione, correzioni e prove sono in `PROGRESS.md`, script e prompt in `_archivio/`, solo in
locale (esclusa da Git).

## Documentazione
- Tenere aggiornato il README con configurazione, avvio, test e diagnosi, riportando solo
  comandi verificati.
- Aggiornare questo file quando cambiano convenzioni stabili (struttura, comandi di test,
  regole di lavoro), non per annotare l'avanzamento. 