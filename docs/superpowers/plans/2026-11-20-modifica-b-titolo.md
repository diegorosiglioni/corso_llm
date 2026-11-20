# Lezione 7, modifica B · Titolo e capitolo nel testo indicizzato — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ogni chunk viene trasformato in vettore preceduto da titolo e capitolo della ricetta
(`CHUNK_HEADER`, predefinito `title_chapter`), mentre payload e ricerca tengono il testo originale;
la collezione `recipes` viene ricalcolata senza ricrearla e valutata prima e dopo.

**Architecture:** funzione pura `indexed_text(...)` in `rag/chunking.py`; `rag/ingest.py` la usa
per i testi passati all'embedder e scrive `chunk_header` nel payload; `rag/store.py` legge il campo
da un punto e `rag/evaluate.py` lo mostra nell'intestazione. Chunking, ID, `text`, `has_doses`,
ricerca e `rag.update_payload` invariati.

**Tech Stack:** Python 3.13, `qdrant-client` 1.20.0 (`:memory:` nei test), pytest. Nessuna
dipendenza nuova.

**Spec:** `docs/superpowers/specs/2026-11-20-modifica-b-titolo-design.md` (base: specifiche
dell'esercizio 1, `2026-11-17-ingestion-ricette-design.md`, e della modifica A,
`2026-11-20-modifica-a-dosi-design.md`).

## Global Constraints

- Branch `dev`, nessun push. Conventional Commits in italiano; prima `git status` e controllo del
  diff, staging selettivo; mai in stage `docs/superpowers/prossimo-prompt.txt`; ultima riga del
  messaggio: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Codice, identificatori, chiavi del payload e commenti in inglese; messaggi, testi del terminale e
  documentazione in italiano.
- Prima il test che fallisce, poi il codice. Test senza LM Studio né Qdrant (`qdrant` in memoria e
  `FakeEmbedder` di `tests/conftest.py`, che registra i testi in `calls`).
- Eseguire solo i file di test delle parti toccate; la suite intera (`pytest`) **solo dopo averlo
  chiesto all'utente** (preferenza registrata), nel Task 5.
- Comandi da PowerShell nella radice: `.\.venv\Scripts\python.exe -m pytest …`.
- `rag/` non importa da `assistant`, `backend`, `frontend`.
- Variabile `CHUNK_HEADER`, valori esattamente `title_chapter` (predefinito) e `none`.
- Testo indicizzato con `title_chapter`, esattamente: `f"{title} (capitolo {chapter})\n\n{text}"`;
  con `none`: `text`.
- Campo nuovo del payload, esattamente: `chunk_header` (str, il valore di `CHUNK_HEADER`). `text`
  resta il testo originale del chunk; `has_doses` si calcola su `text`.
- Riga nuova dell'intestazione della valutazione, dopo `overlap`, chiave esattamente
  `intestazione dei chunk`; se il campo manca, valore esattamente
  `none (indice precedente alla modifica B)`.
- La domanda viene trasformata in vettore senza intestazione.

## Review Focus

- `CHUNK_HEADER` cambiato su una collezione esistente → stessi ID, stesso numero di punti,
  `rimossi: 0`, `chunk_header` aggiornato su tutti i punti, `text` invariato (test nel Task 2).
- Ricetta divisa in più chunk → l'intestazione precede **ogni** chunk, non solo il primo (test nel
  Task 2).
- Risultati della ricerca dopo B → testo senza l'intestazione (test nel Task 2).
- Domanda cercata dopo B → all'embedder arriva la domanda così com'è (test nel Task 2).
- Indice della modifica A (con `chunk_strategy`… ma senza `chunk_header`) → strategia, dimensione e
  overlap dal payload, intestazione `none (indice precedente alla modifica B)` (test nel Task 3).

---

### Task 1: configurazione e testo indicizzato

**Files:**
- Modify: `rag/config.py`, `rag/chunking.py`, `.env.example`
- Test: `tests/test_rag_config.py`, `tests/test_rag_chunking.py`

**Interfaces:**
- Produces: `rag.config.CHUNK_HEADERS = ("title_chapter", "none")`; campo
  `RagConfig.chunk_header: str = "title_chapter"` (dopo `chunk_overlap`);
  `rag.chunking.indexed_text(title: str, chapter: str, text: str, header: str) -> str`.

- [ ] **Step 1: test che falliscono.**
  - `tests/test_rag_config.py`: in `test_defaults` anche `config.chunk_header == "title_chapter"`;
    `test_chunk_header_values` — `" None "` → `"none"`, `"TITLE_CHAPTER"` → `"title_chapter"`;
    aggiungere `("CHUNK_HEADER", "titolo")` ai parametri di `test_invalid_values`, e un test che il
    messaggio contenga `CHUNK_HEADER deve essere uno tra title_chapter, none, ricevuto 'titolo'.`
  - `tests/test_rag_chunking.py`: `test_indexed_text_with_title_and_chapter` —
    `indexed_text("Pollo alla cacciatora", "Fritti", "Prendete un pollo.", "title_chapter") ==
    "Pollo alla cacciatora (capitolo Fritti)\n\nPrendete un pollo."`;
    `test_indexed_text_without_header` — con `"none"` restituisce `"Prendete un pollo."`;
    `test_indexed_text_unknown_header` — `"altro"` → `ValueError`.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_config.py tests/test_rag_chunking.py` → FAIL (nomi assenti).
- [ ] **Step 3: codice.** In `load_config` lettura come `CHUNK_STRATEGY` (`.lower()`, valore
  vuoto → predefinito, errore aggiunto a `problems`). `indexed_text` accanto a `split_recipe`, con
  `ValueError` come per la strategia sconosciuta. Docstring del modulo: una riga sul testo
  indicizzato. `.env.example`, nel blocco del chunking:
  `# Titolo e capitolo prima di ogni chunk nel testo indicizzato: title_chapter o none (default):`
  e `# CHUNK_HEADER=title_chapter`.
- [ ] **Step 4:** stesso comando → PASS.
- [ ] **Step 5: commit** `feat(rag): CHUNK_HEADER e testo indicizzato con titolo e capitolo`.

### Task 2: ingestion con l'intestazione nel vettore

**Files:**
- Modify: `rag/ingest.py`
- Test: `tests/test_rag_ingest.py`

**Interfaces:**
- Consumes: `indexed_text`, `RagConfig.chunk_header` (Task 1).
- Produces: payload con `chunk_header`; vettori calcolati da `indexed_text(title, chapter, text,
  chunk_header)`.

- [ ] **Step 1: test che falliscono** in `tests/test_rag_ingest.py` (con `config` e `RECIPES` del
  file; la ricetta 2 ha due chunk):
  - `test_payload_of_a_point`: il dizionario atteso ha in più `"chunk_header": "title_chapter"`.
  - `test_embedder_receives_title_and_chapter` — dopo `run_ingest`, i testi di
    `embedder.calls[1:]` (appiattiti) sono, in ordine, `"Brodo (capitolo Brodi, gelatina e
    sughi)\n\nBrodo di carne con sedano e carota."`, poi due testi che cominciano con
    `"Minestra lunga (capitolo Minestre in brodo)\n\n"` (uno per chunk), poi quello della Torta.
  - `test_without_header_the_embedder_receives_the_text` — con
    `replace(config, chunk_header="none")` i testi passati sono i `text` dei chunk e il payload ha
    `chunk_header == "none"`.
  - `test_switching_header_rewrites_the_same_points` — `run_ingest` con `none`, poi con
    `title_chapter`: secondo report con `points_before == points_after == chunks` e `removed == 0`;
    con `qdrant.scroll(..., with_vectors=True)` stessi ID prima e dopo, vettori diversi, `text` e
    `has_doses` identici, `chunk_header == "title_chapter"` su tutti i punti.
  - `test_search_returns_the_original_text_and_embeds_the_question_as_is` — dopo `run_ingest`,
    `rag.search.search(qdrant, embedder, "recipes", "modello-scelto", "brodo di carne", k=1)`:
    `results[0].text == "Brodo di carne con sedano e carota."` ed `embedder.calls[-1] ==
    ["brodo di carne"]`.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_ingest.py` → FAIL.
- [ ] **Step 3: codice.** In `run_ingest` il payload riceve `"chunk_header": config.chunk_header`;
  il lotto passa all'embedder `indexed_text(p["title"], p["chapter"], p["text"], p["chunk_header"])`
  al posto di `p["text"]`. Docstring del modulo: il vettore contiene titolo e capitolo secondo
  `CHUNK_HEADER`, il payload il testo originale; cambiare `CHUNK_HEADER` e rieseguire riscrive tutti
  i punti con gli stessi ID.
- [ ] **Step 4:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_ingest.py tests/test_rag_search.py tests/test_rag_update_payload.py` → PASS.
- [ ] **Step 5: commit** `feat(rag): titolo e capitolo nel testo passato all'embedder`.

### Task 3: intestazione dei chunk nella valutazione

**Files:**
- Modify: `rag/store.py`, `rag/evaluate.py`
- Test: `tests/test_rag_store.py`, `tests/test_rag_evaluate.py`

**Interfaces:**
- Consumes: payload con `chunk_header` (Task 2).
- Produces: `rag.store.stored_header(client: QdrantClient, name: str) -> str | None` (valore di
  `chunk_header` di un punto; `None` se non ci sono punti o il campo manca).

- [ ] **Step 1: test che falliscono.**
  - `tests/test_rag_store.py`: `test_stored_header` sullo schema di `test_stored_chunking` —
    nessun punto → `None`; punto senza campo → `None`; punto con `chunk_header="none"` → `"none"`.
  - `tests/test_rag_evaluate.py`: in `test_main_prints_a_reproducible_table` le prime **9** righe,
    con `"- **intestazione dei chunk:** title_chapter"` dopo l'overlap e prima di `k`;
    in `test_header_falls_back_to_the_configuration` anche
    `"- **intestazione dei chunk:** none (indice precedente alla modifica B)\n"`;
    `test_header_of_an_index_after_modification_a` — punto con `chunk_strategy="window"`,
    `chunk_size=300`, `chunk_overlap=50` e senza `chunk_header` (via `upsert_points`, come nel
    test del ripiego): strategia, dimensione e overlap senza «(dalla configurazione)», intestazione
    `none (indice precedente alla modifica B)`.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_store.py tests/test_rag_evaluate.py` → FAIL.
- [ ] **Step 3: codice.** `stored_header` accanto a `stored_chunking`, con `_qdrant_errors`.
  In `evaluate.main` la lettura dentro lo stesso `try` di `stored_chunking`; costante
  `BEFORE_MODIFICATION_B = "none (indice precedente alla modifica B)"`. Docstring del modulo: una
  riga sull'intestazione dei chunk.
- [ ] **Step 4:** stesso comando → PASS.
- [ ] **Step 5: commit** `feat(rag): intestazione dei chunk letta dall'indice nella valutazione`.

### Task 4: prova reale, ingestion sulla collezione e `docs/retrieval.md`

Servono LM Studio con `text-embedding-bge-m3`, `docker compose up -d qdrant`,
`$env:LMSTUDIO_BASE_URL` ed `$env:EMBEDDING_MODEL = "text-embedding-bge-m3"`; `CHUNK_*` non
impostate (valori predefiniti, come la collezione). Se un servizio manca, fermarsi e dirlo.

**Files:**
- Modify: `tests/test_rag_real.py`, `docs/retrieval.md`

- [ ] **Step 1: prova reale nuova** `test_switching_header_on_the_server` in `tests/test_rag_real.py`
  (fixture `setup`): `run_ingest` con `replace(config, chunk_header="none")`, poi con
  `"title_chapter"`; secondo report `removed == 0` e `points_after == points_before`; il vettore di
  `point_id(Path(config.corpus_file).name, 89, 0)` cambia, il suo payload `text` no; la ricerca
  «Quanta farina per gli gnocchi di patate?» con k=5 contiene la 89 e nessun `text` comincia con
  «Gnocchi di patate (capitolo».
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_real.py -m real -v` → 4 passed.
- [ ] **Step 3: prima dell'ingestion**, con un comando Python (qdrant-client, `retrieve` con
  `with_vectors=True`) leggere ID `994780fa-2348-5cff-9e9f-34d1df17568d` (ricetta 89, chunk 0):
  SHA-256 del vettore (atteso `34be37c0…`, come dopo A) e `text`. Annotare entrambi.
- [ ] **Step 4: ingestion** `.\.venv\Scripts\python.exe -m rag.ingest` (senza `--recreate`) → atteso
  `Ricette: 790 · chunk: 1143 · punti prima: 1143 · punti dopo: 1143 · rimossi: 0`; annotare la
  durata. Rileggere il punto del passo 3: SHA-256 diverso, `text` identico, `chunk_header` =
  `title_chapter`. `.\.venv\Scripts\python.exe -m rag.update_payload` → `Punti: 1143 · aggiornati:
  1143 · con dosi: 398 · senza campo: 0`.
- [ ] **Step 5: valutazione.** `rag.evaluate` due volte e `rag.evaluate --doses` due volte: tabelle
  identiche a coppie, intestazione con `intestazione dei chunk: title_chapter` e strategia,
  dimensione e overlap senza «(dalla configurazione)».
- [ ] **Step 6: query.** `rag.search "Che vino si usa per il pollo alla cacciatora?" --chapter Fritti
  --k 5`, la stessa senza `--chapter`, e `rag.search "Qual è la ricetta del tiramisù?" --k 5`.
- [ ] **Step 7: `docs/retrieval.md`**, sezione «Dopo la modifica B» (al posto di «Da fare»), solo
  con valori ottenuti nei passi 2–6: formato dell'intestazione e `CHUNK_HEADER`; ingestion (riga,
  durata, SHA-256 prima e dopo, `text` identico, `con dosi: 398`); intestazione e tabelle di
  valutazione senza e con filtro; confronto domanda per domanda con «Dopo la modifica A» (posizioni
  e score, in particolare 208, 119/120, 7 e 89 «perché si sciolgono»); le due query rieseguite
  confrontate con «Due query commentate» (posizione della 208, score del tiramisù, se la regola
  «nessuna soglia fissa» regge ancora); sintesi in poche righe. Nel commento alla query 1, rimando
  a «Dopo la modifica B».
- [ ] **Step 8: commit** `docs(rag): valutazione dopo la modifica B in docs/retrieval.md`
  (con `tests/test_rag_real.py`; se si preferisce, il test in un commit `test(rag): …` a parte).

### Task 5: documentazione e chiusura

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `docs/superpowers/requisiti.md`, `PROGRESS.md`

- [ ] **Step 1: README**, sezione «Ricerca nelle ricette»: riga di `CHUNK_HEADER` nella tabella
  delle variabili (dopo `CHUNK_OVERLAP`); un paragrafo su titolo e capitolo nel vettore, `text`
  originale, e su come passare all'intestazione una collezione esistente (rieseguire `rag.ingest`,
  stessi punti, circa la durata del Task 4); la riga nuova dell'intestazione della valutazione;
  rimando a «Dopo la modifica B». Solo comandi eseguiti davvero.
- [ ] **Step 2: `CLAUDE.md`** (prima `git diff CLAUDE.md`: se ci sono modifiche dell'utente non
  salvate, fermarsi e chiedere): in «Obiettivo» una voce «(lezione 7, modifica B) titolo e capitolo
  prima di ogni chunk nel testo indicizzato (`CHUNK_HEADER`), testo originale nel payload e nei
  risultati»; in «Confini» la modifica B diventa implementata (restano generazione e strumento MCP
  della ricerca).
- [ ] **Step 3: requisiti** §21 «Lezione 7, esercizio 2 — modifica B: titolo e capitolo nel testo
  indicizzato (2026-11-20)», sullo schema della §20: RF da RF-100, CA da CA-119, dalle verifiche
  della specifica §6, con gli esiti.
- [ ] **Step 4: verifica finale.** Test toccati:
  `.\.venv\Scripts\python.exe -m pytest tests/test_rag_*.py tests/test_docker.py` → PASS. Chiedere
  all'utente se lanciare la suite intera (serve per i conteggi del README e per il criterio
  «`pytest` passa con i servizi spenti»); se no, dichiararlo nei requisiti e in `PROGRESS.md`.
  `git status` → nessun file in `data/` né `.env`.
- [ ] **Step 5: `PROGRESS.md`**, «Stato attuale»: voce della modifica B (specifica, piano, commit,
  eseguito con esito, non eseguito); «Prossimo» aggiornato (esercizio 2 completo; restano le due
  domande dell'utente e i punti di `REVIEW.md`).
- [ ] **Step 6: commit** `docs(rag): modifica B nel README, in CLAUDE.md, nei requisiti e nel diario`.
