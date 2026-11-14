# Specifica — Lezione 6, Step 8: front-end, interfaccia di chat

Data: 2026-11-14
Stato: scritta in modalità autonoma (branch `auto-claude`): l'approvazione è sostituita dal piano
in [`../../../PROGRESS.md`](../../../PROGRESS.md) (regola di `CLAUDE.md`, «Modalità autonoma»).
Requisiti: [`../requisiti.md`](../requisiti.md), §16 (RF-68…RF-75, CA-79…CA-87).
Specifiche precedenti: [`2026-11-14-backend-chat-design.md`](2026-11-14-backend-chat-design.md)
(Step 7, il back-end di cui questo step è il client) e quelle che richiama.
Fonte didattica: `LLM_Lez_6.pdf`, Blocco C e Step 8; riassunto in [`../lezione6.md`](../lezione6.md).

Un'**interfaccia di chat nel browser**, usabile da chi non conosce il progetto, parla **solo con il
back-end** dello Step 7: elenca, crea ed elimina le chat, mostra i messaggi di una chat, invia una
domanda e mostra la risposta con gli strumenti usati, con uno stato di attesa e messaggi d'errore
comprensibili. Il contratto è il documento OpenAPI del back-end; l'indirizzo del back-end viene dalla
configurazione. Agente, back-end e database non cambiano, salvo il CORS del back-end (§6).

```
browser ── pagina e /config.js ──→ front-end (questo step, python -m frontend, porta 8080)
   │
   └──── fetch JSON (CORS) ──────→ back-end (Step 7, porta 8001) → agente (Step 6) → LM Studio
                                        ↓
                                    PostgreSQL
```

## 1. Decisioni

Tutte «scelta del progettista» (modalità autonoma: opzione consigliata o più standard). La traccia
lascia libera la tecnologia.

| Tema | Decisione | Motivo |
|------|-----------|--------|
| Tecnologia della pagina | **HTML, CSS e JavaScript standard** (moduli ES), senza framework, senza `npm` né passo di build | Cinque operazioni e una vista di messaggi non giustificano un framework (React, Vue…) né una catena Node in esercizio; il browser esegue i file così come sono, e chi legge il codice non deve conoscere altro. `CLAUDE.md` vieta framework non concordati |
| Chi serve la pagina | Pacchetto **`frontend/`** con un piccolo servizio **FastAPI + uvicorn** (`python -m frontend`) che serve i file statici (`StaticFiles`) e `/config.js` | È un componente a sé (Step 9: un container per componente); FastAPI e uvicorn sono già fissati (Step 6), quindi nessuna dipendenza nuova in esercizio, stesso stile d'avvio, di log e di test degli altri due servizi (`TestClient`) |
| Indirizzo del back-end | Variabile **`BACKEND_URL`** (predefinita `http://127.0.0.1:8001`) letta dal servizio del front-end e consegnata al browser da **`GET /config.js`** (`window.APP_CONFIG = {"backendUrl": …}`) | La pagina statica non legge l'ambiente: un file di configurazione generato all'avvio è il modo standard di configurare un'applicazione statica senza ricostruirla. L'indirizzo è quello **visto dal browser** (allo Step 9: la porta pubblicata del back-end, non il nome del servizio Compose) |
| Come il browser raggiunge il back-end | **Direttamente** (`fetch` verso `BACKEND_URL`), con il **CORS** abilitato nel back-end per le origini di `CORS_ORIGINS` | Il front-end resta solo statico e «parla solo con il back-end» in modo visibile negli strumenti del browser; `CORSMiddleware` è già in FastAPI. Un proxy nel servizio del front-end sarebbe codice in più da scrivere e provare; la traccia ammette entrambe le strade (Step 9: «porta pubblicata o proxy») |
| `CORS_ORIGINS` (back-end) | Elenco separato da virgole, predefinito `http://127.0.0.1:8080,http://localhost:8080`; metodi `GET`, `POST`, `DELETE`, intestazione `Content-Type`; niente `*`, niente credenziali | Le due forme con cui si apre il front-end in locale; un elenco esplicito invece di `*` è la pratica consigliata. Nessun cookie o autenticazione da inviare |
| Contratto | Il documento OpenAPI del back-end (`/openapi.json`) salvato in **`frontend/backend-openapi.json`**; un test controlla che sia identico a quello generato da `backend.api.create_app`, un altro che ogni richiesta del client JavaScript (metodo e percorso) e ogni campo che la pagina legge esistano nel documento | È il contratto chiesto dalla traccia, leggibile nella repository; se il back-end cambia, il test lo segnala prima che la pagina si rompa. Rigenerazione: `UPDATE_CONTRACT=1` sul test (§9) |
| Struttura del JavaScript | `api.js` (client HTTP del back-end ed errori), `texts.js` (testi, messaggi d'errore e formattazione, funzioni pure), `app.js` (stato della pagina e DOM) | Le parti senza DOM si provano con Node senza browser; il DOM si prova nel browser |
| Testo dei messaggi | Testo semplice con gli a capo (`textContent`, `white-space: pre-wrap`), niente Markdown né HTML | Nessuna libreria di Markdown da aggiungere; `textContent` rende impossibile iniettare HTML dalla risposta del modello. Gli eventuali `**…**` del modello restano visibili come tali |
| Strumenti usati | Sotto la risposta: «Strumenti usati: calculate»; un elemento `<details>` mostra argomenti e risultato in JSON; uno strumento con `ok: false` è segnato «(errore)» | È l'evidenza della traccia («conversazione con uno strumento») visibile a chi usa la pagina, senza ingombrare la lettura |
| Stato di attesa | La domanda compare subito; sotto, «L'assistente sta rispondendo…» con i secondi trascorsi; campo e pulsante «Invia» disattivati **solo per quella chat** | Il turno dura da secondi a minuti (modello locale): l'utente deve vedere che qualcosa succede e poter intanto leggere o creare altre chat. Un invio alla volta per chat, come assume il back-end (specifica dello Step 7, §13) |
| Tempo massimo nel browser | `AbortController` a **660 s** per l'invio (10 s per le altre richieste) | Il back-end aspetta l'agente fino a 600 s e poi risponde `504`; il margine lascia arrivare quel `504`. Un limite evita un'attesa infinita se il back-end resta appeso |
| Errori | Un riquadro in cima alla vista, in italiano, con il motivo e che cosa fare (§5), chiudibile; la pagina resta usabile. Dopo un errore dell'invio la chat si rilegge dal back-end, così mostra la domanda salvata | La traccia chiede errori comprensibili e un'interfaccia che non si blocca con l'agente spento |
| Chat selezionata | Nell'indirizzo della pagina (`#/chats/3`) | Ricaricare la pagina (o riavviare il back-end e ricaricare) riporta alla stessa chat; i link si possono copiare |
| Eliminazione | Conferma con la finestra standard del browser (`confirm`) che riporta il titolo | Un'eliminazione cancella anche i messaggi e non si annulla |
| Date | Formato italiano con l'ora locale del browser (`Intl.DateTimeFormat("it-IT")`); oggi solo l'ora | Il back-end restituisce ISO 8601 in UTC; l'utente legge l'ora del suo computer |
| Porta del front-end | `FRONTEND_HOST` (predefinito `127.0.0.1`) e `FRONTEND_PORT` (predefinita `8080`) | Diversa da agente (8000) e back-end (8001); 8080 è libera su questo computer (verificato con `netstat`) |
| Test del JavaScript senza browser | **`node --test`** (runner integrato di Node.js, verificato con Node 24.15.0), nessun pacchetto `npm`; lanciato da un test pytest, che si salta col motivo se Node manca | Nessuna dipendenza nuova: Node serve solo come interprete per i test, e `pytest` resta l'unico comando |
| Test nel browser | **Playwright per Python 1.65.2** (`playwright` in `requirements-dev.txt`, unica indiretta nuova `greenlet` 3.5.6) con il **browser già installato** (`channel="msedge"`, oppure `chrome` con `BROWSER_CHANNEL`), nuovo marcatore **`browser`** escluso dalla suite predefinita | La traccia chiede «test automatici dove possibili» e una prova reale dal browser, che in modalità autonoma nessuno può fare a mano. Playwright è lo strumento standard per pilotare un browser da Python; con `channel` usa Edge o Chrome installati, senza scaricare browser. Marcatore a parte perché richiede un browser sul computer e apre processi esterni; si esegue con `pytest -m browser` |

## 2. Struttura

```
frontend/
├── __init__.py
├── __main__.py           # avvio: configurazione, logging, uvicorn
├── config.py             # FrontendConfig, load_frontend_config (BACKEND_URL, FRONTEND_HOST/PORT)
├── app.py                # create_app(config): GET /config.js e file statici
├── backend-openapi.json  # contratto: OpenAPI del back-end (non servito al browser)
└── static/
    ├── index.html
    ├── style.css
    ├── api.js            # BackendClient, BackendError
    ├── texts.js          # testi, errorMessage, formatDate, toolsSummary
    └── app.js            # stato della pagina, eventi, DOM
tests/
├── frontend/*.test.mjs   # node --test: api.js e texts.js, contratto
├── test_frontend_js.py   # esegue node --test (saltato se Node manca)
├── test_frontend_config.py, test_frontend_app.py, test_frontend_service.py, test_frontend_contract.py
└── test_frontend_browser.py   # marcatore browser: la pagina vera in Edge con back-end e agente finti
```

Il front-end Python importa da `assistant` solo `config.ConfigError` e `config.configure_logging`
(come il back-end); non importa nulla da `backend` (solo il test del contratto lo fa). Il JavaScript
non conosce agente né database: solo `BACKEND_URL`.

## 3. Servizio del front-end (`frontend/app.py`, `frontend/__main__.py`)

- `create_app(config) -> FastAPI`, senza documentazione OpenAPI propria (`docs_url=None`,
  `openapi_url=None`: non è un'API).
- `GET /config.js` → `window.APP_CONFIG = {"backendUrl": "<BACKEND_URL>"};` con
  `Content-Type: text/javascript` e `Cache-Control: no-store` (cambiare `BACKEND_URL` e riavviare
  basta, senza cache del browser). Il valore è serializzato con `json.dumps`.
- Tutto il resto da `frontend/static/` (`StaticFiles(html=True)`: `/` → `index.html`); file
  inesistente → `404`.
- Avvio: configurazione (errore → «Configurazione non valida: …» su stderr, exit 1), logging,
  `uvicorn.run(app, host=…, port=…, access_log=False, log_config=None)`. Riga d'avvio (logger
  `frontend.service`): `frontend listening=http://<host>:<port> backend_url=<url>`. Il back-end spento
  all'avvio non impedisce l'avvio: lo segnala la pagina.

## 4. Configurazione

| Variabile | Servizio | Predefinito | Regole |
|-----------|----------|-------------|--------|
| `BACKEND_URL` | front-end | `http://127.0.0.1:8001` | deve iniziare con `http://` o `https://`; perde la `/` finale |
| `FRONTEND_HOST` | front-end | `127.0.0.1` | testo non vuoto |
| `FRONTEND_PORT` | front-end | `8080` | intero tra 1 e 65535 |
| `LOG_LEVEL` | front-end | `INFO` | come negli altri servizi |
| `CORS_ORIGINS` | back-end | `http://127.0.0.1:8080,http://localhost:8080` | origini separate da virgola, ciascuna `http(s)://host[:porta]` senza percorso; spazi e `/` finale tolti; elenco vuoto o voce non valida → errore di configurazione |

Più problemi → un solo messaggio, come negli altri servizi. `.env.example`: righe di commento per le
quattro variabili nuove. La riga d'avvio del back-end aggiunge `cors_origins=<elenco>`.

## 5. La pagina

Una sola pagina (`index.html`), in italiano, in due colonne (su schermi stretti una sotto l'altra):

- **Colonna delle chat**: pulsante «Nuova chat»; elenco dal più recente con titolo e data
  dell'ultimo messaggio (oppure «nessun messaggio»); la chat selezionata è evidenziata; accanto a
  ogni chat un pulsante «Elimina» (con `aria-label` «Elimina la chat <titolo>»). Elenco vuoto →
  «Nessuna chat. Premi "Nuova chat" per iniziare.».
- **Vista della chat**: titolo; messaggi in ordine (domande a destra, risposte a sinistra, con
  l'ora); sotto ogni risposta gli strumenti usati (§1); in fondo un campo di testo
  («Scrivi una domanda…»; Invio invia, Maiusc+Invio va a capo) e il pulsante «Invia». Senza chat
  selezionata: «Seleziona una chat o creane una nuova.». Chat senza messaggi: «Nessun messaggio:
  scrivi la prima domanda.».
- **Riquadro degli errori** in cima alla vista, `role="alert"`, con un pulsante «Chiudi»; un nuovo
  errore sostituisce il precedente.
- Mentre si carica l'elenco o una chat: «Caricamento…».

Flussi:
- *Apertura*: legge `/config.js`, chiede `GET /chats`; se l'indirizzo contiene `#/chats/<id>`, apre
  quella chat (`GET /chats/<id>`; `404` → errore «chat non trovata» e nessuna selezione).
- *Nuova chat*: `POST /chats` senza titolo → la chat compare in cima e si apre, con il campo di testo
  pronto.
- *Elimina*: conferma → `DELETE /chats/<id>` → tolta dall'elenco; se era aperta, la vista torna vuota.
- *Invio*: testo senza spazi ai lati vuoto → niente richiesta. Altrimenti la domanda compare subito
  (in attesa), poi `POST /chats/<id>/messages`. `201` → domanda e risposta salvate al posto di quella
  in attesa, elenco aggiornato (titolo e data). Errore → messaggio (tabella sotto), la chat si
  rilegge dal back-end (la domanda salvata resta visibile), il testo inviato torna nel campo se la
  domanda non è stata salvata (back-end non raggiungibile, `400`, `422`). Se nel frattempo l'utente
  ha aperto un'altra chat, la risposta aggiorna solo l'elenco.

Messaggi d'errore (`texts.js`, `errorMessage(error, backendUrl)`):

| Situazione | Messaggio |
|------------|-----------|
| Back-end non raggiungibile (`fetch` fallisce) | «Il back-end non risponde (http://127.0.0.1:8001). Controlla che sia avviato e riprova.» |
| Tempo scaduto nel browser | «Il back-end non ha risposto in tempo. Riprova.» |
| `503 agent_unavailable` | «L'assistente non è raggiungibile in questo momento. La domanda è salvata nella chat: riprova più tardi.» |
| `504 agent_timeout` | «L'assistente non ha risposto in tempo. La domanda è salvata nella chat: riprova.» |
| `502 agent_error` | «L'assistente ha risposto con un errore: <detail>. La domanda è salvata nella chat: riprova.» |
| `503 database_unavailable` | «L'archivio delle chat non è disponibile. Riprova tra poco.» |
| `404 chat_not_found` | «Questa chat non esiste più.» (l'elenco si rilegge) |
| `400 invalid_request` | «Richiesta non valida: <detail>.» |
| Ogni altra risposta (`422`, `500`, corpo non JSON) | «Errore del back-end (<codice>): <detail, se c'è>.» |

## 6. CORS nel back-end

`backend/config.py`: `BackendConfig.cors_origins: tuple[str, ...]` da `CORS_ORIGINS` (§4).
`backend/api.py`: `create_app(*, store, agent, cors_origins=())` aggiunge `CORSMiddleware` con
quelle origini, metodi `GET`/`POST`/`DELETE` e intestazione `Content-Type` quando l'elenco non è
vuoto. Le risposte d'errore del back-end portano anch'esse le intestazioni CORS (il middleware avvolge
tutta l'app), così il browser può leggere `error` e `detail`. Nessun altro cambiamento al back-end.

## 7. Client JavaScript (`api.js`)

```js
export class BackendError extends Error { status; code; detail }   // status 0 = rete o tempo scaduto
export class BackendClient {
  constructor(baseUrl, { fetch = globalThis.fetch, timeoutMs = 10_000, sendTimeoutMs = 660_000 } = {})
  listChats()            // GET    /chats                 → ChatInfo[]
  createChat()           // POST   /chats  {}             → ChatInfo
  getChat(id)            // GET    /chats/{id}            → ChatDetail
  deleteChat(id)         // DELETE /chats/{id}            → null (204)
  sendMessage(id, text)  // POST   /chats/{id}/messages   → SendMessageResponse
}
```

- Risposta `2xx` → corpo JSON (nessuno per `204`); altrimenti `BackendError(status, error, detail)`
  dal corpo `{"error", "detail"}`, oppure `code` `null` se il corpo non lo è.
- `fetch` che fallisce → `BackendError` con `status` 0 e `code` `"network"`; tempo scaduto →
  `code` `"timeout"`. `fetch` è un parametro: nei test con Node è una funzione finta.

## 8. Log

Il front-end non scrive righe per le richieste (servono solo file statici): la riga d'avvio basta, e
gli errori di uvicorn restano nel log. Le operazioni sulle chat si leggono nel log del back-end
(Step 7) e i turni in quello dell'agente (Step 6): sono queste le evidenze della prova reale.

## 9. Test

### Senza browser né modello (`pytest`)

- `test_frontend_config.py`: predefiniti, valori dall'ambiente, `BACKEND_URL` non http, porta non
  valida, messaggio unico; `CORS_ORIGINS` in `test_backend_config.py` (predefinito, elenco, spazi e
  `/` finale, voce non valida, elenco vuoto).
- `test_frontend_app.py` (`TestClient`): `/` è la pagina con i tre script, `/config.js` con
  l'indirizzo configurato, tipo e `no-store`, file statici con il loro tipo, `404`, niente `/docs`.
- `test_frontend_service.py`: avvio con `uvicorn.run` sostituito (indirizzo, riga d'avvio),
  configurazione non valida → exit 1.
- `test_backend_api.py`: richiesta preliminare (`OPTIONS`) e risposte con
  `Access-Control-Allow-Origin` per un'origine ammessa, anche su un errore; nessuna intestazione per
  un'origine non ammessa.
- `test_frontend_contract.py`: `frontend/backend-openapi.json` uguale a
  `create_app(...).openapi()` del back-end; con `UPDATE_CONTRACT=1` il test riscrive il file.
- `test_frontend_js.py` → `node --test tests/frontend/*.test.mjs`: `BackendClient` con un `fetch`
  finto (metodi, percorsi, corpi, `204`, errori con e senza corpo JSON, rete, tempo scaduto),
  `errorMessage` per ogni riga della tabella di §5, `formatDate`, `toolsSummary`; contratto: ogni
  richiesta del client e ogni campo letto dalla pagina esistono in `backend-openapi.json`.

### Nel browser (`pytest -m browser`)

`test_frontend_browser.py`: back-end vero (`create_app` con archivio su SQLite in memoria e CORS) e
servizio del front-end avviati con uvicorn su porte libere, agente finto controllabile (risposta con
uno strumento, risposta lenta, `AgentError`); la pagina vera in Edge senza finestra. Casi: elenco
vuoto; creazione, elenco e selezione; eliminazione con conferma (e annullata); invio con stato
d'attesa e risposta con gli strumenti; durante l'attesa si può creare e aprire un'altra chat; agente
spento → messaggio, domanda visibile, pagina usabile; back-end spento → messaggio; ricarica della
pagina con la chat selezionata; testo con HTML mostrato come testo.

### Prova reale (`pytest -m real -k frontend`)

PostgreSQL (`TEST_DATABASE_URL`, schema temporaneo come allo Step 7), agente con LM Studio, back-end
e front-end come sottoprocessi, Edge con Playwright: nuova chat, «Quanto fa 17 * 23?» → risposta con
«391» e «calculate» tra gli strumenti mostrati (e nel log dell'agente); back-end fermato e riavviato,
pagina ricaricata → chat e messaggi presenti; agente fermato → messaggio d'errore mostrato, domanda
salvata, si può ancora creare una chat. Schermate salvate nella cartella temporanea del test. Se un
servizio (LM Studio, PostgreSQL, browser) non è raggiungibile, il punto si segna `[!]`.

## 10. Dipendenze

`playwright==1.65.2` in `requirements-dev.txt` (solo test, non nell'immagine); in `constraints.txt`
le righe nuove `playwright==1.65.2` e `greenlet==3.5.6` (confrontato `pip freeze` prima e dopo
l'installazione: nessun'altra differenza; `pip check` pulito). Nessun browser scaricato: Playwright
usa Edge (157) o Chrome (157) già installati. Node.js (≥ 22, verificato 24.15.0) serve solo ai test
del JavaScript, non è una dipendenza Python e non entra nell'immagine. Verificato con uno script usa e
getta fuori dal progetto: Edge e Chrome pilotati da Playwright, pagina servita da FastAPI che legge
`/config.js` e chiama con `fetch` un'altra app FastAPI con `CORSMiddleware` (`POST` `201`, `DELETE`
`204`, porta chiusa → `TypeError`); `node --test` importa un modulo ES `.js` senza `package.json`.

## 11. Docker in questo step

`compose.yaml` e `Dockerfile` non cambiano: l'immagine del front-end e i quattro container sono lo
Step 9. Per lo Step 9 restano da decidere l'immagine del front-end e la porta pubblicata del back-end,
che `BACKEND_URL` e `CORS_ORIGINS` dovranno indicare dal punto di vista del browser.

## 12. Incrementi

Coincidono con i punti dello Step 8 in `TODO.md`; ognuno verificato con `pytest` (e `pytest -m
browser` dal punto 2) prima del commit.

1. Questa specifica, i requisiti §16, la dipendenza `playwright`.
2. Pacchetto `frontend/` (configurazione, servizio, avvio), contratto, CORS del back-end; pagina con
   elenco, creazione ed eliminazione; marcatore `browser`; test.
3. Vista dei messaggi e invio, stato di attesa ed errori; test con Node e nel browser.
4. Prova reale dal browser; README (avvio del front-end, uso, diagnosi) e `CLAUDE.md`; esiti in
   requisiti §16 e nel diario.

## 13. Rischi

- **Quattro processi in locale** (agente, back-end, front-end, PostgreSQL in Docker): il README li
  elenca in ordine; lo Step 9 li riunisce in Compose.
- **Origine non ammessa**: aprire la pagina da un indirizzo diverso da quelli di `CORS_ORIGINS` (per
  esempio `localhost` contro `127.0.0.1` con un elenco ridotto) dà «Il back-end non risponde»,
  perché il browser nasconde l'errore CORS. Il README lo mette in «Diagnosi».
- **Browser nei test**: `pytest -m browser` richiede Edge o Chrome; senza, i test falliscono col
  motivo di Playwright (si sceglie l'altro con `BROWSER_CHANNEL`).
- **Risposte lunghe del modello locale**: l'attesa può durare minuti; il contatore dei secondi mostra
  che la pagina non è bloccata.
- **Markdown non interpretato**: le risposte con `**…**` o elenchi Markdown si leggono come testo.

## 14. Fuori ambito

Streaming (facoltativo), Compose a quattro container e immagine del front-end (Step 9), proxy delle
API nel front-end, autenticazione, rinomina delle chat, modifica di singoli messaggi, prompt MCP e
stato dell'agente nella pagina, Markdown, temi, traduzioni, framework e passo di build JavaScript.
