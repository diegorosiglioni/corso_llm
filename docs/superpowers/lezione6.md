# Lezione 6 — Evolvere l'agente (traccia del docente)

Data: 2026-11-09
Stato: **trascrizione della traccia, non ancora requisiti approvati.** Riassume fedelmente le
19 slide di `LLM_Lez_6.pdf` (nella radice, non tracciato). Ogni step avrà il proprio
brainstorming, specifica e piano; i requisiti approvati finiranno in `requisiti.md` (§9 e
seguenti) e nelle specifiche.

## Regola generale

- Ogni step parte da quello precedente funzionante, verificato con le evidenze richieste e
  registrato con un commit.
- Uno step per volta, con specifica e piano approvati prima del codice; estendere senza
  riscrivere e non anticipare gli step successivi.
- Per ogni step: test automatici (modello simulato), prova reale con LM Studio, README
  aggiornato, commit (Conventional Commits). Aggiornare `CLAUDE.md` quando cambiano
  architettura o comandi.
- Le evidenze richieste devono essere verificabili nei log o nei test.

## Blocco A — Un secondo nodo LLM (step 1–3)

Stesso modello, prompt di sistema diversi. Grafo finale dei tre step:

```
START → Riassunto (3) → Router (1) ─ in ambito ──→ Agente LLM + strumenti ⇄ Nodo strumenti
                                    └ fuori ambito → Rifiuto → END
        Agente → Revisore (2) ─ coerente → END
                              └ non coerente + motivo → Agente
```

### Step 1 · Router: conversazione o fuori ambito (base)

L'agente ha un ambito dichiarato in configurazione. Un nodo LLM prima dell'agente decide se la
domanda rientra nell'ambito; la scelta degli strumenti resta all'agente.

- Obiettivo: le domande fuori ambito ricevono un rifiuto senza raggiungere l'agente.
- Da realizzare:
  1. ambito descritto in configurazione, non nel codice;
  2. nodo router con output strutturato: categoria (conversazione o fuori ambito) e motivo;
  3. arco condizionale: conversazione → agente; fuori ambito → nodo di rifiuto → fine;
  4. il router non valuta gli strumenti: se servono, lo decide l'agente come prima.
- Evidenze:
  - domanda in ambito: log con categoria, motivo e passaggio all'agente;
  - domanda fuori ambito: rifiuto, nessuna esecuzione del nodo agente nei log;
  - test con risposte del router simulate per entrambi i percorsi.
- Evidenza minima di consegna: domanda fuori ambito rifiutata senza passare dall'agente.

### Step 2 · Revisore: la risposta è coerente con la domanda? (intermedio)

Dopo la risposta dell'agente, un secondo LLM verifica che risponda davvero alla domanda: tutte le
parti richieste, nessuna deviazione dal tema.

- Obiettivo: una risposta incompleta o fuori tema torna all'agente con il motivo, finché non è
  coerente o si raggiunge il limite.
- Da realizzare:
  1. nodo revisore che riceve la domanda dell'utente e la risposta proposta dall'agente;
  2. output strutturato: coerente (sì o no) e motivo;
  3. se non coerente, il motivo entra nella cronologia come indicazione per l'agente;
  4. limite di revisioni nello stato: al limite si restituisce l'ultima risposta e lo si
     segnala nei log.
- Evidenze:
  - domanda in due parti con risposta parziale: rifiuto motivato e nuova risposta completa;
  - risposta coerente approvata al primo passaggio;
  - limite rispettato con un revisore simulato che rifiuta sempre.
- Evidenza minima: risposta incompleta corretta dopo la revisione, entro il limite.

### Step 3 · Riassunto della cronologia (avanzato)

Con un modello locale il contesto è limitato. Un nodo LLM sostituisce i messaggi più vecchi con
un riassunto e mantiene intatti gli ultimi turni.

- Obiettivo: conversazione utilizzabile su molti turni senza perdere informazioni importanti.
- Da realizzare:
  1. soglia configurabile (numero di messaggi o stima dei token) oltre la quale si riassume;
  2. nodo riassunto all'inizio del turno: comprime i messaggi vecchi e conserva gli ultimi N;
  3. il riassunto è un campo dello stato che viene aggiornato, non accumulato;
  4. il taglio non separa mai una richiesta di tool dal relativo ToolMessage.
- Evidenze:
  - log con numero di messaggi prima e dopo il riassunto;
  - un'informazione del primo turno (per esempio il nome dell'utente) è usata dopo la
    compressione;
  - sotto la soglia il nodo non chiama il modello.
- Evidenza minima: informazione del primo turno ancora usata dopo la compressione.

## Blocco B — MCP: resource e prompt (step 4–5)

| Primitiva | Chi la attiva | Quando | Nei log |
|-----------|---------------|--------|---------|
| Tool | il modello | durante il ciclo, quando serve un'azione o un dato | `tools/call` a ogni richiesta del modello |
| Resource | l'applicazione (host) | prima di chiamare il modello, per preparare il contesto | `resources/read` una volta, prima della prima domanda |
| Prompt | l'utente | quando sceglie esplicitamente un compito | `prompts/get` solo quando l'utente scrive `/prompt` |

Errore comune: esporre tutto come tool.

### Step 4 · Resource: preferenze dell'utente

Esempio della slide: `@mcp.resource("utente://preferenze", name="preferenze",
mime_type="application/json")` che legge `preferenze.json`; l'host fa
`session.read_resource("utente://preferenze")` e mette il testo in cima al prompt di sistema.

- Obiettivo: modificando il file delle preferenze, il comportamento cambia senza toccare il
  codice.
- Da realizzare:
  1. resource `utente://preferenze` con lingua delle risposte, fuso orario predefinito e stile
     (sintetico o dettagliato);
  2. lettura da parte dell'host a inizio sessione e inserimento in cima al prompt di sistema;
  3. la resource non compare tra i tool passati a `bind_tools`;
  4. resource non disponibile: valori predefiniti, segnalati nei log.
- Evidenze:
  - «Che ore sono?» usa il fuso predefinito senza chiederlo (provare con un fuso non ovvio come
    `America/New_York`);
  - cambiando lingua o stile nel file, la sessione successiva risponde di conseguenza;
  - lettura della resource visibile nei log, separata dalle chiamate ai tool.

### Step 5 · Prompt: comandi riusabili nella CLI

Esempio della slide: `@mcp.prompt def spiega(argomento: str, livello: str = "base")`; l'host fa
`session.list_prompts()` e `load_mcp_prompt(session, "spiega", arguments=…)` e aggiunge i
messaggi alla cronologia. MCP non prevede un comando standard: i comandi li definisce la CLI.

- Obiettivo: un prompt richiamato dall'utente passa dal grafo come qualsiasi altra domanda
  (router, strumenti, revisore compresi).
- Da realizzare:
  1. prompt `spiega(argomento, livello)` e `riassumi_conversazione(stile)`;
  2. comando `/prompts` con nome, descrizione e argomenti di ogni prompt;
  3. comando `/prompt nome argomento=valore`: i messaggi ottenuti si aggiungono alla cronologia
     e vanno al grafo;
  4. controllo nell'host rispetto a `prompts/list`: argomenti obbligatori mancanti o sconosciuti
     bloccano la richiesta, senza chiamare il modello.
- Evidenze:
  - `/prompt spiega argomento="Model Context Protocol" livello=base`: risposta adeguata;
  - `riassumi_conversazione` riassume i turni della sessione corrente;
  - log con prompt richiamato, argomenti e messaggi ottenuti dal server.

## Blocco C — Interfaccia e architettura (step 6–9)

Applicazione finale: quattro container (front-end, back-end, agente, PostgreSQL); server MCP
dentro l'agente; LM Studio sull'host. Front-end → HTTP → back-end → HTTP → agente.

### Step 6 · L'agente come servizio HTTP

- Obiettivo: lo stesso grafo risponde sia alla CLI sia alle chiamate HTTP, senza duplicare la
  logica.
- Da realizzare:
  1. separare il modulo dell'agente dall'interfaccia: la CLI diventa un client dell'API;
  2. endpoint che riceve messaggio e cronologia e restituisce risposta e strumenti usati;
  3. endpoint di stato: agente, server MCP e modello raggiungibili;
  4. agente senza stato: cronologia ed eventuale riassunto arrivano dal chiamante e tornano
     aggiornati.
- Evidenze: chiamata HTTP con un tool (risposta e traccia nei log); modello o strumenti non
  disponibili → codice e messaggio comprensibili; test dell'API con il grafo simulato;
  OpenAPI consultabile.
- Evidenza minima: stessa risposta dalla CLI e dall'API.

### Step 7 · Back-end: API e salvataggio delle chat

Unico punto di contatto del front-end; salva in PostgreSQL e inoltra all'agente.

| Operazione | Comportamento atteso |
|------------|----------------------|
| Creare una chat | restituisce l'identificativo della nuova chat |
| Elencare le chat | titolo e data dell'ultimo messaggio |
| Leggere una chat | messaggi in ordine cronologico |
| Inviare un messaggio | salva la domanda, chiama l'agente, salva e restituisce la risposta |
| Eliminare una chat | rimuove la chat e i suoi messaggi |

- Evidenze: OpenAPI generata e consultabile; agente non raggiungibile → errore chiaro e
  documentato; test con l'agente simulato; chat presenti dopo il riavvio.

### Step 8 · Front-end: interfaccia di chat

Tecnologia libera; usabile da chi non conosce il progetto; parla solo con il back-end. Dare a
Claude il documento OpenAPI del back-end come contratto.

- Da realizzare: elenco, creazione ed eliminazione delle chat; vista dei messaggi e invio;
  stato di attesa ed errori comprensibili; indirizzo del back-end da configurazione.
- Evidenze: conversazione completa dal browser con uno strumento; chat ancora presente dopo il
  riavvio; con l'agente spento l'interfaccia mostra l'errore senza bloccarsi.

### Step 9 · Docker Compose: un container per componente

- Da realizzare:
  1. quattro servizi in `compose.yaml`: tre con il proprio Dockerfile, PostgreSQL con
     l'immagine ufficiale;
  2. il browser raggiunge il front-end; le API arrivano al back-end (porta pubblicata o proxy);
     l'agente non è esposto;
  3. volume per i dati di PostgreSQL; credenziali in `.env` escluso da Git; back-end avviato a
     database pronto;
  4. l'agente raggiunge LM Studio con `host.docker.internal`; i server MCP stdio partono nel suo
     container.
- Evidenze: `docker compose up` avvia i quattro servizi e `docker compose ps` li mostra attivi;
  chat dal browser con uno strumento, visibile nei log dell'agente; dopo `down` e `up` le chat
  sono ancora presenti.

## Facoltativo — streaming della risposta

Se la risposta compare solo completa: l'agente emette testo ed eventi degli strumenti man mano;
il back-end inoltra il flusso (per esempio Server-Sent Events) e salva il messaggio completo alla
fine; il front-end mostra il testo mentre arriva e indica l'uso di uno strumento. Decisione da
prendere e documentare: con il revisore attivo, mostrare la bozza mentre viene scritta oppure
solo la risposta approvata.

## Prompt di partenza suggerito dal docente (slide 17)

> Leggi il CLAUDE.md e controlla lo stato della repository. Vogliamo realizzare lo step [numero e
> nome]: [obiettivo e requisiti dello step]. Il progetto attuale funziona fino allo step
> precedente: estendilo senza riscriverlo e non anticipare gli step successivi. Chiariscimi le
> decisioni mancanti e proponi una soluzione semplice. Distingui i test con il modello simulato
> dalle prove reali con LM Studio. Le evidenze richieste devono essere verificabili nei log o nei
> test. Non iniziare l'implementazione prima dell'approvazione della specifica e del piano.
