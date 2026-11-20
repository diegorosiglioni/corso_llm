# Lezione 7, esercizio 2 · Modifica B: titolo e capitolo nel testo indicizzato — specifica

Data: 2026-11-20. Traccia: `docs/superpowers/lezione7.md` (esercizio 2, «B · Chunking»). Parte dalla
pipeline dell'esercizio 1 (`specs/2026-11-17-ingestion-ricette-design.md`) e dalla modifica A
(`specs/2026-11-20-modifica-a-dosi-design.md`), che restano valide dove questa specifica non le cambia.

## 1. Scopo e perché

La traccia chiede, come seconda modifica obbligatoria, che ogni chunk sia indicizzato preceduto da
titolo e capitolo della sua ricetta, mentre la ricerca restituisce il testo originale. Il motivo si
vede in `docs/retrieval.md` («Due query commentate», 1): nella domanda sul pollo alla cacciatora la
parola più distintiva, «cacciatora», sta solo nel titolo della 208, che oggi non entra nel vettore; la
208 è assente nella valutazione e solo quinta col filtro per capitolo. Lo stesso vale per i chunk
successivi al primo di una ricetta lunga, che oggi non portano nessun segno di quale ricetta siano.

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Obiettivi**
- Il testo passato all'embedder per ogni chunk è l'intestazione (titolo e capitolo) seguita dal
  testo del chunk; il campo `text` del payload resta il testo originale, e la ricerca mostra quello.
- La scelta è una variabile d'ambiente, `CHUNK_HEADER`, attiva per impostazione predefinita (decisione
  dell'utente del 2026-11-20, sotto §4), registrata nel payload e mostrata dalla valutazione.
- Sulla collezione `recipes` esistente, `python -m rag.ingest` (senza `--recreate`) ricalcola tutti i
  vettori: stessi ID, punti non aumentati.
- Valutazione dopo B, senza e con `--doses`, in `docs/retrieval.md` («Dopo la modifica B»), confrontata
  con «Dopo la modifica A».

**Non obiettivi**
- Altri formati dell'intestazione (solo titolo, numero della ricetta, etichette diverse) e il
  confronto sistematico tra strategie di chunking: è un'estensione della lezione, non concordata.
- Domande nuove dell'utente (le aggiungerà più avanti: la valutazione usa le 9 attuali; con
  `CHUNK_HEADER=none` in un'altra collezione si potrà rifare il «prima» anche per quelle).
- Cambiare la domanda: viene trasformata in vettore com'è, senza intestazione.
- Lo strumento MCP della lezione 8.

**Anti-obiettivi**
- L'intestazione salvata in `text` o mostrata nei risultati.
- Chunk diversi da prima (tagli, numero, ID): l'intestazione non conta nei `CHUNK_SIZE` caratteri.
- `has_doses` calcolato sul testo con l'intestazione.
- Una valutazione che dichiara un'intestazione diversa da quella usata per i vettori di un indice
  completo.

## 3. Formato dell'intestazione

Con `CHUNK_HEADER=title_chapter` il testo indicizzato è:

```
{titolo} (capitolo {capitolo})

{testo del chunk}
```

per esempio `Pollo alla cacciatora (capitolo Fritti)`, una riga vuota, poi il chunk. Con
`CHUNK_HEADER=none` è il testo del chunk, come prima della modifica. Titolo e capitolo sono quelli già
nel payload (`title`, `chapter`). Scelta di Claude: una sola riga, senza etichette ripetute uguali in
ogni chunk («Ricetta:»), che sposterebbero tutti i vettori nella stessa direzione senza distinguerli.
La funzione che costruisce il testo è pura e testata a parte.

## 4. Approcci

1. **Variabile d'ambiente, attiva per impostazione predefinita** — scelto dall'utente. Segue lo
   schema di `CHUNK_STRATEGY`, `CHUNK_SIZE` e `CHUNK_OVERLAP` (scelta configurabile, registrata nel
   payload, mostrata dalla valutazione); permette di rifare il «prima» senza tornare a una versione
   vecchia del codice, per esempio per le due domande che l'utente aggiungerà.
2. Intestazione sempre presente: codice più semplice, ma il «prima» si riproduce solo dalla storia di
   Git. Scartato per il motivo sopra.
3. Intestazione contata nella dimensione del chunk: cambierebbe i tagli e forse il numero dei punti,
   contro la traccia. Scartato.

## 5. Cosa cambia

**Configurazione.** `CHUNK_HEADER`: `title_chapter` (predefinito) o `none`, senza distinzione tra
maiuscole e minuscole; altro valore → errore di configurazione con i valori ammessi, come per
`CHUNK_STRATEGY`. In `.env.example` (commentata) e nella tabella delle variabili del README.

**Ingestion.** Chunking invariato; all'embedder va il testo indicizzato (§3); il payload ha in più
`chunk_header` (`title_chapter` o `none`). Tutto il resto invariato: stessi ID, `text` originale,
`has_doses` dal testo originale, stessa rimozione dei punti superati. Cambiare `CHUNK_HEADER` su una
collezione esistente è permesso: l'ingestion riscrive tutti i punti con gli stessi ID.

**Valutazione.** Nell'intestazione, dopo l'overlap, la riga `intestazione dei chunk:` col valore di
`chunk_header` letto dal payload di un punto (come strategia, dimensione e overlap); se il campo manca
(indice costruito prima di questa modifica) `none (indice precedente alla modifica B)`: prima di B
nessun vettore aveva l'intestazione, quindi non è un ripiego sulla configurazione.

**Ricerca e aggiornamento del payload.** Invariati: la ricerca restituisce `text`;
`rag.update_payload` legge `text`, che resta originale.

**Rischio accettato.** Un'ingestion interrotta a metà dopo un cambio di `CHUNK_HEADER` lascia punti
con intestazioni diverse, come già succede cambiando i parametri del chunking; la valutazione legge
un punto solo. Si rimedia rieseguendo l'ingestion; non si aggiunge un controllo.

## 6. Verifiche

**Automatiche** (Qdrant in memoria, embedder finto che registra i testi ricevuti):
- Testo indicizzato: con `title_chapter` titolo, capitolo, riga vuota e testo; con `none` il testo.
- Ingestion: l'embedder riceve il testo con l'intestazione; `text` nel payload è l'originale;
  `chunk_header` scritto; `has_doses` uguale al calcolo sul testo originale; con `none` l'embedder
  riceve il testo originale.
- Ingestion con `none`, poi con `title_chapter` sulla stessa collezione: stesso numero di punti,
  stessi ID, vettori cambiati, `text` invariato, `chunk_header` aggiornato, nessun punto rimosso.
- Configurazione: predefinito, `none`, maiuscole, valore non ammesso.
- Valutazione: riga dell'intestazione dal payload; campo assente → `none (indice precedente alla
  modifica B)`.
- `pytest` passa con LM Studio e Qdrant spenti.

**Reali** (LM Studio con `text-embedding-bge-m3`, Qdrant di Compose, la collezione `recipes`):
- `python -m rag.ingest` senza `--recreate`: `punti prima: 1143 · punti dopo: 1143 · rimossi: 0`; il
  vettore della ricetta 89, chunk 0, ha uno SHA-256 diverso da quello registrato dopo A
  (`34be37c0…`), il suo `text` è identico; `rag.update_payload` dà ancora `con dosi: 398`.
- `rag.evaluate` e `rag.evaluate --doses`, ciascuna due volte: tabelle identiche a coppie, con
  `intestazione dei chunk: title_chapter`; in «Dopo la modifica B» il confronto domanda per domanda
  con le tabelle di «Dopo la modifica A».
- Le due query commentate (pollo alla cacciatora con `--chapter Fritti`, tiramisù) rieseguite e
  commentate: posizione della 208, score del tiramisù.
- Le prove reali esistenti (`tests/test_rag_real.py -m real`) passano ancora.

## 7. Lasciato al costruttore

Dove sta la funzione del testo indicizzato (`rag/chunking.py` o un modulo piccolo a parte) e il suo
nome; se le prove reali ricevono un caso nuovo per l'intestazione; forma del messaggio d'errore della
variabile, purché elenchi i valori ammessi. Requisiti e criteri di accettazione nuovi in
`docs/superpowers/requisiti.md` (sezione 21), aggiornamento di `CLAUDE.md` (Obiettivo e Confini),
README e `PROGRESS.md` come per la modifica A.
