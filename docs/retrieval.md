# Retrieval sulle ricette dell'Artusi

Risultati della pipeline di partenza della lezione 7 (esercizio 1: ingestion e ricerca, senza
generazione). Specifica: `docs/superpowers/specs/2026-11-17-ingestion-ricette-design.md`.
Prove eseguite il 2026-11-19 dal computer, con LM Studio sull'host e Qdrant in Compose.

## Modello e parametri

| Voce | Valore |
|---|---|
| Modello di embedding | `text-embedding-bge-m3` (LM Studio, file `gpustack/bge-m3-GGUF`) |
| Dimensione dei vettori, distanza | 1024, coseno |
| Collezione | `recipes` su `http://127.0.0.1:6333` |
| Libro | `data/Ricettario.txt` (Project Gutenberg 59047): 790 ricette, 23 capitoli |
| Strategia di chunking | `paragraph` |
| Dimensione, overlap | 1200, 200 caratteri |
| Lotto di embedding | 32 testi |
| k | 5 |

Il testo di ogni chunk è il solo testo della ricetta: titolo e capitolo sono nel payload, non nel
vettore (la modifica B li aggiungerà).

## Ingestion completa, due volte

`python -m rag.ingest` lanciato due volte di seguito, senza `--recreate` (circa 4 minuti e 45
secondi ciascuna, 36 lotti):

```
Ricette: 790 · chunk: 1143 · punti prima: 0 · punti dopo: 1143 · rimossi: 0
Ricette: 790 · chunk: 1143 · punti prima: 1143 · punti dopo: 1143 · rimossi: 0
```

La seconda esecuzione riscrive gli stessi punti (ID stabili) senza duplicati. Dopo
`docker compose restart qdrant` la collezione conta ancora 1143 punti (volume `qdrant-data`).
Un punto controllato (ricetta 763 «Gelato di aranci», capitolo Gelati) ha tutti i campi del
payload: `source`, `recipe_number`, `title`, `chapter`, `chunk_index`, `text`, `embedding_model`.

## Valutazione di partenza

`python -m rag.evaluate` lanciato due volte: le due tabelle sono identiche. Stampata così:

- **modello:** text-embedding-bge-m3
- **collezione:** recipes
- **punti:** 1143
- **strategia:** paragraph
- **dimensione:** 1200
- **overlap:** 200
- **k:** 5

| Domanda | Fonte attesa | Posizione | Score fonte | Score migliore |
|---|---|---|---|---|
| Quanta farina serve per 400 grammi di patate negli gnocchi? | 89 | 1 | 0,671 | 0,671 |
| Quanti cappelletti bastano a un mangiatore moderato? | 7 | 1 | 0,622 | 0,622 |
| Che vino si usa per il pollo alla cacciatora? | 208 | assente | — | 0,515 |
| Perché gli gnocchi possono sciogliersi nell'acqua? | 89 | 1 | 0,639 | 0,639 |
| Come si chiama il cacciucco sulle coste dell'Adriatico? | 455, 456 | 1 | 0,603 | 0,603 |
| Qual è la ricetta del tiramisù? | — | — | — | 0,531 |
| Come si cucinano i petti di pollo e quali ricette si possono fare con essi? | 207, 269 | 1 | 0,728 | 0,728 |
| Che salsa al prezzemolo posso servire con la carne bollita? | 119, 120 | assente | — | 0,627 |
| Come si conservano i pomodori per averli tutto l'anno? | 732 | 2 | 0,639 | 0,665 |

Fonte attesa trovata in 6 casi su 8.

Confronto con la prima valutazione del docente (`docs/superpowers/lezione7.md`, stessi parametri ma
`nomic-embed-text-v1.5`): anche lì 6 su 8, ma i cappelletti erano in posizione 4 e «perché gli
gnocchi si sciolgono» assente; con bge-m3 sono entrambi in posizione 1. Il pollo alla cacciatora
resta assente con tutti e due i modelli. Gli score dei due modelli non sono confrontabili tra loro
(bge-m3 sta più in basso: 0,5–0,7 contro 0,7–0,8).

Provenienza delle domande (`rag/data/questions.json`): le prime sei vengono dalla traccia della
lezione; delle ultime tre, quella sui petti di pollo è stata scritta dall'utente, con le fonti
scelte da lui; quelle sulla salsa al prezzemolo e sulla conserva di pomodoro le ha scritte Claude su
richiesta esplicita dell'utente, scegliendo le fonti dai titoli prima di ogni ricerca. La specifica
(§15, criterio 7) ne chiede tre dell'utente: il criterio è soddisfatto solo in parte.

## Due query commentate

### 1. Il vino del pollo alla cacciatora, nel capitolo Fritti

```
python -m rag.search "Che vino si usa per il pollo alla cacciatora?" --chapter Fritti --k 5
```

| Pos. | Score | Ricetta | Capitolo | Chunk |
|---|---|---|---|---|
| 1 | 0,473 | 205 «Pollo dorato I» | Fritti | 0 |
| 2 | 0,460 | 210 «Fegato col vino bianco» | Fritti | 0 |
| 3 | 0,460 | 209 «Pollo fritto coi pomodori» | Fritti | 0 |
| 4 | 0,451 | 211 «Fegato alla cacciatora» | Fritti | 0 |
| 5 | 0,450 | 208 «Pollo alla cacciatora» | Fritti | 0 |

Il passaggio che risponde è il quinto: la 208 dice di annaffiare il pollo «con mezzo bicchiere di
San Giovese od altro vino rosso del migliore». Gli altri non rispondono: la 205 e la 209 parlano di
pollo senza vino, la 210 e la 211 di vino con il fegato. La parola «cacciatora», la più distintiva
della domanda, sta solo nel titolo, che non entra nel vettore: il modello vede «pollo» e «vino»,
che la 208 condivide con le altre quattro, e la mette ultima. Senza il filtro per capitolo la 208
esce dai primi cinque (riga «assente» della valutazione); con nomic, nella prova del docente, non
compariva neppure col filtro. È il motivo della modifica B (titolo nel
testo indicizzato).

### 2. Una ricetta che il libro non ha: il tiramisù

```
python -m rag.search "Qual è la ricetta del tiramisù?" --k 5
```

| Pos. | Score | Ricetta | Capitolo | Chunk |
|---|---|---|---|---|
| 1 | 0,531 | 351 «Sformato di riso colle rigaglie» | Umidi | 0 |
| 2 | 0,528 | 73 «Risotto colle tinche» | Minestre asciutte e di magro | 2 |
| 3 | 0,525 | 372 «Pasticcio di lepre» | Rifreddi | 3 |
| 4 | 0,525 | 375 «Pasticcio di fegato» | Rifreddi | 0 |
| 5 | 0,523 | 80 «Risotto alla milanese III» | Minestre asciutte e di magro | 0 |

Nessun passaggio risponde: il tiramisù non è nel libro (che è del 1891), e i risultati non sono
nemmeno dolci, né con mascarpone o caffè. La ricerca restituisce comunque k risultati: non ha una
soglia. Gli score sono bassi e quasi uguali tra loro (da 0,523 a 0,531), segno che nessun
passaggio spicca; ma una soglia fissa non basterebbe a riconoscere l'assenza, perché la domanda
sulla 208, la cui risposta nel libro c'è, ha uno score migliore di 0,515, più basso di questo.
Chi genererà la risposta (esercizi successivi) dovrà poter dire «non lo so» anche con cinque
passaggi in mano.

## Dopo la modifica A

Da fare (`has_doses` nel payload e filtro sulle ricette con le dosi).

## Dopo la modifica B

Da fare (titolo nel testo indicizzato, senza ricreare la collezione).
