# Specifica — Robustezza del servizio dell'agente (R-B3, R-B4, R-B9)

Data: 2026-11-16
Stato: approvata (2026-11-16)
Debiti: R-B3, R-B4 e R-B9 di [`TODO.md`](../../../TODO.md), descritti nel rapporto
[`../reviews/2026-11-15-auto-claude.md`](../reviews/2026-11-15-auto-claude.md), §3.
Specifica di base del servizio: [`2026-11-14-servizio-http-design.md`](2026-11-14-servizio-http-design.md).

## 1. Scopo

Quando qualcosa si rompe, oggi il servizio dell'agente e la CLI restano bloccati o mostrano un
traceback. Con queste modifiche l'agente si ripara da solo dove può. Dove non può, dice
chiaramente che cosa non va. Il comportamento nei casi normali non cambia.

| Id | Oggi | Dopo |
|---|---|---|
| R-B3 | Se il server MCP muore, ogni chiamata fallisce con «Connection closed» finché qualcuno non riavvia il servizio; `/status` risponde `503` per sempre; il controllo di salute di `agent` in Compose accetta qualsiasi risposta | Alla richiesta successiva il servizio riavvia il server MCP e ripete la richiesta; il controllo di salute dice «non sano» solo se MCP resta irraggiungibile |
| R-B4 | `/status` aspetta MCP fino a 35 s, la CLI aspetta `/status` 10 s: con MCP bloccato la CLI esce | `/status` dà a MCP 5 s; la CLI aspetta 20 s e, con MCP bloccato, si apre con l'avviso «server MCP non disponibile» |
| R-B9 | `AGENT_URL=http://[::1` → traceback `InvalidURL` alla prima richiesta | «Configurazione non valida: AGENT_URL non è un indirizzo valido: …» all'avvio, nella CLI e nel back-end |

Fuori scopo: gli altri debiti di `TODO.md`, `BACKEND_URL` del front-end, un controllo continuo
del server MCP in sottofondo.

## 2. Approcci considerati (R-B3)

1. **Riconnessione automatica nel client MCP** (scelto). Il servizio riavvia il server morto
   alla prima richiesta che lo trova chiuso. Funziona allo stesso modo in locale e in Docker e
   non chiede interventi. Il lavoro sta in `mcp_client.py`, la parte asincrona.
2. **Il servizio esce e Compose lo riavvia.** Poco codice, ma in locale il servizio va
   riavviato a mano e la CLI perde la connessione.
3. **Solo messaggi più onesti** e controllo di salute severo. È il lavoro minimo, ma il riavvio
   resta manuale.

L'utente ha lasciato la scelta al progettista (2026-11-16). La 1 è l'unica che toglie il
problema invece di spiegarlo meglio.

## 3. Riconnessione del server MCP (R-B3)

Tutto avviene dentro `McpClient` (`assistant/mcp_client.py`). I metodi pubblici
(`list_tools`, `call_tool`, `read_resource`, `list_prompts`, `get_prompt`) restano gli stessi,
quindi grafo, API e servizio non cambiano.

**Quando si riavvia.** Fa scattare il riavvio solo una connessione chiusa. Oggi si vede come
`MCPError` con codice `CONNECTION_CLOSED` (−32000): verificato il 2026-11-16 uccidendo il
processo del server, ogni richiesta successiva fallisce subito così. Valgono come connessione
chiusa anche gli stream chiusi o rotti di anyio (`ClosedResourceError`, `BrokenResourceError`).
Gli errori che il server restituisce rispondendo (prompt sconosciuto, risorsa inesistente,
argomenti non validi, errore di uno strumento) non fanno riavviare niente.

**Che cosa succede.**
- Connessione chiusa: il client chiude la sessione vecchia, avvia un nuovo processo del server
  (stesso comando, stessi argomenti, con la stessa attesa massima dell'avvio) e ripete **una
  volta** la stessa richiesta. Se anche il secondo tentativo trova la connessione chiusa,
  l'errore arriva al chiamante come oggi.
- Riavvio fallito (`McpStartupError`): la richiesta fallisce con
  `ToolUnavailableError("server MCP non riavviato: <motivo>")`. La richiesta successiva prova di
  nuovo a riavviarlo. Non c'è nessun ciclo in sottofondo: si riprova solo quando qualcuno chiede
  qualcosa.
- Tempo scaduto (server bloccato, non morto): **nessuna ripetizione immediata**, che
  raddoppierebbe l'attesa. L'errore arriva come oggi, ma la sessione viene segnata da
  riavviare: la richiesta successiva riavvia il server prima di partire.

**Più richieste insieme.** Il servizio chiama il client da più thread: le richieste
dell'endpoint e lo streaming. Il riavvio è protetto da un lock e da un contatore di
generazione: riavvia solo il thread che ha visto fallire la sessione ancora attuale, gli altri
usano la nuova.

**Che cosa non cambia.** La resource delle preferenze resta letta una sola volta all'avvio
del servizio. Anche il catalogo degli strumenti resta quello letto all'avvio: il server
riavviato è lo stesso programma, con gli stessi strumenti. Le note in SQLite restano, perché
il nuovo processo apre lo stesso file.

**Rischio accettato.** Ripetere `call_tool` dopo una connessione chiusa può raddoppiare una
scrittura (`add_note`, `delete_note`) solo se il server muore dopo aver scritto e prima di
rispondere. È un caso raro; con il server già morto la richiesta non arriva proprio.

**Log** (logger `assistant.mcp_client`):
- `WARNING mcp_restart reason="Connection closed"` quando il riavvio comincia;
- `INFO mcp_restarted duration_ms=…` quando riesce;
- `WARNING mcp_restart_failed error="…"` quando fallisce.

**Testo per il modello** (`assistant/graph.py`, errore di trasporto di uno strumento):
«Strumento non raggiungibile: {errore}. Riprova o riavvia il servizio dell'agente.» Oggi dice
«riavvia l'assistente», che dalla Lezione 6, Step 6, non è più il processo giusto.

## 4. Controllo di salute di `agent` in Compose (R-B3)

Il container è sano quando `/status` risponde e il server MCP risulta raggiungibile, cioè con
`mcp.status == "ok"`, qualunque sia lo stato del modello: LM Studio sta fuori dal container e,
se è spento, l'agente resta comunque sano.

```yaml
test: ["CMD", "python", "-c", "import httpx, sys; sys.exit(httpx.get('http://127.0.0.1:8000/status', timeout=10).json()['mcp']['status'] != 'ok')"]
```

Gli altri parametri (`start_period`, `start_interval`, `interval`, `timeout`, `retries`) restano
come sono. Il controllo ogni 30 s chiama `/status`, che a sua volta chiama `list_tools`: in
Docker, quindi, un server MCP morto viene riavviato entro 30 s anche se nessuno sta usando
l'app. Il commento sopra il controllo va aggiornato.

## 5. Tempi di attesa di `/status` (R-B4)

- `McpClient.list_tools` riceve un parametro facoltativo `timeout`. Se è indicato, vale come
  attesa massima di quella richiesta, al posto di `timeout + 5`.
- `/status` (`_mcp_status` in `assistant/api.py`) chiama `list_tools(timeout=STATUS_MCP_TIMEOUT)`,
  con `STATUS_MCP_TIMEOUT = 5.0`. Con MCP bloccato risponde `503` con
  `mcp.detail = "nessuna risposta entro 5 s"`.
- `STATUS_TIMEOUT` della CLI (`assistant/api_client.py`) passa da 10 a 20 s. Il conto: 5 s per
  MCP, più 5 s al massimo per il controllo del modello, più il margine per un eventuale riavvio
  del server, che di solito richiede 1–3 s.
- `FakeMcpClient` (`tests/conftest.py`) accetta lo stesso parametro.

Caso limite accettato: se il server MCP si blocca proprio durante un riavvio fatto da
`/status`, l'attesa dell'avvio (30 s) supera i 20 s della CLI, che esce con
«l'agente non ha risposto entro 20 s».

## 6. Controllo di `AGENT_URL` (R-B9)

`load_client_config` (`assistant/config.py`) controlla l'indirizzo completo con
`urllib.parse.urlsplit`. L'indirizzo deve avere schema `http` o `https` e un nome di host, e la
porta, se c'è, deve essere un numero valido; vanno intercettati i `ValueError` di `urlsplit` e
di `.port`. Gli errori diventano `ConfigError`:

- schema sbagliato: messaggio di oggi, invariato;
- tutto il resto: «AGENT_URL non è un indirizzo valido, ricevuto '<valore>'.»

Il back-end usa la stessa funzione (`backend/config.py`), quindi la correzione vale anche per
lui. Non servono nuove dipendenze.

## 7. Test

**Senza modello (`pytest`)**
- Configurazione: `http://[::1`, `http://host:porta`, `http://` e `http://:8000` danno
  `ConfigError`; `main()` della CLI e del back-end stampano «Configurazione non valida: …» ed
  escono con 1. Gli indirizzi validi di oggi continuano a passare.
- Client MCP, con un piccolo server FastMCP di prova in `tests/` che ha uno strumento che
  termina il processo e uno che resta fermo oltre il tempo massimo:
  - dopo la morte del server, `list_tools` e `call_tool` riescono, e il processo del server è
    nuovo;
  - prompt sconosciuto e risorsa inesistente non fanno riavviare;
  - un riavvio fallito dà «server MCP non riavviato: …» e la richiesta successiva riprova;
  - con il tempo scaduto la richiesta non viene ripetuta, la successiva riavvia il server;
  - due thread che trovano la sessione chiusa nello stesso momento fanno un solo riavvio;
  - i tre messaggi di log.
- API: `/status` passa `timeout=5.0` a `list_tools`; con MCP bloccato risponde `503` senza
  aspettare oltre.
- Grafo: il nuovo testo «Riprova o riavvia il servizio dell'agente».
- Docker (`test_docker.py`): il controllo di salute di `agent` legge `mcp.status`.

**Prove manuali** (resoconto in `PROGRESS.md`)
- Locale: servizio avviato, processo del server MCP ucciso, poi `/status` di nuovo `200` e una
  domanda dalla CLI che usa uno strumento MCP.
- Docker: con `docker compose up -d`, processo del server MCP ucciso dentro `agent`, poi
  `docker compose ps` mostra ancora `agent` sano dopo il controllo successivo e la pagina usa
  ancora gli strumenti.

Non servono nuove prove reali con LM Studio: la riconnessione non coinvolge il modello.

## 8. Documentazione

- README: nella parte sulla diagnosi, riavvio automatico del server MCP, nuovi messaggi e
  nuovo controllo di salute.
- `TODO.md`: R-B3, R-B4 e R-B9 passano da «Debiti noti» a «Già fatto».
- `PROGRESS.md`: voce del lavoro, con le prove eseguite.
- La specifica del servizio HTTP del 2026-11-14 resta com'è, perché è storica: questa la
  aggiorna.

## 9. Scelte del progettista da controllare

1. Riconnessione automatica invece delle altre due strade (§2).
2. Una sola ripetizione della richiesta, e nessuna con il tempo scaduto (§3).
3. Rischio accettato di una nota doppia in un caso raro (§3).
4. Container sano se MCP risponde, anche con LM Studio spento (§4).
5. 5 s a MCP dentro `/status` e 20 s di attesa nella CLI (§5).
6. Nessuna nuova prova reale con LM Studio, solo le due prove manuali (§7).
