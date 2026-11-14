# Specifica — Lezione 6, Step 6: l'agente come servizio HTTP

Data: 2026-11-14
Stato: scritta in modalità autonoma (branch `auto-claude`): l'approvazione è sostituita dal piano
in [`../../../PROGRESS.md`](../../../PROGRESS.md) (regola di `CLAUDE.md`, «Modalità autonoma»).
Requisiti: [`../requisiti.md`](../requisiti.md), §14 (RF-52…RF-59, CA-61…CA-69).
Specifiche precedenti: [`2026-11-14-prompt-mcp-design.md`](2026-11-14-prompt-mcp-design.md) (Step 5)
e quelle che richiama.
Fonte didattica: `LLM_Lez_6.pdf`, Blocco C e Step 6; riassunto in [`../lezione6.md`](../lezione6.md).

Lo stesso grafo (riassunto, router, agente con gli strumenti, revisore) risponde sia alla CLI sia
alle chiamate HTTP, senza duplicare la logica. Un **modulo dell'agente** senza stato riceve i
messaggi che aprono il turno, la cronologia e il riassunto e restituisce risposta, strumenti usati,
cronologia e riassunto aggiornati. Un **servizio HTTP** (FastAPI, OpenAPI generata) lo espone con tre
endpoint: conversazione, prompt MCP e stato. Il servizio tiene aperti il server MCP stdio e i modelli,
come oggi il terminale, ma non conserva nessuna conversazione: cronologia e riassunto arrivano dal
chiamante e tornano aggiornati. La **CLI diventa un client dell'API**: conserva cronologia e
riassunto per la durata della sessione e si comporta come il terminale attuale, comandi `/prompts` e
`/prompt` compresi. Dove non dice altro, valgono le specifiche precedenti.

## 1. Decisioni

Tutte «scelta del progettista» (modalità autonoma: opzione consigliata o più standard).

| Tema | Decisione | Motivo |
|------|-----------|--------|
| Framework HTTP | **FastAPI** 0.162.7, con **uvicorn** 0.54.0 | È lo standard Python per API con OpenAPI generata dai modelli `pydantic` (già usato dal router); endpoint sincroni (`def`), coerenti con la regola «codice sincrono». Verificato con i vincoli attuali: aggiunge solo `fastapi` e `annotated-doc`; `starlette` 1.10.0 e `uvicorn` 0.54.0 sono già indirette di `fastmcp` |
| Client HTTP della CLI | **httpx** 0.28.1, sincrono | Già indiretta (di `fastmcp`) e richiesta da `fastapi.testclient`; resta una sola libreria HTTP per CLI, controllo del modello e test |
| OpenAPI | `GET /openapi.json` e la pagina `GET /docs` di FastAPI | Generata dal codice: il contratto non si può disallineare dall'implementazione |
| Endpoint | `POST /chat` (turno), `GET /prompts` (elenco dei prompt MCP), `GET /status` (stato) | I tre bisogni della traccia e dei comandi della CLI; percorsi in inglese come gli altri identificatori |
| Formato dei messaggi | JSON proprio, simile all'API di OpenAI: `role` (`user`, `assistant`, `tool`), `content`, e i campi di ruolo (§4) | Leggibile, documentato nell'OpenAPI, indipendente da LangChain (il back-end dello Step 7 lo salverà così com'è). Conserva ciò che il grafo usa: chiamate agli strumenti, chiamate non interpretabili, `tool_call_id`, il nome `reviewer` delle indicazioni del revisore |
| Messaggi di sistema | Non ammessi nella cronologia | I prompt di sistema li aggiungono i nodi a ogni chiamata; uno nella cronologia sarebbe duplicato o una via per cambiare le istruzioni dell'agente |
| Controllo della cronologia | L'agente controlla anche l'ordine: ogni messaggio `tool` risponde a una chiamata del messaggio `assistant` che lo precede e ogni chiamata ha la sua risposta prima del messaggio successivo | Una cronologia così rotta farebbe fallire LM Studio con un errore poco chiaro; meglio un 400 che dice che cosa non va |
| Prompt MCP nell'API | `POST /chat` accetta, al posto di `message`, `prompt: {name, arguments}`; il servizio controlla la richiesta rispetto a `prompts/list`, chiama `prompts/get` e manda i messaggi al grafo | Il server MCP vive nell'agente: il controllo dell'host (Step 5) resta accanto al client MCP, una sola chiamata HTTP per turno. L'analisi della sintassi del comando resta nella CLI (è testo della CLI, non dell'API) |
| Strumenti usati | Ogni risposta di uno strumento del turno: `name`, `args`, `result` (l'oggetto restituito) e `ok` (`false` se `result` ha `error`) | La traccia chiede «strumenti usati»; il risultato serve al chiamante per mostrarli (Step 8) e per capire un errore |
| Strumenti non disponibili durante un turno | Il turno resta `200`: l'errore dello strumento va al modello come oggi e compare in `tools_used` con `ok: false`; `GET /status` e `GET /prompts` rispondono `503` se il server MCP non risponde | Lo Step 5 già passa al modello l'errore di trasporto; l'orologio e la conversazione funzionano anche senza MCP. L'evidenza «strumenti non disponibili» è visibile con codice e messaggio in `/status` e `/prompts` e nel risultato dello strumento |
| Codici d'errore | `400` richiesta o cronologia non valide, prompt rifiutato dall'host; `422` corpo non conforme allo schema (FastAPI); `502` errore di LM Studio o prompt non ottenibile dal server MCP; `503` LM Studio o server MCP non raggiungibili; `500` errore imprevisto (§6) | Codici HTTP standard: `4xx` colpa della richiesta, `502`/`503` servizio a valle in errore o assente |
| Corpo degli errori | `{"error": "<codice>", "detail": "<messaggio in italiano>"}` (tranne il `422` standard di FastAPI) | Il codice è stabile per i programmi (CLI, back-end), il messaggio è per le persone |
| Stato | `GET /status`: agente, server MCP (`tools/list`) e modello (`GET <LMSTUDIO_BASE_URL>/models`, il modello configurato deve esserci); `200` se tutto risponde, `503` altrimenti, stesso corpo | Il codice basta a un controllo automatico (Compose dello Step 9); `GET /models` non carica il modello e risponde in pochi secondi |
| Avvio del servizio | `python -m assistant.service`; indirizzo da `AGENT_HOST` (predefinito `127.0.0.1`) e `AGENT_PORT` (predefinita `8000`) | In locale il servizio non è raggiungibile da altri computer; in Docker si imposta `0.0.0.0` |
| Avvio della CLI | `python -m assistant` resta il comando della CLI, ora client; indirizzo dell'agente da `AGENT_URL` (predefinito `http://127.0.0.1:8000`) | Il comando documentato non cambia significato per l'utente; la CLI non ha più bisogno delle variabili di LM Studio |
| CLI e agente non raggiungibile | All'avvio la CLI chiama `GET /status`: agente non raggiungibile → messaggio ed exit 1; agente raggiungibile con MCP o modello non disponibili → avviso e conversazione comunque aperta | Senza agente la CLI non può fare nulla (come oggi senza server MCP); un modello spento può tornare durante la sessione |
| Concorrenza | Nessun blocco: ogni richiesta è indipendente (agente senza stato); FastAPI esegue gli endpoint sincroni in thread separati | Il grafo compilato e il client MCP (un loop con richieste numerate) accettano richieste concorrenti; LM Studio le mette in coda |
| Log | Logger `assistant.api`: una riga per richiesta e una per risposta (codice, strumenti, durata); i log del grafo e di MCP restano quelli di oggi; log di accesso di uvicorn disattivati | Le righe nostre hanno i campi utili alle evidenze; il log di accesso le duplicherebbe |
| Docker in questo step | `compose.yaml` con due servizi dalla stessa immagine: `agent` (servizio HTTP, porta pubblicata solo su `127.0.0.1:8000`) e `assistant` (CLI, `AGENT_URL=http://agent:8000`); `docker compose run --rm assistant` resta il comando | Il comando documentato continua a funzionare; i quattro container e l'agente non esposto sono lo Step 9 |
| `Session` in processo | Resta, e delega al modulo dell'agente | La usano le prove reali e i test del grafo; una sola implementazione del turno |

## 2. Struttura

```
assistant/
├── agent.py         # NUOVO: turno senza stato (run_turn, TurnResult), messaggi ↔ JSON
├── api.py           # NUOVO: app FastAPI (modelli pydantic, endpoint, errori)
├── service.py       # NUOVO: avvio del servizio (configurazione, MCP, modelli, grafo, uvicorn)
├── api_client.py    # NUOVO: client HTTP sincrono della CLI (AgentClient, AgentError, RemoteSession)
├── config.py        # + AGENT_HOST, AGENT_PORT (servizio); load_client_config con AGENT_URL (CLI)
├── model.py         # + check_model (GET /models)
├── commands.py      # /prompt: la CLI analizza, il servizio controlla e chiama prompts/get
├── session.py       # delega a agent.run_turn
├── terminal.py      # errori del client HTTP al posto di openai.APIError
└── __main__.py      # avvio della CLI come client dell'API
```

`graph.py`, `router.py`, `reviewer.py`, `summary.py`, `preferences.py`, il server MCP e i moduli degli
strumenti non cambiano. Variabili d'ambiente nuove: `AGENT_HOST`, `AGENT_PORT` (servizio),
`AGENT_URL` (CLI).

## 3. Modulo dell'agente (`assistant/agent.py`)

```python
@dataclass(frozen=True)
class TurnResult:
    reply: str                    # testo dell'ultimo messaggio, EMPTY_REPLY se vuoto
    tools_used: list[dict]        # {"name", "args", "result", "ok"} in ordine di esecuzione
    history: list[BaseMessage]    # cronologia aggiornata (dopo l'eventuale riassunto)
    summary: str                  # riassunto aggiornato

def run_turn(graph, history: list[BaseMessage], summary: str,
             messages: list[BaseMessage]) -> TurnResult: ...
def messages_to_json(messages: list[BaseMessage]) -> list[dict]: ...
def messages_from_json(data: list[dict]) -> list[BaseMessage]: ...   # ValueError se non valida
```

- `run_turn` dà un `id` nuovo ai messaggi che aprono il turno, invoca il grafo con
  `{"messages": history + messages, "summary": summary, "steps": 0, "reviews": 0}` e prende come
  messaggi del turno quelli dopo l'ultimo messaggio d'apertura (il nodo riassunto toglie messaggi
  solo dall'inizio e conserva sempre almeno l'ultimo, che è proprio quello). Non conserva nulla tra una chiamata e l'altra. Le
  eccezioni (per esempio `openai.APIError`) arrivano al chiamante.
- `tools_used`: per ogni `ToolMessage` del turno, il nome, gli argomenti della chiamata
  corrispondente (anche non interpretabile: allora la stringa ricevuta), il contenuto decodificato da
  JSON (se non è JSON, la stringa) e `ok = "error" not in result`. Comprende le chiamate non eseguite
  per il limite di passaggi (`ok: false`).
- `EMPTY_REPLY` si sposta da `session.py` ad `agent.py`; `Session.send_messages` chiama `run_turn` e
  conserva `history` e `summary` del risultato.
- `messages_from_json` controlla, oltre ai campi, l'ordine descritto in §1 e l'assenza di messaggi
  `system`; il primo problema dà un `ValueError` con un messaggio italiano che indica la posizione
  (da 1), per esempio «messaggio 3: risposta di uno strumento senza una chiamata corrispondente».
- `messages_to_json(messages_from_json(x)) == x` per ogni cronologia valida nella forma normalizzata
  (campi assenti omessi); lo verificano i test.

## 4. Formato JSON dei messaggi

| `role` | Campi | Messaggio LangChain |
|--------|-------|---------------------|
| `user` | `content` (testo), `name` facoltativo (`reviewer` per le indicazioni del revisore) | `HumanMessage` |
| `assistant` | `content`, `tool_calls` facoltativo: `[{"id", "name", "args": {…}}]`, `invalid_tool_calls` facoltativo: `[{"id", "name", "args": "<testo>" \| null, "error": "<testo>" \| null}]` | `AIMessage` |
| `tool` | `content` (testo, di solito JSON), `tool_call_id`, `name` | `ToolMessage` |

- `content` è sempre una stringa (per un `AIMessage` con contenuto a blocchi si usa `.text`). Gli
  altri campi di LangChain (`id`, metadati della risposta, `additional_kwargs`) non si trasmettono:
  il grafo non li usa e gli `id` li riassegna `add_messages`.
- Campi assenti o vuoti si omettono in uscita; in ingresso `tool_calls` e `invalid_tool_calls`
  vuoti equivalgono ad assenti.

## 5. API (`assistant/api.py`)

`create_app(*, graph, client, model_id, model_status) -> FastAPI`: `graph` è il grafo compilato,
`client` il client MCP (vero o `FakeMcpClient`), `model_id` l'identificativo configurato
(`LMSTUDIO_MODEL`), `model_status` una funzione senza argomenti che restituisce
`(ok: bool, detail: str)`. Così i test usano grafo, client e stato finti. Titolo dell'OpenAPI
«Assistente del laboratorio — agente», descrizioni in italiano.

### `POST /chat`

Corpo:

```json
{"message": "Quanto fa 17 * 23?", "history": [], "summary": ""}
{"prompt": {"name": "spiega", "arguments": {"argomento": "Model Context Protocol"}},
 "history": [...], "summary": "..."}
```

- Esattamente uno tra `message` (testo non vuoto dopo aver tolto gli spazi) e `prompt`; `history`
  (predefinita `[]`) e `summary` (predefinito `""`) facoltativi.
- Con `prompt`: `prompts/list`, controllo con `check_request` (Step 5), `prompts/get`,
  `to_messages`, con le stesse righe di log dello Step 5. La funzione che lo fa
  (`resolve_prompt(client, name, arguments) -> list[BaseMessage]`) sta in `commands.py`, accanto a
  `check_request` e `to_messages`.
- Risposta `200`:

```json
{"reply": "17 * 23 fa 391.",
 "tools_used": [{"name": "calculate", "args": {"expression": "17 * 23"},
                 "result": {"result": 391}, "ok": true}],
 "history": [...], "summary": ""}
```

### `GET /prompts`

`200` con `[{"name", "description", "arguments": [{"name", "description", "required"}]}]`, lo stesso
contenuto di `prompts/list`; `503 mcp_unavailable` se l'elenco non si ottiene. Riga di log
`prompts/list …` come nello Step 5.

### `GET /status`

```json
{"status": "ok", "agent": "ok",
 "mcp": {"status": "ok", "detail": "7 strumenti"},
 "model": {"status": "ok", "id": "google/gemma-4-e2b", "detail": ""}}
```

`status` vale `ok` se MCP e modello sono `ok`, altrimenti `degraded` (codice `503`); `mcp.status` e
`model.status` valgono `ok` o `unavailable`, con il motivo in `detail` in italiano (per esempio «LM
Studio non raggiungibile su http://localhost:1234/v1» o «modello 'x' non presente in /models»).
`check_model(config)` in `model.py` fa `GET <base_url>/models` con timeout di 5 s.

## 6. Errori

| Situazione | Codice | `error` | Esempio di `detail` |
|------------|--------|---------|---------------------|
| Corpo non conforme (campo mancante o di tipo sbagliato, ruolo sconosciuto) | 422 | — (formato FastAPI) | — |
| Né `message` né `prompt`, oppure entrambi; `message` vuoto | 400 | `invalid_request` | «indicare esattamente uno tra 'message' e 'prompt'» |
| Cronologia non valida (§3) | 400 | `invalid_history` | «messaggio 3: risposta di uno strumento senza una chiamata corrispondente» |
| Prompt sconosciuto, argomento sconosciuto, obbligatorio mancante | 400 | `prompt_rejected` | «argomenti obbligatori mancanti per 'spiega': 'argomento'» |
| `prompts/get` fallito (valore rifiutato dal server, sessione chiusa) o messaggi non utilizzabili | 502 | `prompt_unavailable` | «il prompt 'spiega' non è disponibile (Livello non ammesso…)» |
| `prompts/list` fallito | 503 | `mcp_unavailable` | «prompt non disponibili (sessione MCP chiusa)» |
| LM Studio non raggiungibile o senza risposta (`APIConnectionError`, `APITimeoutError`) | 503 | `model_unavailable` | «LM Studio non raggiungibile: …» |
| Altro errore di LM Studio (`openai.APIError`) | 502 | `model_error` | «LM Studio non ha risposto correttamente: …» |
| Qualsiasi altra eccezione | 500 | `internal_error` | «errore interno dell'agente; dettagli nel log» (traceback nel log) |

Nessun errore cambia cronologia o riassunto del chiamante: li aggiorna solo una risposta `200`.

## 7. Log (logger `assistant.api`)

```
api request=chat kind=message history=4 summary_chars=0
api response=chat status=200 tools=calculate reply_chars=16 history=6 duration_ms=5321
api response=chat status=503 error=model_unavailable detail="LM Studio non raggiungibile: …" duration_ms=2010
api request=chat kind=prompt name=spiega history=0 summary_chars=0
api response=status status=503 mcp=ok model=unavailable
```

Il testo dei messaggi non entra nelle righe dell'API (c'è già nei log del grafo e di MCP, quando
serve). Le risposte `4xx` sono a livello INFO, `5xx` a WARNING (`500` a ERROR con traceback).

Aggiunte del punto 3 (modalità autonoma): `kind` vale `none` o `both` per una richiesta senza
`message` né `prompt` o con entrambi; `tools=` resta vuoto in un turno senza strumenti; un corpo non
conforme allo schema (`422`) è rifiutato da FastAPI prima dell'endpoint e non scrive righe `api`. Il
testo di `message` arriva al grafo senza gli spazi iniziali e finali, come nel terminale.

Aggiunte del punto 4 (modalità autonoma): anche le righe di risposta di `/status` e `/prompts`
terminano con `duration_ms=` (stesso formato di `/chat`; `/status` può durare fino al timeout di
`GET /models`); `/prompts` riuscito scrive `api response=prompts status=200 count=<n>`; un `500`
scrive la stessa riga degli altri errori a livello ERROR, con il traceback; nessuna riga
`api request=` per `/status` e `/prompts` (non hanno corpo). La riga d'avvio del servizio (§8)
aggiunge `model=<id> base_url=<url>` e usa il logger `assistant.service`. L'elenco dei prompt per
CLI, `POST /chat` e `GET /prompts` viene da una sola funzione, `available_prompts(client)` in
`commands.py` (`PromptListError` «prompt non disponibili (…)»).

## 8. Servizio (`assistant/service.py`)

Stessa sequenza dell'avvio attuale: configurazione (`load_config`, più `AGENT_HOST` e `AGENT_PORT`),
logging, client MCP, strumenti, preferenze (lette una volta all'avvio del servizio), modelli, grafo;
poi `uvicorn.run(create_app(...), host=…, port=…, access_log=False, log_config=None)` dentro il
`with McpClient(...)`. Riga d'avvio `api listening=http://<host>:<port> docs=/docs`. Errori di
configurazione o di avvio del server MCP → messaggio su stderr ed exit 1, come oggi. LM Studio spento
all'avvio non impedisce l'avvio (lo segnala `/status`).

`AGENT_PORT`: intero tra 1 e 65535; `AGENT_HOST`: testo non vuoto (predefinito `127.0.0.1`).

## 9. CLI come client (`assistant/api_client.py`, `__main__.py`)

- `AgentClient(base_url, http=None)`: `status()`, `prompts()`, `chat(history, summary, message=… |
  prompt=…)`, con `httpx.Client` (timeout di 10 s per stato e prompt, 600 s per `/chat`: un turno può
  contenere più chiamate al modello). Agente non raggiungibile o risposta d'errore → `AgentError`
  con `code` e il `detail` del servizio (per l'agente non raggiungibile: «agente non raggiungibile su
  <url>»).
- `RemoteSession(client)`: `send(text)` e `send_prompt(name, arguments)`; conserva `history` (JSON) e
  `summary` solo dopo una risposta `200`.
- `PromptCommands` della CLI: `/prompts` → `client.prompts()` e `format_prompts`; `/prompt` →
  `parse_prompt_command` (errori di sintassi senza chiamate, come oggi), poi
  `CommandResult(prompt=(name, arguments))`, che il terminale manda con `session.send_prompt`.
  `prompt_rejected` si mostra come oggi: «Errore nel comando: <motivo>. Scrivi /prompts per l'elenco
  dei prompt.»; gli altri errori «Errore: <detail>».
- `terminal.run` intercetta `AgentError` al posto di `openai.APIError`: «Errore: <detail>. Riprova.» e
  la sessione continua con la cronologia invariata.
- `__main__.py`: `load_client_config` (`AGENT_URL`, `LOG_LEVEL`), `GET /status`; benvenuto
  «Assistente del laboratorio — agente su <url>, modello <id>. Scrivi /prompts …». Con stato
  `degraded`, prima del benvenuto: «Attenzione: <componente> non disponibile (<detail>).»

## 10. Docker

- `Dockerfile`: invariato tranne la porta documentata (`EXPOSE 8000`); `CMD` resta la CLI.
- `compose.yaml`: servizio `agent` (stessa immagine, `command: python -m assistant.service`,
  `AGENT_HOST=0.0.0.0`, variabili di LM Studio e volume delle note che oggi ha `assistant`, porta
  `127.0.0.1:8000:8000`, `healthcheck` che passa quando `/status` risponde con qualsiasi codice);
  servizio `assistant` (CLI, `AGENT_URL=http://agent:8000`, `depends_on` con
  `condition: service_healthy`, `stdin_open` e `tty`). Si arriva qui con il punto della CLI client,
  perché è lì che il comando Docker attuale smetterebbe di funzionare.

Aggiunte del punto 5 (modalità autonoma):
- Errori del client oltre a quelli del servizio: `agent_unreachable` («agente non raggiungibile su
  <url>», anche per connessione chiusa o tempo scaduto in connessione), `agent_timeout` («l'agente
  non ha risposto entro N s»), `bad_response` («risposta inattesa dell'agente (HTTP N)», anche per un
  corpo di forma sbagliata). `GET /status` con `503` e corpo di stato non è un errore per il client.
- Nel terminale ogni `AgentError` tranne `prompt_rejected` dà «Errore: <detail>. Riprova.» (anche gli
  errori del prompt, che si possono riprovare); il punto finale del `detail` non si raddoppia. Un
  errore di `/prompts` dà «Errore: <detail>.».
- All'avvio ogni `AgentError` su `/status` (anche `500`) → «Agente non disponibile: <detail>.» su
  stderr ed exit 1; per l'agente non raggiungibile si aggiunge «Avvia il servizio con: python -m
  assistant.service». Gli avvisi sono «Attenzione: server MCP non disponibile (…).» e «Attenzione:
  modello non disponibile (…).», su stdout prima del benvenuto.
- `CommandResult` ha `prompt=(name, arguments)` al posto di `messages`; la CLI controlla solo la
  sintassi, il controllo rispetto a `prompts/list` lo fa il servizio (righe di log nel servizio).
- `configure_logging` e `QUIET_LIBRARIES` stanno in `config.py` (li usano servizio e CLI, che così non
  importa FastAPI e il grafo); `load_client_config` legge solo `AGENT_URL` (senza `/` finale) e
  `LOG_LEVEL`.
- `healthcheck` con `start_period: 60s`, `start_interval: 2s` e `interval: 30s`: rapido all'avvio,
  poi rado, perché ogni controllo scrive una riga `api response=status` e chiama `GET /models`.
- Nei test il `TestClient` dell'app sostituisce la rete del client; l'avviso di Starlette sul
  parametro `timeout` è filtrato in `pytest.ini`.

## 11. Dipendenze

`fastapi==0.162.7` (nuova, con l'indiretta `annotated-doc==0.0.6`), `uvicorn==0.54.0` e
`httpx==0.28.1` (già indirette, ora dirette perché importate) in `requirements.txt`; `constraints.txt`
rigenerato con il comando del README. `pip check` senza problemi.

## 12. Test

### Senza modello (`pytest`)

- `test_agent.py` (nuovo, con `fake_graph`): `run_turn` senza stato (stessi argomenti → stesso
  risultato, gli argomenti non cambiano), risposta, `tools_used` con risultato e `ok` (strumento
  riuscito, errore, chiamata non eseguita per il limite), cronologia e riassunto aggiornati anche dopo
  una compressione; andata e ritorno JSON per ogni ruolo e campo; ogni errore di
  `messages_from_json` col suo messaggio.
- `test_api.py` (nuovo, `fastapi.testclient.TestClient`, grafo e `FakeMcpClient` finti): `/chat` con
  messaggio e con cronologia e riassunto di un turno precedente; con prompt (righe `prompts/get`, nessun
  `prompts/get` se rifiutato dall'host); ogni riga della tabella di §6; `/prompts`; `/status` in tutte
  le combinazioni; `/openapi.json` con i tre percorsi e gli schemi; righe di log esatte.
- `test_service.py` (nuovo): avvio con client MCP e `uvicorn.run` sostituiti (argomenti passati,
  configurazione non valida, server MCP non avviato).
- `test_api_client.py` (nuovo, con un `httpx.MockTransport` o con il `TestClient` dell'app con grafo
  finto): stato, prompt, chat, errori in `AgentError`, `RemoteSession` che aggiorna la cronologia solo
  dopo un `200`.
- `test_commands.py`, `test_terminal.py`, `test_main.py`, `test_config.py`, `test_model.py`,
  `test_session.py`: adeguati.

### Prove reali (`pytest -m real`)

- **Chiamata HTTP con uno strumento** (CA-67): servizio avviato come sottoprocesso su una porta
  libera; `POST /chat` «Quanto fa 17 * 23?» → `200`, `tools_used` con `calculate`, «391» nella
  risposta, righe `api response=chat status=200 tools=calculate` e `tool=calculate` nel log del
  servizio.
- **Stessa risposta da CLI e API** (CA-68): stessa domanda alla CLI (`python -m assistant` con la
  domanda e `esci` in ingresso) e all'API, stesso servizio: stessi strumenti e «391» in entrambe; si
  annota nel diario se i testi coincidono alla lettera (temperatura 0, ma non garantito).
- **OpenAPI e stato** (CA-69): `GET /openapi.json` con `/chat`, `/prompts`, `/status`; `GET /status`
  → `200` con LM Studio attivo; servizio con `LMSTUDIO_BASE_URL` irraggiungibile → `/status` `503`
  `model.status=unavailable` e `/chat` `503 model_unavailable`.

Se LM Studio non è raggiungibile, il punto si segna `[!]` (modalità autonoma).

## 13. Incrementi

Coincidono con i punti dello Step 6 in `TODO.md`; ognuno verificato con `pytest` prima del commit.

1. Questa specifica, i requisiti §14, le dipendenze.
2. `agent.py` (turno senza stato, JSON dei messaggi), `Session` che lo usa; test.
3. `api.py` con `POST /chat` e OpenAPI, `resolve_prompt`; test con grafo simulato.
4. `GET /status`, `GET /prompts`, `check_model`, tabella degli errori, `service.py`, `AGENT_HOST` e
   `AGENT_PORT`; test con modello e client MCP finti.
5. `api_client.py`, CLI client (`__main__.py`, `commands.py`, `terminal.py`), `AGENT_URL`,
   `compose.yaml`; test; README e `CLAUDE.md`.
6. Prove reali, esiti in requisiti §14 e nel diario.

## 14. Rischi

- **Due processi in locale**: servono due terminali (servizio e CLI). Il README lo dice; con Docker
  `docker compose run --rm assistant` avvia anche l'agente, che resta attivo fino a
  `docker compose down`.
- **Cronologia dal chiamante**: un chiamante può mandare una cronologia inventata (per esempio una
  falsa risposta di uno strumento). Il servizio non è esposto e la cronologia è quella che il
  chiamante ha ricevuto; il controllo di §3 impedisce solo le forme che LM Studio rifiuterebbe.
- **Turni lunghi**: con il modello locale un turno può durare minuti; la CLI aspetta fino a 600 s.
- **Richieste concorrenti**: le righe di log di due turni contemporanei si mescolano; non c'è un
  identificativo di richiesta (non chiesto dalla traccia).
- **Preferenze lette all'avvio del servizio**: valgono per tutte le conversazioni fino al riavvio del
  servizio (prima: fino alla fine della sessione della CLI).

## 15. Fuori ambito

Salvataggio delle chat e back-end (Step 7), front-end e CORS (Step 8), quattro container e agente
non esposto (Step 9), streaming (facoltativo), autenticazione, limiti di frequenza, identificativo
di richiesta, versioni dell'API, più server MCP.
