# TODO

Lavori fatti e debiti noti. Nessun punto aperto: un lavoro nuovo (debito o lezione successiva) parte
con il proprio ciclo di specifica e piano (`CLAUDE.md`, «Metodo»). Test senza modello:
`.\.venv\Scripts\python.exe -m pytest`.

## Già fatto

- [x] Base (lezioni 3–4): grafo LangGraph esplicito, configurazione da variabili d'ambiente, cronologia di sessione, terminale, modello di LM Studio, strumento orologio con fuso IANA, Docker Compose
- [x] Correzioni dell'audit: versioni fissate in `constraints.txt`, indirizzo di LM Studio configurabile in Docker, cache escluse dall'immagine
- [x] Lezione 5: server FastMCP stdio con convertitore di unità, calcolatrice sicura, catalogo locale e note SQLite, client MCP sincrono collegato al grafo, prove reali, volume Docker delle note
- [x] Progetto spostato nella radice della repository, `lezione3/` esclusa da Git
- [x] Lezione 6, Step 1 · Router: ambito in `scope.txt`, rifiuto senza passare dall'agente, prove reali
- [x] Lezione 6, Step 2 · Revisore: coerenza della risposta, indicazione all'agente, limite `MAX_REVIEWS`, prove reali
- [x] Lezione 6, Step 3 · Riassunto: nodo `summary` con `SUMMARY_MAX_MESSAGES` e `SUMMARY_KEEP_MESSAGES`, prove reali e Docker
- [x] Lezione 6, Step 4–9 (loop autonomo del 2026-11-14 su `auto-claude`, poi revisione, correzioni e verifica del 2026-11-15 e 16): resource `utente://preferenze`, prompt MCP `spiega` e `riassumi_conversazione` con `/prompts` e `/prompt`, agente come servizio HTTP, back-end con chat in PostgreSQL, front-end web, Docker Compose a quattro container
- [x] Facoltativo · Streaming della risposta con Server-Sent Events: bozza mostrata mentre arriva, strumenti indicati, risposta salvata alla fine
- [x] Robustezza del servizio (2026-11-16, debiti R-B3, R-B4, R-B9): riavvio automatico del server MCP, controllo di salute di `agent` legato a MCP, `/status` con 5 s per MCP e CLI che aspetta 20 s, `AGENT_URL` malformato come «Configurazione non valida»
- [x] Revisione del 2026-11-16 (`REVIEW.md`), I-1: dopo una connessione chiusa il client MCP non ripete più le chiamate agli strumenti (`ToolOutcomeUnknownError`, testo «esito incerto» per il modello). Gli altri punti della revisione sono aperti in `REVIEW.md`, «Punti da riprendere»

## Debiti noti

Accettati dall'utente nella rilettura del 2026-11-15 e nelle correzioni del 2026-11-16; descrizione
di ciascuno nel rapporto [`docs/superpowers/reviews/2026-11-15-auto-claude.md`](docs/superpowers/reviews/2026-11-15-auto-claude.md), §2 (R-D1), §9 (R-A1a e R-A1b, minori del secondo giro di revisione) e §3 (gli altri).

| Id | Che cosa | Motivo | Rapporto |
|---|---|---|---|
| R-D1 | Pagina chiusa durante lo streaming: il turno dell'agente continua e la risposta a volte si salva, a volte no (documentato in specifica dello streaming, README e RF-84) | Salvare la risposta anche a pagina chiusa è utile; un endpoint asincrono che chiude il flusso è un lavoro grande | §2 |
| R-A8 | Ambito del router largo («informatica, programmazione e intelligenza artificiale»): `/prompt spiega` accetta qualsiasi spiegazione di informatica | La riga ristretta non fa rifiutare al modello una spiegazione di informatica generale (due prove reali fallite il 2026-11-16); l'ambito resta largo per decisione dell'utente | §3 |
| R-A11 | La prova reale delle preferenze (CA-51) cambia solo la lingua, non lo stile | La traccia chiede «lingua o stile»: la prova sulla lingua basta | §3 |
| R-B6 | «Stessa risposta da CLI e API» (CA-68): l'uguaglianza dei testi è solo stampata | Le risposte del modello variano: un'uguaglianza esatta CLI/API sarebbe instabile | §3 |
| R-C4 | Invii contemporanei nella stessa chat: il secondo sovrascrive lo stato dell'agente; chat eliminata durante il salvataggio → `500` | Raro con un solo utente, documentato; va con R-D1 | §3 |
| R-C10 | Evidenze di Compose (CA-91…CA-93) dimostrate con uno script temporaneo non versionato | Evidenze nel diario; streaming da Compose ripetuto il 2026-11-15 | §3 |
| R-D3 | Tempo scaduto dopo la risposta del back-end: il testo torna nel campo anche se la domanda è salvata | Raro, la domanda non si perde | §3 |
| R-P1 | La pagina mostra markdown e LaTeX delle risposte così come sono | Servirebbe una libreria o un'istruzione nel prompt, che rischia di far perdere l'uso degli strumenti | §3 |
| R-A9 | CLI e back-end importano `mcp_client` (quindi `fastmcp`, `langchain_core`) per due dataclass | Minore confermato che l'utente ha scelto di non correggere ora | §3 |
| R-B2 | Nessun test di `/chat` con uno strumento MCP irraggiungibile durante il turno (solo a livello di grafo) | Come sopra | §3 |
| R-C5 | `list_chats` e `get_chat` caricano anche la cronologia JSON completa dell'agente | Come sopra | §3 |
| R-C8 | Test di `test_docker.py` saltati solo senza l'eseguibile `docker`, non senza il plugin `compose` | Come sopra | §3 |
| R-D2 | `chat_stream` chiuso prima del primo `next` lascia aperta la connessione httpx | Come sopra | §3 |
| R-D4 | Il contratto del front-end non confronta con l'OpenAPI i campi degli eventi dello streaming | Come sopra | §3 |
| R-D5 | La bozza riporta in fondo chi sta leggendo più in alto; `#waiting` annunciato ogni secondo | Come sopra | §3 |
| R-A1a | Se CA-58 (`test_explain_prompt_from_the_cli`) passasse il controllo di merito risulterebbe un semplice `passed`, mentre `requisiti.md`, README e rapporto direbbero ancora «non soddisfatta per limite del modello» | Minore del secondo giro di revisione; l'utente ha scelto di non correggerlo ora (2026-11-16): con il modello attuale il merito non passa | §9 |
| R-A1b | Con CA-58 `xfailed` la risposta del modello si vede solo con `-rA` o `-s` | Come sopra | §9 |
