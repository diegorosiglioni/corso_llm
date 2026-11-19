# Lezione 7, modifica A · Chunk con le dosi — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** campo `has_doses` nel payload dei chunk delle ricette, con indice, filtro `--doses` in
ricerca e valutazione, aggiornamento dei punti esistenti senza ricalcolare gli embedding, e
intestazione della valutazione letta dall'indice.

**Architecture:** funzione pura `has_doses(text)` in `rag/doses.py`, usata dall'ingestion e da un
nuovo comando `python -m rag.update_payload` che scorre i punti e scrive solo il payload
(`set_payload` per ID). `rag/store.py` aggiunge l'indice booleano, il filtro sulle dosi, il conteggio
dei punti senza campo e la lettura dei parametri di chunking salvati. `search` ed `evaluate` ricevono
l'opzione `--doses`.

**Tech Stack:** Python 3.13, `qdrant-client` 1.20.0 (`:memory:` nei test), pytest. Nessuna
dipendenza nuova.

**Spec:** `docs/superpowers/specs/2026-11-20-modifica-a-dosi-design.md` (base:
`docs/superpowers/specs/2026-11-17-ingestion-ricette-design.md`).

## Global Constraints

- Branch `dev`, nessun push. Conventional Commits in italiano; prima `git status` e controllo del
  diff, staging selettivo; mai in stage `docs/superpowers/prossimo-prompt.txt`; ultima riga del
  messaggio: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Codice, identificatori, chiavi del payload e commenti in inglese; messaggi, testi del terminale e
  documentazione in italiano.
- Prima il test che fallisce, poi il codice. Test senza LM Studio né Qdrant (`qdrant` in memoria e
  `FakeEmbedder` di `tests/conftest.py`).
- Eseguire solo i test delle parti toccate (`tests/test_rag_*.py` pertinenti); la suite intera una
  volta, nel Task 8.
- Comandi da PowerShell nella radice: `.\.venv\Scripts\python.exe -m pytest …`.
- `rag/` non importa da `assistant`, `backend`, `frontend`. `EMBEDDING_MODEL` senza valore
  predefinito.
- Nuovi campi del payload, esattamente: `has_doses` (bool), `chunk_strategy` (str), `chunk_size`
  (int), `chunk_overlap` (int), in aggiunta ai sette dell'esercizio 1.
- Riga di `rag.update_payload`, esattamente:
  `Punti: {points} · aggiornati: {updated} · con dosi: {with_doses} · senza campo: {missing}`.
- Errore della ricerca con dosi su punti senza campo, esattamente:
  `Alcuni punti non hanno has_doses: eseguire python -m rag.update_payload`.
- Gli embedding esistenti non si ricalcolano per aggiungere `has_doses` (requisito della traccia).

## Review Focus

- Aggiornamento interrotto a metà (alcuni punti con il campo, altri no) → `search --doses` rifiuta
  con il messaggio; `update_payload` rieseguito completa e dà `senza campo: 0` (test nei Task 4 e 5).
- `update_payload` non deve toccare vettori né altri campi del payload (`text`, `embedding_model`)
  (test nel Task 4).
- Collezione dell'esercizio 1, creata senza l'indice `has_doses` → l'indice viene creato da
  ingestion e aggiornamento (test nel Task 2).
- Capitolo senza chunk con dosi, cercato con `--doses` → «Nessun risultato.», non un errore
  (test nel Task 5).
- Una sola riga di dosi in un chunk (elenco tagliato dalla finestra o dall'overlap) → `has_doses`
  falso: serve un paragrafo di almeno due righe (test nel Task 1).

---

### Task 1: regola `has_doses` (`rag/doses.py`)

**Files:**
- Create: `rag/doses.py`, `tests/test_rag_doses.py`

**Interfaces:**
- Produces: `has_doses(text: str) -> bool`.

- [ ] **Step 1: test che falliscono** in `tests/test_rag_doses.py`:
  - `test_list_with_quantities` — `"Patate, grammi 400.\nFarina, grammi 150.\n\nCuocete…"` → `True`;
    anche con `"Uova, N. 3.\nSale, quanto basta."` e con `"Zucchero, gr. 100.\nAcqua, mezzo bicchiere."`.
  - `test_list_with_one_quantity_line_is_enough` — tre righe, una sola con `decilitri 2` → `True`.
  - `test_list_without_units` — `"Mezzo petto di cappone.\nUn fegatino di pollo."` → `False`.
  - `test_verses` — `"Se il maiale volasse\nNon ci saria danar che lo pagasse,"` → `False`.
  - `test_illustration_caption` — `"[Illustrazione: Disco — grammi 10\nnell'illustrazione]"` → `False`.
  - `test_dose_inside_prose` — un paragrafo di una riga con `grammi 300 di farina` → `False`.
  - `test_single_dose_line` — `"Farina, grammi 200."` da sola, o seguita da un paragrafo di prosa
    → `False`.
  - `test_list_in_a_later_paragraph` — prosa, riga vuota, elenco con unità → `True`.
  - `test_unit_is_a_word` — `"Rettore della chiesa.\nAltro verso."` (contiene «etto» dentro
    una parola) → `False`.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_doses.py -q` → FAIL
  (`ModuleNotFoundError: rag.doses`).
- [ ] **Step 3: implementare `has_doses`.** Paragrafi separati da `"\n\n"`; un paragrafo conta se ha
  almeno due righe non vuote, non comincia con `[Illustrazione` e almeno una riga corrisponde a
  un'espressione regolare (senza maiuscole/minuscole, con confini di parola) per: `grammi`, `gr.`,
  `decilitri`, `litro`/`litri`, `chilogrammi`, `N.` seguito da cifre, `quanto basta`,
  `cucchiaio`/`cucchiai`/`cucchiaiata`/`cucchiaiate`, `bicchiere`/`bicchieri`, `etto`/`etti`.
  Docstring con la regola e il rimando alla specifica §3.
- [ ] **Step 4:** stesso comando → PASS. Poi, sul libro vero (se `data/Ricettario.txt` c'è), contare
  i chunk con `has_doses` vero (`load_corpus` + `split_recipe(..., "paragraph", 1200, 200)`) con uno
  script nella cartella temporanea; annotare il numero nel registro (atteso vicino a 400; se è lontano
  più di 20, controllare gli esempi prima di andare avanti).
- [ ] **Step 5: commit** `feat(rag): regola has_doses per i chunk con l'elenco delle dosi`.

---

### Task 2: archivio Qdrant (`rag/store.py`)

**Files:**
- Modify: `rag/store.py`, `tests/test_rag_store.py`

**Interfaces:**
- Produces:
  - `INDEXES` con `"has_doses": models.PayloadSchemaType.BOOL`;
  - `ensure_indexes(client, name: str) -> None` (crea gli indici di `INDEXES` che mancano;
    `ensure_collection` la chiama anche su una collezione esistente);
  - `query(client, name, vector, limit, chapter: str | None, doses: bool = False)`;
  - `count_missing(client, name: str, field: str) -> int` (punti senza `field`, filtro `IsEmpty`);
  - `iter_texts(client, name: str) -> Iterator[tuple[str, str]]` (ID e `text` di ogni punto, a
    pagine di `SCROLL_PAGE`, senza vettori);
  - `set_field(client, name: str, field: str, value, ids: Sequence[str]) -> None` (`set_payload` a
    lotti di `DELETE_BATCH`, `wait=True`, solo quel campo);
  - `stored_chunking(client, name: str) -> tuple[str, int, int] | None` (strategia, dimensione e
    overlap dal payload di un punto; `None` se mancano).
  Tutte dentro `_qdrant_errors`.

- [ ] **Step 1: test che falliscono** in `tests/test_rag_store.py` (gli helper `payload`/`points`
  accettano un `has_doses` facoltativo):
  - `test_indexes_are_added_to_an_existing_collection` — collezione creata e popolata senza
    l'indice `has_doses` (creata a mano con `create_collection`), `ensure_collection` →
    `qdrant.get_collection(name).payload_schema` contiene `has_doses`.
  - `test_query_with_doses_returns_only_true` — 6 punti, 2 con `has_doses` vero → `limit=5,
    doses=True` dà 2 risultati, tutti veri.
  - `test_query_with_doses_and_chapter` — veri in due capitoli → solo quelli del capitolo chiesto.
  - `test_count_missing` — 3 punti, uno con `has_doses` → `count_missing(..., "has_doses") == 2`.
  - `test_iter_texts_past_one_page` — `SCROLL_PAGE + 1` punti (monkeypatch di `SCROLL_PAGE` a 2
    con 3 punti) → tutti gli ID e i testi.
  - `test_set_field_keeps_vector_and_other_fields` — vettore e payload letti con `retrieve` prima e
    dopo `set_field(..., "has_doses", True, [id])` → vettore uguale, payload uguale più il campo.
  - `test_stored_chunking` — punti con i tre campi → `("paragraph", 1200, 200)`; senza → `None`.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_store.py -q` → FAIL.
- [ ] **Step 3: implementare** le funzioni dell'Interfaces block.
- [ ] **Step 4:** stesso comando → PASS (anche i 14 test esistenti).
- [ ] **Step 5: commit** `feat(rag): indice e filtro has_doses nell'archivio Qdrant`.

---

### Task 3: ingestion con i campi nuovi (`rag/ingest.py`)

**Files:**
- Modify: `rag/ingest.py`, `tests/test_rag_ingest.py`

**Interfaces:**
- Consumes: `has_doses` (Task 1); `ensure_collection` con gli indici (Task 2).
- Produces: payload di ogni punto con `has_doses`, `chunk_strategy`, `chunk_size`, `chunk_overlap`
  (dai valori di `config`).

- [ ] **Step 1: test che falliscono:** aggiornare `test_payload_of_a_point` (payload con
  `"has_doses": False, "chunk_strategy": "paragraph", "chunk_size": 1200, "chunk_overlap": 200`);
  nuovo `test_payload_marks_the_dose_list` — una ricetta con testo
  `"Farina, grammi 200.\nUova, N. 2.\n\nImpastate."` → il suo punto ha `has_doses` vero.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_ingest.py -q` → FAIL.
- [ ] **Step 3:** aggiungere i quattro campi al dizionario del payload in `run_ingest`; docstring del
  modulo aggiornata.
- [ ] **Step 4:** stesso comando → PASS.
- [ ] **Step 5: commit** `feat(rag): l'ingestion scrive has_doses e i parametri del chunking`.

---

### Task 4: comando `python -m rag.update_payload`

**Files:**
- Create: `rag/update_payload.py`, `tests/test_rag_update_payload.py`

**Interfaces:**
- Consumes: `has_doses` (Task 1); `connect`, `count_points`, `ensure_indexes`, `iter_texts`,
  `set_field`, `count_missing` (Task 2); `load_config`, `configure_logging`.
- Produces: `@dataclass(frozen=True) UpdateReport(points: int, updated: int, with_doses: int,
  missing: int)`; `run_update(client, collection: str) -> UpdateReport`;
  `format_report(report: UpdateReport) -> str`; `main(argv=None, env=os.environ) -> int`.

- [ ] **Step 1: test che falliscono** in `tests/test_rag_update_payload.py`, su punti scritti con
  `upsert_points` senza `has_doses` (payload dell'esercizio 1):
  - `test_every_point_gets_the_field` — 3 punti, uno col testo di un elenco con unità →
    `UpdateReport(3, 3, 1, 0)`; `count_missing == 0`.
  - `test_vectors_and_other_fields_unchanged` — `retrieve(with_vectors=True)` prima e dopo:
    vettori identici, payload identico più `has_doses`.
  - `test_rerun_gives_the_same_report` — due esecuzioni, stesso `UpdateReport` e stesso numero di
    punti.
  - `test_interrupted_update_then_rerun` — `set_field` reso fallibile alla seconda chiamata con
    monkeypatch (`StoreError`) → poi `run_update` completo → `missing == 0`.
  - `test_creates_the_index` — dopo `run_update`, `payload_schema` contiene `has_doses`.
  - `test_missing_or_empty_collection` — `StoreError` con «rag.ingest».
  - `test_report_line` — `format_report(UpdateReport(1143, 1143, 400, 0))` ==
    `"Punti: 1143 · aggiornati: 1143 · con dosi: 400 · senza campo: 0"`.
  - `test_main_success_and_missing_collection` — `main([], VALID)` con `connect` sostituito dal
    client in memoria (e `close` neutralizzata): 0 e la riga su stdout; collezione assente: 1 e
    messaggio su stderr.
  - `test_main_does_not_call_lm_studio` — `create_embedder` e `check_embedding_model` non sono
    importati dal modulo (`not hasattr(update_payload, "create_embedder")`).
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_update_payload.py -q` → FAIL.
- [ ] **Step 3: implementare.** `run_update`: collezione assente o vuota → `StoreError` col
  messaggio di `check_collection` per la collezione vuota; `ensure_indexes`; raccoglie gli ID per
  valore di `has_doses(text)` da `iter_texts` e chiama `set_field` una volta per valore (a lotti);
  `missing = count_missing(...)`. `main`: `load_config(env)` (stesse variabili degli altri comandi,
  LM Studio non contattato), `connect`, `run_update`, stampa `format_report`; codice 1 con il
  messaggio per `ConfigError`/`StoreError` e se `missing > 0`
  («{missing} punti senza has_doses dopo l'aggiornamento: rieseguire python -m rag.update_payload»).
  Docstring: perché non ricalcola gli embedding.
- [ ] **Step 4:** stesso comando → PASS.
- [ ] **Step 5: commit** `feat(rag): has_doses sui punti esistenti senza ricalcolare gli embedding`.

---

### Task 5: ricerca con `--doses` (`rag/search.py`)

**Files:**
- Modify: `rag/search.py`, `tests/test_rag_search.py`

**Interfaces:**
- Consumes: `query(..., doses=)`, `count_missing` (Task 2).
- Produces: `SearchResult` con un ultimo campo `has_doses: bool = False`;
  `search(client, embedder, collection, model, question, k=5, chapter=None, doses: bool = False)`;
  CLI `--doses`.

- [ ] **Step 1: test che falliscono** (le ricette di `RECIPES` in `test_rag_search.py` ricevono un
  elenco con unità nelle ricette 1, 2 e 6, testo `"…\n\nOlio, grammi 100.\nSale, quanto basta."`):
  - `test_doses_filter_returns_only_dose_chunks` — `run(indexed, doses=True, k=5)` → 3 risultati,
    tutti `has_doses`.
  - `test_doses_with_chapter` — `doses=True, chapter="Lesso"` → solo la ricetta 6.
  - `test_doses_in_a_chapter_without_doses` — capitolo con ricette senza elenco (aggiungere a
    `RECIPES` la ricetta 7 «Arrosto» nel capitolo `Arrosti`, senza elenco) →
    `run(..., doses=True, chapter="Arrosti") == []`.
  - `test_doses_on_points_without_the_field` — punti scritti senza `has_doses` (payload
    dell'esercizio 1) → `StoreError` con il messaggio esatto dei Global Constraints; senza `--doses`
    la stessa ricerca funziona.
  - `test_result_line` aggiornato: un risultato con `has_doses=True` termina con `· chunk 0 · dosi`.
  - `test_main_prints_the_results` con `--doses` aggiunto agli argomenti.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_search.py -q` → FAIL.
- [ ] **Step 3: implementare.** In `search`, dopo `check_collection`: se `doses` e
  `count_missing(..., "has_doses") > 0` → `StoreError` col messaggio; passa `doses` a `query`;
  `has_doses=payload.get("has_doses", False)`. `format_results`: ` · dosi` in fondo
  all'intestazione quando vero. CLI: `--doses` (`store_true`, aiuto «solo i chunk con un elenco di
  ingredienti»).
- [ ] **Step 4:** stesso comando → PASS.
- [ ] **Step 5: commit** `feat(rag): ricerca solo tra i chunk con le dosi (--doses)`.

---

### Task 6: valutazione con `--doses` e intestazione dall'indice (`rag/evaluate.py`)

**Files:**
- Modify: `rag/evaluate.py`, `tests/test_rag_evaluate.py`

**Interfaces:**
- Consumes: `search(..., doses=)` (Task 5); `stored_chunking` (Task 2).
- Produces: CLI `--doses`; intestazione con le chiavi, in quest'ordine: `modello`, `collezione`,
  `punti`, `strategia`, `dimensione`, `overlap`, `k`, `filtro dosi` (`sì`/`no`).

- [ ] **Step 1: test che falliscono:**
  - `test_main_prints_a_reproducible_table` aggiornato: indice costruito con `run_ingest` →
    `- **strategia:** paragraph` (dal payload) e `- **filtro dosi:** no`.
  - `test_header_from_the_index_not_the_session` — ingestion con `CHUNK_STRATEGY=window`, poi
    `main` con le variabili predefinite → `- **strategia:** window`.
  - `test_header_falls_back_to_the_configuration` — punti senza i campi del chunking (scritti con
    `upsert_points` e payload dell'esercizio 1 più `has_doses`) →
    `- **strategia:** paragraph (dalla configurazione)` e lo stesso per dimensione e overlap.
  - `test_main_with_doses` — `--doses` → `- **filtro dosi:** sì` e solo fonti con dosi trovate.
- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_rag_evaluate.py -q` → FAIL.
- [ ] **Step 3: implementare** `--doses` (passato a ogni `search`) e l'intestazione; aggiornare la
  docstring del modulo (non dice più «evaluate with the same variables»).
- [ ] **Step 4:** stesso comando → PASS.
- [ ] **Step 5: commit** `feat(rag): valutazione con --doses e chunking letto dall'indice`.

---

### Task 7: prova reale, aggiornamento della collezione e `docs/retrieval.md`

**Files:**
- Modify: `tests/test_rag_real.py`, `docs/retrieval.md`

**Interfaces:**
- Consumes: tutti i comandi dei Task 3–6.

- [ ] **Step 1: prova reale in più** in `tests/test_rag_real.py`:
  `test_update_payload_then_search_with_doses` — sulla collezione di prova (ricette 85–95): ingestion;
  `has_doses` tolto da tutti i punti con `client.delete_payload` (così la collezione è come quella
  dell'esercizio 1); `run_update` → `missing == 0` e vettore di un punto uguale prima e dopo; `search(..., "Quanta farina per gli gnocchi di patate?", k=5, doses=True)`
  → tutti `has_doses` e la 89 tra i risultati.
- [ ] **Step 2:** con `LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1`, `EMBEDDING_MODEL=text-embedding-bge-m3`
  e Qdrant di Compose attivo: `.\.venv\Scripts\python.exe -m pytest tests/test_rag_real.py -m real -v`
  → 3 passed.
- [ ] **Step 3: collezione `recipes` vera.** Leggere con l'API di Qdrant il vettore di un punto
  (per esempio la ricetta 89, chunk 0); `.\.venv\Scripts\python.exe -m rag.update_payload` due volte:
  annotare le due righe (1143 punti, `senza campo: 0`, stesso numero «con dosi»); rileggere il
  vettore → identico; conteggio dei punti ancora 1143.
- [ ] **Step 4: ricerca.** `rag.search "Quanta farina serve per 400 grammi di patate negli gnocchi?" --doses --chapter "Minestre asciutte e di magro" --k 3`
  → al massimo 3 risultati, tutti `· dosi` e di quel capitolo.
- [ ] **Step 5: valutazione.** `rag.evaluate` e `rag.evaluate --doses`, ciascuna due volte (tabelle
  identiche a coppie). L'intestazione dirà «(dalla configurazione)» per il chunking: i punti
  dell'esercizio 1 non hanno quei campi (spec §5).
- [ ] **Step 6: `docs/retrieval.md`**, sezione «Dopo la modifica A»: regola e numero di chunk con
  dosi sul libro; le due righe di `update_payload` e il controllo del vettore; la query del passo 4;
  le due tabelle; commento domanda per domanda su che cosa cambia col filtro e perché (in particolare
  le domande che non chiedono quantità, come il nome del cacciucco).
- [ ] **Step 7: commit** `test(rag): prova reale e valutazione dopo la modifica A`.

---

### Task 8: documentazione e chiusura

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `docs/superpowers/requisiti.md`, `PROGRESS.md`, `TODO.md`

- [ ] **Step 1: README**, sezione «Ricerca nelle ricette»: campo `has_doses` e regola, comando
  `rag.update_payload` con la riga verificata, `--doses` in ricerca e valutazione con gli esempi del
  Task 7, intestazione letta dall'indice (togliere l'avviso aggiunto dopo la revisione finale
  dell'esercizio 1, sostituirlo con il ripiego «(dalla configurazione)»); in «Diagnosi» il messaggio
  dei punti senza campo; conteggi di `pytest` del passo 4. Solo comandi eseguiti davvero.
- [ ] **Step 2: `CLAUDE.md`** (controllare prima con `git diff CLAUDE.md` che non ci siano modifiche
  dell'utente non salvate; se ci sono, fermarsi e chiedere): `rag.update_payload` e `--doses` nella
  riga dei comandi della ricerca; in «Confini» la modifica A diventa implementata.
- [ ] **Step 3: requisiti** §20 «Lezione 7, esercizio 2 — modifica A: chunk con le dosi
  (2026-11-20)», RF e CA numerati dopo RF-95 e CA-112, dalle verifiche della specifica §6.
  **`TODO.md`**: in «Debiti noti» il libro rinominato che raddoppia i punti (minore della revisione
  dell'esercizio 1).
- [ ] **Step 4: verifica finale.** `.\.venv\Scripts\python.exe -m pytest` → PASS (una volta sola);
  `git status` → nessun file in `data/` né `.env`.
- [ ] **Step 5: `PROGRESS.md`**, «Stato attuale»: fatto, eseguito con esito, non eseguito;
  «Prossimo: modifica B».
- [ ] **Step 6: commit** `docs(rag): modifica A nel README, in CLAUDE.md, nei requisiti e nel diario`.
