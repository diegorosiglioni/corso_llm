# Lezione 7, esercizio 1 · Ingestion e ricerca semantica sulle ricette dell'Artusi

Data: 2026-11-17. Traccia: `docs/superpowers/lezione7.md`. Questa specifica copre solo
l'esercizio 1 (pipeline di partenza). Le modifiche A (`has_doses`) e B (titolo nel testo
indicizzato) avranno ciascuna specifica e piano propri, dopo la valutazione di partenza.

## 1. Scopo e perché

Costruire un indice vettoriale ripetibile del libro dell'Artusi e recuperare, per una domanda, i
passaggi pertinenti con la loro fonte (ricetta, capitolo, posizione del chunk). È il laboratorio
della lezione 7, da consegnare con le evidenze richieste. Nella lezione 8 la ricerca diventerà lo
strumento MCP `search_documents` dell'agente: per questo vive in questa repository e non in un
progetto a parte.

Il retrieval resta isolato: nessun modello generativo, nessun cambiamento all'agente.

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Obiettivi**
- Ingestion come script separato, rieseguibile senza duplicati.
- Ricerca top-k con filtro per capitolo applicato durante la ricerca.
- Valutazione riproducibile sulle domande con fonte attesa (situazione di partenza).
- Test che passano con LM Studio e Qdrant spenti.

**Non obiettivi** (in questo ciclo)
- Modifiche A e B dell'esercizio 2; estensioni (confronto di strategie, secondo modello).
- Strumento MCP, agente, back-end, front-end: nulla cambia in `assistant/`, `backend/`,
  `frontend/`.
- Ingestion dentro Docker: si lancia dal computer (decisione dell'utente).
- Prefazione, glossario, introduzioni dei capitoli, appendice e indice del libro: non sono ricette e
  non entrano nell'indice.

**Anti-obiettivi** (sarebbe un fallimento anche se "funziona")
- Una seconda ingestion che aumenta i punti.
- Un risultato di cui non si sa dire ricetta, capitolo e posizione del chunk.
- Documenti e domande trasformati in vettori con modelli diversi senza che il programma se ne
  accorga.
- Un filtro per capitolo che restituisce risultati di altri capitoli, o meno di k quando il
  capitolo ne ha almeno k.
- Un nome di modello scritto nel codice o nella documentazione come valore predefinito.

## 3. Vincoli

- Regole di `CLAUDE.md`: Python sincrono, moduli piccoli, codice e chiavi in inglese, testi e
  messaggi in italiano, configurazione solo da variabili d'ambiente, dipendenze concordate con
  versione fissata, comandi documentati per PowerShell.
- **Il modello di embedding lo sceglie l'utente:** `EMBEDDING_MODEL` è obbligatoria e senza valore
  predefinito; deve comparire in `GET /v1/models` di LM Studio, come il modello di chat.
- Qdrant in Docker Compose, LM Studio sull'host, dati scaricati (`data/`) fuori da Git.
- Campi del payload in inglese (decisione dell'utente).

## 4. Approcci considerati

**Database dei vettori**
1. **Qdrant** — scelto (decisione dell'utente, dopo il confronto). È quello della lezione:
   requisiti e verifiche della slide 25 si applicano senza traduzione; filtro durante la ricerca
   anche con l'indice approssimato; modalità in memoria di `qdrant-client` per i test con il codice
   vero; dashboard per la diagnosi. Costo: quinto servizio Compose e una dipendenza.
2. PostgreSQL con pgvector, nello stesso container delle chat. Scartato dall'utente: si allontana
   dalla lezione; con l'indice HNSW un filtro può restituire meno di k risultati; i test con i
   servizi spenti avrebbero richiesto un archivio finto.

**Dove gira l'ingestion**
1. **Dal computer, con Qdrant in Compose** — scelto (decisione dell'utente). Comandi
   `python -m rag.ingest`, `rag.search`, `rag.evaluate` da PowerShell, Qdrant su `127.0.0.1:6333`.
   Il più rapido da rieseguire e valutare.
2. Anche come servizio Compose con profilo `rag`. Più fedele allo schema della slide 19, ma chiede
   un Dockerfile e una prova in più; rimandato alla lezione 8, quando l'agente nel container dovrà
   raggiungere Qdrant.

**Chiamata al modello di embedding** (scelta mia)
1. **Client `openai`, già tra le dipendenze**, verso `/v1/embeddings` di LM Studio — scelto.
2. `OpenAIEmbeddings` di `langchain-openai`: scartato, per impostazione predefinita suddivide il
   testo in token con `tiktoken` (dipendenza in più) e manda a LM Studio liste di token invece del
   testo.
3. `httpx` diretto: possibile, ma riscrive ciò che il client `openai` già fa (errori, tempi).

**Ripetizione dell'ingestion** (slide 18)
1. **ID stabili e upsert, con rimozione dei punti rimasti** — scelto: è il requisito della slide 25
   («ID stabili») e serve alla modifica B («senza ricreare la collezione»).
2. Ricostruzione completa a ogni esecuzione: disponibile solo come opzione esplicita `--recreate`,
   per cambiare modello.

## 5. Architettura

Nuovo pacchetto `rag/`, indipendente: non importa nulla da `assistant`, `backend`, `frontend`, e
nessuno lo importa (fino alla lezione 8).

| Modulo | Compito |
|---|---|
| `rag/config.py` | `RagConfig` e `load_config(env)`: legge e valida le variabili (§11), elenca tutti i problemi |
| `rag/corpus.py` | Legge e pulisce il file del libro, restituisce le 790 ricette (`Recipe`) |
| `rag/chunking.py` | Divide il testo di una ricetta in chunk (due strategie) |
| `rag/embedder.py` | `Embedder` (protocollo) e `LMStudioEmbedder` su `/v1/embeddings`, a lotti; controllo del modello su `/v1/models` |
| `rag/store.py` | Collezione Qdrant: creazione, controllo di modello e dimensione, upsert, rimozione dei punti rimasti, conteggio, ricerca con filtro |
| `rag/ingest.py` | `python -m rag.ingest [--recreate]`: collega corpus, chunking, embedder e store; stampa i conteggi |
| `rag/search.py` | `search(...)` e `python -m rag.search "domanda" [--chapter NOME] [--k N]` |
| `rag/evaluate.py` | `python -m rag.evaluate [--k N] [--questions FILE]`: tabella della valutazione |
| `rag/data/questions.json` | Domande con fonte attesa (versionato) |

Ogni modulo che parla con un servizio riceve il client dall'esterno (Qdrant, `openai`), così i test
passano un `QdrantClient(":memory:")` e un embedder finto.

## 6. Corpus (`rag/corpus.py`)

File: `CORPUS_FILE`, predefinito `data/Ricettario.txt` (il file Gutenberg n. 59047 già presente in
locale). Lettura in UTF-8, fine riga normalizzati.

**Delimitazione**
- Si tiene solo il testo tra `*** START OF THE PROJECT GUTENBERG EBOOK` e `*** END OF THE PROJECT
  GUTENBERG EBOOK`: intestazione e licenza escono.
- La parte delle ricette va dal primo capitolo («BRODI, GELATINA E SUGHI») alla riga `APPENDICE`
  esclusa; entrambe devono esistere, altrimenti errore.

**Capitoli**
- I 23 capitoli sono un elenco fisso nel codice, nell'ordine del libro, con il titolo in maiuscolo
  com'è nel file e il nome da salvare: Brodi, gelatina e sughi · Minestre in brodo · Minestre
  asciutte e di magro · Principii · Salse · Uova · Paste e pastelle · Ripieni · Fritti · Lesso ·
  Tramessi · Umidi · Rifreddi · Erbaggi e legumi · Piatti di pesce · Arrosti · Pasticceria · Torte e
  dolci al cucchiaio · Siroppi · Conserve · Liquori · Gelati · Cose diverse.
- Perché un elenco e non una regola sulle maiuscole: nel libro ci sono righe maiuscole che non sono
  capitoli («MINESTRE», che ne raggruppa due, «PASTA FROLLA», «RICETTA A», «QUALITÀ E STAGIONE DEI
  PESCI» subito dopo «PIATTI DI PESCE»). Un titolo è riconosciuto quando una riga coincide con
  quello atteso, tra righe vuote, nell'ordine dell'elenco.

**Ricette**
- Un titolo di ricetta è una riga a inizio colonna `N. Titolo`, preceduta da una riga vuota, con `N`
  uguale al numero atteso (il precedente più uno, partendo da 1). Le righe dello stesso formato con
  un numero diverso restano testo: nel libro ce ne sono cinque (un indice dentro «Brodi», rimandi
  nell'appendice).
- Il testo di una ricetta va dalla riga dopo il titolo al titolo successivo (ricetta o capitolo) o
  ad `APPENDICE`. Il titolo non fa parte del testo (sta nel payload; metterlo nel testo è la
  modifica B). Il testo introduttivo di un capitolo, prima della sua prima ricetta, non appartiene a
  nessuna ricetta e non viene indicizzato.
- Ogni `Recipe` ha `number`, `title`, `chapter` (nome da salvare), `text`.

**Pulizia del testo**
- Le righe spezzate a circa 70 caratteri si ricongiungono: le righe di un paragrafo diventano una
  sola, separate da uno spazio. I paragrafi restano separati da una riga vuota.
- Le righe rientrate (dosi come «  Patate grosse e gialle, grammi 400.», versi) restano righe
  distinte, senza il rientro: un elenco di ingredienti resta un elenco (servirà alla modifica A).
- Tolti i trattini bassi del corsivo Gutenberg (`_Pastella per fritti_` → `Pastella per fritti`),
  i caratteri di controllo e gli spazi multipli.

**Controllo** (errore in italiano se fallisce, con il primo problema trovato): 790 ricette numerate
da 1 a 790 senza buchi; 23 capitoli, ciascuno con almeno una ricetta; nessuna ricetta con titolo o
testo vuoto.

## 7. Chunking (`rag/chunking.py`)

Un chunk non attraversa mai due ricette. Parametri: `CHUNK_STRATEGY` (`paragraph` o `window`,
predefinito `paragraph`), `CHUNK_SIZE` (caratteri, predefinito 1200), `CHUNK_OVERLAP` (caratteri,
predefinito 200). I valori predefiniti sono quelli della valutazione del docente (slide 22).

- **`paragraph`**: i paragrafi si aggiungono uno dopo l'altro finché il chunk resta entro
  `CHUNK_SIZE`; un paragrafo più lungo di `CHUNK_SIZE` da solo viene diviso a finestra (come sotto).
- **`window`**: finestre di `CHUNK_SIZE` caratteri sul testo della ricetta, a passo
  `CHUNK_SIZE - CHUNK_OVERLAP`.
- **Overlap**, in entrambe: ogni chunk dopo il primo comincia con la coda del precedente, al più
  `CHUNK_OVERLAP` caratteri, e la coda è compresa nei `CHUNK_SIZE`. Con `paragraph`, se coda e
  paragrafo successivo insieme superano `CHUNK_SIZE`, la coda si accorcia (sempre a uno spazio),
  fino a sparire: il paragrafo intero ha la precedenza sulla ripetizione.
- I tagli cadono su uno spazio: mai una parola spezzata (una parola più lunga di tutto il chunk è
  l'unica eccezione).
- Una ricetta più corta di `CHUNK_SIZE` è un solo chunk, con qualsiasi strategia.
- Ogni chunk ha `chunk_index` (0, 1, … nella ricetta) e `text`.

## 8. Embedding (`rag/embedder.py`)

- `LMStudioEmbedder.embed(texts) -> list[list[float]]` chiama `client.embeddings.create(model=…,
  input=[…])` a lotti di `EMBEDDING_BATCH_SIZE` (predefinito 32), conservando l'ordine. Lo stesso
  metodo serve a chunk e domande: nessun prefisso o trasformazione diversa tra i due.
- All'avvio di ingestion, ricerca e valutazione si controlla che `EMBEDDING_MODEL` compaia in
  `GET /v1/models`; se no, errore che elenca i modelli disponibili.
- Tutti i vettori di una chiamata devono avere la stessa dimensione, altrimenti errore.
- Errori di connessione, tempo scaduto e risposte di errore di LM Studio diventano messaggi in
  italiano con l'indirizzo usato (mai credenziali).

## 9. Qdrant (`rag/store.py`)

**Collezione** `QDRANT_COLLECTION` (predefinita `recipes`), distanza coseno, dimensione dei vettori
presa dal modello (un embedding di prova all'avvio dell'ingestion). Indici sul payload: `chapter`
(keyword), `recipe_number` (integer), `source` (keyword).

**Punto** = un chunk. ID: UUID versione 5 di `source`, `recipe_number`, `chunk_index`: stesso chunk,
stesso ID. Payload:

| Campo | Esempio | A che cosa serve |
|---|---|---|
| `source` | `Ricettario.txt` | Nome del file del corpus (non il percorso: l'ID non deve cambiare se si sposta la cartella) |
| `recipe_number` | `89` | Citare la ricetta; filtrare |
| `title` | `Gnocchi di patate` | Fonte leggibile |
| `chapter` | `Minestre asciutte e di magro` | Fonte leggibile; filtro per capitolo |
| `chunk_index` | `0` | Posizione nella ricetta; chunk adiacenti |
| `text` | testo del chunk | Ciò che la ricerca restituisce |
| `embedding_model` | valore di `EMBEDDING_MODEL` | Modello registrato con ogni punto |

**Modello registrato e cambio bloccato.** Ogni punto porta `embedding_model`. Prima di scrivere,
l'ingestion controlla che la collezione, se esiste, abbia la dimensione dei vettori del modello
attuale e che i suoi punti abbiano lo stesso `embedding_model`; ricerca e valutazione fanno lo
stesso controllo prima di interrogare. Se non coincidono: errore in italiano con i due modelli e
l'istruzione `python -m rag.ingest --recreate`. Perché nel payload e non nei metadati della
collezione: funziona con qualsiasi versione di Qdrant e anche nella modalità in memoria dei test; la
dimensione si legge dalla configurazione della collezione.

**Ripetizione.** Upsert di tutti i punti; poi si cancellano i punti della stessa `source` il cui ID
non è tra quelli appena scritti (chunk spariti perché una ricetta si è accorciata o il chunking è
cambiato). Il numero di punti dopo l'ingestion è quindi sempre il numero di chunk attuali.
`--recreate` cancella la collezione prima di cominciare. Alla fine l'ingestion stampa ricette,
chunk, punti prima, punti dopo e punti rimossi: sono i conteggi da registrare.

**Volume.** In Compose la collezione sta nel volume `qdrant-data`: sopravvive al riavvio.

## 10. Ricerca e valutazione

**Ricerca** (`rag/search.py`)
- `search(query, k=5, chapter=None)`: embedding della domanda così com'è, query a Qdrant con il
  filtro sul campo `chapter` dentro la richiesta (filtro durante la ricerca, non dopo).
- `k` da 1 a `MAX_TOP_K = 20`, costante nel codice: fuori da questo intervallo, errore. Domanda vuota:
  errore.
- `--chapter` accetta il nome di uno dei 23 capitoli senza distinguere maiuscole e minuscole e lo
  converte nel nome salvato; un nome sconosciuto dà errore con l'elenco dei capitoli. Questo previene
  il «filtro senza risultati» della slide 23.
- Collezione assente o vuota: errore che invita a eseguire prima `python -m rag.ingest`.
- Risultato: per ciascun punto posizione, score, `recipe_number`, `title`, `chapter`,
  `chunk_index` e testo. La CLI stampa per ciascuno una riga d'intestazione (`1. 0,777 · ricetta 89
  «Gnocchi di patate» · Minestre asciutte e di magro · chunk 0`) e il testo sotto.

**Valutazione** (`rag/evaluate.py`)
- `--k` predefinito 5, come nella valutazione del docente.
- Legge `rag/data/questions.json`: elenco di `{"question": "…", "expected": [89]}`; `expected`
  vuoto per le domande senza risposta nel libro.
- Contenuto iniziale: le sei domande note della lezione — farina degli gnocchi (89), cappelletti per
  un mangiatore moderato (7), vino del pollo alla cacciatora (208), perché gli gnocchi si sciolgono
  (89), nome del cacciucco sull'Adriatico (455, 456), tiramisù (nessuna) — più **almeno tre domande
  scritte dall'utente** senza copiare le parole del testo (le chiede il piano, con le fonti attese
  decise prima di eseguire).
- Stampa in Markdown un'intestazione con modello, strategia, dimensione, overlap, k e numero di
  punti, poi una tabella: domanda, fonte attesa, posizione del primo chunk di una ricetta attesa
  (o «assente»; «—» se la domanda non ha risposta), score di quel chunk, score migliore. In fondo:
  «Fonte attesa trovata in X casi su Y». A parità di indice e domande la tabella è identica.

## 11. Configurazione

Variabili d'ambiente, impostate in PowerShell come per gli altri comandi; esempi in `.env.example`.

| Variabile | Predefinito | Note |
|---|---|---|
| `LMSTUDIO_BASE_URL` | — (obbligatoria) | La stessa del servizio dell'agente |
| `EMBEDDING_MODEL` | — (obbligatoria) | Scelta dall'utente, presente in `/v1/models` |
| `QDRANT_URL` | `http://127.0.0.1:6333` | |
| `QDRANT_COLLECTION` | `recipes` | |
| `CORPUS_FILE` | `data/Ricettario.txt` | Solo per l'ingestion |
| `CHUNK_STRATEGY` | `paragraph` | `paragraph` o `window` |
| `CHUNK_SIZE` | `1200` | Intero, almeno 100 |
| `CHUNK_OVERLAP` | `200` | Intero, da 0 a metà di `CHUNK_SIZE` |
| `EMBEDDING_BATCH_SIZE` | `32` | Intero, almeno 1 |
| `LOG_LEVEL` | `INFO` | Come nel resto del progetto |

Valori non validi: errore che elenca tutti i problemi, come `assistant/config.py`.

## 12. Docker Compose e dipendenze

- `compose.yaml`: quinto servizio `qdrant`, immagine `qdrant/qdrant` con versione fissata, porta
  `127.0.0.1:6333:6333` (solo da questo computer; anche la dashboard su
  `http://127.0.0.1:6333/dashboard`), volume `qdrant-data:/qdrant/storage`. Parte con
  `docker compose up -d` insieme agli altri; da solo con `docker compose up -d qdrant` (serve
  comunque la password di PostgreSQL nel `.env`, come per ogni comando `docker compose`). Gli altri
  servizi non cambiano e non dipendono da `qdrant`.
- Dipendenza nuova: `qdrant-client`, versione fissata in `requirements.txt` con le indirette
  in `constraints.txt`; versione del client e dell'immagine verificate insieme nel piano (stessa
  versione minore, per evitare l'avviso di incompatibilità del client).

## 13. Test

Con i servizi spenti (`pytest`, nessun marcatore):
- **corpus**: testo sintetico in stile Gutenberg (intestazione, capitoli, ricette, una riga
  `N. …` fuori sequenza, dosi rientrate, corsivi) → ricette, capitoli e testo pulito attesi; errori
  per numerazione con un buco e per capitolo mancante. Un test sul file vero (790 ricette, 23
  capitoli, ricetta 89 e 208 con titolo e capitolo giusti) che viene saltato se `data/Ricettario.txt`
  non c'è.
- **chunking**: una ricetta breve (un chunk) e una lunga (più chunk, ognuno entro `CHUNK_SIZE`,
  overlap presente, nessun testo perso, nessuna parola spezzata), per entrambe le strategie.
- **embedder**: client `openai` con trasporto finto: lotti e ordine, modello assente da
  `/v1/models`, dimensioni diverse, errori di connessione.
- **store e ingestion** con `QdrantClient(":memory:")` ed embedder finto deterministico: due
  ingestion → stesso numero di punti e stessi ID; ricetta accorciata → punti rimasti cancellati;
  modello o dimensione diversi → errore; `--recreate` → collezione nuova.
- **ricerca**: filtro per capitolo → tutti i risultati di quel capitolo, al massimo k; capitolo
  sconosciuto, `k` fuori intervallo, domanda vuota, collezione assente → errori.
- **valutazione**: tabella attesa con risultati noti (posizione, «assente», «—», riepilogo).
- **configurazione**: obbligatorie mancanti, valori non validi, predefiniti.
- **Compose**: `tests/test_docker.py` aggiornato per il servizio `qdrant` (porta solo locale,
  volume).

Prove reali (marcatore `real`, attivate esplicitamente, con LM Studio, `EMBEDDING_MODEL` e Qdrant):
ingestion di poche ricette in una collezione di prova eseguita due volte (stesso numero di punti),
ricerca con filtro, collezione cancellata alla fine.

## 14. Documentazione

- `docs/retrieval.md` (nuovo): conteggi della prima e della seconda ingestion completa, tabella della
  valutazione di partenza con modello e parametri, due query commentate. Le sezioni «dopo A» e
  «dopo B» arriveranno con le modifiche.
- README: sezione sulla ricerca nelle ricette (variabili, avvio di Qdrant, comandi, dashboard,
  diagnosi degli errori tipici della slide 23), solo con comandi verificati.
- `CLAUDE.md`: pacchetto `rag/` e i suoi confini, comandi, Compose con cinque servizi; la regola sul
  RAG non anticipato diventa «ingestion e ricerca della lezione 7 implementate, generazione e
  strumento MCP nella lezione 8».
- `docs/superpowers/requisiti.md`: nuova sezione 19 con i requisiti di questa specifica.
- `.env.example`: le variabili del §11, senza nomi di modello.
- `PROGRESS.md`: stato e prossimo passo.

## 15. Criteri di accettazione

1. Sul file vero: 790 ricette numerate da 1 a 790 senza buchi, 23 capitoli, ciascuna ricetta con
   numero, titolo, capitolo e testo pulito.
2. Strategia, dimensione e overlap si cambiano dalle variabili; test su una ricetta breve e una
   lunga.
3. `EMBEDDING_MODEL` obbligatoria e verificata su `/v1/models`; lo stesso modello per chunk e
   domande; ogni punto registra il modello; un modello diverso blocca ingestion e ricerca finché non
   si usa `--recreate`.
4. Due ingestion complete reali danno lo stesso numero di punti (registrato in
   `docs/retrieval.md`).
5. `python -m rag.search "…" --chapter Fritti --k 3` restituisce al massimo 3 risultati, tutti del
   capitolo Fritti; `--k 21` è rifiutato.
6. Ogni risultato mostra ricetta, titolo, capitolo e `chunk_index`.
7. `python -m rag.evaluate` stampa una tabella identica a parità di indice e domande; la
   valutazione di partenza è in `docs/retrieval.md`, con almeno tre domande dell'utente.
8. `pytest` passa con LM Studio e Qdrant spenti; `data/` e `.env` restano fuori da Git.

## 16. Lasciato al costruttore

- Versioni esatte di `qdrant-client` e dell'immagine `qdrant/qdrant` (verificate nel piano).
- Tempo massimo delle chiamate a LM Studio e a Qdrant, forma dei messaggi di avanzamento
  dell'ingestion, nomi interni di funzioni e classi.
- Algoritmo dell'embedder finto dei test, purché deterministico e tale che testi con parole in comune
  risultino vicini.
