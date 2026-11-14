# Specifica — Lezione 6, Step 7: back-end, API e salvataggio delle chat

Data: 2026-11-14
Stato: scritta in modalità autonoma (branch `auto-claude`): l'approvazione è sostituita dal piano
in [`../../../PROGRESS.md`](../../../PROGRESS.md) (regola di `CLAUDE.md`, «Modalità autonoma»).
Requisiti: [`../requisiti.md`](../requisiti.md), §15 (RF-60…RF-67, CA-70…CA-78).
Specifiche precedenti: [`2026-11-14-servizio-http-design.md`](2026-11-14-servizio-http-design.md)
(Step 6) e quelle che richiama.
Fonte didattica: `LLM_Lez_6.pdf`, Blocco C e Step 7; riassunto in [`../lezione6.md`](../lezione6.md).

Un **servizio back-end** separato dall'agente è l'unico punto di contatto del front-end (Step 8):
gestisce le chat, le salva in **PostgreSQL** e inoltra ogni domanda all'agente dello Step 6 via HTTP
(`POST /chat`), passando la cronologia e il riassunto della chat e salvando quelli aggiornati. Le
chat restano dopo il riavvio del back-end. L'agente non cambia: resta senza stato e non sa nulla del
database. Dove non dice altro, valgono le specifiche precedenti.

```
front-end (Step 8) → HTTP → back-end (questo step) → HTTP → agente (Step 6) → LM Studio
                               ↓
                           PostgreSQL
```

## 1. Decisioni

Tutte «scelta del progettista» (modalità autonoma: opzione consigliata o più standard).

| Tema | Decisione | Motivo |
|------|-----------|--------|
| Dove sta il codice | Nuovo pacchetto **`backend/`** nella radice, accanto ad `assistant/` | È un servizio distinto (Step 9: un container e un Dockerfile per componente); il pacchetto `assistant/` resta l'agente e la CLI |
| Framework HTTP | **FastAPI** con uvicorn, endpoint sincroni, come l'agente | Stesse librerie già fissate; OpenAPI generata dal codice, che lo Step 8 usa come contratto |
| Accesso al database | **SQLAlchemy 2.1.8** (ORM dichiarativo, sessioni sincrone) con il driver **psycopg 3.3.9** (`psycopg[binary]`) | SQLAlchemy è lo standard Python per i database relazionali e fa girare lo stesso codice su PostgreSQL (esercizio) e su SQLite in memoria (test senza PostgreSQL). psycopg 3 è il driver PostgreSQL consigliato da SQLAlchemy 2; la variante `binary` porta la libreria client compilata (niente `libpq` da installare su Windows o nell'immagine). Verificato con i vincoli attuali: aggiunge solo `SQLAlchemy`, `psycopg`, `psycopg-binary`; `pip check` pulito |
| Creazione dello schema | `metadata.create_all` all'avvio (crea le tabelle mancanti, non tocca quelle esistenti) | Lo schema è nuovo e piccolo; uno strumento di migrazione (Alembic) sarebbe una dipendenza senza uso. Se lo schema cambierà, quel passo avrà la sua specifica |
| Chiamata all'agente | Il back-end usa `AgentClient.chat` di `assistant/api_client.py` | Un solo client HTTP dell'agente, con gli stessi codici d'errore (`agent_unreachable`, `agent_timeout`, `bad_response` e quelli del servizio) e lo stesso timeout di 600 s; niente codice duplicato. Conseguenza per lo Step 9: l'immagine del back-end contiene il pacchetto `assistant` e le dipendenze comuni (stessi `requirements.txt` e `constraints.txt`) |
| Che cosa si salva | Due cose distinte: i **messaggi della chat** (domande e risposte che l'utente vede, con gli strumenti usati) in una tabella, e lo **stato dell'agente** (cronologia JSON dello Step 6 e riassunto) nella riga della chat | La cronologia dell'agente contiene chiamate agli strumenti, bozze e indicazioni del revisore, e dopo un riassunto perde i turni vecchi: non è ciò che l'utente deve rileggere. «Leggere una chat» mostra tutti i messaggi, anche quelli già riassunti per l'agente |
| Cronologia dell'agente nel database | Colonna JSON salvata e restituita così come arriva dall'agente | Il back-end non interpreta il formato dello Step 6: lo controlla l'agente a ogni turno (`400 invalid_history`) |
| Identificativi | Interi generati dal database (`id` autoincrementale) | Leggibili nei log, negli URL e nei test; non c'è autenticazione, quindi un identificativo difficile da indovinare non proteggerebbe nulla |
| Titolo della chat | Facoltativo alla creazione; se assente, la prima domanda lo fissa (prima riga, al più 60 caratteri, «…» se tagliata); finché manca l'API mostra «Nuova chat» | La traccia chiede l'elenco con il titolo; dare un nome a mano a ogni chat sarebbe scomodo |
| Data dell'ultimo messaggio | Calcolata con una query (`max(created_at)` dei messaggi), `null` per una chat senza messaggi; elenco ordinato dalla chat con l'attività più recente (ultimo messaggio o, se non ce ne sono, creazione) | Nessun dato duplicato da tenere allineato |
| Orari | Salvati in UTC (`timestamp with time zone`), restituiti in ISO 8601 con fuso; l'orologio è un parametro dell'archivio | Standard per le API; nei test l'orologio fisso rende gli orari confrontabili |
| Ordine dei messaggi | Per `id` crescente | `created_at` può coincidere per domanda e risposta in test con l'orologio fisso; l'`id` cresce con l'inserimento |
| Domanda e agente non disponibile | La domanda si salva **prima** di chiamare l'agente (come dice la traccia); se l'agente fallisce, la domanda resta nella chat senza risposta, lo stato dell'agente non cambia e la risposta HTTP è l'errore | La domanda dell'utente non si perde e la chat mostra che cosa è successo; l'agente riceve solo turni completi, perché la sua cronologia si aggiorna solo con una risposta riuscita |
| Errori | Corpo `{"error", "detail"}` come l'agente; `404` chat inesistente, `400` richiesta non valida, `503` agente non raggiungibile o database non disponibile, `504` agente senza risposta entro il timeout, `502` agente che risponde con un errore, `500` errore imprevisto (§6) | Codici HTTP standard: `4xx` colpa della richiesta, `502`/`503`/`504` servizio a valle in errore, assente o lento |
| Configurazione | `DATABASE_URL` obbligatoria (solo PostgreSQL), `AGENT_URL` (predefinito `http://127.0.0.1:8000`), `BACKEND_HOST` (predefinito `127.0.0.1`), `BACKEND_PORT` (predefinita `8001`), `LOG_LEVEL` | Credenziali solo nell'ambiente, mai nel codice né nei log (password nascosta); porta diversa da quella dell'agente, così i due servizi convivono in locale |
| Avvio | `python -m backend`; database non raggiungibile all'avvio → messaggio ed exit 1; agente spento all'avvio → avvio comunque | Senza database il back-end non serve a nulla (lo Step 9 lo avvia a database pronto); l'agente può arrivare dopo, e ogni invio lo segnala |
| Prompt MCP, stato dell'agente | Non esposti dal back-end | La tabella della traccia elenca solo le cinque operazioni sulle chat |
| Concorrenza | Nessun blocco tra due invii contemporanei nella stessa chat | Un blocco della riga durante un turno di minuti fermerebbe anche le letture; il front-end manda un messaggio alla volta. Rischio in §13 |

## 2. Struttura

```
backend/
├── __init__.py
├── __main__.py   # avvio: configurazione, logging, database, client dell'agente, uvicorn
├── config.py     # BackendConfig, load_backend_config (DATABASE_URL, AGENT_URL, BACKEND_HOST/PORT)
├── db.py         # schema SQLAlchemy (Chat, ChatMessage), create_db_engine, init_db
├── store.py      # ChatStore: operazioni sulle chat e sui messaggi (l'archivio)
└── api.py        # create_app(*, store, agent): modelli pydantic, endpoint, errori
```

Il back-end importa da `assistant` solo `api_client.AgentClient`/`AgentError` e
`config.configure_logging` (e le regole di `AGENT_URL`/`LOG_LEVEL`); `assistant` non importa nulla da
`backend`. Test in `tests/test_backend_*.py`.

## 3. Schema (PostgreSQL)

```
chats
  id          integer, chiave primaria, generato
  title       varchar(200), null finché non c'è un titolo
  created_at  timestamp with time zone, non null
  summary     text, non null, predefinito ''           -- riassunto dell'agente
  history     json, non null, predefinito []            -- cronologia dell'agente (formato Step 6)

chat_messages
  id          integer, chiave primaria, generato
  chat_id     integer, non null, riferimento a chats(id) ON DELETE CASCADE, indice
  role        varchar(16), non null                     -- 'user' o 'assistant'
  content     text, non null
  tools_used  json, non null, predefinito []            -- strumenti del turno (solo 'assistant')
  created_at  timestamp with time zone, non null
```

- Eliminare una chat elimina i suoi messaggi: `ON DELETE CASCADE` nel database (su SQLite nei test
  con `PRAGMA foreign_keys=ON`) e la relazione ORM con `cascade="all, delete-orphan"`.
- `tools_used` di una risposta è l'elenco `{"name", "args", "result", "ok"}` restituito dall'agente.
- SQLite restituisce orari senza fuso: l'archivio li considera UTC.

## 4. Archivio (`backend/store.py`)

```python
class ChatNotFoundError(Exception): ...

@dataclass(frozen=True)
class MessageRecord: id: int; role: str; content: str; tools_used: list; created_at: datetime
@dataclass(frozen=True)
class ChatRecord: id: int; title: str | None; created_at: datetime; last_message_at: datetime | None
@dataclass(frozen=True)
class AgentState: history: list[dict]; summary: str

class ChatStore:
    def __init__(self, engine, now=lambda: datetime.now(UTC)): ...
    def create_chat(self, title: str | None = None) -> ChatRecord: ...
    def list_chats(self) -> list[ChatRecord]: ...             # attività più recente per prima
    def get_chat(self, chat_id) -> tuple[ChatRecord, list[MessageRecord]]: ...  # messaggi per id
    def delete_chat(self, chat_id) -> None: ...                # con i messaggi
    def add_question(self, chat_id, text) -> tuple[MessageRecord, AgentState]: ...
    def add_answer(self, chat_id, reply, tools_used, state: AgentState) -> MessageRecord: ...
```

- Ogni metodo apre e chiude la propria sessione (una transazione); nessuna transazione resta aperta
  durante la chiamata all'agente.
- `add_question` salva la domanda, fissa il titolo se manca (§1) e restituisce lo stato dell'agente
  da mandare; `add_answer` salva la risposta e sostituisce cronologia e riassunto della chat nella
  stessa transazione. Chat inesistente (anche se eliminata durante il turno) → `ChatNotFoundError`.
- Gli errori di SQLAlchemy (`sqlalchemy.exc.SQLAlchemyError`) arrivano al chiamante.

## 5. API (`backend/api.py`)

`create_app(*, store, agent) -> FastAPI`: `store` è il `ChatStore`, `agent` un oggetto con il metodo
`chat(history, summary, *, message)` come `AgentClient` (nei test l'`AgentClient` collegato al
`TestClient` dell'agente con il grafo finto, oppure un agente finto). Titolo dell'OpenAPI
«Assistente del laboratorio — back-end», descrizioni in italiano; `GET /openapi.json` e `GET /docs`.

| Operazione | Endpoint | Successo |
|------------|----------|----------|
| Creare una chat | `POST /chats`, corpo `{"title": "..."}` facoltativo | `201` con la chat |
| Elencare le chat | `GET /chats` | `200` con l'elenco |
| Leggere una chat | `GET /chats/{chat_id}` | `200` con la chat e i messaggi in ordine cronologico |
| Inviare un messaggio | `POST /chats/{chat_id}/messages`, corpo `{"content": "..."}` | `201` con domanda e risposta salvate |
| Eliminare una chat | `DELETE /chats/{chat_id}` | `204` senza corpo |

```json
// chat (POST /chats, elementi di GET /chats)
{"id": 3, "title": "Quanto fa 17 * 23?", "created_at": "2026-11-14T10:00:00Z",
 "last_message_at": "2026-11-14T10:00:05Z"}
// GET /chats/3: la chat con "messages"
{"id": 3, "title": "...", "created_at": "...", "last_message_at": "...",
 "messages": [
   {"id": 11, "role": "user", "content": "Quanto fa 17 * 23?", "tools_used": [],
    "created_at": "2026-11-14T10:00:00Z"},
   {"id": 12, "role": "assistant", "content": "17 * 23 fa 391.",
    "tools_used": [{"name": "calculate", "args": {"expression": "17 * 23"},
                    "result": {"result": 391}, "ok": true}],
    "created_at": "2026-11-14T10:00:05Z"}]}
// POST /chats/3/messages
{"question": {...messaggio user...}, "answer": {...messaggio assistant...}}
```

- `title` della risposta: quello salvato oppure «Nuova chat» se manca. In ingresso il titolo perde
  gli spazi iniziali e finali; vuoto = assente; più di 200 caratteri → `400 invalid_request`.
- `content` perde gli spazi iniziali e finali (come nella CLI e nell'agente); vuoto → `400`.
- Flusso dell'invio: `add_question` → `agent.chat(history, summary, message=content)` →
  `add_answer(reply, tools_used, AgentState(history, summary))` → `201`.

## 6. Errori

| Situazione | Codice | `error` | Esempio di `detail` |
|------------|--------|---------|---------------------|
| Corpo non conforme allo schema (tipo sbagliato, campo sconosciuto), `chat_id` non intero | 422 | — (formato FastAPI) | — |
| Titolo troppo lungo, messaggio vuoto | 400 | `invalid_request` | «il messaggio è vuoto» |
| Chat inesistente (lettura, eliminazione, invio) | 404 | `chat_not_found` | «chat 42 inesistente» |
| Agente non raggiungibile (`agent_unreachable`) | 503 | `agent_unavailable` | «agente non raggiungibile su http://127.0.0.1:8000» |
| Agente senza risposta entro il timeout (`agent_timeout`) | 504 | `agent_timeout` | «l'agente non ha risposto entro 600 s» |
| Agente che risponde con un errore (ogni altro `AgentError`, per esempio LM Studio spento) | 502 | `agent_error` | «l'agente ha risposto con un errore (model_unavailable): LM Studio non raggiungibile: …» |
| Database non raggiungibile (`sqlalchemy.exc.OperationalError`) | 503 | `database_unavailable` | «database non disponibile; dettagli nel log» |
| Qualsiasi altra eccezione | 500 | `internal_error` | «errore interno del back-end; dettagli nel log» (traceback nel log) |

Con un errore dell'agente la domanda resta salvata e lo stato dell'agente della chat non cambia
(§1). Il `detail` di `database_unavailable` non riporta il messaggio del driver, che può contenere
indirizzo e utente del database: quello va nel log.

## 7. Log (logger `backend.api`)

```
backend request=send_message chat=3 chars=18
backend agent_call chat=3 history=4 summary_chars=0
backend response=send_message chat=3 status=201 tools=calculate reply_chars=16 duration_ms=5321
backend response=send_message chat=3 status=503 error=agent_unavailable detail="agente non raggiungibile su http://127.0.0.1:8000" duration_ms=12
backend response=create_chat status=201 chat=3 duration_ms=4
backend response=list_chats status=200 count=2 duration_ms=3
```

Una riga di risposta per ogni richiesta (operazione, chat, codice, durata), più le righe della
richiesta e della chiamata all'agente per l'invio. Il testo dei messaggi non entra nei log (lo
registra l'agente). `4xx` a INFO, `502`/`503`/`504` a WARNING, `500` a ERROR con il traceback. Log di
accesso di uvicorn disattivati, come nell'agente. Riga d'avvio (logger `backend.service`):
`backend listening=http://<host>:<port> docs=/docs agent_url=<url> database=<url senza password>`.

## 8. Configurazione e avvio (`backend/config.py`, `backend/__main__.py`)

- `DATABASE_URL` obbligatoria, forma `postgresql+psycopg://utente:password@host:5432/nome`; anche
  `postgresql://…` (diventa `postgresql+psycopg://…`); altri schemi → errore di configurazione.
- `AGENT_URL` e `LOG_LEVEL` con le stesse regole della CLI; `BACKEND_HOST` testo non vuoto,
  `BACKEND_PORT` intero tra 1 e 65535. Più problemi → un solo messaggio, come in `assistant/config.py`.
- Avvio: configurazione (errore → stderr, exit 1), logging, `create_db_engine`, `init_db` (database
  non raggiungibile → «Database non raggiungibile: …» su stderr, exit 1), `AgentClient(AGENT_URL)`,
  `uvicorn.run(create_app(...), host=…, port=…, access_log=False, log_config=None)`.
- Connessione a PostgreSQL con `connect_timeout=10` s (aggiunto al punto 3): senza, psycopg aspetta
  130 s un host che non risponde (osservato su Windows con una porta chiusa), sia all'avvio sia
  prima di un `503 database_unavailable`.
- `.env.example`: righe di commento per `DATABASE_URL`, `BACKEND_HOST`, `BACKEND_PORT`, senza
  credenziali vere.

## 9. Docker in questo step

`compose.yaml` e `Dockerfile` non cambiano: i quattro container, PostgreSQL in Compose e l'immagine
del back-end sono lo Step 9. Per le prove di questo step PostgreSQL gira in un container avviato a
mano con l'immagine ufficiale (`docker run … postgres:18`), comando nel README.

## 10. Test

### Senza PostgreSQL né modello (`pytest`)

- Database dei test: SQLite in memoria (`sqlite://`, `StaticPool`, `PRAGMA foreign_keys=ON`), con lo
  stesso `init_db` dell'esercizio; orologio fisso e avanzabile.
- `test_backend_store.py`: creazione con e senza titolo; elenco con titolo, data dell'ultimo
  messaggio e ordine; lettura in ordine; eliminazione con i messaggi (contati nella tabella); titolo
  dalla prima domanda (taglio a 60 caratteri, prima riga) e non dalle successive; `add_question` e
  `add_answer` con lo stato dell'agente; chat inesistente; chat eliminata durante il turno.
- `test_backend_config.py`: valori predefiniti, `DATABASE_URL` mancante o con schema sbagliato,
  `postgresql://` normalizzato, porta non valida, messaggio unico.
- `test_backend_api.py` (`TestClient`): le cinque operazioni, OpenAPI con i percorsi e gli schemi,
  ogni riga della tabella di §6, righe di log esatte; invio con l'agente dello Step 6 su grafo finto
  (`fake_service` di `conftest.py`): la domanda e la risposta salvate, l'agente riceve cronologia e
  riassunto della chat al secondo invio; agente non raggiungibile (porta chiusa), tempo scaduto ed
  errore del servizio con un agente finto; domanda salvata e stato invariato dopo un errore;
  database non disponibile con un archivio che solleva `OperationalError`.
- `test_backend_service.py`: avvio con `uvicorn.run` sostituito (indirizzo, app che risponde),
  configurazione non valida, database non raggiungibile → exit 1, password assente dalla riga d'avvio.

### Prove reali (`pytest -m real`)

- **Archivio su PostgreSQL** (CA-77): i test dell'archivio rieseguiti su PostgreSQL vero quando è
  impostata `TEST_DATABASE_URL` (tabelle create in uno schema temporaneo ed eliminate alla fine).
- **Back-end, agente e PostgreSQL** (CA-78): back-end e agente avviati come sottoprocessi, LM Studio
  attivo; creazione di una chat, «Quanto fa 17 * 23?» → `201`, `calculate` negli strumenti usati,
  «391»; back-end fermato e riavviato → la chat e i due messaggi ci sono ancora e un secondo messaggio
  usa la cronologia salvata; agente fermato → `503 agent_unavailable` e la domanda resta nella chat.

Se PostgreSQL o LM Studio non sono raggiungibili, il punto si segna `[!]` (modalità autonoma).

## 11. Dipendenze

`SQLAlchemy==2.1.8` e `psycopg[binary]==3.3.9` in `requirements.txt` (con le indirette
`psycopg-binary==3.3.9`; nessun'altra nuova) e in `constraints.txt`. Verificato con uno script usa e
getta fuori dal progetto: tabelle create su SQLite in memoria, colonna JSON, `ON DELETE CASCADE` con
`PRAGMA foreign_keys=ON`, `max(created_at)` con `outer join`, DDL PostgreSQL generato
(`SERIAL`, `TIMESTAMP WITH TIME ZONE`, `JSON`), porta chiusa → `OperationalError`; `pip check`
pulito. FastAPI, uvicorn e httpx sono già fissate (Step 6).

## 12. Incrementi

Coincidono con i punti dello Step 7 in `TODO.md`; ognuno verificato con `pytest` prima del commit.

1. Questa specifica, i requisiti §15, le dipendenze.
2. `backend/db.py` e `backend/store.py` (schema e archivio); test su SQLite.
3. `backend/api.py` con creazione, elenco, lettura ed eliminazione e OpenAPI; `backend/config.py` e
   `backend/__main__.py` (avvio); `.env.example`; test.
4. Invio di un messaggio con la chiamata all'agente ed errori dell'agente; test con l'agente
   simulato.
5. Prove reali con PostgreSQL e agente, README (avvio del back-end, PostgreSQL in un container,
   diagnosi) e `CLAUDE.md` (struttura e comandi); esiti in requisiti §15 e nel diario.

## 13. Rischi

- **Tre processi in locale** (agente, back-end, PostgreSQL in Docker): il README lo spiega; lo Step 9
  li riunisce in Compose.
- **Invii contemporanei nella stessa chat**: il secondo `add_answer` sovrascrive lo stato
  dell'agente del primo (i messaggi visibili restano entrambi). Il front-end manda un messaggio alla
  volta.
- **SQLite nei test, PostgreSQL in esercizio**: differenze di tipo (JSON, orari) coperte dalla prova
  reale CA-77 sugli stessi test.
- **Domande senza risposta**: dopo un errore dell'agente la chat mostra la domanda senza risposta;
  per riprovare l'utente rimanda il messaggio (che compare due volte).
- **Cronologia dell'agente che cresce**: la limita il riassunto dell'agente (Step 3); la colonna JSON
  la contiene per intero.

## 14. Fuori ambito

Front-end e CORS (Step 8), Compose con quattro container e immagine del back-end (Step 9), streaming
(facoltativo), autenticazione e utenti, rinomina delle chat, modifica o eliminazione di singoli
messaggi, prompt MCP e stato dell'agente esposti dal back-end, migrazioni dello schema, paginazione.
