# Lezione 7, esercizio 2 · Modifica A: chunk con le dosi — specifica

Data: 2026-11-20. Traccia: `docs/superpowers/lezione7.md` (esercizio 2, «A · Metadati»). Parte dalla
pipeline dell'esercizio 1 (`specs/2026-11-17-ingestion-ricette-design.md`), che resta valida dove
questa specifica non la cambia. La modifica B (titolo nel testo indicizzato) avrà il proprio ciclo.

## 1. Scopo e perché

La traccia chiede, come seconda parte obbligatoria del laboratorio, un metadato nel payload che dica
se un chunk contiene un elenco di ingredienti, e un'opzione per cercare solo tra quei chunk. Serve
per le domande sulle quantità («quanta farina…», «per quante persone…»): il passaggio utile è quello
con l'elenco delle dosi. Va consegnata con test, commit e una nuova valutazione in
`docs/retrieval.md`.

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Obiettivi**
- Campo booleano `has_doses` nel payload di ogni punto (nome in inglese al posto di `contiene_dosi`,
  decisione dell'utente del 2026-11-17), con un indice sul payload.
- `rag.search --doses`: solo chunk con `has_doses` vero, al massimo k, combinabile con `--chapter`,
  filtro applicato da Qdrant durante la ricerca.
- I 1143 punti esistenti ricevono il campo **senza ricalcolare gli embedding** (requisito della
  traccia).
- Valutazione dopo A, con e senza filtro, in `docs/retrieval.md`.
- L'intestazione della valutazione legge strategia, dimensione e overlap dall'indice, non dalle
  variabili della sessione (problema importante della revisione finale dell'esercizio 1).

**Non obiettivi**
- Modifica B; domande nuove dell'utente (le aggiungerà più avanti: la valutazione usa le 9 di oggi).
- Un libro rinominato che raddoppia i punti (minore della revisione): annotato in `TODO.md`.
- Riconoscere gli elenchi senza unità di misura (sotto, §3).

**Anti-obiettivi**
- Con `--doses`, un risultato con `has_doses` falso o assente.
- Una ricerca con `--doses` su una collezione in cui qualche punto non ha ancora il campo, che
  restituisce meno risultati senza dirlo.
- Vettori cambiati o punti in più dopo l'aggiornamento del payload.

## 3. Regola: che cosa è un elenco di ingredienti

La pulizia del corpus riunisce la prosa in paragrafi di una sola riga; restano su più righe solo gli
elenchi di dosi, alcuni versi e le didascalie `[Illustrazione: …]`. Regola, sul testo del chunk così
come è salvato in `text`:

> `has_doses` è vero se il chunk contiene almeno un paragrafo (blocco separato da una riga vuota) di
> **due o più righe**, che **non comincia con `[Illustrazione`**, con **almeno una riga che contiene
> una quantità**: `grammi`, `gr.`, `decilitri`, `litro`/`litri`, `chilogrammi`, `N.` seguito da un
> numero, `quanto basta`, `cucchiaio`/`cucchiaiata`/`cucchiai`, `bicchiere`/`bicchieri`, `etto`.

Misurata sul libro (1143 chunk, `paragraph`, 1200/200): 400 chunk. Le alternative scartate: solo
«paragrafo su più righe» (413) fa passare i versi (ricette 688, 702); «qualunque dose, anche nella
prosa» (570) non è più «un elenco di ingredienti», come lo definisce la traccia. Costo accettato:
pochi elenchi senza unità (per esempio le ricette 99 e 308) restano con `has_doses` falso. La
funzione è pura (`rag/doses.py`, `has_doses(text) -> bool`) e la usano sia l'ingestion sia
l'aggiornamento.

## 4. Approcci per i punti esistenti

1. **Comando a parte che legge il testo salvato nei punti** — scelto. `python -m rag.update_payload`
   scorre la collezione, calcola `has_doses` dal campo `text` di ogni punto e scrive solo quel campo
   (`set_payload` per ID, a lotti). Non usa LM Studio né il libro, non dipende dalle variabili del
   chunking: aggiorna esattamente i punti che ci sono.
2. Opzione di `rag.ingest` che rilegge il libro e aggiorna il payload per ID: funziona solo se
   strategia, dimensione e overlap della sessione coincidono con quelli dell'indice, altrimenti
   calcola ID che non esistono. Scartato.
3. Rieseguire l'ingestion: ricalcola gli embedding, escluso dalla traccia.

## 5. Cosa cambia

**Payload.** Nuovi campi: `has_doses` (bool), scritto da ingestion e aggiornamento; `chunk_strategy`,
`chunk_size`, `chunk_overlap`, scritti solo dall'ingestion (non si possono ricavare dal testo
salvato). Indice `has_doses` di tipo booleano, creato con la collezione e, se manca, anche su una
collezione esistente (ingestion e aggiornamento).

**`rag.update_payload`.** Collezione assente o vuota: errore come per la ricerca. Alla fine stampa
`Punti: 1143 · aggiornati: 1143 · con dosi: N · senza campo: 0` e controlla che nessun punto sia
rimasto senza `has_doses` (altrimenti codice 1). Rieseguito, dà lo stesso risultato. Errori di
Qdrant come negli altri comandi (messaggio, codice 1).

**`rag.search --doses`.** Aggiunge al filtro la condizione `has_doses = true` (insieme a quella sul
capitolo, se c'è). Prima di cercare con `--doses`, se qualche punto non ha il campo: errore «Alcuni
punti non hanno has_doses: eseguire python -m rag.update_payload». Nella riga d'intestazione di
ogni risultato, `· dosi` quando il campo è vero (anche senza `--doses`), così la verifica si vede a
occhio.

**`rag.evaluate --doses`.** Applica il filtro a tutte le domande. Intestazione: in più `filtro
dosi: sì`/`no`; strategia, dimensione e overlap letti dal payload di un punto; se i punti non li
hanno (indice costruito prima di questa modifica), dalla configurazione con l'indicazione «(dalla
configurazione)». La tabella resta identica a parità di indice, domande e opzioni.

**Ingestion.** Scrive i campi nuovi; per il resto invariata (stessi ID, stessa rimozione dei punti
superati).

## 6. Verifiche

**Automatiche** (Qdrant in memoria, embedder finto):
- `has_doses`: elenco con unità → vero; elenco senza unità, versi, didascalia su due righe, dose
  dentro un paragrafo di prosa → falso; elenco dentro un chunk lungo → vero.
- Aggiornamento: punti senza campo lo ricevono, vettori identici prima e dopo, stesso numero di
  punti, rieseguito dà lo stesso risultato, indice creato su una collezione che non lo aveva.
- Ricerca con `--doses`: tutti i risultati hanno il campo vero, al massimo k; con `--chapter` anche
  tutti di quel capitolo; collezione con punti senza campo → errore.
- Valutazione: intestazione dal payload, ripiego sulla configurazione, `filtro dosi`.
- Ingestion: payload con i campi nuovi.

**Reali** (LM Studio, Qdrant di Compose, la collezione `recipes` dell'esercizio 1):
- `rag.update_payload` due volte: stessi conteggi, 1143 punti, nessuno senza campo; il vettore di
  un punto letto prima e dopo è identico.
- `rag.search "…" --doses --chapter Fritti --k 3`: al massimo 3 risultati, tutti `· dosi` e di
  Fritti.
- `rag.evaluate` e `rag.evaluate --doses`: tabelle in «Dopo la modifica A» di `docs/retrieval.md`,
  con il commento sulle domande che migliorano o peggiorano col filtro.

## 7. Lasciato al costruttore

Elenco esatto delle forme delle unità nella espressione regolare (purché i conteggi sul libro restino
spiegati in `docs/retrieval.md`), dimensione dei lotti di `set_payload`, nomi delle funzioni nuove
in `store.py`, forma del controllo «punti senza campo» (conteggio con filtro `IsEmpty`).
