# Lezione 7, esercizio 1 · Ingestion e ricerca sulle ricette — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** indice vettoriale ripetibile delle 790 ricette dell'Artusi in Qdrant, con ricerca top-k
filtrabile per capitolo e valutazione riproducibile sulle domande con fonte attesa.

**Architecture:** nuovo pacchetto `rag/`, indipendente da `assistant/`, `backend/`, `frontend/`
(non importa niente da loro, nessuno lo importa). Moduli puri (`corpus`, `chunking`) più moduli
che ricevono i client dall'esterno (`embedder` con il client `openai`, `store` con `QdrantClient`),
collegati da tre comandi: `python -m rag.ingest`, `python -m rag.search`, `python -m rag.evaluate`,
lanciati dal computer. Qdrant è il quinto servizio di Compose.

**Tech Stack:** Python 3.13, `qdrant-client` (nuova, modalità `:memory:` nei test), `openai` 3.37.0
(già presente) verso `/v1/embeddings` di LM Studio, `httpx` per `GET /v1/models`, pytest.

**Spec:** `docs/superpowers/specs/2026-11-17-ingestion-ricette-design.md` (traccia:
`docs/superpowers/lezione7.md`).

## Global Constraints

- Branch `dev`, nessun push. Conventional Commits in italiano, prima `git status` e controllo del
  diff, staging selettivo; ultima riga del messaggio:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- `CLAUDE.md` ha una modifica dell'utente non salvata: non metterla mai in stage insieme ai file
  del piano.
- Codice, identificatori, chiavi del payload e commenti in inglese; messaggi d'errore, testi del
  terminale e documentazione in italiano.
- Prima il test che fallisce, poi il codice. Test senza LM Studio né Qdrant.
- Comandi da PowerShell nella radice: `.\.venv\Scripts\python.exe -m pytest …`.
- `rag/` non importa da `assistant`, `backend`, `frontend`.
- `EMBEDDING_MODEL` obbligatoria, **mai** un nome di modello come valore predefinito nel codice, in
  `.env.example` o nel README.
- Valori fissati dalla specifica: `QDRANT_URL` = `http://127.0.0.1:6333`, `QDRANT_COLLECTION` =
  `recipes`, `CORPUS_FILE` = `data/Ricettario.txt`, `CHUNK_STRATEGY` = `paragraph` (o `window`),
  `CHUNK_SIZE` = 1200 (≥ 100), `CHUNK_OVERLAP` = 200 (da 0 a `CHUNK_SIZE // 2`),
  `EMBEDDING_BATCH_SIZE` = 32 (≥ 1), `MAX_TOP_K` = 20, k predefinito 5, 790 ricette, 23 capitoli.
- Campi del payload, esattamente: `source`, `recipe_number`, `title`, `chapter`, `chunk_index`,
  `text`, `embedding_model`.
- Score stampati con la virgola e tre decimali (`0,777`).

## Review Focus

- `CORPUS_FILE` inesistente o non UTF-8 → messaggio in italiano e codice d'uscita 1, non un
  traceback (test nel Task 7, passo 1).
- LM Studio restituisce meno vettori dei testi inviati, o vettori di dimensioni diverse → errore,
  mai punti con vettori scambiati (test nel Task 5, passo 1).
- Ingestion interrotta a metà (LM Studio cade al secondo lotto) e poi rieseguita → stesso numero di
  punti di un'ingestion completa, nessun duplicato (test nel Task 7, passo 1).
- Capitolo con meno chunk di k («Lesso» ha una sola ricetta) → restituisce quelli che ci sono, senza
  errore (test nel Task 8, passo 1).
- `questions.json` con un numero di ricetta fuori da 1–790 o un campo mancante → errore al
  caricamento, non una riga «assente» ingannevole (test nel Task 9, passo 1).

---

### Task 1: dipendenza `qdrant-client` e servizio `qdrant` in Compose

**Files:**
- Modify: `requirements.txt`, `constraints.txt`, `compose.yaml`
- Test: `tests/test_docker.py`

**Interfaces:**
- Produces: servizio Compose `qdrant` su `127.0.0.1:6333`, volume `qdrant-data`; pacchetto
  `qdrant_client` installato nel venv.

- [ ] **Step 1: scegliere le versioni.** `.\.venv\Scripts\python.exe -m pip index versions qdrant-client`
  (il 2026-11-17 l'ultima era 1.20.0). Verificare che esista l'immagine con la stessa versione:
  `docker manifest inspect qdrant/qdrant:v1.20.0` (o la versione scelta). Se il tag non esiste,
  prendere la versione più alta per cui esistono sia il client sia il tag `vX.Y.Z` con la stessa
  `X.Y`. Annotare le due versioni: valgono per tutto il piano.

- [ ] **Step 2: test che falliscono in `tests/test_docker.py`.** Aggiornare
  `MAIN_SERVICES` a `{"frontend", "backend", "agent", "postgres", "qdrant"}`, il volume atteso in
  `test_compose_up_starts_exactly_the_four_services` (rinominarlo
  `test_compose_up_starts_exactly_the_five_services`) a `{"notes-data", "postgres-data",
  "qdrant-data"}`, e aggiungere:

```python
def test_qdrant_has_a_pinned_image_a_local_port_and_a_volume(compose):
    qdrant = compose["services"]["qdrant"]
    assert qdrant["image"] == "qdrant/qdrant:v1.20.0"  # versione dello Step 1
    (published,) = qdrant["ports"]
    assert (published["host_ip"], published["published"], published["target"]) == (
        "127.0.0.1", "6333", 6333,
    )
    (volume,) = qdrant["volumes"]
    assert (volume["type"], volume["source"], volume["target"]) == (
        "volume", "qdrant-data", "/qdrant/storage",
    )


def test_no_service_depends_on_qdrant(compose):
    for name, service in compose["services"].items():
        assert "qdrant" not in service.get("depends_on", {}), name
```

- [ ] **Step 3: verificare che falliscano.**
  `.\.venv\Scripts\python.exe -m pytest tests/test_docker.py -v` → FAIL sui test nuovi e sul
  conteggio dei servizi.

- [ ] **Step 4: aggiungere il servizio** in `compose.yaml` dopo `postgres`: `image`, `ports`
  `"127.0.0.1:6333:6333"`, `volumes` `qdrant-data:/qdrant/storage`, commento in italiano (ricerca
  nelle ricette della lezione 7, dashboard su `http://127.0.0.1:6333/dashboard`, nessun servizio
  dipende da lui); `qdrant-data: {}` tra i volumi. Aggiornare il commento in testa al file (cinque
  servizi).

- [ ] **Step 5: verificare che passino.** Stesso comando → PASS.

- [ ] **Step 6: dipendenza.** In `requirements.txt` aggiungere, con commento in italiano,
  `qdrant-client==1.20.0` (versione dello Step 1). Installare
  (`.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`), poi
  `.\.venv\Scripts\python.exe -m pip check` → «No broken requirements found». Se `pip` vuole
  cambiare una versione già fissata in `constraints.txt` (per esempio `httpx`, `numpy`,
  `protobuf`), fermarsi e chiedere all'utente. Rigenerare `constraints.txt` con il comando del
  README (sezione Installazione).

- [ ] **Step 7: prova del container.** `docker compose up -d qdrant`, poi
  `curl.exe -s http://127.0.0.1:6333/` → JSON con `"version":"1.20.0"`;
  `.\.venv\Scripts\python.exe -c "from qdrant_client import QdrantClient; print(QdrantClient(url='http://127.0.0.1:6333').get_collections())"`
  → nessun avviso di incompatibilità. Suite intera: `.\.venv\Scripts\python.exe -m pytest` → PASS.

- [ ] **Step 8: commit** di `requirements.txt`, `constraints.txt`, `compose.yaml`,
  `tests/test_docker.py`: `build(rag): qdrant-client e servizio qdrant in Compose`.

---

### Task 2: configurazione (`rag/config.py`)

**Files:**
- Create: `rag/__init__.py` (docstring del pacchetto), `rag/config.py`
- Modify: `.env.example`
- Test: `tests/test_rag_config.py`

**Interfaces:**
- Produces:
  - `class ConfigError(Exception)` — messaggio con tutti i problemi, uno per riga.
  - `@dataclass(frozen=True) class RagConfig` con campi `base_url: str`, `embedding_model: str`,
    `qdrant_url: str = "http://127.0.0.1:6333"`, `collection: str = "recipes"`,
    `corpus_file: str = "data/Ricettario.txt"`, `chunk_strategy: str = "paragraph"`,
    `chunk_size: int = 1200`, `chunk_overlap: int = 200`, `batch_size: int = 32`,
    `log_level: str = "INFO"`.
  - `load_config(env: Mapping[str, str]) -> RagConfig`.
  - `configure_logging(level: str) -> None` (formato come `assistant/config.py`, `httpx`, `openai`,
    `httpx2` e `qdrant_client` a WARNING salvo DEBUG).

- [ ] **Step 1: test che falliscono.**

```python
VALID = {"LMSTUDIO_BASE_URL": "http://127.0.0.1:1234/v1", "EMBEDDING_MODEL": "modello-scelto"}

def test_defaults():
    config = load_config(VALID)
    assert (config.qdrant_url, config.collection, config.corpus_file) == (
        "http://127.0.0.1:6333", "recipes", "data/Ricettario.txt")
    assert (config.chunk_strategy, config.chunk_size, config.chunk_overlap, config.batch_size) == (
        "paragraph", 1200, 200, 32)

def test_required_variables_are_all_listed():
    with pytest.raises(ConfigError) as error:
        load_config({"EMBEDDING_MODEL": "  "})
    assert "LMSTUDIO_BASE_URL" in str(error.value) and "EMBEDDING_MODEL" in str(error.value)

@pytest.mark.parametrize("name, value", [
    ("CHUNK_STRATEGY", "sentence"), ("CHUNK_SIZE", "99"), ("CHUNK_SIZE", "mille"),
    ("CHUNK_OVERLAP", "-1"), ("CHUNK_OVERLAP", "601"), ("EMBEDDING_BATCH_SIZE", "0"),
    ("QDRANT_URL", "127.0.0.1:6333"), ("LMSTUDIO_BASE_URL", "localhost:1234"), ("LOG_LEVEL", "TRACE"),
])
def test_invalid_values(name, value):
    with pytest.raises(ConfigError, match=name):
        load_config({**VALID, name: value})

def test_overlap_limit_follows_the_size():
    assert load_config({**VALID, "CHUNK_SIZE": "400", "CHUNK_OVERLAP": "200"}).chunk_overlap == 200

def test_no_import_from_the_other_packages():
    source = "\n".join(p.read_text(encoding="utf-8") for p in Path("rag").glob("*.py"))
    assert not re.search(r"^\s*(from|import)\s+(assistant|backend|frontend)\b", source, re.M)
```

- [ ] **Step 2: verificare che falliscano.**
  `.\.venv\Scripts\python.exe -m pytest tests/test_rag_config.py -v` → FAIL (modulo assente).

- [ ] **Step 3: implementare `rag/config.py`** sullo stile di `load_config` in
  `assistant/config.py` (valori vuoti o di soli spazi = mancanti, problemi raccolti in una lista).

- [ ] **Step 4: verificare che passino.** Stesso comando → PASS.

- [ ] **Step 5: `.env.example`.** Nuovo blocco commentato «Ricerca nelle ricette (lezione 7,
  `python -m rag.…`)» con le variabili del §11 della specifica; `EMBEDDING_MODEL=` vuota con il
  commento «identificativo restituito da GET /v1/models di LM Studio, scelto dall'utente».

- [ ] **Step 6: commit** `feat(rag): configurazione della pipeline delle ricette`.

---

### Task 3: corpus (`rag/corpus.py`)

**Files:**
- Create: `rag/corpus.py`
- Test: `tests/test_rag_corpus.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Chapter: heading: str; name: str`
  - `CHAPTERS: tuple[Chapter, ...]` — i 23 capitoli del §6 della specifica, nell'ordine del libro
    (`Chapter("BRODI, GELATINA E SUGHI", "Brodi, gelatina e sughi")`, …,
    `Chapter("COSE DIVERSE", "Cose diverse")`).
  - `EXPECTED_RECIPES = 790`
  - `@dataclass(frozen=True) class Recipe: number: int; title: str; chapter: str; text: str`
  - `class CorpusError(Exception)`
  - `parse_corpus(raw: str, chapters: Sequence[Chapter] = CHAPTERS, expected: int = EXPECTED_RECIPES) -> list[Recipe]`
  - `load_corpus(path: str | Path) -> list[Recipe]` — legge in UTF-8 (`utf-8-sig`), file assente o
    non decodificabile → `CorpusError` con il percorso.
  - `clean_text(lines: Sequence[str]) -> str` — pulizia del §6.

- [ ] **Step 1: test che falliscono.** Un testo sintetico `SAMPLE` nel file di test: intestazione
  Gutenberg con `*** START OF THE PROJECT GUTENBERG EBOOK X ***`, una prefazione con la riga
  `1. Non è una ricetta`, capitoli `ZUPPE` e `DOLCI` (con `MINESTRE` maiuscolo non nell'elenco
  prima di `ZUPPE`), tre ricette `1.`, `2.`, `3.`, una riga `7. rimando` dentro la ricetta 2, dosi
  rientrate, un corsivo `_Brodo_`, `APPENDICE`, licenza e `*** END OF …`. Capitoli di prova:
  `TEST_CHAPTERS = (Chapter("ZUPPE", "Zuppe"), Chapter("DOLCI", "Dolci"))`.

```python
def test_recipes_titles_and_chapters():
    recipes = parse_corpus(SAMPLE, TEST_CHAPTERS, expected=3)
    assert [(r.number, r.title, r.chapter) for r in recipes] == [
        (1, "Zuppa di pane", "Zuppe"), (2, "Zuppa lunga", "Zuppe"), (3, "Torta", "Dolci")]

def test_out_of_sequence_line_stays_in_the_text():
    assert "7. rimando" in parse_corpus(SAMPLE, TEST_CHAPTERS, expected=3)[1].text

def test_cleaning_joins_wrapped_lines_and_keeps_doses_as_lines():
    text = parse_corpus(SAMPLE, TEST_CHAPTERS, expected=3)[0].text
    assert "Farina, grammi 150.\nBurro, grammi 50." in text      # dosi: righe distinte, senza rientro
    assert "riga spezzata che continua" in text                  # a capo ricongiunto
    assert "_" not in text and "  " not in text

def test_header_preface_chapter_intro_and_appendix_are_excluded():
    texts = " ".join(r.text for r in parse_corpus(SAMPLE, TEST_CHAPTERS, expected=3))
    for excluded in ("Project Gutenberg", "Non è una ricetta", "Introduzione ai dolci", "Appendice"):
        assert excluded not in texts

@pytest.mark.parametrize("broken, message", [
    (lambda s: s.replace("\n2. Zuppa lunga", "\n4. Zuppa lunga"), "2"),   # buco nella numerazione
    (lambda s: s.replace("\nDOLCI\n", "\nDOLCETTI\n"), "DOLCI"),          # capitolo mancante
    (lambda s: s.replace("APPENDICE", "FINE"), "APPENDICE"),
])
def test_structural_errors(broken, message):
    with pytest.raises(CorpusError, match=message):
        parse_corpus(broken(SAMPLE), TEST_CHAPTERS, expected=3)

def test_missing_file(tmp_path):
    with pytest.raises(CorpusError, match="assente.txt"):
        load_corpus(tmp_path / "assente.txt")

REAL = Path("data/Ricettario.txt")

@pytest.mark.skipif(not REAL.exists(), reason="data/Ricettario.txt non presente")
def test_real_book():
    recipes = load_corpus(REAL)
    assert [r.number for r in recipes] == list(range(1, 791))
    assert len({r.chapter for r in recipes}) == 23
    by_number = {r.number: r for r in recipes}
    assert (by_number[89].title, by_number[89].chapter) == ("Gnocchi di patate", "Minestre asciutte e di magro")
    assert (by_number[208].title, by_number[208].chapter) == ("Pollo alla cacciatora", "Fritti")
    assert "cacciatora" not in by_number[208].text.lower()
    assert by_number[226].chapter == "Lesso"
    assert all(r.title and r.text for r in recipes)
```

- [ ] **Step 2: verificare che falliscano.**
  `.\.venv\Scripts\python.exe -m pytest tests/test_rag_corpus.py -v` → FAIL.

- [ ] **Step 3: implementare `rag/corpus.py`.** Regole del §6 della specifica: delimitazione tra i
  marcatori Gutenberg, parte delle ricette dal primo capitolo dell'elenco alla riga `APPENDICE`;
  capitolo = riga uguale al titolo atteso successivo, tra righe vuote; ricetta = riga
  `^(\d+)\. (.+)$` a inizio colonna, dopo una riga vuota, con il numero atteso; testo fino al titolo
  successivo; il testo tra un capitolo e la sua prima ricetta si scarta. Nel controllo finale,
  l'errore cita il primo numero mancante o il primo capitolo non trovato.

- [ ] **Step 4: verificare che passino.** Stesso comando → PASS (il test sul libro vero non deve
  essere SKIPPED su questo computer).

- [ ] **Step 5: commit** `feat(rag): lettura e pulizia delle ricette dell'Artusi`.

---

### Task 4: chunking (`rag/chunking.py`)

**Files:**
- Create: `rag/chunking.py`
- Test: `tests/test_rag_chunking.py`

**Interfaces:**
- Produces:
  - `STRATEGIES = ("paragraph", "window")`
  - `@dataclass(frozen=True) class Chunk: chunk_index: int; text: str`
  - `split_recipe(text: str, strategy: str, size: int, overlap: int) -> list[Chunk]`

- [ ] **Step 1: test che falliscono.** Testi costruiti nel test: `SHORT` (un paragrafo di 300
  caratteri), `LONG` (otto paragrafi da circa 400 caratteri, parole distinte numerate
  `parola001 parola002 …` per controllare perdite e tagli), `HUGE_PARAGRAPH` (un solo paragrafo di
  3000 caratteri).

```python
@pytest.mark.parametrize("strategy", STRATEGIES)
def test_short_recipe_is_one_chunk(strategy):
    assert split_recipe(SHORT, strategy, 1200, 200) == [Chunk(0, SHORT)]

@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("text", [LONG, HUGE_PARAGRAPH])
def test_long_recipe(strategy, text):
    chunks = split_recipe(text, strategy, 1200, 200)
    assert len(chunks) > 1 and [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert all(len(c.text) <= 1200 for c in chunks)
    words = set(text.split())
    assert all(set(c.text.split()) <= words for c in chunks)               # nessuna parola spezzata
    assert set().union(*(c.text.split() for c in chunks)) == words         # nessun testo perso

def test_window_chunks_overlap():
    chunks = split_recipe(LONG, "window", 1200, 200)
    for previous, current in zip(chunks, chunks[1:]):
        head = current.text.split()[0]
        assert head in previous.text.split()

def test_paragraph_chunks_keep_whole_paragraphs():
    for chunk in split_recipe(LONG, "paragraph", 1200, 200):
        for paragraph in chunk.text.split("\n\n")[1:]:   # il primo pezzo può essere la coda ripetuta
            assert paragraph in LONG.split("\n\n")

def test_paragraph_overlap_shrinks_to_fit_the_next_paragraph():
    first = " ".join(f"uno{i:03d}" for i in range(100))      # 699 caratteri
    second = " ".join(f"due{i:03d}" for i in range(143))     # 1000 caratteri: non resta spazio per la coda
    chunks = split_recipe(first + "\n\n" + second, "paragraph", 1000, 200)
    assert [c.text for c in chunks] == [first, second]

def test_zero_overlap_repeats_nothing():
    chunks = split_recipe(LONG, "window", 1200, 0)
    assert sum(len(c.text.split()) for c in chunks) == len(LONG.split())
```

- [ ] **Step 2: verificare che falliscano.**
  `.\.venv\Scripts\python.exe -m pytest tests/test_rag_chunking.py -v` → FAIL.

- [ ] **Step 3: implementare `split_recipe`** secondo il §7 della specifica: paragrafi separati da
  riga vuota; `paragraph` impacchetta paragrafi interi, un paragrafo oltre `size` va a finestra;
  `window` a passo `size - overlap`; ogni chunk dopo il primo comincia con la coda del precedente
  (≤ `overlap`, tagliata a uno spazio), che in `paragraph` si accorcia fino a sparire se non lascia
  spazio al paragrafo successivo; tagli sempre su uno spazio. Strategia sconosciuta → `ValueError`.

- [ ] **Step 4: verificare che passino.** Stesso comando → PASS.

- [ ] **Step 5: commit** `feat(rag): chunking per paragrafi e a finestra con overlap`.

---

### Task 5: embedder (`rag/embedder.py`) ed embedder finto dei test

**Files:**
- Create: `rag/embedder.py`
- Modify: `tests/conftest.py` (aggiunge `FakeEmbedder` e la fixture `qdrant`)
- Test: `tests/test_rag_embedder.py`

**Interfaces:**
- Produces:
  - `class Embedder(Protocol): def embed(self, texts: Sequence[str]) -> list[list[float]]`
  - `class EmbeddingError(Exception)`
  - `class LMStudioEmbedder` — `__init__(self, client, model: str, batch_size: int)`; `client` è
    un oggetto con `client.embeddings.create(model=..., input=[...])` (in esercizio
    `openai.OpenAI`); `embed(texts)` a lotti, ordine conservato (ordina per `data[i].index`).
  - `create_embedder(config: RagConfig) -> LMStudioEmbedder` — `openai.OpenAI(base_url=config.base_url, api_key="lm-studio", timeout=60.0, max_retries=0)`.
  - `check_embedding_model(base_url: str, model: str, http: httpx.Client | None = None) -> None` —
    `GET {base_url}/models`; modello assente → `EmbeddingError` che elenca gli id disponibili; LM
    Studio spento → `EmbeddingError("LM Studio non raggiungibile su …")`.
  - In `tests/conftest.py`: `class FakeEmbedder` (`DIMENSION = 64`; ogni parola minuscola `\w+`
    incrementa la coordinata `md5(parola) % 64`; vettore normalizzato; testo senza parole →
    vettore unitario sulla coordinata 0; registra in `self.calls: list[list[str]]` i testi di ogni
    chiamata); fixture `qdrant` → `QdrantClient(":memory:")`, chiusa alla fine.

- [ ] **Step 1: test che falliscono.** Un client finto `FakeOpenAI` nel file di test: registra le
  chiamate e restituisce `SimpleNamespace(data=[SimpleNamespace(index=i, embedding=[...]) ...])`,
  oppure solleva l'eccezione indicata (usare `lm_studio_error()` di `conftest.py`).

```python
def test_batches_and_order():
    client = FakeOpenAI(reverse=True)               # restituisce i dati in ordine inverso
    vectors = LMStudioEmbedder(client, "m", batch_size=2).embed(["a", "b", "c"])
    assert client.inputs == [["a", "b"], ["c"]] and client.models == ["m", "m"]
    assert vectors == [vector_of("a"), vector_of("b"), vector_of("c")]

def test_fewer_vectors_than_texts():
    with pytest.raises(EmbeddingError, match="2 testi.*1 vettor"):
        LMStudioEmbedder(FakeOpenAI(drop_last=True), "m", 32).embed(["a", "b"])

def test_vectors_of_different_dimensions():
    with pytest.raises(EmbeddingError, match="dimensione"):
        LMStudioEmbedder(FakeOpenAI(ragged=True), "m", 32).embed(["a", "b"])

def test_connection_error_is_italian():
    with pytest.raises(EmbeddingError, match="LM Studio non raggiungibile"):
        LMStudioEmbedder(FakeOpenAI(error=lm_studio_error()), "m", 32).embed(["a"])

def test_model_must_be_listed():
    http = httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"data": [{"id": "altro"}, {"id": "chat"}]})))
    with pytest.raises(EmbeddingError, match="'scelto'.*altro, chat"):
        check_embedding_model("http://lm.test/v1", "scelto", http)

def test_fake_embedder_is_deterministic_and_close_for_shared_words():
    fake = FakeEmbedder()
    a, b, c = fake.embed(["gnocchi di patate", "patate per gnocchi", "liquore di ciliegie"])
    assert fake.embed(["gnocchi di patate"])[0] == a
    assert dot(a, b) > dot(a, c)
```

- [ ] **Step 2: verificare che falliscano.**
  `.\.venv\Scripts\python.exe -m pytest tests/test_rag_embedder.py -v` → FAIL.

- [ ] **Step 3: implementare `rag/embedder.py`** e le aggiunte a `tests/conftest.py`. Errori di
  `openai` (`APIConnectionError`, `APITimeoutError`, `APIStatusError`) → `EmbeddingError` in
  italiano con l'indirizzo.

- [ ] **Step 4: verificare che passino.** Stesso comando → PASS.

- [ ] **Step 5: commit** `feat(rag): embedding con LM Studio a lotti e controllo del modello`.

---

### Task 6: archivio Qdrant (`rag/store.py`)

**Files:**
- Create: `rag/store.py`
- Test: `tests/test_rag_store.py`

**Interfaces:**
- Consumes: fixture `qdrant`, `FakeEmbedder` (Task 5).
- Produces:
  - `class StoreError(Exception)`
  - `@dataclass(frozen=True) class ChunkPoint: id: str; vector: list[float]; payload: dict`
  - `point_id(source: str, recipe_number: int, chunk_index: int) -> str` — `uuid5(NAMESPACE_URL, f"{source}#{recipe_number}#{chunk_index}")`.
  - `connect(url: str) -> QdrantClient` — chiama `get_collections()`; non raggiungibile →
    `StoreError("Qdrant non raggiungibile su {url}: avviarlo con docker compose up -d qdrant")`.
  - `ensure_collection(client, name: str, dimension: int, model: str) -> None` — crea (coseno,
    indici `chapter` keyword, `recipe_number` integer, `source` keyword) se manca; se c'è, controlla
    dimensione e modello.
  - `check_collection(client, name: str, dimension: int, model: str) -> None` — per la ricerca:
    assente o vuota → `StoreError` che invita a `python -m rag.ingest`; poi stessi controlli.
  - `drop_collection(client, name: str) -> None` (nessun errore se manca).
  - `count_points(client, name: str) -> int` (0 se la collezione manca; conteggio esatto).
  - `upsert_points(client, name: str, points: Sequence[ChunkPoint]) -> None`
  - `remove_stale(client, name: str, source: str, keep: set[str]) -> int` — scorre gli ID della
    `source` e cancella quelli non in `keep`; restituisce quanti.
  - `query(client, name: str, vector: list[float], limit: int, chapter: str | None) -> list[tuple[float, dict]]`
    — `query_points` con `query_filter` su `chapter` (`MatchValue`) dentro la richiesta; restituisce
    `(score, payload)` in ordine.
  - Messaggio di modello diverso, esatto nel contenuto: «La collezione '{name}' contiene embedding
    di '{stored}', la configurazione usa '{model}': per reindicizzare eseguire python -m rag.ingest
    --recreate». Dimensione diversa: stesso invito, con le due dimensioni.

- [ ] **Step 1: test che falliscono.**

```python
def payload(n, i, chapter="Zuppe", model="m"):
    return {"source": "libro.txt", "recipe_number": n, "title": f"R{n}", "chapter": chapter,
            "chunk_index": i, "text": f"testo {n} {i}", "embedding_model": model}

def points(fake, specs, model="m"):
    items = [payload(n, i, c, model) for n, i, c in specs]
    vectors = fake.embed([p["text"] for p in items])
    return [ChunkPoint(point_id("libro.txt", p["recipe_number"], p["chunk_index"]), v, p)
            for p, v in zip(items, vectors)]

def test_point_id_is_stable_and_distinct():
    assert point_id("libro.txt", 89, 0) == point_id("libro.txt", 89, 0) != point_id("libro.txt", 89, 1)

def test_upsert_twice_keeps_the_count(qdrant):
    batch = points(FakeEmbedder(), [(1, 0, "Zuppe"), (1, 1, "Zuppe"), (2, 0, "Dolci")])
    for _ in range(2):
        ensure_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
        upsert_points(qdrant, "c", batch)
    assert count_points(qdrant, "c") == 3

def test_remove_stale_points(qdrant):
    ensure_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
    batch = points(FakeEmbedder(), [(1, 0, "Zuppe"), (1, 1, "Zuppe")])
    upsert_points(qdrant, "c", batch)
    assert remove_stale(qdrant, "c", "libro.txt", {batch[0].id}) == 1
    assert count_points(qdrant, "c") == 1

def test_other_model_is_blocked(qdrant):
    ensure_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
    upsert_points(qdrant, "c", points(FakeEmbedder(), [(1, 0, "Zuppe")]))
    for check in (ensure_collection, check_collection):
        with pytest.raises(StoreError, match="'m'.*'altro'.*--recreate"):
            check(qdrant, "c", FakeEmbedder.DIMENSION, "altro")

def test_other_dimension_is_blocked(qdrant):
    ensure_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
    with pytest.raises(StoreError, match="--recreate"):
        ensure_collection(qdrant, "c", 32, "m")

def test_missing_or_empty_collection_for_search(qdrant):
    with pytest.raises(StoreError, match="rag.ingest"):
        check_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
    ensure_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")
    with pytest.raises(StoreError, match="rag.ingest"):
        check_collection(qdrant, "c", FakeEmbedder.DIMENSION, "m")

def test_query_filters_during_the_search(qdrant):
    fake = FakeEmbedder()
    ensure_collection(qdrant, "c", fake.DIMENSION, "m")
    upsert_points(qdrant, "c", points(fake, [(n, 0, "Zuppe") for n in range(1, 9)] + [(9, 0, "Dolci"), (10, 0, "Dolci")]))
    results = query(qdrant, "c", fake.embed(["testo 1 0"])[0], 2, "Dolci")
    assert len(results) == 2 and {p["chapter"] for _, p in results} == {"Dolci"}
    assert results[0][0] >= results[1][0]

def test_connect_refused():
    with pytest.raises(StoreError, match="docker compose up -d qdrant"):
        connect("http://127.0.0.1:9")
```

- [ ] **Step 2: verificare che falliscano.**
  `.\.venv\Scripts\python.exe -m pytest tests/test_rag_store.py -v` → FAIL.

- [ ] **Step 3: implementare `rag/store.py`.** Modello registrato letto da un punto qualsiasi
  (`scroll`, `limit=1`, solo payload); dimensione da `get_collection(name).config.params.vectors.size`.
  `connect` usa un `timeout` breve (5 s) e intercetta le eccezioni di rete di `qdrant_client`
  (`ResponseHandlingException`, `httpx.HTTPError`).

- [ ] **Step 4: verificare che passino.** Stesso comando → PASS.

- [ ] **Step 5: commit** `feat(rag): collezione Qdrant con ID stabili e modello registrato`.

---

### Task 7: ingestion (`rag/ingest.py`)

**Files:**
- Create: `rag/ingest.py` (nessun `rag/__main__.py`: ogni comando è un modulo)
- Test: `tests/test_rag_ingest.py`

**Interfaces:**
- Consumes: `load_corpus`, `split_recipe`, `Embedder`, `ensure_collection`, `drop_collection`,
  `count_points`, `upsert_points`, `remove_stale`, `point_id`, `ChunkPoint`, `RagConfig`.
- Produces:
  - `@dataclass(frozen=True) class IngestReport: recipes: int; chunks: int; points_before: int; points_after: int; removed: int`
  - `run_ingest(config: RagConfig, recipes: Sequence[Recipe], client, embedder: Embedder, recreate: bool = False) -> IngestReport`
    — dimensione dall'embedding di prova `embedder.embed(["prova"])`; `source` =
    `Path(config.corpus_file).name`; embedding a lotti di `config.batch_size` e upsert lotto per
    lotto; `remove_stale` solo dopo l'ultimo lotto.
  - `format_report(report: IngestReport) -> str` — una riga: «Ricette: 790 · chunk: N · punti
    prima: X · punti dopo: Y · rimossi: Z».
  - `main(argv: Sequence[str] | None = None, env: Mapping[str, str] = os.environ) -> int` —
    opzione `--recreate`; ordine: config → `check_embedding_model` → `connect` → `load_corpus` →
    `run_ingest`; ogni `ConfigError`, `CorpusError`, `EmbeddingError`, `StoreError` → messaggio su
    stderr e 1; successo → report su stdout e 0.

- [ ] **Step 1: test che falliscono.** Ricette di prova costruite nel test (tre ricette, di cui una
  lunga due chunk con `CHUNK_SIZE=100`); `config = load_config({**VALID, "CHUNK_SIZE": "100", "CHUNK_OVERLAP": "20", "EMBEDDING_BATCH_SIZE": "2"})`.

```python
def test_two_runs_same_points(qdrant):
    first = run_ingest(config, RECIPES, qdrant, FakeEmbedder())
    second = run_ingest(config, RECIPES, qdrant, FakeEmbedder())
    assert first.points_after == second.points_after == second.points_before == first.chunks
    assert second.removed == 0

def test_shorter_recipe_removes_its_old_chunks(qdrant):
    run_ingest(config, RECIPES, qdrant, FakeEmbedder())
    shorter = [replace(r, text=r.text[:50]) for r in RECIPES]
    report = run_ingest(config, shorter, qdrant, FakeEmbedder())
    assert report.points_after == report.chunks and report.removed > 0

def test_interrupted_run_then_rerun_has_no_duplicates(qdrant):
    with pytest.raises(EmbeddingError):
        run_ingest(config, RECIPES, qdrant, FailingEmbedder(fail_on_call=3))  # prova + 1 lotto, poi errore
    report = run_ingest(config, RECIPES, qdrant, FakeEmbedder())
    assert report.points_after == report.chunks

def test_payload_of_a_point(qdrant):
    run_ingest(config, RECIPES, qdrant, FakeEmbedder())
    (_, payload), = query(qdrant, "recipes", FakeEmbedder().embed([RECIPES[0].text])[0], 1, None)
    assert set(payload) == {"source", "recipe_number", "title", "chapter", "chunk_index", "text", "embedding_model"}
    assert payload["source"] == "Ricettario.txt" and payload["embedding_model"] == "modello-scelto"

def test_recreate_starts_from_an_empty_collection(qdrant):
    run_ingest(config, RECIPES, qdrant, FakeEmbedder())
    report = run_ingest(replace(config, embedding_model="altro"), RECIPES, qdrant, FakeEmbedder(), recreate=True)
    assert report.points_before == 0

def test_main_missing_corpus_is_a_message(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(ingest, "check_embedding_model", lambda *a, **k: None)
    monkeypatch.setattr(ingest, "connect", lambda url: QdrantClient(":memory:"))
    code = ingest.main([], {**VALID, "CORPUS_FILE": str(tmp_path / "manca.txt")})
    assert code == 1 and "manca.txt" in capsys.readouterr().err

def test_report_line():
    assert format_report(IngestReport(790, 2950, 0, 2950, 0)) == (
        "Ricette: 790 · chunk: 2950 · punti prima: 0 · punti dopo: 2950 · rimossi: 0")
```

  `FailingEmbedder` nel file di test: sottoclasse di `FakeEmbedder` che solleva `EmbeddingError`
  alla chiamata numero `fail_on_call`.

- [ ] **Step 2: verificare che falliscano.**
  `.\.venv\Scripts\python.exe -m pytest tests/test_rag_ingest.py -v` → FAIL.

- [ ] **Step 3: implementare `rag/ingest.py`** con `if __name__ == "__main__": sys.exit(main())`;
  `main` chiama `configure_logging` e registra l'avanzamento ogni lotto a livello INFO.

- [ ] **Step 4: verificare che passino.** Stesso comando → PASS.

- [ ] **Step 5: commit** `feat(rag): ingestion ripetibile delle ricette in Qdrant`.

---

### Task 8: ricerca (`rag/search.py`)

**Files:**
- Create: `rag/search.py`
- Test: `tests/test_rag_search.py`

**Interfaces:**
- Consumes: `CHAPTERS`, `check_collection`, `query`, `Embedder`, `check_embedding_model`,
  `connect`, `run_ingest` (nei test).
- Produces:
  - `MAX_TOP_K = 20`, `DEFAULT_TOP_K = 5`
  - `class SearchError(Exception)`
  - `@dataclass(frozen=True) class SearchResult: rank: int; score: float; recipe_number: int; title: str; chapter: str; chunk_index: int; text: str`
  - `resolve_chapter(name: str) -> str` — confronto senza maiuscole/minuscole con `Chapter.name`
    e `Chapter.heading`; sconosciuto → `SearchError` con l'elenco dei 23 nomi.
  - `search(client, embedder: Embedder, collection: str, model: str, question: str, k: int = DEFAULT_TOP_K, chapter: str | None = None) -> list[SearchResult]`
    — controlla domanda (vuota o di soli spazi → errore) e `k` (1…`MAX_TOP_K`), fa l'embedding
    della domanda così com'è, poi `check_collection` con la dimensione di quel vettore, poi `query`.
  - `format_results(results: Sequence[SearchResult]) -> str` — per ciascuno
    `1. 0,777 · ricetta 89 «Gnocchi di patate» · Minestre asciutte e di magro · chunk 0`, poi il
    testo rientrato di due spazi, riga vuota tra i risultati; nessun risultato → «Nessun
    risultato.».
  - `main(argv=None, env=os.environ) -> int` — `python -m rag.search "domanda" [--chapter NOME] [--k N]`;
    errori come in `ingest.main`.

- [ ] **Step 1: test che falliscono.** Fixture che indicizza con `run_ingest` sei ricette di prova
  (cinque in «Fritti», una in «Lesso»).

```python
def test_chapter_filter_returns_only_that_chapter(indexed):
    results = search(indexed, FakeEmbedder(), "recipes", "modello-scelto", "pollo fritto", k=3, chapter="fritti")
    assert len(results) == 3 and {r.chapter for r in results} == {"Fritti"}
    assert [r.rank for r in results] == [1, 2, 3]

def test_chapter_with_fewer_points_than_k(indexed):
    results = search(indexed, FakeEmbedder(), "recipes", "modello-scelto", "pollo", k=5, chapter="LESSO")
    assert [r.chapter for r in results] == ["Lesso"]

@pytest.mark.parametrize("k", [0, 21])
def test_k_out_of_range(indexed, k):
    with pytest.raises(SearchError, match="20"):
        search(indexed, FakeEmbedder(), "recipes", "modello-scelto", "pollo", k=k)

def test_blank_question(indexed):
    with pytest.raises(SearchError):
        search(indexed, FakeEmbedder(), "recipes", "modello-scelto", "   ")

def test_unknown_chapter_lists_the_chapters():
    with pytest.raises(SearchError, match="Fritti.*Cose diverse"):
        resolve_chapter("Frittate")

def test_result_line():
    line = format_results([SearchResult(1, 0.7771, 89, "Gnocchi di patate", "Minestre asciutte e di magro", 0, "Testo")])
    assert line.splitlines()[:2] == [
        "1. 0,777 · ricetta 89 «Gnocchi di patate» · Minestre asciutte e di magro · chunk 0", "  Testo"]

def test_main_without_ingestion(capsys, monkeypatch):
    monkeypatch.setattr(search_module, "check_embedding_model", lambda *a, **k: None)
    monkeypatch.setattr(search_module, "connect", lambda url: QdrantClient(":memory:"))
    monkeypatch.setattr(search_module, "create_embedder", lambda config: FakeEmbedder())
    assert search_module.main(["pollo"], VALID) == 1
    assert "rag.ingest" in capsys.readouterr().err
```

- [ ] **Step 2: verificare che falliscano.**
  `.\.venv\Scripts\python.exe -m pytest tests/test_rag_search.py -v` → FAIL.

- [ ] **Step 3: implementare `rag/search.py`.**

- [ ] **Step 4: verificare che passino.** Stesso comando → PASS.

- [ ] **Step 5: commit** `feat(rag): ricerca top-k con filtro per capitolo`.

---

### Task 9: valutazione (`rag/evaluate.py`) e domande di prova

**Files:**
- Create: `rag/evaluate.py`, `rag/data/questions.json`
- Test: `tests/test_rag_evaluate.py`

**Interfaces:**
- Consumes: `search`, `SearchResult`, `DEFAULT_TOP_K`, `count_points`.
- Produces:
  - `DEFAULT_QUESTIONS = Path(__file__).parent / "data" / "questions.json"`
  - `@dataclass(frozen=True) class Question: question: str; expected: tuple[int, ...]`
  - `load_questions(path: Path) -> list[Question]` — campi mancanti, domanda vuota, numeri fuori da
    1–790 → `ValueError` con la posizione della domanda nel file.
  - `@dataclass(frozen=True) class Outcome: question: Question; position: int | None; source_score: float | None; best_score: float | None`
  - `evaluate_question(question: Question, results: Sequence[SearchResult]) -> Outcome` — posizione
    e score del primo risultato con `recipe_number` in `expected`.
  - `format_report(header: Mapping[str, str], outcomes: Sequence[Outcome]) -> str` — Markdown:
    righe d'intestazione `- **chiave:** valore` (modello, collezione, punti, strategia,
    dimensione, overlap, k), tabella `| Domanda | Fonte attesa | Posizione | Score fonte | Score migliore |`,
    riga finale «Fonte attesa trovata in X casi su Y.» (Y = domande con `expected` non vuoto).
    Fonte attesa: `89` o `455, 456`, `—` se vuota; Posizione: numero, «assente», «—» se `expected`
    vuoto; score con la virgola e tre decimali, «—» se assente.
  - `main(argv=None, env=os.environ) -> int` — `python -m rag.evaluate [--k N] [--questions FILE]`;
    stessi controlli e stessa gestione degli errori di `search.main` (modello su `/v1/models`,
    `connect`), più `ValueError` di `load_questions` → messaggio e 1; tabella su stdout.
    Strategia, dimensione e overlap nell'intestazione vengono dalla configurazione attuale: il README
    dirà di valutare con le stesse variabili dell'ingestion.

- [ ] **Step 1: test che falliscono.**

```python
def result(n, score, rank):
    return SearchResult(rank, score, n, f"R{n}", "Zuppe", 0, "t")

def test_found_absent_and_no_answer():
    found = evaluate_question(Question("q", (455, 456)), [result(7, 0.8, 1), result(456, 0.75, 2)])
    assert (found.position, found.source_score, found.best_score) == (2, 0.75, 0.8)
    absent = evaluate_question(Question("q", (208,)), [result(7, 0.72, 1)])
    assert (absent.position, absent.source_score, absent.best_score) == (None, None, 0.72)

def test_report():
    outcomes = [evaluate_question(Question("Farina?", (89,)), [result(89, 0.777, 1)]),
                evaluate_question(Question("Vino?", (208,)), [result(7, 0.724, 1)]),
                evaluate_question(Question("Tiramisù?", ()), [result(3, 0.735, 1)])]
    text = format_report({"modello": "m", "k": "5"}, outcomes)
    assert "| Farina? | 89 | 1 | 0,777 | 0,777 |" in text
    assert "| Vino? | 208 | assente | — | 0,724 |" in text
    assert "| Tiramisù? | — | — | — | 0,735 |" in text
    assert text.rstrip().endswith("Fonte attesa trovata in 1 casi su 2.")
    assert format_report({"modello": "m", "k": "5"}, outcomes) == text      # riproducibile

@pytest.mark.parametrize("content", [
    '[{"question": "q"}]', '[{"question": "", "expected": []}]', '[{"question": "q", "expected": [791]}]',
])
def test_invalid_questions(tmp_path, content):
    path = tmp_path / "q.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="1"):
        load_questions(path)

def test_shipped_questions_are_valid():
    questions = load_questions(DEFAULT_QUESTIONS)
    assert len(questions) >= 9 and sum(not q.expected for q in questions) >= 1
```

- [ ] **Step 2: verificare che falliscano.**
  `.\.venv\Scripts\python.exe -m pytest tests/test_rag_evaluate.py -v` → FAIL.

- [ ] **Step 3: chiedere all'utente le sue domande — FERMARSI QUI.** Servono almeno tre domande
  scritte dall'utente, senza copiare le parole del libro, ciascuna con la ricetta o le ricette in
  cui si aspetta la risposta (o «nessuna»), decise **prima** di eseguire la ricerca. Non
  inventarle.

- [ ] **Step 4: scrivere `rag/data/questions.json`** con le sei domande della specifica (§10) più
  quelle dell'utente:
  - «Quanta farina serve per 400 grammi di patate negli gnocchi?» → `[89]`
  - «Quanti cappelletti bastano a un mangiatore moderato?» → `[7]`
  - «Che vino si usa per il pollo alla cacciatora?» → `[208]`
  - «Perché gli gnocchi possono sciogliersi nell'acqua?» → `[89]`
  - «Come si chiama il cacciucco sulle coste dell'Adriatico?» → `[455, 456]`
  - «Qual è la ricetta del tiramisù?» → `[]`

- [ ] **Step 5: implementare `rag/evaluate.py`.**

- [ ] **Step 6: verificare che passino.** Stesso comando → PASS. Poi la suite intera:
  `.\.venv\Scripts\python.exe -m pytest` → PASS.

- [ ] **Step 7: commit** `feat(rag): valutazione con domande a fonte attesa`.

---

### Task 10: prove reali, ingestion completa e `docs/retrieval.md`

**Files:**
- Create: `tests/test_rag_real.py`, `docs/retrieval.md`

**Interfaces:**
- Consumes: tutti i comandi dei Task 7–9.

- [ ] **Step 1: prova reale automatica** in `tests/test_rag_real.py`, con
  `pytestmark = pytest.mark.real`, saltata se mancano `LMSTUDIO_BASE_URL` o `EMBEDDING_MODEL` o se
  il libro non c'è: indicizza le ricette 85–95 del libro vero, con `QDRANT_URL` reale, in una
  collezione `recipes_test_<uuid4 breve>`, due volte (stesso numero di punti), poi
  `search(..., "Quanta farina per gli gnocchi di patate?", k=5)` ha la ricetta 89 tra i risultati e
  `search(..., chapter="Minestre asciutte e di magro")` restituisce solo quel capitolo;
  `drop_collection` in un `finally`.

- [ ] **Step 2: chiedere all'utente** di avviare LM Studio con il modello di embedding che ha
  scelto e di indicarne l'identificativo (deve comparire in `GET /v1/models`); avviare Qdrant con
  `docker compose up -d qdrant`. Impostare in PowerShell `LMSTUDIO_BASE_URL` ed `EMBEDDING_MODEL`.

- [ ] **Step 3: eseguire la prova reale.**
  `.\.venv\Scripts\python.exe -m pytest tests/test_rag_real.py -m real -v` → PASS. Se fallisce,
  usare superpowers:systematic-debugging prima di cambiare codice.

- [ ] **Step 4: ingestion completa due volte.** `.\.venv\Scripts\python.exe -m rag.ingest` due
  volte di seguito; annotare le due righe di riepilogo (stessi punti dopo; seconda esecuzione con
  «rimossi: 0» e «punti prima» uguale a «punti dopo»). Controllare un punto nella dashboard
  (`http://127.0.0.1:6333/dashboard`). Riavviare Qdrant (`docker compose restart qdrant`) e
  verificare che il conteggio resti lo stesso (volume).

- [ ] **Step 5: valutazione di partenza.** `.\.venv\Scripts\python.exe -m rag.evaluate` due volte:
  le due tabelle devono essere identiche.

- [ ] **Step 6: due query commentate.**
  `.\.venv\Scripts\python.exe -m rag.search "Che vino si usa per il pollo alla cacciatora?" --chapter Fritti --k 5`
  e una seconda scelta con l'utente; per ciascuna, leggere i risultati e annotare se il passaggio
  risponde e perché (per la 208: la parola «cacciatora» è solo nel titolo, motivo della modifica B).

- [ ] **Step 7: scrivere `docs/retrieval.md`**: modello e parametri usati; le due righe di
  riepilogo dell'ingestion; la tabella di partenza com'è stata stampata; le due query con
  risultati e commento; sezioni «Dopo la modifica A» e «Dopo la modifica B» con «da fare».

- [ ] **Step 8: commit** di `tests/test_rag_real.py` e `docs/retrieval.md`:
  `test(rag): prova reale e valutazione di partenza del retrieval`.

---

### Task 11: documentazione e chiusura

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `docs/superpowers/requisiti.md`, `PROGRESS.md`

- [ ] **Step 1: README.** Nuova sezione «Ricerca nelle ricette (lezione 7)» prima di «Docker»:
  libro in `data/Ricettario.txt` (scaricabile da `https://www.gutenberg.org/ebooks/59047.txt.utf-8`,
  escluso da Git), variabili, `docker compose up -d qdrant`, i tre comandi con i loro esempi
  verificati nel Task 10, dashboard, `--recreate` per cambiare modello. In «Diagnosi» gli errori
  tipici della slide 23 con il messaggio che il programma stampa. In «Docker» i servizi diventano
  cinque. In «Test automatici» il comando della prova reale del Task 10 e i conteggi aggiornati di
  `pytest`. Solo comandi eseguiti davvero.

- [ ] **Step 2: `CLAUDE.md`.** Prima chiedere all'utente se la sua modifica in sospeso va salvata
  in un commit a parte. Poi: pacchetto `rag/` e i suoi confini in «Struttura e comandi»; comandi
  `rag.ingest`, `rag.search`, `rag.evaluate` e la prova reale; Compose con cinque servizi
  (`qdrant` su `127.0.0.1:6333`); in «Obiettivo» la riga della lezione 7; in «Confini» il RAG
  diventa «ingestion e ricerca della lezione 7 implementate; generazione, strumento MCP e
  modifiche A e B ciascuna col proprio ciclo».

- [ ] **Step 3: `docs/superpowers/requisiti.md`.** Sezione «19. Lezione 7, esercizio 1 — ingestion e
  ricerca sulle ricette (2026-11-17)» con i requisiti e gli 8 criteri di accettazione della
  specifica (§15), rimandando alla specifica per i dettagli.

- [ ] **Step 4: `PROGRESS.md`.** Voce in «Stato attuale»: fatto, eseguito con esito (test,
  prova reale, due ingestion con i conteggi, valutazione), non eseguito; «Prossimo: modifica A
  (`has_doses`), poi B».

- [ ] **Step 5: verifica finale.** `.\.venv\Scripts\python.exe -m pytest` → PASS;
  `git status` → nessun file in `data/` né `.env` tra quelli da aggiungere.

- [ ] **Step 6: commit** dei quattro file (senza la modifica dell'utente a `CLAUDE.md`, se ha
  scelto di tenerla separata): `docs(rag): ricerca nelle ricette nel README, in CLAUDE.md e nei requisiti`.
