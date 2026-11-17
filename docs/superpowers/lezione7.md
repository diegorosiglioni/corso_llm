# Lezione 7 — Dai documenti alla ricerca semantica: introduzione al RAG e ingestion (traccia del docente)

Data: 2026-11-17
Stato: **trascrizione della traccia.** Riassume fedelmente le 30 slide di `LLM_Lez_7.pdf` (solo in
locale, escluso da Git). Esercizio 1, modifica A e modifica B avranno ciascuno brainstorming,
specifica e piano.

## Obiettivo

Costruire un indice vettoriale ripetibile a partire da un corpus di documenti e recuperare i
passaggi pertinenti a una domanda, con la loro fonte. Il retrieval resta isolato: il modello
generativo torna in gioco nella lezione 8.

## Blocco 1 — Perché il RAG

- Dato strutturato («stato dell'ordine 4521») → ricerca esatta per identificativo con uno
  strumento. Testo libero («posso restituire un prodotto comprato due mesi fa?») → nessun
  identificativo: si cerca il passaggio **per significato**.
- La conoscenza del modello è ferma al pretraining e non comprende documenti privati o recenti; se
  manca, il modello può inventare. Tre modi di fornirla: tutto nel prompt (contesto limitato, lento),
  fine-tuning (costoso, nessuna fonte citabile, fuori dal corso), **RAG** (pochi passaggi pertinenti
  nel contesto; la risposta dipende dalla qualità del recupero).
- Due fasi, con lo **stesso modello di embedding** in entrambe:

```
FASE 1 · INGESTION (quando il corpus viene preparato o aggiornato)
  Documenti → Pulizia e metadati → Chunking → Embedding (un vettore per chunk) → Qdrant (vettori + payload)
FASE 2 · INTERROGAZIONE (a ogni domanda)
  Domanda → Embedding (stesso modello) → Ricerca top-k in Qdrant, con filtri → Passaggi (testo, fonte, score) ⇢ LLM risponde (lezione 8)
```

- Il retrieval si valuta separatamente dalla generazione: la ricerca è deterministica, si controlla
  un fatto osservabile (la fonte attesa è tra i primi risultati?), si cambia un parametro per volta
  (chunking, metadati, top-k) e si ripetono le stesse domande. Se il passaggio giusto non arriva,
  nessun prompt al generatore può compensarlo.
- Vocabolario: corpus, documento, chunk, metadati, embedding, collezione (vettori tutti della stessa
  dimensione), punto (ID, vettore, payload con testo e metadati), top-k.

## Blocco 2 — Embedding e similarità

- Un embedding trasforma un testo in un vettore di lunghezza fissa (la dimensione, per esempio 768);
  testi di significato simile danno vettori vicini anche con parole diverse («chiedere un
  rimborso» ritrova «restituzione del prezzo pagato»).
- Similarità tipica: coseno. Si ordinano i chunk e si restituiscono i primi k.
- **Lo score non è una probabilità:** indica vicinanza, non correttezza; dipende dal modello (una
  soglia non si trasferisce); anche se il corpus non contiene la risposta la ricerca restituisce k
  risultati.
- Generazione ed embedding sono compiti distinti: `/v1/chat/completions` contro `/v1/embeddings`;
  in LM Studio entrambi i modelli possono stare sullo stesso server.
- Regole per il modello di embedding: uno solo, con la stessa configurazione, per documenti e
  domande; dimensione dei vettori uguale a quella della collezione; cambiarlo richiede di
  reindicizzare tutto; il nome sta nella configurazione, non nel codice.

## Blocco 3 — Ingestion

- Pipeline, ogni passo ispezionabile: 01 caricare (ricordando la provenienza), 02 pulire (residui,
  spazi, conservare i titoli), 03 suddividere (per sezione o a finestra), 04 arricchire (fonte,
  titolo, sezione, posizione), 05 embedding (a lotti, modello configurato), 06 salvare (upsert dei
  punti in Qdrant: vettore e payload).
- **L'ingestion è uno script separato:** si esegue quando si prepara o aggiorna il corpus, non a
  ogni domanda; non è uno strumento dell'agente, che userà soltanto la ricerca.
- Preparare il corpus: testo e Markdown si leggono direttamente; PDF, HTML, Office richiedono
  estrazione; casi difficili OCR, tabelle, immagini. Rimuovere intestazioni ripetute, menu, piè di
  pagina, a capo spezzati, caratteri di controllo; conservare titoli e struttura. Un passaggio
  sporco viene restituito così com'è.
- Ogni chunk dice da dove viene (esempio illustrativo): `source`, `title`, `section`, `version`,
  `chunk_index` (ordine nel documento, per recuperare gli adiacenti), `text`.
- Chunking: dimensione, overlap, confine (titolo, paragrafo, frase). Troppo piccolo perde il
  contesto; troppo grande mescola argomenti e consuma contesto; rischio principale: separare
  informazioni correlate (il passo 3 in un chunk, l'avvertenza nel successivo).
- Due strategie da confrontare: per sezione o paragrafo (coerente, `section` diretto, ma sezioni
  molto lunghe o brevi) e finestra fissa con overlap (uniforme, ma taglia frasi). Combinazione
  frequente: per sezione, poi solo le sezioni troppo lunghe a paragrafi o a finestra. Si sceglie
  confrontando sulle stesse domande con fonte attesa.
- Qdrant: database vettoriale come servizio di Docker Compose, con API e dashboard; collezione con
  nome, dimensione e distanza (coseno), può registrare metadati propri come il modello di embedding;
  punto con ID, vettore e payload; indici sul payload per i filtri frequenti; volume persistente.
  Esempio di punto (ricetta 89): id UUID, vettore di 768 valori, payload con `documento_id`,
  `numero`, `titolo`, `capitolo`, `posizione`, `testo`, `fonte`. Il database non è uno strumento
  dell'agente: è la funzione di ricerca a interrogarlo.
- Filtri sui metadati **durante** la ricerca (Qdrant considera solo i punti che soddisfano la
  condizione: k risultati se ce ne sono almeno k), non dopo (spesso meno di k). Esempio:
  `python -m rag.ricerca "Come si frigge il pollo?" --capitolo Fritti --k 3` →
  `{"must": [{"key": "capitolo", "match": {"value": "Fritti"}}]}`. Il filtro non rende
  recuperabile un chunk che non contiene l'informazione.
- Rieseguire l'ingestion senza raddoppiare il corpus: strategia A, ID stabili (hash di `source` e
  `chunk_index`) e upsert, ma i chunk eliminati restano e vanno rimossi; strategia B, ricostruzione
  completa (semplice per corpus piccoli, non per collezioni grandi o condivise). Controllo: stesso
  numero di punti dopo la prima e la seconda esecuzione.
- Componenti: sul computer host LM Studio (modello generativo e di embedding, raggiunto da Docker
  con `host.docker.internal`); in Docker Compose lo script di ingestion (eseguito a parte, legge il
  corpus, embedding dei chunk, upsert), l'applicazione (funzione di ricerca; nella lezione 8 anche
  l'agente: embedding della domanda, query + filtro) e Qdrant (porta 6333, collezione «ricette»,
  volume persistente).

## Blocco 4 — Verificare il retrieval

- La ricerca passo per passo: domanda senza modifiche → embedding con lo stesso modello → query a
  Qdrant (k più vicini, eventuale filtro) → testo, metadati e score → lettura umana (il passaggio
  risponde? la fonte è quella attesa?). Il generatore non è coinvolto: se il passaggio giusto non
  arriva va corretta l'ingestion. k piccolo (3–5) per partire, poi verificato.
- Domande con fonte attesa, decise prima di eseguire la ricerca (corpus Artusi):

| Domanda | Fonte attesa | Che cosa registrare |
|---|---|---|
| Quanta farina serve per 400 grammi di patate negli gnocchi? | Ricetta 89 · Gnocchi di patate | Posizione e score della fonte |
| Che vino si usa per il pollo alla cacciatora? | Ricetta 208 · Pollo alla cacciatora | Posizione e score della fonte |
| Come si chiama il cacciucco sulle coste dell'Adriatico? | Ricette 455–456 · Cacciucco | Posizione e score della fonte |
| Qual è la ricetta del tiramisù? | Nessuna: non compare nel libro | Score dei risultati |

  Criterio: la fonte attesa compare tra i primi k e il chunk contiene davvero l'informazione.
  «Funziona» non è un'evidenza.
- Prima valutazione del docente (risultati reali, nomic-embed-text-v1.5, chunk per paragrafi, 1200
  caratteri, overlap 200, top-k 5): otto domande con fonte attesa e due senza risposta; fonte trovata
  in 6 casi su 8. Esempi: gnocchi/farina posizione 1 (0,777); cappelletti per un mangiatore moderato
  posizione 4 (0,748); vino del pollo alla cacciatora assente (0,724); perché gli gnocchi si
  sciolgono assente (0,742); tiramisù — (0,735). La ricetta 208 non contiene mai «cacciatora»: la
  parola è solo nel titolo, che non è nel chunk; neppure col filtro sul capitolo (Fritti) compare.
  Nessuna soglia: il tiramisù ha uno score simile alle domande con risposta.
- Errori tipici: risultati duplicati (ID casuali → contare i punti); errore di dimensione (modello
  diverso da quello della collezione → metadati della collezione); Qdrant non raggiungibile
  (`docker compose ps`, `QDRANT_URL`); passaggio giusto ma incompleto (chunk adiacenti con
  `chunk_index`); risultati generici (chunk troppo grandi o testo sporco); fonte non identificabile
  (payload); collezione vuota dopo il riavvio (volume in `compose.yaml`); filtro senza risultati
  (valore scritto diversamente: valori distinti del campo, facet).

## Blocco 5 — Laboratorio

- Ciclo di Superpowers: brainstorming (unità di documento, chunking, campi del payload, ID,
  ripetizioni) → specifica (requisiti e criteri osservabili, approvata prima del piano) → piano
  (passi piccoli con test e commit) → implementazione (test senza LM Studio né Qdrant) → verifica
  (review, ingestion reale ripetuta, valutazione). La pipeline mostrata in aula è un esempio, non
  codice da copiare. Nel `CLAUDE.md` le regole stabili: ingestion come script separato, modello di
  embedding dalla configurazione, Qdrant con Docker Compose, dati scaricati fuori da Git.
- Requisiti e verifica:

| Componente | Requisito | Verifica |
|---|---|---|
| Corpus | Pulizia; ogni ricetta è un documento con numero, titolo e capitolo | 790 ricette, numerazione senza buchi |
| Chunking | Strategia, dimensione e overlap configurabili | Test su una ricetta breve e su una lunga |
| Embedding | Modello di LM Studio dalla configurazione, lo stesso per documenti e domande | Modello registrato nella collezione; cambio bloccato |
| Qdrant | Un punto per chunk, ID stabili, payload con testo e metadati, indici sui campi filtrati | Due ingestion: stesso numero di punti |
| Ricerca | Top-k con massimo imposto dal codice; filtro per capitolo durante la ricerca | Risultati tutti del capitolo richiesto |
| Valutazione | Domande con fonte attesa; posizione e score della fonte | Tabella riproducibile |
| Test | Embedder finto e Qdrant in memoria | Test superati con i servizi spenti |

- Corpus: Pellegrino Artusi, *La scienza in cucina e l'arte di mangiar bene* (1891), Project
  Gutenberg n. 59047 (`https://www.gutenberg.org/ebooks/59047.txt.utf-8`), di pubblico dominio;
  salvato nel progetto ed escluso da Git. 790 ricette numerate, 23 capitoli, lunghezze molto
  diverse, italiano dell'Ottocento; nel file intestazione e licenza Gutenberg, capitoli in
  maiuscolo, ricette nel formato «7. Titolo», righe spezzate a circa 70 caratteri.
- **Esercizio 1:** cartella e `CLAUDE.md`; brainstorming e specifica approvata; piano e
  implementazione con test, un passo per volta, con commit; avviare Qdrant e LM Studio ed eseguire
  l'ingestion completa due volte; valutare sulle domande con fonte attesa (situazione di partenza).
  Evidenze: specifica e piano nella repository, test superati con i servizi spenti, stesso numero di
  punti dopo le due ingestion, tabella della valutazione di partenza. Domande: quelle viste in aula
  più almeno tre proprie, scritte senza copiare le parole del testo.
- **Esercizio 2** (entrambe obbligatorie, ciascuna con il ciclo di Superpowers e una nuova
  valutazione):
  - **A · Metadati:** campo `contiene_dosi` nel payload (il chunk ha un elenco di ingredienti) e
    opzione per cercare solo tra questi chunk. Con il filtro tutti i risultati hanno il campo vero, al
    massimo k; si combina con il filtro per capitolo; il campo ha un indice sul payload; tutti i
    punti esistenti ricevono il campo senza ricalcolare gli embedding.
  - **B · Chunking:** ogni chunk indicizzato preceduto da titolo e capitolo della ricetta; la ricerca
    restituisce il testo originale. Un test verifica il testo passato all'embedder; l'ingestion
    ricalcola tutti i chunk senza ricreare la collezione e i punti non aumentano; valutazione prima e
    dopo, confronto registrato.
- **Consegna:** pipeline funzionante (ingestion ripetibile, ricerca con filtro per capitolo, test con
  i servizi spenti); modifiche A e B con test e commit Conventional Commits; `docs/retrieval.md`
  con i conteggi delle due ingestion, la valutazione di partenza, dopo A e dopo B, due query
  commentate; specifiche e piani nella repository, `dati/` e `.env` fuori da Git.
- **Criterio di completamento:** dato un risultato si sanno indicare ricetta, capitolo e posizione
  del chunk; si riesegue l'ingestion senza duplicati; si sa motivare ogni scelta della specifica.
- Estensioni: confronto tra strategie di chunking sulle stesse domande; un modello di embedding
  multilingue in una seconda collezione.

## Verso la lezione 8

La ricerca diventa lo strumento `search_documents(query, top_k)` esposto via MCP accanto agli altri;
le citazioni rimandano ai passaggi effettivamente ricevuti; una domanda senza evidenze nel corpus
non deve produrre informazioni inventate.
