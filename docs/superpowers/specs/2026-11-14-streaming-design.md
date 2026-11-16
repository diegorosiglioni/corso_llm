# Specifica — Lezione 6, facoltativo: streaming della risposta

Data: 2026-11-14
Stato: scritta in modalità autonoma (branch `auto-claude`): l'approvazione è sostituita dal piano
in [`../../../PROGRESS.md`](../../../PROGRESS.md) (regola di `CLAUDE.md`, «Modalità autonoma»).
Requisiti: [`../requisiti.md`](../requisiti.md), §18 (RF-81…RF-87, CA-94…CA-104).
Specifiche precedenti: [`2026-11-14-compose-design.md`](2026-11-14-compose-design.md) (Step 9),
[`2026-11-14-frontend-chat-design.md`](2026-11-14-frontend-chat-design.md) (Step 8),
[`2026-11-14-backend-chat-design.md`](2026-11-14-backend-chat-design.md) (Step 7),
[`2026-11-14-servizio-http-design.md`](2026-11-14-servizio-http-design.md) (Step 6) e quelle che
richiamano.
Fonte didattica: `LLM_Lez_6.pdf`, «Facoltativo — streaming della risposta»; riassunto in
[`../lezione6.md`](../lezione6.md).

Oggi la pagina mostra la risposta solo quando il turno è finito: con il modello locale si aspetta
più di un minuto davanti a «L'assistente sta rispondendo… N s». Con lo streaming **l'agente emette
il testo e l'uso degli strumenti man mano**, il **back-end inoltra il flusso** al browser come
**Server-Sent Events** e **salva il messaggio completo alla fine**, e la **pagina mostra il testo
mentre arriva** e indica quando l'agente usa uno strumento. Gli endpoint attuali (`POST /chat`,
`POST /chats/{chat_id}/messages`) restano invariati: la CLI e i test esistenti continuano a usarli.

```
browser ──POST /chats/{id}/messages/stream──→ backend ──POST /chat/stream──→ agent ──→ LM Studio
   ▲   question · text · tool_start · tool_end ·  │   text · tool_start · tool_end ·   (stream=true
   │   reset · done{question, answer} | error     │   reset · done{ChatResponse} | error  solo per
   └──────────────── text/event-stream ───────────┘◄────────── text/event-stream ───── l'agente)
                                                  └─ alla fine salva risposta, cronologia, riassunto
```

## 1. Decisioni

Tutte «scelta del progettista» (modalità autonoma: opzione consigliata o più standard).

| Tema | Decisione | Motivo |
|------|-----------|--------|
| **Bozza o sola risposta approvata** (decisione chiesta dalla traccia) | **Si mostra la bozza mentre viene scritta**, segnata nella pagina come provvisoria finché il turno non finisce. Se il revisore la respinge, il servizio manda `reset` con il motivo: la pagina toglie la bozza, scrive che la risposta viene riscritta su indicazione del revisore e mostra la riscrittura che arriva. Il messaggio **salvato** è sempre e solo la risposta finale (quella di `/chat`), che sostituisce la bozza all'evento `done` | Con il modello locale un turno dura decine di secondi e il revisore di solito approva: mostrare solo la risposta approvata vorrebbe dire non mostrare testo fino alla fine, cioè rinunciare allo streaming proprio dove serve. Il segno «provvisoria» e il `reset` esplicito rendono onesto il caso raro del rifiuto; nel database non entra mai una bozza |
| Protocollo | **Server-Sent Events** (`text/event-stream`) sia tra agente e back-end sia tra back-end e browser, con **`POST`** (il corpo porta domanda, cronologia e riassunto) | Lo suggerisce la traccia; è testo su HTTP, passa dal CORS dello Step 8 senza nulla di nuovo e si legge in Python con `httpx` e nel browser con `fetch` |
| Libreria SSE | Quella **inclusa in FastAPI 0.162.7** (`fastapi.sse.EventSourceResponse`, `ServerSentEvent`): funzione generatrice sincrona, eventi codificati da FastAPI, commento `: ping` ogni 15 s quando non arriva nulla, intestazioni `Cache-Control: no-cache` e `X-Accel-Buffering: no`. **Nessuna dipendenza nuova** (`sse-starlette` resta solo indiretta di fastmcp) | Già fissata in `constraints.txt` e documentata nell'OpenAPI come `text/event-stream`; il `ping` tiene viva la connessione mentre girano strumenti e revisore |
| Lettura del flusso | In Python un piccolo lettore SSE in `assistant/api_client.py` sopra `httpx.Client.stream` (righe `event:`/`data:`, commenti ignorati); nel browser `fetch` con `response.body.getReader()` e lo stesso lettore in JavaScript | `EventSource` del browser non permette `POST` né un corpo; `httpx-sse` sarebbe una dipendenza per venti righe |
| Endpoint nuovi, non sostituiti | Agente: **`POST /chat/stream`** (stesso corpo di `/chat`). Back-end: **`POST /chats/{chat_id}/messages/stream`** (stesso corpo di `/messages`). Gli endpoint dello Step 6 e 7 restano | La CLI, le prove reali e il contratto attuali non cambiano; la pagina passa all'endpoint con lo streaming |
| CLI | **Invariata** (usa `POST /chat`) | La traccia chiede agente, back-end e front-end; la CLI non è nominata: niente oltre la traccia |
| Che cosa si trasmette come testo | Solo i token del nodo **`llm`** (l'agente). Riassunto, router e revisore non producono eventi di testo | Sono decisioni interne (JSON strutturato o riassunto): non sono la risposta |
| Come si ottengono i token | `graph.stream(..., stream_mode=["messages", "updates", "values"])` di LangGraph: `messages` dà i pezzi del modello col nome del nodo (`langgraph_node`), `updates` i messaggi aggiunti da ogni nodo (chiamate e risultati degli strumenti, decisione del revisore), `values` lo stato finale | È il meccanismo standard di LangGraph; il grafo non cambia. Verificato con un modello finto: i pezzi del nodo `llm` arrivano con `langgraph_node="llm"` |
| Modelli di router, revisore e riassunto | **`disable_streaming=True`** (campo standard dei modelli di LangChain) | In `stream_mode="messages"` LangChain farebbe chiamate in streaming anche per l'output strutturato (`json_schema`): con `disable_streaming` le loro richieste a LM Studio restano identiche a oggi. Solo l'agente chiede `stream=true` a LM Studio, e solo nel percorso con lo streaming (con `graph.invoke` di `/chat` nulla cambia) |
| Testo prima di una chiamata a strumenti | Se un passo dell'agente che ha già mandato testo finisce con chiamate a strumenti, il servizio manda **`reset`** con `reason: "tools"` prima di `tool_start` | Oggi quel testo non compare nella risposta (la risposta è l'ultimo messaggio): la pagina deve mostrarlo uguale |
| Fine del flusso | Sempre con **un** evento finale: `done` (riuscito) oppure `error`; poi il servizio chiude la risposta | Il client sa quando smettere di leggere; un flusso chiuso senza evento finale è un errore |
| Errori prima e dopo l'inizio | Gli errori che si scoprono **prima** di eseguire il grafo (richiesta, cronologia, prompt, chat inesistente, database, agente non raggiungibile o che rifiuta la richiesta) restano **risposte JSON** con lo stesso codice HTTP e lo stesso corpo degli endpoint senza streaming; quelli **durante** il turno (LM Studio irraggiungibile o in errore, errore imprevisto, agente che si interrompe o va oltre il tempo) diventano un evento **`error`** `{error, detail}` con gli stessi codici | Dopo il primo byte il codice HTTP è già `200`; prima, conviene che client e test trattino gli errori come oggi. I controlli preliminari stanno in una **dipendenza di FastAPI** (eseguita prima del generatore) che solleva l'`ApiError` del servizio, convertita in JSON da un gestore delle eccezioni |
| Contenuto di `done` | Agente: lo stesso corpo di `ChatResponse` (`reply`, `tools_used`, `history`, `summary`), calcolato dallo stesso codice di `run_turn`. Back-end: lo stesso corpo di `SendMessageResponse` (`question`, `answer`), dopo il salvataggio | Una sola definizione di risposta per endpoint; il back-end non manda al browser cronologia e riassunto dell'agente |
| Salvataggio nel back-end | Domanda salvata **prima** di aprire il flusso (come oggi); risposta, strumenti, cronologia e riassunto salvati **solo all'evento `done`** dell'agente, nella stessa operazione di `add_answer` di oggi | La traccia: «salva il messaggio completo alla fine». Con un errore o un'interruzione la chat resta come dopo un errore dell'agente oggi: domanda senza risposta, stato dell'agente invariato |
| Browser che chiude la pagina durante il turno | Il back-end se ne accorge solo quando prova a scrivere al browser l'evento successivo dell'agente: allora chiude il flusso dell'agente, la domanda resta senza risposta, lo stato dell'agente non cambia e il log ha `outcome=client_gone`. Se invece il prossimo evento dell'agente è `done`, la risposta viene salvata come sempre (`outcome=done`), anche se nessuno la legge; il `ping` dei 15 s non basta ad accorgersene. Se l'utente rimanda la domanda mentre il primo turno è ancora in corso, i turni sono due (R-C4) (descrizione corretta il 2026-11-16 dopo un'osservazione con uno script; il comportamento resta un debito noto, R-D1) | Lo stesso esito di un errore dell'agente, già gestito dalla pagina (domanda senza risposta); fermare subito il turno o continuarlo senza nessuno che legge richiederebbe un lavoro in background che il progetto non ha |
| Tempi | Back-end → agente: connessione 10 s come oggi, **60 s** al massimo senza ricevere nulla (con il `ping` ogni 15 s solo un agente bloccato li supera), **600 s** per l'intero turno (come `CHAT_TIMEOUT`); oltre → `error` `agent_timeout`. Pagina: 660 s per l'intero invio, come oggi | Stessi limiti complessivi degli Step 6–8; il limite tra due eventi scopre prima un agente fermo |
| Riconnessione | **Nessuna**: niente `id` negli eventi né `Last-Event-ID`; un flusso interrotto è un errore e la pagina rilegge la chat | Il turno non si può riprendere a metà; rileggere la chat mostra la domanda salvata, come dopo gli errori dello Step 8 |
| Indicazione degli strumenti nella pagina | All'evento `tool_start` la risposta in arrivo mostra «Uso lo strumento calculate…»; a `tool_end` la riga diventa quella dello Step 8 (nome, argomenti, risultato, errore segnalato) | La traccia: «indica l'uso di uno strumento»; riusa il formato già noto all'utente |

## 2. Struttura

```
assistant/agent.py        # + stream_turn (generatore di eventi), TurnResult condiviso con run_turn
assistant/model.py        # router, revisore e riassunto con disable_streaming=True
assistant/api.py          # + POST /chat/stream (EventSourceResponse), controlli in una dipendenza
assistant/api_client.py   # + iter_sse (lettore SSE) e AgentClient.chat_stream
backend/api.py            # + POST /chats/{chat_id}/messages/stream
frontend/static/api.js    # + readEvents (lettore SSE) e BackendClient.sendMessageStream
frontend/static/texts.js  # + testi di bozza, strumento in corso e riscrittura
frontend/static/app.js    # invio con lo streaming, risposta in arrivo
frontend/backend-openapi.json  # contratto rigenerato
tests/…                   # vedi §8
```

Nessuna variabile d'ambiente nuova; nessun cambiamento a grafo, database, Docker o Compose.

## 3. Eventi

Ogni evento ha un nome (`event:`) e un oggetto JSON (`data:`). Le due tabelle condividono i primi
cinque eventi, che il back-end inoltra così come li riceve.

| Evento | `data` | Quando |
|--------|--------|--------|
| `text` | `{"delta": "…"}` | Un pezzo di testo dell'agente (nodo `llm`), nell'ordine in cui arriva; pezzi vuoti non si mandano |
| `reset` | `{"reason": "tools" \| "review", "detail": "…"}` | Il testo mandato dall'ultimo `reset` (o dall'inizio) **non** sarà la risposta: `tools` se il passo dell'agente finisce con chiamate a strumenti, `review` se il revisore respinge la risposta e la rimanda all'agente (`detail` = motivo del revisore; vuoto per `tools`). Solo se è stato mandato almeno un `text` dopo l'ultimo `reset` |
| `tool_start` | `{"id", "name", "args"}` | L'agente ha chiesto uno strumento (una per chiamata, anche non interpretabile: `args` è allora il testo ricevuto) |
| `tool_end` | `{"id", "name", "args", "result", "ok"}` | Lo strumento ha risposto (anche con errore, o «Non eseguito» al limite di passaggi); stessi campi di una voce di `tools_used` più `id` |
| `error` | `{"error", "detail"}` | Il turno si è fermato; codici della tabella degli errori del servizio. Ultimo evento |
| `done` (agente) | il corpo di `ChatResponse` | Il turno è finito; ultimo evento |
| `question` (back-end) | il corpo di `ChatMessageInfo` della domanda salvata | Primo evento del back-end, prima di quelli dell'agente |
| `done` (back-end) | il corpo di `SendMessageResponse` (`question`, `answer`) | Risposta salvata; ultimo evento |

Regole per chi legge: il testo della risposta in arrivo è la concatenazione dei `delta` dall'ultimo
`reset`; la risposta vera è sempre quella di `done` (per un rifiuto del router o il limite di
passaggi non arriva nessun `text`: la pagina la riceve solo con `done`). Commenti (`: ping`) ed
eventi con un nome sconosciuto si ignorano.

## 4. Agente

### `stream_turn` (`assistant/agent.py`)

`stream_turn(graph, history, summary, messages)` è un generatore con gli stessi argomenti di
`run_turn`: prepara l'ingresso come `run_turn` (copie, nuovi id), chiama `graph.stream` con i tre modi
e produce coppie `(nome, dati)`:
- `messages`: un pezzo di `AIMessageChunk` con `langgraph_node == "llm"` e testo non vuoto → `text`;
- `updates` del nodo `llm`: se il messaggio ha chiamate (valide o no) → `reset` `tools` (se c'è testo
  da annullare) e un `tool_start` per chiamata;
- `updates` dei nodi `tools` e `limit`: un `tool_end` per ogni `ToolMessage`, con gli argomenti
  della chiamata;
- `updates` del nodo `reviewer` con un messaggio d'indicazione (rifiuto con nuovo tentativo) →
  `reset` `review` con il motivo (se c'è testo da annullare);
- alla fine `done` con il `TurnResult` costruito **dalla stessa funzione** usata da `run_turn`
  (estratta: risposta, strumenti usati del turno, cronologia, riassunto) sullo stato finale.

Le eccezioni del grafo (per esempio `openai.APIError`) escono dal generatore come da `run_turn`.
`run_turn` resta com'è (con `graph.invoke`), salvo l'estrazione della funzione comune.

### `POST /chat/stream` (`assistant/api.py`)

- Corpo: `ChatRequest`. Risposta `200` `text/event-stream` con gli eventi del §3; nell'OpenAPI la
  descrizione elenca eventi e campi.
- Prima del flusso, in una dipendenza: gli stessi controlli di `/chat` nello stesso ordine (uno tra
  `message` e `prompt`, messaggio non vuoto, cronologia, prompt con il controllo dell'host e
  `prompts/get`); un errore → la stessa risposta JSON di `/chat` (400, 502, 503).
- Durante il flusso: `openai.APIConnectionError` → `error` `model_unavailable`; altri
  `openai.APIError` → `error` `model_error`; ogni altra eccezione → `error` `internal_error` con
  il dettaglio di `/chat` (traceback solo nel log). Stessi testi di `/chat`.
- Log: `api request=chat_stream kind=… history=… summary_chars=…`; alla fine
  `api response=chat_stream status=200 outcome=done tools=… reply_chars=… history=… text_events=…
  resets=… duration_ms=…` (INFO), oppure `outcome=error error=… detail=…` (WARNING, ERROR per
  `internal_error`), oppure `outcome=client_gone` (INFO) se il servizio si accorge che il client ha
  chiuso prima della fine, presumibilmente alla scrittura di un evento: è quanto osservato nel
  back-end, e per l'agente è dedotto per analogia (stesso meccanismo SSE di FastAPI), non osservato
  (descrizione corretta il 2026-11-16, debito R-D1). I log
  del grafo, degli strumenti e di MCP restano quelli di oggi.

### Modelli (`assistant/model.py`)

`create_router_model`, `create_reviewer_model` e `create_summary_model` costruiscono `ChatOpenAI`
con `disable_streaming=True`; l'agente no. Nessun altro cambiamento.

## 5. Client dell'agente (`assistant/api_client.py`)

- `iter_sse(lines)`: dalle righe di testo di un flusso SSE produce `(evento, dati)`; `data` su più
  righe unite con `\n`, commenti e campi sconosciuti ignorati, evento senza nome = `message`,
  evento emesso alla riga vuota. Il JSON si decodifica in `chat_stream`.
- `AgentClient.chat_stream(history, summary, *, message=None, prompt=None)`: generatore. Apre
  `POST /chat/stream`; una risposta non `200` → `AgentError` con codice e dettaglio del servizio
  (come `chat`), connessione rifiutata → `agent_unreachable`. Poi produce `(evento, dati)` per
  `text`, `reset`, `tool_start`, `tool_end`; all'evento `done` controllato come oggi (`_is_chat`)
  produce `("done", corpo)` e termina; all'evento `error` solleva `AgentError(error, detail)`; più di
  60 s senza dati → `AgentError("agent_timeout", …)`; oltre 600 s dall'inizio → lo stesso;
  flusso chiuso prima della fine, JSON non valido o `done` malformato → `AgentError("bad_response",
  …)`. Chiudere il generatore chiude la connessione.

## 6. Back-end (`backend/api.py`)

### `POST /chats/{chat_id}/messages/stream`

- Corpo: `SendMessageRequest`. Prima del flusso, in una dipendenza: controllo del testo e
  `store.add_question` (400, 404, 503 come oggi), riga `backend agent_call chat=… history=…
  summary_chars=… stream=true`, apertura del flusso dell'agente (la prima lettura): agente non
  raggiungibile, troppo lento o che risponde con un errore prima del flusso → la risposta JSON di
  `/messages` (503 `agent_unavailable`, 504 `agent_timeout`, 502 `agent_error`), con la domanda
  salvata.
- Flusso `200` `text/event-stream`: `question` (la domanda salvata), poi `text`, `reset`,
  `tool_start`, `tool_end` inoltrati così come arrivano; al `done` dell'agente `store.add_answer`
  (stessa funzione e stessi dati di `/messages`) e `done` con `{question, answer}`.
- Errori durante il flusso → `error` con i codici del back-end: `AgentError` tradotto da
  `_agent_error` come oggi (`agent_unavailable`, `agent_timeout`, `agent_error` con il codice
  dell'agente nel dettaglio), errori dell'archivio al salvataggio come oggi
  (`database_unavailable`, …), ogni altra eccezione `internal_error`. La domanda resta, lo stato
  dell'agente non cambia.
- Log: `backend request=send_message_stream chat=… chars=…`; alla fine
  `backend response=send_message_stream chat=… status=200 outcome=done tools=… reply_chars=…
  duration_ms=…`, oppure `outcome=error error=… detail=…` (WARNING; ERROR per `internal_error`),
  oppure `outcome=client_gone` quando la scrittura di un evento al browser fallisce (pagina chiusa
  con un turno che non è ancora finito; se arriva prima `done`, la riga è `outcome=done`:
  descrizione corretta il 2026-11-16, debito R-D1);
  errori prima del flusso con le righe di oggi
  (`backend response=send_message_stream chat=… status=… error=…`). Mai il testo dei messaggi.
- CORS: invariato (metodo `POST`, intestazione `Content-Type` già ammessi).
- Il contratto `frontend/backend-openapi.json` si rigenera con `UPDATE_CONTRACT=1`.

## 7. Front-end

### Client (`frontend/static/api.js`)

- `readEvents(chunks)`: lettore SSE in JavaScript, funzione pura (testi già decodificati in pezzi
  qualsiasi, anche a metà riga) → eventi `{event, data}` con `data` decodificato da JSON; stesse
  regole di `iter_sse`.
- `BackendClient.sendMessageStream(id, text, onEvent)`: `POST …/messages/stream`; risposta non `2xx`
  → `BackendError` come oggi; poi chiama `onEvent(evento)` per ogni evento e si risolve con i dati di
  `done` (`{question, answer}`); `error` → `BackendError(200, error, detail)`; flusso chiuso senza
  evento finale → `BackendError(200, "stream_interrupted", …)`; rete o 660 s → `BackendError(0, …)`
  come oggi.

### Pagina (`app.js`, `texts.js`, CSS)

- Invio con `sendMessageStream`. La domanda compare subito (come oggi) con la riga d'attesa e i
  secondi; sotto, una **risposta in arrivo** (classe `draft`) con il testo dei `text` dall'ultimo
  `reset`, l'etichetta «Bozza: la risposta può ancora cambiare» e l'elenco degli strumenti del turno
  («Uso lo strumento calculate…» → dettaglio dello Step 8 a `tool_end`).
- `reset` `review`: la bozza si svuota e compare «Il revisore ha chiesto di riscrivere la risposta:
  <motivo>»; `reset` `tools`: la bozza si svuota senza avviso.
- `done`: domanda e risposta salvate al posto di domanda in attesa e bozza (stesso codice di oggi).
- `error` o interruzione: messaggio d'errore dello Step 8 per il codice (nuovo testo per
  `stream_interrupted`), la chat si rilegge e mostra la domanda salvata; la bozza scompare.
- Lo stato d'attesa resta per chat (solo la chat che aspetta è bloccata); se l'utente apre un'altra
  chat e torna, la risposta in arrivo riprende da dove è arrivata (gli eventi si accumulano nello
  stato della chat, non nel DOM). Testi sempre con `textContent`.

## 8. Test

Automatici (`pytest`, senza modello né PostgreSQL):
- **Agente** (`test_agent.py`): un modello finto **in streaming** (sottoclasse di `BaseChatModel` in
  `conftest.py` con risposte scritte e `_stream` che le spezza in pezzi, chiamate comprese): ordine
  degli eventi per risposta semplice, con uno strumento (`reset` `tools` solo se c'era testo),
  strumento in errore, chiamata non interpretabile, limite di passaggi, rifiuto del router (solo
  `done`), revisore che respinge (`reset` `review` col motivo) e poi approva, riassunto; `done` uguale
  al risultato di `run_turn` sugli stessi dati; eccezione del modello che esce dal generatore. Modelli
  di router, revisore e riassunto con `disable_streaming`.
- **API dell'agente** (`test_api.py`): `TestClient.stream` su `POST /chat/stream`: intestazione
  `text/event-stream`, eventi e `done`; controlli preliminari → JSON con i codici di `/chat`;
  `model_unavailable`, `model_error`, `internal_error` come eventi `error`; righe di log; OpenAPI con
  il percorso e `text/event-stream`.
- **Client** (`test_api_client.py`): `iter_sse` (più righe, commenti, `\r\n`, evento senza nome,
  ultima riga senza riga vuota); `chat_stream` sul servizio finto: eventi, `error`, risposta JSON
  d'errore, agente spento, flusso interrotto, `done` malformato, tempo tra eventi superato.
- **Back-end** (`test_backend_api.py`): agente finto con `chat_stream`: `question` primo evento,
  eventi inoltrati, risposta e stato salvati al `done` e uguali a quelli di `/messages`; errori prima
  del flusso (404, 400, 503, 502, 504) in JSON con la domanda salvata dove previsto; `error` durante il
  flusso con domanda salvata e stato invariato; righe di log; contratto rigenerato
  (`test_frontend_contract.py`).
- **JavaScript** (`node --test`): `readEvents` con pezzi spezzati a metà riga, commenti, `\r\n`;
  `sendMessageStream` con `fetch` finto che restituisce un `ReadableStream`: eventi, `done`, `error`,
  interruzione, risposta d'errore JSON; testi nuovi.
- **Browser** (`pytest -m browser`, back-end e agente finti): il testo compare a pezzi prima della
  fine, «Uso lo strumento…» visibile durante l'attesa, `reset` `review` con l'avviso, `done` con i
  messaggi salvati, errore durante il flusso con la domanda salvata, pagina usabile durante il
  flusso.

Prove reali (marcatore `real`, LM Studio, PostgreSQL, Edge):
- `POST /chat/stream` «Quanto fa 17 * 23?»: almeno un `tool_start` e un `tool_end` di `calculate`,
  `done` con «391»; LM Studio accetta `stream=true` con gli strumenti di `google/gemma-4-e2b`.
- Dal browser con agente, back-end e front-end come processi: il testo compare prima della fine del
  turno (almeno due aggiornamenti della bozza), lo strumento è indicato durante l'attesa, la risposta
  salvata è nella chat dopo la ricarica.

## 9. Rischi e limiti

- LM Studio potrebbe non restituire le chiamate a strumenti in streaming con il modello scelto; se la
  prova reale lo mostra, il punto si segna `[!]` con il motivo (nessun ripiego simulato).
- Con `gemma-4-e2b` la maggior parte del tempo è nell'elaborazione del prompt e nelle chiamate a
  router e revisore, che non producono testo: il guadagno visibile riguarda la parte finale del turno.
- Una bozza respinta dal revisore è stata vista dall'utente prima del `reset`: è la scelta del §1,
  segnalata dall'etichetta «Bozza».
- Nessuna ripresa di un flusso interrotto (§1).

## 10. Fuori ambito

Streaming nella CLI, WebSocket, annullamento di un turno dalla pagina, streaming del riassunto, del
router o del revisore, ripresa del flusso con `Last-Event-ID`, cambiamenti a Docker o Compose.
