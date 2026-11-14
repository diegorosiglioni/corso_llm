# TODO

Fonte dei lavori mancanti: traccia della lezione 6 in `docs/superpowers/lezione6.md` (step 4–9 e
streaming facoltativo). Si fa solo ciò che chiede la traccia (decisione dell'utente del
2026-11-13, vedi `PROGRESS.md`). Regole della modalità autonoma: `CLAUDE.md`, sezione
«Modalità autonoma». Test senza modello: `.\.venv\Scripts\python.exe -m pytest`.

## Già fatto

- [x] Base (lezioni 3–4): grafo LangGraph esplicito, configurazione da variabili d'ambiente, cronologia di sessione, terminale, modello di LM Studio, strumento orologio con fuso IANA, Docker Compose
- [x] Correzioni dell'audit: versioni fissate in `constraints.txt`, indirizzo di LM Studio configurabile in Docker, cache escluse dall'immagine
- [x] Lezione 5: server FastMCP stdio con convertitore di unità, calcolatrice sicura, catalogo locale e note SQLite, client MCP sincrono collegato al grafo, prove reali, volume Docker delle note
- [x] Progetto spostato nella radice della repository, `lezione3/` esclusa da Git
- [x] Lezione 6, Step 1 · Router: ambito in `scope.txt`, rifiuto senza passare dall'agente, prove reali
- [x] Lezione 6, Step 2 · Revisore: coerenza della risposta, indicazione all'agente, limite `MAX_REVIEWS`, prove reali
- [x] Lezione 6, Step 3 · Riassunto: nodo `summary` con `SUMMARY_MAX_MESSAGES` e `SUMMARY_KEEP_MESSAGES`, prove reali e Docker

## Step 4 · Resource MCP: preferenze dell'utente

- [x] Specifica dello Step 4 in `docs/superpowers/specs/` e requisiti §12 in `docs/superpowers/requisiti.md` (formato del file delle preferenze, valori predefiniti, variabile d'ambiente del percorso, righe di log), con le scelte del progettista annotate
- [x] Server MCP: resource `utente://preferenze` (`application/json`) con lingua delle risposte, fuso orario predefinito e stile (sintetico o dettagliato), letta da un file `preferenze.json` di esempio; test che la resource compare in `resources/list` e non in `tools/list`
- [x] Client MCP: metodo sincrono `read_resource` in `mcp_client.py` e nel `FakeMcpClient` di `conftest.py`; test con il server reale via stdio, resource leggibile e resource assente
- [x] Host: lettura della resource una sola volta a inizio sessione e testo in cima al prompt di sistema dell'agente; resource non disponibile → valori predefiniti e WARNING nel log; log `resources/read` separato da quelli dei tool; la resource non entra in `bind_tools`; test con client finto
- [x] Prova reale Step 4 (marcatore `real`, LM Studio attivo): «Che ore sono?» con fuso predefinito `America/New_York` usa quel fuso senza chiederlo; cambio di lingua o stile nel file cambia la risposta della sessione successiva; README aggiornato (sezione preferenze e diagnosi)

## Step 5 · Prompt MCP: comandi riusabili nella CLI

- [x] Specifica dello Step 5 in `docs/superpowers/specs/` e requisiti §13 (sintassi di `/prompts` e `/prompt nome chiave=valore` con valori tra virgolette, messaggi d'errore, righe di log)
- [x] Server MCP: prompt `spiega(argomento, livello="base")` e `riassumi_conversazione(stile)`; test di `prompts/list` (nome, descrizione, argomenti) e `prompts/get`
- [x] Client MCP: metodi sincroni `list_prompts` e `get_prompt` in `mcp_client.py` e nel `FakeMcpClient`; test con il server reale via stdio
- [x] Terminale: comando `/prompts` che mostra nome, descrizione e argomenti di ogni prompt; test con client finto
- [x] Terminale: comando `/prompt nome chiave=valore` con controllo rispetto a `prompts/list` (argomenti obbligatori mancanti o sconosciuti bloccano la richiesta senza chiamare il modello); i messaggi ottenuti entrano nella cronologia e passano dal grafo (router, strumenti, revisore); log con prompt, argomenti e messaggi ricevuti; test con client e modello finti
- [x] Prova reale Step 5: `/prompt spiega argomento="Model Context Protocol" livello=base` dà una risposta adeguata e `riassumi_conversazione` riassume i turni della sessione; README aggiornato

## Step 6 · L'agente come servizio HTTP

- [x] Specifica dello Step 6 e requisiti §14 (framework HTTP con OpenAPI, formato JSON di messaggi, cronologia e riassunto, codici d'errore, porta), con dipendenze motivate e versioni fissate in `requirements.txt` e `constraints.txt`
- [x] Modulo dell'agente separato dall'interfaccia: funzione senza stato che riceve messaggio, cronologia e riassunto e restituisce risposta, strumenti usati, cronologia e riassunto aggiornati; serializzazione JSON dei messaggi; test con il grafo simulato
- [x] Endpoint HTTP di conversazione (messaggio e cronologia in ingresso, risposta e strumenti usati in uscita) con OpenAPI consultabile; test dell'API con il grafo simulato
- [x] Endpoint di stato (agente, server MCP e modello raggiungibili) ed errori comprensibili con codice HTTP quando modello o strumenti non sono disponibili; test con modello e client MCP finti
- [x] CLI come client dell'API HTTP (stesso comportamento del terminale attuale, comandi `/prompts` e `/prompt` compresi); test con l'API simulata; README e CLAUDE.md aggiornati con i nuovi comandi di avvio
- [x] Prova reale Step 6: chiamata HTTP con uno strumento (risposta e traccia nei log), stessa risposta da CLI e API, OpenAPI consultabile; esiti nel diario

## Step 7 · Back-end: API e salvataggio delle chat

- [x] Specifica dello Step 7 e requisiti §15 (struttura del servizio back-end, schema PostgreSQL di chat e messaggi, libreria di accesso al database, configurazione da variabili d'ambiente, come si testa senza PostgreSQL attivo)
- [x] Back-end: modello dati e archivio di chat e messaggi (creare, elencare con titolo e data dell'ultimo messaggio, leggere in ordine cronologico, eliminare con i messaggi); test dell'archivio
- [x] Back-end: endpoint di creazione, elenco, lettura ed eliminazione delle chat con OpenAPI; test dell'API
- [x] Back-end: invio di un messaggio (salva la domanda, chiama l'agente via HTTP con cronologia e riassunto, salva e restituisce la risposta); agente non raggiungibile → errore chiaro e documentato; test con l'agente simulato
- [x] Prova reale Step 7 con PostgreSQL e agente attivi: chat presenti dopo il riavvio del back-end; README aggiornato

## Step 8 · Front-end: interfaccia di chat

- [x] Specifica dello Step 8 e requisiti §16 (tecnologia del front-end, contratto = OpenAPI del back-end, indirizzo del back-end da configurazione)
- [x] Front-end: elenco, creazione ed eliminazione delle chat, collegato solo al back-end
- [x] Front-end: vista dei messaggi e invio, stato di attesa ed errori comprensibili (agente spento → errore mostrato senza bloccare l'interfaccia); test automatici dove possibili
- [x] Prova reale Step 8 dal browser: conversazione completa con uno strumento, chat presente dopo il riavvio, agente spento gestito; README aggiornato

## Step 9 · Docker Compose: un container per componente

- [x] Dockerfile dell'agente come servizio HTTP (server MCP stdio nel suo container, LM Studio via `host.docker.internal`), del back-end e del front-end
- [x] `compose.yaml` con quattro servizi (front-end, back-end, agente, PostgreSQL ufficiale): volume dei dati di PostgreSQL, credenziali in `.env` (con esempio in `.env.example`), back-end avviato a database pronto, agente non esposto, front-end raggiungibile dal browser
- [ ] Prova reale Step 9: `docker compose up` avvia i quattro servizi e `docker compose ps` li mostra attivi; chat dal browser con uno strumento visibile nei log dell'agente; chat presenti dopo `down` e `up`; README e CLAUDE.md aggiornati (comandi Docker)

## Facoltativo · Streaming della risposta

- [ ] Specifica dello streaming (eventi di testo e strumenti, Server-Sent Events nel back-end, decisione documentata su bozza o sola risposta approvata con il revisore attivo)
- [ ] Streaming nell'agente e nel back-end (messaggio completo salvato alla fine) con test
- [ ] Streaming nel front-end (testo mentre arriva, indicazione dell'uso di uno strumento) e prova reale; README aggiornato
