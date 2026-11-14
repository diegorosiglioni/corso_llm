# Requisiti — Assistente del laboratorio

Data: 2026-10-26, rivisti il 2026-11-09 (lezione 5) e integrati per la lezione 6 (§9–§18)
Stato: §1–§7 approvati il 2026-10-26; revisioni del 2026-11-09 e §8 approvate il 2026-11-09
(insieme alla specifica `specs/2026-11-09-strumenti-mcp-design.md`); §9 (lezione 6, Step 1)
e §10 (lezione 6, Step 2) approvate il 2026-11-11; §11 (lezione 6, Step 3) approvata il 2026-11-13;
§12 (lezione 6, Step 4), §13 (lezione 6, Step 5), §14 (lezione 6, Step 6), §15 (lezione 6,
Step 7), §16 (lezione 6, Step 8), §17 (lezione 6, Step 9) e §18 (streaming, facoltativo)
scritte il 2026-11-14 in modalità autonoma (piano in `PROGRESS.md`)

Questo documento fissa **che cosa** deve fare l'applicazione. Il **come** (architettura,
moduli, dettagli del grafo) sarà descritto nella specifica, che rimanda a questi requisiti.

Le note «*Rivisto il 2026-11-09*» indicano i punti cambiati dalla lezione 5 (MCP e quattro
strumenti nuovi, codice in inglese); i requisiti nuovi sono in §8. Nomi di variabili,
strumenti e argomenti seguono la convenzione di RNF-10.

## 1. Scopo

Un'applicazione Python da terminale con cui l'utente conversa con un modello linguistico
servito da LM Studio sul computer host. Il flusso è organizzato in un grafo LangGraph
esplicito. Il modello può richiedere uno strumento orologio, che il programma esegue
davvero. È il primo passo di un progetto che continuerà nelle lezioni successive.

## 2. Requisiti funzionali

### Conversazione

- **RF-1** L'utente scrive una domanda nel terminale e riceve la risposta del modello.
- **RF-2** La cronologia della conversazione è conservata per tutta la sessione: ogni
  nuova domanda viene inviata al modello insieme ai messaggi precedenti.
- **RF-3** Alla chiusura dell'applicazione la cronologia viene persa; non è prevista
  alcuna persistenza.
  *Rivisto il 2026-11-09: vale per la cronologia della conversazione; le note salvate con lo
  strumento note (RF-20) restano invece tra una sessione e l'altra.*
- **RF-4** La sessione si chiude con il comando `esci`, con Ctrl+D (fine input) o con
  Ctrl+C, mostrando un saluto e senza traccia d'errore. Gli input vuoti vengono ignorati.

### Strumento orologio

- **RF-5** È disponibile un solo strumento, `ora_corrente`, con un unico parametro
  obbligatorio `fuso`: nome di fuso orario IANA (es. `Europe/Rome`, `Asia/Tokyo`).
- **RF-6** Lo strumento restituisce il fuso richiesto e la data/ora corrente in quel fuso
  in formato ISO 8601 con offset, es.
  `{"fuso": "Asia/Tokyo", "data_ora": "2026-10-27T00:47:12+09:00"}`.
  *Rivisto il 2026-11-09 (RF-5, RF-6): lo strumento si chiama `get_current_time` con il
  parametro `timezone`, come nella lezione 5; risultato
  `{"timezone": "Asia/Tokyo", "datetime": "2026-10-27T00:47:12+09:00"}`, errore
  `{"error": "..."}` con messaggio in italiano. Non è più l'unico strumento (§8).*
- **RF-7** Con un fuso sconosciuto o mancante lo strumento non interrompe il programma:
  restituisce al modello un messaggio d'errore che indica il problema e un esempio di
  nome valido, così che il modello possa correggersi.
- **RF-8** È il modello a decidere se richiedere lo strumento, tramite tool calling.
  Il grafo esegue lo strumento richiesto, restituisce il risultato al modello e ottiene
  da questo la risposta finale per l'utente.

### Limite dei passaggi

- **RF-9** In un singolo turno il numero di chiamate al modello è limitato.
  Il limite è configurabile (default 5).
- **RF-10** Se il limite viene raggiunto mentre il modello chiede ancora strumenti, il turno
  termina con un messaggio chiaro all'utente (es. «Ho raggiunto il limite di 5 passaggi
  senza una risposta finale.»). La sessione resta attiva e la cronologia resta utilizzabile
  nei turni successivi.

### Log

- **RF-11** Ogni chiamata allo strumento è visibile nei log: nome dello strumento,
  argomenti, risultato (o errore) e numero del passaggio rispetto al limite.
  *Rivisto il 2026-11-09: anche identificativo della chiamata, variante e tipo di esito (RF-22).*
- **RF-12** I log vanno su stderr, separati dalla conversazione su stdout; il livello è
  configurabile (default `INFO`). A livello `INFO` si vedono le chiamate allo strumento.

### Errori

- **RF-13** Se LM Studio non è raggiungibile o restituisce un errore, l'utente vede un
  messaggio comprensibile, la domanda fallita non entra nella cronologia e la sessione
  continua: si può riprovare senza perdere la conversazione precedente.
- **RF-14** Se manca una configurazione obbligatoria o un valore non è valido, l'applicazione
  non parte, spiega che cosa manca ed esce con codice diverso da zero.

## 3. Requisiti non funzionali

- **RNF-1** Python, codice sincrono, moduli piccoli con separazione tra grafo, collegamento
  al modello, strumenti e interfaccia da terminale.
  *Rivisto il 2026-11-09: il client MCP è asincrono; l'asincronia resta confinata nel modulo del
  client, che offre al resto dell'applicazione metodi sincroni.*
- **RNF-2** Il grafo LangGraph è esplicito: stato, nodi e instradamento sono riconoscibili
  nel codice (niente agenti precostruiti che li nascondono).
- **RNF-3** Il modello è servito da LM Studio sull'host e raggiunto tramite la sua API
  compatibile con OpenAI. LM Studio non viene containerizzato.
- **RNF-4** Indirizzo del server e identificativo del modello si configurano solo tramite
  variabili d'ambiente. L'identificativo è quello restituito da `GET /v1/models`; il valore
  di riferimento per le prove è `google/gemma-4-e2b`.
- **RNF-5** Configurazione tramite variabili d'ambiente:
  `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODELLO` (obbligatorie), `MAX_PASSI`, `LOG_LEVEL` (facoltative).
  Un file `.env.example` senza credenziali è versionato; il file `.env` reale resta fuori da Git.
  *Rivisto il 2026-11-09: `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL` (obbligatorie), `MAX_STEPS`,
  `LOG_LEVEL`, `NOTES_DB` (facoltative); `LMSTUDIO_BASE_URL_DOCKER` resta solo per Compose.
  I nomi `LMSTUDIO_MODELLO` e `MAX_PASSI` non sono più letti: un `.env` esistente va aggiornato.*
- **RNF-6** L'applicazione si avvia sia in locale sia con Docker Compose; dal container
  raggiunge LM Studio sull'host.
- **RNF-7** Dipendenze motivate e con versioni fissate (`requirements.txt` per l'app,
  `requirements-dev.txt` per i test).
- **RNF-8** Tutti i comandi documentati (installazione, avvio, test, Docker, diagnosi)
  funzionano in PowerShell su Windows e sono stati verificati.
- **RNF-9** Il progetto vive interamente in `assistente-laboratorio/`.
- **RNF-10** *(2026-11-09)* Lingua: il codice è in inglese (nomi di pacchetto, moduli, classi,
  funzioni, variabili d'ambiente, strumenti e loro argomenti, chiavi JSON dei risultati, commenti
  e docstring), come negli esempi della lezione 5. Sono in italiano i testi che leggono l'utente e
  il modello: prompt di sistema, testi del terminale, descrizioni degli strumenti, messaggi
  d'errore. Documentazione e messaggi di commit restano in italiano.

## 4. Test e verifica

- **RT-1** Test automatici ripetibili che non richiedono LM Studio né rete: strumento con
  istante controllato, instradamento, ciclo modello → strumento → modello, limite dei
  passaggi, cronologia tra turni, turno fallito, configurazione, comandi del terminale.
  Il modello è sostituito da un modello finto con risposte programmate.
- **RT-2** Prove reali con LM Studio, tenute separate ed eseguite solo su richiesta
  esplicita; non partono con il comando di test predefinito.
- **RT-3** Procedura documentata per la prova reale dell'intera soluzione in Docker.
- **RT-4** Una risposta simulata non dimostra che il modello locale sappia usare lo
  strumento: questo si dimostra solo con la prova reale. Se il modello non usa lo
  strumento in modo affidabile, il risultato viene riportato così com'è.

## 5. Criteri di accettazione

| ID | Verifica | Come |
|----|----------|------|
| CA-1 | La suite di test predefinita passa con LM Studio spento. | automatica |
| CA-2 | Alla domanda «Che ore sono a Tokyo?» il log mostra `ora_corrente` con `fuso` = `Asia/Tokyo` e la risposta riporta l'orario restituito dallo strumento. | reale, locale |
| CA-3 | Dopo CA-2, la domanda «E a Roma?» produce una chiamata con `Europe/Rome`: il modello usa la cronologia. | reale, locale |
| CA-4 | Dopo «Mi chiamo Paolo», la domanda «Come mi chiamo?» ottiene «Paolo» senza chiamate allo strumento. | reale, locale |
| CA-5 | Con LM Studio fermo, una domanda produce un messaggio d'errore e la sessione resta attiva; riavviato LM Studio, la domanda successiva funziona e la cronologia precedente è intatta. | reale, locale |
| CA-6 | Il raggiungimento del limite produce il messaggio di RF-10 e lascia la sessione utilizzabile. | automatica (modello finto) |
| CA-7 | Senza `LMSTUDIO_MODELLO` l'applicazione esce con un messaggio chiaro e codice diverso da zero. | automatica e manuale |
| CA-8 | `docker compose build` e l'avvio interattivo con Docker Compose riproducono CA-2 dal container. | reale, Docker |
| CA-9 | `esci`, Ctrl+D e Ctrl+C chiudono la sessione senza traccia d'errore. | automatica e manuale |
| CA-10 | `git status` non mostra mai `.env`, ambienti virtuali o cache come file da versionare. | manuale |

*Rivisto il 2026-11-09: CA-1…CA-10 restano validi con i nomi nuovi (RNF-10); i criteri della
lezione 5 sono in §8.4.*

## 6. Fuori ambito

Rimandati alle lezioni successive o esclusi:

- MCP, RAG, workflow aggiuntivi, altri strumenti oltre all'orologio;
- interfacce grafiche o web, servizi cloud;
- persistenza della cronologia tra sessioni;
- comandi del terminale diversi da `esci` (es. azzeramento o stampa della cronologia);
- streaming delle risposte;
- containerizzazione di LM Studio.

*Rivisto il 2026-11-09: MCP e i quattro strumenti di §8 entrano nell'ambito. Restano fuori
RAG, workflow aggiuntivi, gli altri strumenti proposti nella lezione 5 («Giorni e scadenze»,
«Meteo da API pubblica»), le varianti FastAPI dell'orologio, le resources e i prompts MCP, il
trasporto Streamable HTTP, più server MCP, la conferma dell'utente prima delle modifiche e la
riconnessione automatica al server MCP.*

## 7. Decisioni già prese

| Tema | Decisione |
|------|-----------|
| Modello di riferimento | `google/gemma-4-e2b`, l'unico modello chat caricato in LM Studio |
| Fuso orario | IANA, obbligatorio, nessun default |
| Limite passaggi | contatore nel grafo, default 5, configurabile con `MAX_PASSI` |
| Log | modulo `logging` su stderr, livello da `LOG_LEVEL` |
| Comandi terminale | solo `esci` (più Ctrl+D / Ctrl+C) |
| Dipendenze | pip + `requirements.txt` / `requirements-dev.txt` con versioni fissate |
| Cronologia | tenuta dall'applicazione per la sessione, aggiornata solo a turno riuscito |

## 8. Lezione 5 — strumenti MCP (2026-11-09)

Riferimento: `LLM_Lez_5.pdf` («MCP: dalle funzioni agli strumenti condivisi»), blocchi 2, 4 e 5
e laboratorio. Stato: approvati il 2026-11-09.

### 8.1 Server MCP e discovery

- **RF-15** Quattro capacità nuove sono esposte da **un solo server MCP locale** (FastMCP,
  trasporto stdio) che l'applicazione avvia come sottoprocesso all'inizio della sessione e chiude
  all'uscita. Le capacità diventano sette strumenti MCP: `convert_units`, `calculate`,
  `search_catalog`, `get_item`, `add_note`, `list_notes`, `delete_note`. L'orologio
  `get_current_time` resta una funzione locale.
- **RF-16** Nome, descrizione e schema degli argomenti degli strumenti MCP provengono dal server
  (`tools/list`), non sono riscritti nell'applicazione. L'applicazione espone al modello solo gli
  strumenti di un elenco consentito; quelli non consentiti vengono ignorati e annotati nel log.
  Un nome che coincide con uno strumento locale impedisce l'avvio.

### 8.2 Strumenti

- **RF-17** *Convertitore di unità* — `convert_units(value, from_unit, to_unit)`. Unità ammesse
  come elenco chiuso (lunghezza, massa, temperatura, volume). Errore per unità sconosciuta, per
  conversioni fra grandezze incompatibili, per valori non finiti e per temperature sotto lo zero
  assoluto. Il risultato riporta valore, unità di partenza e di arrivo, grandezza e risultato.
- **RF-18** *Calcolatrice sicura* — `calculate(expression)`. Espressioni aritmetiche valutate
  **senza `eval`**: solo numeri, `+ - * / // % **`, segno e parentesi. Ogni altro input è
  rifiutato con un messaggio che indica il motivo (nomi, chiamate, attributi, operatori non
  ammessi, divisione per zero, espressione troppo lunga, numeri troppo grandi).
- **RF-19** *Catalogo locale* — `search_catalog(query, max_results)` e `get_item(code)` su un
  file JSON di corsi d'esempio (codice, titolo, sede, durata). Una ricerca senza risultati
  restituisce una lista vuota dichiarata, senza elementi inventati. Errori per testo di ricerca
  vuoto, `max_results` fuori intervallo e codice inesistente.
- **RF-20** *Note persistenti* — `add_note(text)`, `list_notes(limit)`, `delete_note(note_id)` su
  un archivio SQLite nella cartella del progetto, escluso da Git. La nota creata restituisce id e
  data; l'elenco è ordinato; l'eliminazione avviene solo per id esatto e restituisce la nota
  eliminata. Errori per testo vuoto o troppo lungo, id inesistente (nessuna eliminazione) e
  archivio non accessibile. Ogni modifica è scritta nel log. Le note restano dopo il riavvio
  dell'applicazione, anche con Docker Compose.

### 8.3 Errori e log

- **RF-21** Se il server MCP non si avvia o la discovery fallisce, l'applicazione non parte,
  spiega il motivo ed esce con codice diverso da zero (come RF-14). Se il server smette di
  rispondere durante la sessione, la chiamata riceve un errore di collegamento, distinto dagli
  errori dello strumento, e la sessione continua.
- **RF-22** Per ogni chiamata a uno strumento il log riporta passaggio, variante (`local` o
  `mcp`), nome, identificativo della chiamata (`call_id`) e argomenti; poi il tipo di esito
  (`ok`, errore dello strumento, errore di collegamento) con il risultato; infine il `call_id`
  del `ToolMessage` creato e il nodo successivo. Così il log distingue una chiamata realmente
  eseguita da una risposta soltanto plausibile.

### 8.4 Criteri di accettazione

| ID | Verifica | Come |
|----|----------|------|
| CA-11 | La discovery restituisce dal server i sette strumenti con nome, descrizione e schema; uno strumento non consentito non arriva al modello; una collisione di nomi blocca l'avvio. | automatica |
| CA-12 | Invocazione diretta di ogni strumento MCP con input noto → risultato atteso; input non valido → errore comprensibile, nessun falso successo. | automatica |
| CA-13 | Server MCP non disponibile → errore di collegamento distinto dall'errore dello strumento; all'avvio, uscita con codice diverso da zero. | automatica |
| CA-14 | La calcolatrice rifiuta espressioni come `__import__('os')`, `2^3` (con l'indicazione di usare `**`) e `9**9**9`. | automatica |
| CA-15 | Le note restano dopo la chiusura e la riapertura dell'archivio; gli id eliminati non vengono riusati. | automatica |
| CA-16 | «Quanto fa 17 * 23?» → chiamata `calculate`, risposta con 391; «Converti 10 km in miglia» → chiamata `convert_units`, risposta con il risultato restituito. | reale |
| CA-17 | «Ricordami di consegnare il report venerdì» → una sola chiamata `add_note`. | reale |
| CA-18 | «Elimina la nota 99» con id inesistente → `delete_note` restituisce un errore e il numero di note non cambia. | reale |
| CA-19 | Dopo il riavvio dell'applicazione `list_notes` mostra la nota salvata. | reale |
| CA-20 | Una domanda sulla durata di un corso → `search_catalog` e poi `get_item`; una ricerca senza risultati non produce corsi inventati. | reale |
| CA-21 | Il log di una prova reale mostra, per la stessa chiamata, variante `mcp`, `call_id`, argomenti, esito e `ToolMessage` con lo stesso `call_id`. | reale |
| CA-22 | Con Docker Compose CA-16 funziona dal container e una nota salvata in un `run --rm` è presente nel successivo. | reale, Docker |

Se una prova reale fallisce perché il modello non sceglie lo strumento o lo usa male, l'esito viene
riportato così com'è, con il punto esatto del percorso (RT-4).

## 9. Lezione 6, Step 1 — router (2026-11-11)

Riferimento: `LLM_Lez_6.pdf`, slide 3 e 4 (riassunto in `lezione6.md`). Stato: approvati il 2026-11-11,
insieme alla specifica `specs/2026-11-11-router-design.md`.

- **RF-23** *Ambito in configurazione* — L'ambito dell'assistente è un testo in un file, non nel
  codice: per default `assistant/data/scope.txt`, sostituibile con la variabile `SCOPE_FILE`. Sono
  in ambito gli argomenti degli strumenti (data e ora, conversioni di unità, calcoli, catalogo dei
  corsi, note), i saluti, i ringraziamenti, le domande sull'assistente, le presentazioni
  dell'utente e le domande su quanto detto nella conversazione. Un file mancante, illeggibile o
  vuoto impedisce l'avvio con un messaggio comprensibile (come RF-14).
- **RF-24** *Router* — Prima dell'agente un nodo LLM (stesso modello, prompt di sistema diverso)
  classifica l'ultimo messaggio dell'utente con un output strutturato: categoria (`conversation`
  oppure `out_of_scope`) e motivo. Legge l'ambito e la cronologia filtrata (domande dell'utente e
  risposte testuali dell'assistente); non riceve gli strumenti e non decide se usarli.
- **RF-25** *Instradamento* — `conversation` → agente, che sceglie gli strumenti come prima;
  `out_of_scope` → nodo di rifiuto → fine, senza eseguire l'agente. Il rifiuto riporta il motivo,
  invita a chiedere che cosa sa fare l'assistente ed entra nella cronologia come una risposta.
- **RF-26** *Errori del router* — Se l'output del router non è valido, il turno prosegue verso
  l'agente come `conversation` e il log lo segnala con un WARNING. Gli errori di collegamento con
  LM Studio sono trattati come per l'agente.
- **RF-27** *Log* — Per ogni turno il log riporta la categoria, il motivo e il nodo successivo
  (`llm` o `refusal`); il nodo di rifiuto scrive la propria riga. Il limite di RF-9 conta solo le
  chiamate del modello dell'agente: la chiamata del router non consuma passaggi.

| ID | Verifica | Come |
|----|----------|------|
| CA-23 | Ambito predefinito letto dal pacchetto; `SCOPE_FILE` personalizzato usato; file mancante o vuoto → «Configurazione non valida: …», exit 1. | automatica |
| CA-24 | Router simulato `conversation` → l'agente viene eseguito; il log contiene categoria, motivo e `next_node=llm`; il router riceve l'ambito e la cronologia filtrata. | automatica |
| CA-25 | Router simulato `out_of_scope` → risposta di rifiuto con il motivo; il modello dell'agente non viene chiamato; nel log `node=refusal` e nessuna riga `node=llm`. | automatica |
| CA-26 | Output del router non valido → l'agente viene eseguito con il WARNING `fallback=invalid_output`; errore di LM Studio nel router → cronologia invariata. | automatica |
| CA-27 | Con LM Studio: «Che ore sono a Tokyo?» → `category=conversation` e `node=llm`; «Chi ha vinto i Mondiali del 2006?» → rifiuto, nessun `node=llm`, nessuno strumento; «Ciao!» → `conversation`. | reale |
| CA-28 | Le prove reali precedenti (CA-2…CA-4, CA-16…CA-21) passano anche con il router attivo. | reale |
| CA-29 | Da terminale, in locale e con Docker Compose, una domanda in ambito e una fuori ambito mostrano nei log i due percorsi. | reale, manuale |

## 10. Lezione 6, Step 2 — revisore (2026-11-11)

Riferimento: `LLM_Lez_6.pdf`, slide 3 e slide dello Step 2 (riassunto in `lezione6.md`). Stato:
approvati il 2026-11-11, insieme alla specifica `specs/2026-11-11-revisore-design.md`; CA-30…CA-37
verificati il 2026-11-13 (comandi ed esiti in `PROGRESS.md`, ex `handoff.md`).

- **RF-28** *Revisore* — Dopo la risposta finale dell'agente (nessuna richiesta di strumenti) un
  nodo LLM (stesso modello, prompt di sistema diverso, nessuno strumento) riceve solo la domanda
  dell'utente e la risposta proposta e decide se la risposta è coerente: risponde a tutte le parti
  della domanda senza uscire dal tema. Non giudica stile, lunghezza né esattezza dei dati. Il
  rifiuto del router e l'avviso del limite dei passaggi non vengono rivisti.
- **RF-29** *Output strutturato* — Il revisore produce un motivo e un verdetto (`coherent`: sì o
  no).
- **RF-30** *Motivo nella cronologia* — Se la risposta non è coerente, il motivo entra nella
  cronologia come indicazione per l'agente (un messaggio utente marcato come del revisore) e il
  turno torna all'agente. Bozza rifiutata e indicazione restano nella cronologia della sessione; il
  router non le vede. La domanda giudicata resta sempre quella dell'utente.
- **RF-31** *Limite delle revisioni* — `MAX_REVIEWS` (intero ≥ 1, default 2) fissa le chiamate al
  revisore in un turno; il contatore sta nello stato. Al limite si restituisce l'ultima risposta
  dell'agente e il log lo segnala con un WARNING. Il revisore non consuma i passaggi di RF-9, che
  restano il limite totale delle chiamate all'agente nel turno, riscritture comprese: un rifiuto
  all'ultimo passaggio chiude il turno con l'ultima risposta e un WARNING. Un valore non valido impedisce
  l'avvio con un messaggio comprensibile (come RF-14).
- **RF-32** *Errori del revisore* — Se l'output del revisore non è valido, la risposta passa come
  coerente e il log lo segnala con un WARNING. Gli errori di collegamento con LM Studio sono
  trattati come per l'agente.
- **RF-33** *Log* — Per ogni revisione il log riporta numero e limite della revisione, verdetto,
  motivo e nodo successivo (`llm` o `end`); il raggiungimento del limite e il ripiego sono
  WARNING. All'avvio il log riporta `max_reviews`.

| ID | Verifica | Come |
|----|----------|------|
| CA-30 | `MAX_REVIEWS` predefinito 2, valori non validi → «Configurazione non valida: …», exit 1; il revisore riceve solo domanda e risposta, anche dopo gli strumenti e alla seconda revisione. | automatica |
| CA-31 | Revisore simulato che approva → una chiamata all'agente e una al revisore; log `coherent=true … next_node=end`; nessuna indicazione nella cronologia. | automatica |
| CA-32 | Domanda in due parti con risposta parziale simulata → rifiuto con motivo, indicazione all'agente, nuova risposta completa approvata; log dei due passaggi. | automatica |
| CA-33 | Revisore simulato che rifiuta sempre → revisore e agente chiamati `MAX_REVIEWS` volte, ultima risposta restituita, WARNING `review_limit_reached`. | automatica |
| CA-34 | Output del revisore non valido o `None` → risposta approvata con WARNING `fallback=invalid_output`; errore di LM Studio nel revisore → cronologia invariata. | automatica |
| CA-35 | Rifiuto del router e avviso di `limit` non rivisti; il revisore non consuma passaggi; limite dei passaggi durante una riscrittura → `limit`. | automatica |
| CA-36 | Con LM Studio: prima risposta parziale imposta → rifiuto motivato del revisore reale e risposta completa dell'agente reale entro il limite; la stessa domanda interamente reale → risposta completa e righe `node=reviewer` nei log. | reale |
| CA-37 | Le prove reali precedenti (CA-2…CA-4, CA-16…CA-21, CA-27) passano con il revisore attivo; da terminale, in locale e con Docker Compose, la domanda in due parti mostra le righe `node=reviewer`. | reale, manuale |

## 11. Lezione 6, Step 3 — riassunto della cronologia (2026-11-13)

Riferimento: `LLM_Lez_6.pdf`, slide 3 e 6 (riassunto in `lezione6.md`). Stato: approvati il
2026-11-13 insieme alla specifica `specs/2026-11-13-riassunto-design.md`; CA-38…CA-45 verificati il
2026-11-13 (comandi ed esiti in `PROGRESS.md`, ex `handoff.md`).

- **RF-34** *Soglia configurabile* — `SUMMARY_MAX_MESSAGES` (intero ≥ 1, default 20) è il numero
  di messaggi della cronologia, domanda appena arrivata compresa, oltre il quale si riassume.
  `SUMMARY_KEEP_MESSAGES` (intero ≥ 1, default 6, minore di `SUMMARY_MAX_MESSAGES`) è il numero
  minimo di messaggi recenti conservati. Valori non validi impediscono l'avvio con un messaggio
  comprensibile (come RF-14).
- **RF-35** *Nodo riassunto* — All'inizio di ogni turno, prima del router, un nodo LLM (stesso
  modello, prompt di sistema diverso, nessuno strumento) comprime i messaggi vecchi e conserva
  almeno gli ultimi `SUMMARY_KEEP_MESSAGES`. Il taglio cade sempre su una domanda dell'utente che
  apre un turno: non separa mai una richiesta di strumento dal relativo risultato, né una bozza
  rifiutata dall'indicazione del revisore. Chi riassume riceve il riassunto precedente e le sole
  domande e risposte finali dei messaggi tolti. Sotto la soglia, o se non c'è nulla da togliere,
  il nodo non chiama il modello.
- **RF-36** *Riassunto nello stato* — Il riassunto è un campo dello stato che a ogni compressione
  viene sostituito da uno nuovo, comprensivo del precedente; la sessione lo conserva tra i turni
  (non oltre la sessione, come la cronologia). Agente, router e revisore lo ricevono in fondo al loro
  prompt di sistema (router e revisore dal 2026-11-13, dopo la prova reale: specifica §16).
- **RF-37** *Errori del riassunto* — Un riassunto vuoto non comprime nulla: il turno prosegue con
  la cronologia intatta e il log lo segnala con un WARNING. Gli errori di collegamento con LM
  Studio sono trattati come per l'agente: cronologia e riassunto restano invariati.
- **RF-38** *Log* — Per ogni turno il nodo scrive una riga: con la compressione il numero di
  messaggi prima e dopo e quanti ne ha tolti; senza, il conteggio rispetto alla soglia e il motivo
  (`below_threshold`, `nothing_to_compress`). All'avvio il log riporta le due soglie.

| ID | Verifica | Come |
|----|----------|------|
| CA-38 | Soglie predefinite 20 e 6; valori non interi o < 1, oppure `SUMMARY_KEEP_MESSAGES ≥ SUMMARY_MAX_MESSAGES` → «Configurazione non valida: …», exit 1. | automatica |
| CA-39 | Cronologia non oltre la soglia → il modello del riassunto non viene chiamato; log `skipped=below_threshold`. | automatica |
| CA-40 | Cronologia oltre la soglia → una chiamata; log `messages_before=… messages_after=… removed=…` con i numeri attesi; messaggi vecchi tolti; `summary` sostituito (al secondo riassunto chi riassume riceve il precedente); l'agente riceve il riassunto nel prompt di sistema. | automatica |
| CA-41 | Il taglio non separa mai tool_call e `ToolMessage` né bozza e indicazione; un turno unico troppo lungo → nessuna chiamata, log `skipped=nothing_to_compress`. | automatica |
| CA-42 | Riassunto vuoto → WARNING `fallback=empty_summary`, cronologia intatta; errore di LM Studio nel riassunto → cronologia e riassunto invariati. | automatica |
| CA-43 | Con LM Studio e soglie 4 e 2: «Mi chiamo Paolo», «Che ore sono a Tokyo?», «Come mi chiamo?» → entro il terzo turno riga con i messaggi prima e dopo; nessun messaggio conservato prima dell'ultima domanda contiene «Paolo»; risposta con «Paolo». | reale |
| CA-44 | Le prove reali precedenti (CA-2…CA-4, CA-16…CA-21, CA-27, CA-36) passano con il nodo riassunto attivo. | reale |
| CA-45 | Da terminale, in locale e con Docker Compose, la sequenza di CA-43 con soglie 4 e 2 mostra le righe `node=summary` e la risposta con «Paolo». | reale, manuale |

## 12. Lezione 6, Step 4 — resource MCP delle preferenze (2026-11-14)

Riferimento: `LLM_Lez_6.pdf`, Blocco B e Step 4 (riassunto in `lezione6.md`). Stato: scritti il
2026-11-14 in modalità autonoma insieme alla specifica `specs/2026-11-14-preferenze-design.md`; le
scelte del progettista sono nella sua §1. CA-46…CA-52 verificati il 2026-11-14 (comandi ed esiti in
`PROGRESS.md`); CA-52 è passata dopo la correzione della descrizione dello stile sintetico
(specifica §11).

- **RF-39** *File delle preferenze* — Le preferenze dell'utente stanno in un file JSON, non nel
  codice: per default `assistant/data/preferenze.json`, sostituibile con la variabile
  `PREFERENCES_FILE`. Il file è un oggetto con `language` (lingua delle risposte, testo libero su una
  riga, al massimo 40 caratteri), `timezone` (fuso orario predefinito, nome IANA) e `style`
  (`sintetico` o `dettagliato`). Valori predefiniti: `italiano`, `Europe/Rome`, `sintetico`.
- **RF-40** *Resource* — Il server MCP locale espone la resource `utente://preferenze` (nome
  `preferenze`, tipo `application/json`), che a ogni lettura restituisce il contenuto del file. La
  resource compare in `resources/list` e non in `tools/list`. Un file mancante, illeggibile o che non
  contiene un oggetto JSON produce un errore MCP con un messaggio in italiano.
- **RF-41** *Lettura dell'host* — L'applicazione legge la resource una sola volta, a inizio sessione
  e prima della prima domanda, e mette in cima al prompt di sistema dell'agente un testo con lingua,
  fuso predefinito e stile; il fuso predefinito si usa quando l'utente chiede data o ora senza
  indicare un luogo o un fuso. La resource non è passata al modello come strumento (`bind_tools`
  riceve gli stessi strumenti di prima) e il modello non la richiede. Router, revisore e riassunto
  non ricevono le preferenze.
- **RF-42** *Resource non disponibile* — Se la resource non si può leggere o il suo contenuto non è
  un oggetto JSON, la sessione parte con i valori predefiniti e il log lo segnala con un WARNING. Un
  singolo campo mancante o non valido prende il valore predefinito, con un WARNING che indica campo,
  problema e valore; gli altri campi restano quelli del file. Le preferenze non impediscono mai
  l'avvio.
- **RF-43** *Log* — La lettura della resource ha righe proprie, che cominciano con `resources/read`
  e riportano URI, esito (`ok`, `partial`, `unavailable`) e valori usati, separate dalle righe delle
  chiamate agli strumenti; il server scrive `event=resource_read`. All'avvio il log riporta
  `preferences_file`.
- **RF-44** *Effetto* — Modificando il file, la sessione successiva segue le preferenze nuove senza
  modifiche al codice.

| ID | Verifica | Come |
|----|----------|------|
| CA-46 | Lettura del file: esempio → tre valori predefiniti; BOM ammesso; file mancante, JSON non valido o non oggetto → errore con il percorso. Validazione: ogni campo mancante o non valido prende il predefinito da solo. | automatica |
| CA-47 | Server via stdio: `utente://preferenze` in `resources/list` con nome e `application/json`, assente da `tools/list` (restano i sette strumenti); lettura → JSON del file; file mancante → errore MCP. | automatica |
| CA-48 | Client via stdio: `read_resource` restituisce il testo; URI inesistente, file mancante e sessione chiusa → `ResourceUnavailableError`. | automatica |
| CA-49 | Con client e modello finti: resource letta una sola volta in una sessione di più turni; testo delle preferenze in cima al prompt di sistema dell'agente, prima di `SYSTEM_PROMPT` e del riassunto; strumenti del modello invariati; resource assente → predefiniti e WARNING `status=unavailable`; riga di avvio con `preferences_file`. | automatica |
| CA-50 | Con LM Studio e `timezone="America/New_York"`: «Che ore sono?» → `get_current_time` con `America/New_York`, senza chiedere il fuso. | reale |
| CA-51 | Con LM Studio: la stessa domanda in due sessioni, preferenze predefinite e poi `language="inglese"` → prima risposta in italiano, seconda in inglese. | reale |
| CA-52 | Le prove reali precedenti (CA-2…CA-4, CA-16…CA-21, CA-27, CA-36, CA-43) passano con le preferenze predefinite. | reale |

## 13. Lezione 6, Step 5 — prompt MCP come comandi della CLI (2026-11-14)

Riferimento: `LLM_Lez_6.pdf`, Blocco B e Step 5 (riassunto in `lezione6.md`). Stato: scritti il
2026-11-14 in modalità autonoma insieme alla specifica `specs/2026-11-14-prompt-mcp-design.md`; le
scelte del progettista sono nella sua §1. CA-53…CA-60 verificati il 2026-11-14 (comandi ed esiti in
`PROGRESS.md`); per CA-59 il testo dello stile `sintetico` è stato corretto (specifica §13), e in
CA-60 CA-43 è fallita una volta su tre esecuzioni (rifiuto del router, vedi `PROGRESS.md`).

- **RF-45** *Prompt del server* — Il server MCP locale espone due prompt: `spiega` (argomenti
  `argomento`, obbligatorio, e `livello`, facoltativo con valore predefinito `base`; livelli `base`,
  `intermedio`, `avanzato`) e `riassumi_conversazione` (argomento obbligatorio `stile`: `sintetico` o
  `dettagliato`). Compaiono in `prompts/list` con descrizioni in italiano del prompt e di ogni
  argomento, e non in `tools/list`. `prompts/get` restituisce un solo messaggio dell'utente con il
  testo della richiesta. Un valore non ammesso produce un errore MCP con un messaggio in italiano.
- **RF-46** *Comando `/prompts`* — Il comando `/prompts` mostra, per ogni prompt di `prompts/list`,
  nome, descrizione e argomenti (nome, obbligatorio o facoltativo, descrizione), più una riga d'uso.
  Non chiama il modello.
- **RF-47** *Comando `/prompt`* — Il comando `/prompt nome chiave=valore …` richiama un prompt. I
  valori con spazi vanno tra virgolette doppie; l'apostrofo è un carattere normale. Errori di
  sintassi (virgolette non chiuse, nome mancante, parola senza `=`, chiave ripetuta, valore vuoto)
  danno un messaggio comprensibile. Le parole dei comandi non distinguono maiuscole e minuscole; un
  altro testo che comincia con `/` dà «Comando sconosciuto». In nessuno di questi casi si chiama il
  modello.
- **RF-48** *Controllo dell'host* — Prima di `prompts/get` l'applicazione controlla la richiesta
  rispetto a `prompts/list`: un prompt non pubblicato, un argomento non dichiarato o un argomento
  obbligatorio mancante bloccano la richiesta con un messaggio che nomina gli argomenti in questione,
  senza chiamare `prompts/get` né il modello. Prompt non disponibili (errore MCP, sessione chiusa) o
  rifiutati dal server danno un messaggio d'errore e nessuna chiamata al modello.
- **RF-49** *Passaggio dal grafo* — I messaggi ottenuti con `prompts/get` si aggiungono alla
  cronologia e attraversano il grafo come una domanda scritta a mano: riassunto, router, agente con
  gli strumenti e revisore. Se il turno fallisce, cronologia e riassunto restano invariati.
  `riassumi_conversazione` riassume i turni della sessione corrente (compreso l'eventuale riassunto
  dello Step 3).
- **RF-50** *Log* — Il log riporta `prompts/list` (numero e nomi), `prompts/get` con nome, argomenti,
  esito e numero di messaggi, e una riga per ogni messaggio ricevuto (ruolo e testo); le richieste
  bloccate dall'host hanno una riga `prompt_command status=rejected` con il motivo; il server scrive
  `event=prompt_get`. Queste righe compaiono solo quando l'utente scrive un comando.
- **RF-51** *Ambito* — L'ambito predefinito del router comprende le spiegazioni di concetti di
  informatica, programmazione e intelligenza artificiale e i riassunti della conversazione, così che
  i due prompt non vengano rifiutati; le domande chiaramente fuori ambito restano rifiutate.

| ID | Verifica | Come |
|----|----------|------|
| CA-53 | Logica pura e server via stdio: i due prompt in `prompts/list` con descrizioni e argomenti (`livello` facoltativo), assenti da `tools/list` (restano sette strumenti); `prompts/get` → un messaggio `user` con il testo atteso, `livello` predefinito `base`; valore non ammesso, obbligatorio mancante, prompt inesistente → errore MCP. | automatica |
| CA-54 | Client via stdio: `list_prompts` → nomi, descrizioni e argomenti; `get_prompt` → messaggi; valore rifiutato, prompt inesistente, sessione chiusa → `PromptUnavailableError`. | automatica |
| CA-55 | Analisi di `/prompt`: virgolette doppie, apostrofo, `=` nel valore, maiuscole del comando; ogni errore di sintassi dà il suo messaggio senza chiamare il client. | automatica |
| CA-56 | `/prompts` con client finto: nome, descrizione e argomenti di ogni prompt; nessun prompt; `prompts/list` non disponibile → messaggio d'errore; modello mai chiamato. | automatica |
| CA-57 | `/prompt` con client e modello finti: prompt sconosciuto, argomento sconosciuto, obbligatorio mancante → nessun `prompts/get`, nessuna chiamata al modello, riga `status=rejected`; richiesta valida → messaggio nella cronologia, righe `prompts/get` e righe del grafo (riassunto, router, agente, revisore). | automatica |
| CA-58 | Con LM Studio: `/prompt spiega argomento="Model Context Protocol" livello=base` → router `conversation`, revisore attivo, risposta non vuota che nomina il protocollo. | reale |
| CA-59 | Con LM Studio: «Mi chiamo Paolo», «Quanto fa 17 * 23?», poi `/prompt riassumi_conversazione stile=sintetico` → risposta con «Paolo» e «391». | reale |
| CA-60 | Le prove reali precedenti (CA-2…CA-4, CA-16…CA-21, CA-27, CA-36, CA-43, CA-50, CA-51) passano con l'ambito esteso. | reale |

## 14. Lezione 6, Step 6 — l'agente come servizio HTTP (2026-11-14)

Riferimento: `LLM_Lez_6.pdf`, Blocco C e Step 6 (riassunto in `lezione6.md`). Stato: scritti il
2026-11-14 in modalità autonoma insieme alla specifica `specs/2026-11-14-servizio-http-design.md`; le
scelte del progettista sono nella sua §1. Esiti delle verifiche in `PROGRESS.md`. CA-61…CA-66
verificati con `pytest`; CA-67…CA-69 verificati il 2026-11-14 con LM Studio (`google/gemma-4-e2b`)
dalle quattro prove reali del servizio in `test_real.py` (stessa risposta da CLI e API, alla
lettera).

- **RF-52** *Agente senza stato* — Il turno dell'agente è una funzione separata dall'interfaccia: riceve
  i messaggi che aprono il turno, la cronologia e il riassunto e restituisce la risposta, gli
  strumenti usati, la cronologia e il riassunto aggiornati, senza conservare nulla tra un turno e
  l'altro. La CLI e l'API usano lo stesso grafo attraverso questa funzione.
- **RF-53** *Messaggi in JSON* — Cronologia e messaggi viaggiano in un formato JSON documentato con
  ruoli `user`, `assistant` e `tool`, che conserva le chiamate agli strumenti (anche quelle non
  interpretabili), le risposte degli strumenti e le indicazioni del revisore. Una cronologia con
  messaggi di sistema, risposte di strumenti senza chiamata o chiamate senza risposta è rifiutata
  con un messaggio che indica il messaggio in questione.
- **RF-54** *Endpoint di conversazione* — `POST /chat` riceve un messaggio (oppure un prompt MCP con
  nome e argomenti), la cronologia e il riassunto, e restituisce risposta, strumenti usati (nome,
  argomenti, risultato, esito), cronologia e riassunto aggiornati. Con un prompt il servizio fa il
  controllo dell'host dello Step 5 prima di `prompts/get`.
- **RF-55** *Endpoint di stato e dei prompt* — `GET /status` riporta se agente, server MCP e modello
  (presente in `/models` di LM Studio) sono raggiungibili, con codice `200` se tutto risponde e `503`
  altrimenti; `GET /prompts` restituisce l'elenco di `prompts/list`.
- **RF-56** *Errori* — Richieste non valide, prompt rifiutati, LM Studio o server MCP non raggiungibili
  ed errori imprevisti producono il codice HTTP della specifica §6 e un corpo
  `{"error", "detail"}` con un messaggio in italiano; un errore non cambia cronologia e riassunto del
  chiamante. Un errore di uno strumento durante un turno resta nel turno (risultato con `ok: false`).
- **RF-57** *OpenAPI* — Il servizio pubblica il documento OpenAPI (`/openapi.json`) e la pagina
  `/docs`, con gli schemi di richieste e risposte.
- **RF-58** *Avvio e log* — Il servizio si avvia con `python -m assistant.service`, all'indirizzo di
  `AGENT_HOST` e `AGENT_PORT` (predefiniti `127.0.0.1` e `8000`); il log ha una riga per ogni
  richiesta e risposta (codice, strumenti, durata) accanto ai log del grafo e di MCP.
- **RF-59** *CLI client* — `python -m assistant` è un client dell'API all'indirizzo di `AGENT_URL`
  (predefinito `http://127.0.0.1:8000`): conserva cronologia e riassunto per la sessione e si comporta
  come il terminale dello Step 5, comandi `/prompts` e `/prompt` compresi. Agente non raggiungibile
  all'avvio → messaggio ed exit 1; errori durante la sessione → messaggio e sessione che continua.
  `docker compose run --rm assistant` avvia anche l'agente.

| ID | Verifica | Come |
|----|----------|------|
| CA-61 | Modulo dell'agente con grafo simulato: risposta, strumenti usati (riuscito, errore, non eseguito), cronologia e riassunto aggiornati anche dopo una compressione; argomenti non modificati; andata e ritorno JSON; ogni cronologia non valida rifiutata col suo messaggio. | automatica |
| CA-62 | `POST /chat` con grafo simulato: messaggio, cronologia di un turno precedente, prompt (controllo dell'host senza `prompts/get` né modello); schema OpenAPI con `/chat`. | automatica |
| CA-63 | Errori con grafo, modello e client MCP finti: ogni riga della tabella della specifica §6 col suo codice, `error` e `detail`. | automatica |
| CA-64 | `GET /status` e `GET /prompts` con client MCP e stato del modello finti: tutte le combinazioni, codici `200`/`503`. | automatica |
| CA-65 | Avvio del servizio con MCP e uvicorn sostituiti: indirizzo e porta, configurazione non valida, server MCP non avviato. | automatica |
| CA-66 | CLI client con l'API simulata: domanda, `/prompts`, `/prompt` (errori di sintassi locali, rifiuto dell'host), errore del servizio senza perdere la cronologia, agente non raggiungibile all'avvio. | automatica |
| CA-67 | Con LM Studio: `POST /chat` «Quanto fa 17 * 23?» → `200`, `calculate` negli strumenti usati, «391», righe dell'API e dello strumento nel log del servizio. | reale |
| CA-68 | Con LM Studio: la stessa domanda dalla CLI e dall'API dà gli stessi strumenti e lo stesso risultato. | reale |
| CA-69 | Con LM Studio: `/openapi.json` consultabile, `/status` `200`; con LM Studio irraggiungibile `/status` `503` e `/chat` `503 model_unavailable`. | reale |

## 15. Lezione 6, Step 7 — back-end: API e salvataggio delle chat (2026-11-14)

Riferimento: `LLM_Lez_6.pdf`, Blocco C e Step 7 (riassunto in `lezione6.md`). Stato: scritti il
2026-11-14 in modalità autonoma insieme alla specifica `specs/2026-11-14-backend-chat-design.md`; le
scelte del progettista sono nella sua §1. Esiti delle verifiche in `PROGRESS.md`. CA-70…CA-76
verificati con `pytest`; CA-77 il 2026-11-14 su PostgreSQL 18.6 in un container (37 test
dell'archivio passati, il solo test del `PRAGMA` di SQLite saltato); CA-78 il 2026-11-14 con
PostgreSQL, agente e LM Studio (`google/gemma-4-e2b`) dalla prova `test_backend_keeps_chats_across_restarts`.

- **RF-60** *Servizio back-end* — Un servizio HTTP distinto dall'agente (pacchetto `backend`, avvio con
  `python -m backend`, indirizzo da `BACKEND_HOST` e `BACKEND_PORT`, predefiniti `127.0.0.1` e
  `8001`) è l'unico punto di contatto del front-end; raggiunge l'agente solo via HTTP all'indirizzo
  di `AGENT_URL`.
- **RF-61** *Archivio PostgreSQL* — Chat e messaggi sono salvati in PostgreSQL (indirizzo e
  credenziali solo in `DATABASE_URL`, mai nei log); le tabelle si creano all'avvio se mancano. Per
  ogni chat si conservano titolo, data di creazione, i messaggi visibili (domande e risposte con gli
  strumenti usati, con la loro data) e lo stato dell'agente (cronologia e riassunto dello Step 6).
  Le chat restano dopo il riavvio del back-end.
- **RF-62** *Operazioni sulle chat* — Creare una chat restituisce il suo identificativo; l'elenco
  riporta per ogni chat titolo e data dell'ultimo messaggio, dalla più recente; la lettura
  restituisce i messaggi in ordine cronologico; l'eliminazione rimuove la chat e i suoi messaggi.
  Senza un titolo dato alla creazione, la prima domanda dà il titolo alla chat.
- **RF-63** *Invio di un messaggio* — Il back-end salva la domanda, chiama l'agente (`POST /chat`)
  con la domanda, la cronologia e il riassunto salvati per la chat, poi salva la risposta con gli
  strumenti usati, sostituisce cronologia e riassunto con quelli restituiti e restituisce domanda e
  risposta salvate.
- **RF-64** *Errori* — Chat inesistente, richiesta non valida, agente non raggiungibile, agente senza
  risposta, agente che risponde con un errore, database non disponibile ed errori imprevisti
  producono il codice HTTP della specifica §6 e un corpo `{"error", "detail"}` con un messaggio in
  italiano. Con un errore dell'agente la domanda resta salvata e lo stato dell'agente della chat non
  cambia.
- **RF-65** *OpenAPI* — Il back-end pubblica `/openapi.json` e `/docs` con gli schemi di richieste,
  risposte ed errori: è il contratto del front-end (Step 8).
- **RF-66** *Log* — Una riga per ogni risposta (operazione, chat, codice, durata), più la richiesta e
  la chiamata all'agente per l'invio (strumenti usati, dimensione di cronologia e riassunto), senza il
  testo dei messaggi né le credenziali.
- **RF-67** *Test senza PostgreSQL* — Archivio e API si provano senza PostgreSQL né modello, con lo
  stesso schema su SQLite in memoria e l'agente simulato; le prove con PostgreSQL vero sono separate
  e attivate esplicitamente.

| ID | Verifica | Come |
|----|----------|------|
| CA-70 | Configurazione: predefiniti, `DATABASE_URL` mancante o non PostgreSQL rifiutata, `postgresql://` accettato, porta non valida, problemi in un solo messaggio. | automatica |
| CA-71 | Archivio su SQLite: creazione con e senza titolo, elenco con titolo, data dell'ultimo messaggio e ordine, lettura in ordine cronologico, eliminazione con i messaggi, titolo dalla prima domanda, stato dell'agente salvato con la risposta, chat inesistente. | automatica |
| CA-72 | API con archivio su SQLite: creazione, elenco, lettura ed eliminazione con i codici della specifica; OpenAPI con i percorsi e gli schemi. | automatica |
| CA-73 | Invio con l'agente simulato: domanda e risposta salvate e restituite, strumenti usati salvati, al secondo invio l'agente riceve cronologia e riassunto aggiornati dal primo. | automatica |
| CA-74 | Errori: ogni riga della tabella della specifica §6 col suo codice, `error` e `detail`; dopo un errore dell'agente la domanda resta e lo stato dell'agente non cambia. | automatica |
| CA-75 | Avvio con uvicorn sostituito: indirizzo e porta, configurazione non valida e database non raggiungibile → exit 1, password assente dalla riga d'avvio. | automatica |
| CA-76 | Righe di log esatte per le cinque operazioni e per gli errori, ai livelli della specifica §7. | automatica |
| CA-77 | Con PostgreSQL: i test dell'archivio passano anche sul database vero. | reale |
| CA-78 | Con PostgreSQL, agente e LM Studio: messaggio con uno strumento salvato; dopo il riavvio del back-end chat e messaggi presenti e il turno successivo usa la cronologia salvata; agente fermato → `503 agent_unavailable` con la domanda salvata. | reale |

## 16. Lezione 6, Step 8 — front-end: interfaccia di chat (2026-11-14)

Riferimento: `LLM_Lez_6.pdf`, Blocco C e Step 8 (riassunto in `lezione6.md`). Stato: scritti il
2026-11-14 in modalità autonoma insieme alla specifica `specs/2026-11-14-frontend-chat-design.md`; le
scelte del progettista sono nella sua §1. Esiti delle verifiche in `PROGRESS.md`. CA-79…CA-83
verificati con `pytest`; CA-84 e CA-85 con `pytest -m browser` in Edge (e Chrome); CA-86 e CA-87 il
2026-11-14 con PostgreSQL 18.6 nel container, LM Studio (`google/gemma-4-e2b`), agente, back-end e
front-end come processi ed Edge senza finestra, dalla prova `test_frontend_chat_from_the_browser`.

- **RF-68** *Front-end* — Un'interfaccia di chat nel browser, in italiano, usabile da chi non conosce
  il progetto, scritta in HTML, CSS e JavaScript senza framework né passo di build, servita da un
  servizio distinto (pacchetto `frontend`, avvio con `python -m frontend`, indirizzo da
  `FRONTEND_HOST` e `FRONTEND_PORT`, predefiniti `127.0.0.1` e `8080`).
- **RF-69** *Solo il back-end* — La pagina comunica solo con il back-end dello Step 7, all'indirizzo
  di `BACKEND_URL` (predefinito `http://127.0.0.1:8001`) consegnato al browser da `/config.js`; non
  conosce agente né database. Il back-end ammette le chiamate del browser dalle origini di
  `CORS_ORIGINS` (predefinite `http://127.0.0.1:8080` e `http://localhost:8080`).
- **RF-70** *Contratto* — Il documento OpenAPI del back-end è salvato nella repository come contratto
  del front-end; i test controllano che coincida con quello generato dal back-end e che ogni richiesta
  e ogni campo usati dalla pagina vi compaiano.
- **RF-71** *Chat* — La pagina elenca le chat (titolo e data dell'ultimo messaggio, dalla più
  recente), ne crea una nuova e la apre, ne elimina una dopo una conferma; la chat aperta resta
  nell'indirizzo della pagina e si ritrova ricaricandola.
- **RF-72** *Messaggi e invio* — La pagina mostra i messaggi della chat in ordine, ciascuno con l'ora,
  e sotto ogni risposta gli strumenti usati (nome, argomenti e risultato, errore segnalato); invia una
  domanda con Invio o con il pulsante e mostra la risposta salvata. I testi sono mostrati come testo,
  mai interpretati come HTML.
- **RF-73** *Attesa* — Durante un invio la domanda compare subito con l'indicazione che l'assistente
  sta rispondendo e i secondi trascorsi; solo l'invio in quella chat è bloccato, il resto della pagina
  resta usabile.
- **RF-74** *Errori* — Back-end non raggiungibile, tempo scaduto, agente non raggiungibile, senza
  risposta o in errore, archivio non disponibile, chat inesistente e altri errori producono il
  messaggio in italiano della specifica §5, senza bloccare la pagina; dopo un errore dell'agente la
  chat mostra la domanda salvata.
- **RF-75** *Test* — Configurazione, servizio, contratto e CORS si provano con `pytest`; client HTTP
  e messaggi del JavaScript con `node --test` (lanciato da `pytest`); la pagina nel browser con
  Playwright e il browser installato (marcatore `browser`); la prova con agente, LM Studio e PostgreSQL
  veri è separata (marcatore `real`).

| ID | Verifica | Come |
|----|----------|------|
| CA-79 | Configurazione: predefiniti, `BACKEND_URL` non http, porta non valida, `CORS_ORIGINS` (predefinito, elenco, voce non valida, vuoto), problemi in un solo messaggio. | automatica |
| CA-80 | Servizio del front-end: pagina, `/config.js` con l'indirizzo configurato e `no-store`, file statici, `404`; avvio con uvicorn sostituito e configurazione non valida → exit 1. | automatica |
| CA-81 | CORS del back-end: richiesta preliminare e risposte (anche d'errore) con `Access-Control-Allow-Origin` per un'origine ammessa, nessuna per le altre. | automatica |
| CA-82 | Contratto: `frontend/backend-openapi.json` uguale all'OpenAPI del back-end; richieste e campi del client presenti nel documento. | automatica |
| CA-83 | JavaScript con Node: client HTTP (percorsi, corpi, `204`, errori con e senza corpo, rete, tempo scaduto) e ogni messaggio d'errore della specifica §5. | automatica |
| CA-84 | Nel browser con back-end e agente finti: elenco vuoto, creazione, selezione, eliminazione con conferma, ricarica con la chat aperta. | browser |
| CA-85 | Nel browser con back-end e agente finti: invio con stato d'attesa e strumenti mostrati, pagina usabile durante l'attesa, agente spento e back-end spento con il messaggio giusto, testo HTML mostrato come testo. | browser |
| CA-86 | Con LM Studio, PostgreSQL, agente e back-end veri, dal browser: «Quanto fa 17 * 23?» → «391» con `calculate` mostrato e nel log dell'agente; dopo il riavvio del back-end e la ricarica la chat c'è ancora. | reale |
| CA-87 | Con l'agente fermato, dal browser: messaggio d'errore mostrato, domanda salvata visibile, pagina ancora usabile (creazione di una chat). | reale |

## 17. Lezione 6, Step 9 — Docker Compose: un container per componente (2026-11-14)

Riferimento: `LLM_Lez_6.pdf`, Step 9 (riassunto in `lezione6.md`). Stato: scritti il 2026-11-14 in
modalità autonoma insieme alla specifica `specs/2026-11-14-compose-design.md`; le scelte del
progettista sono nella sua §1. Esiti delle verifiche in `PROGRESS.md`. CA-88 e CA-90 verificati con
`pytest` (CA-90 con Docker Compose v5.6.0);
CA-89 il 2026-11-14 con Docker 29.9.1, LM Studio (`google/gemma-4-e2b`) e il PostgreSQL 18.6 del
container dello Step 7. CA-91, CA-92 e CA-93 verificati il 2026-11-14 con `docker compose up -d
--build` (Docker 29.9.1, LM Studio con `google/gemma-4-e2b`, pagina in Edge con Playwright): quattro
servizi attivi, agente non raggiungibile dall'host, «17 * 23 fa 391.» con `calculate` mostrato e in
`docker compose logs agent`, chat e messaggi presenti dopo `down` e `up -d`.

- **RF-76** *Immagini* — Agente (servizio HTTP), back-end e front-end hanno ciascuno il proprio
  Dockerfile (`docker/agent.Dockerfile`, `docker/backend.Dockerfile`, `docker/frontend.Dockerfile`),
  con la stessa immagine base fissata per digest e le stesse dipendenze di `requirements.txt` e
  `constraints.txt`; ogni immagine esegue come utente non root, avvia il proprio servizio come
  comando predefinito e ascolta su tutte le interfacce del container, sulla porta predefinita del
  servizio. Il server MCP stdio parte come sottoprocesso nel container dell'agente.
- **RF-77** *Quattro servizi* — `compose.yaml` definisce `frontend`, `backend`, `agent` (ognuno dal
  proprio Dockerfile) e `postgres` (immagine ufficiale `postgres:18.6`); `docker compose up` avvia
  questi quattro. La CLI resta disponibile con `docker compose run --rm assistant`, senza partire
  con `up`.
- **RF-78** *Rete ed esposizione* — Il front-end è raggiungibile dal browser su
  `http://127.0.0.1:8080`, il back-end è pubblicato su `127.0.0.1:8001` (la pagina lo chiama
  direttamente, con il CORS dello Step 8); agente e PostgreSQL non sono pubblicati e si raggiungono
  solo sulla rete di Compose. L'agente raggiunge LM Studio sull'host con `host.docker.internal`.
- **RF-79** *Dati, credenziali, avvio* — I dati di PostgreSQL stanno nel volume `postgres-data` (le
  note dell'agente restano nel volume `notes-data`); utente, password e nome del database stanno solo
  nel `.env` escluso da Git, con un esempio in `.env.example`; senza la password Compose si ferma con
  un messaggio. Il back-end parte solo quando PostgreSQL è pronto.
- **RF-80** *Verifiche* — Dockerfile e `compose.yaml` si controllano con `pytest` senza costruire
  immagini (il controllo di `compose.yaml` richiede solo la CLI di Docker); le prove con le immagini e
  con Compose avviato sono separate, a mano.

| ID | Verifica | Come |
|----|----------|------|
| CA-88 | Dockerfile: stessa base fissata, dipendenze da `requirements.txt` con `constraints.txt`, pacchetti copiati, utente non root, porta esposta uguale alla predefinita del servizio, indirizzo `0.0.0.0`, comando col modulo del servizio. | automatica |
| CA-89 | Le tre immagini costruite e avviate una per una: agente con LM Studio → `/status` `200` con gli strumenti MCP; back-end con PostgreSQL → `GET /chats` `200`; front-end → pagina e `/config.js`; utente `app`. | Docker, a mano |
| CA-90 | `docker compose config`: quattro servizi senza profilo e CLI nel profilo `cli`; agente e PostgreSQL senza porte, back-end e front-end su `127.0.0.1`; volume e `healthcheck` di PostgreSQL; back-end dopo PostgreSQL `service_healthy`, `DATABASE_URL` e `AGENT_URL` interni; password mancante → errore. | automatica (CLI di Docker) |
| CA-91 | `docker compose up`: `docker compose ps` mostra i quattro servizi attivi; l'agente non risponde su `127.0.0.1:8000` dell'host. | Docker, reale |
| CA-92 | Dal browser con Compose e LM Studio: «Quanto fa 17 * 23?» → «391» con `calculate` mostrato e nel log dell'agente (`docker compose logs agent`). | Docker, reale |
| CA-93 | Dopo `docker compose down` e `docker compose up` la chat e i suoi messaggi sono ancora presenti. | Docker, reale |

## 18. Lezione 6, facoltativo — streaming della risposta (2026-11-14)

Riferimento: `LLM_Lez_6.pdf`, «Facoltativo — streaming della risposta» (riassunto in `lezione6.md`).
Stato: scritti il 2026-11-14 in modalità autonoma insieme alla specifica
`specs/2026-11-14-streaming-design.md`; le scelte del progettista sono nella sua §1. Esiti delle
verifiche in `PROGRESS.md`. CA-94…CA-99 e CA-103 verificati con `pytest` (CA-99 con Node 24.15.0);
CA-100 con `pytest -m browser` (Edge e Chrome); CA-101 e CA-102 il 2026-11-14 con LM Studio
(`google/gemma-4-e2b`), il PostgreSQL 18.6 del container dello Step 7 ed Edge; CA-104 nel README.
Per CA-103: la prova dal browser dello Step 8 (CA-86) cambia solo nelle righe di log attese, perché
la pagina ora usa l'endpoint con lo streaming.

- **RF-81** *Agente in streaming* — `POST /chat/stream` riceve lo stesso corpo di `/chat` e risponde
  con Server-Sent Events: i pezzi del testo dell'agente man mano che il modello li scrive (`text`),
  l'inizio e il risultato di ogni strumento (`tool_start`, `tool_end`), l'annullamento del testo già
  mandato che non sarà la risposta (`reset`), e alla fine un solo evento `done` con lo stesso
  contenuto della risposta di `/chat`, oppure `error`. Riassunto, router e revisore non producono
  testo nel flusso.
- **RF-82** *Bozza e revisore* — Con il revisore attivo la bozza si mostra mentre viene scritta,
  indicata come provvisoria; se il revisore la respinge, il flusso lo segnala con il motivo
  (`reset` `review`) prima della riscrittura. Si salva solo la risposta finale.
- **RF-83** *Back-end in streaming* — `POST /chats/{chat_id}/messages/stream` salva la domanda,
  inoltra al browser come Server-Sent Events gli eventi dell'agente (preceduti dalla domanda salvata)
  e, solo alla fine del turno, salva la risposta completa con gli strumenti usati e lo stato
  dell'agente, come `/messages`, mandando per ultimo domanda e risposta salvate.
- **RF-84** *Errori* — Gli errori scoperti prima del flusso hanno il codice HTTP e il corpo
  `{"error", "detail"}` degli endpoint senza streaming; quelli durante il flusso arrivano come evento
  `error` con gli stessi codici e chiudono il flusso. Dopo un errore o un'interruzione la domanda
  resta salvata senza risposta e lo stato dell'agente della chat non cambia.
- **RF-85** *Pagina* — La pagina invia con lo streaming, mostra il testo mentre arriva (segnato come
  bozza), indica lo strumento in uso durante l'attesa e poi il suo risultato, segnala la riscrittura
  chiesta dal revisore, sostituisce la bozza con la risposta salvata alla fine e mostra gli errori come
  nello Step 8, senza bloccare le altre chat.
- **RF-86** *Compatibilità* — `POST /chat` e `POST /chats/{chat_id}/messages` non cambiano; la CLI
  continua a usare `/chat`. Nessuna dipendenza nuova; il contratto del front-end include l'endpoint
  con lo streaming.
- **RF-87** *Log* — Agente e back-end scrivono una riga d'inizio e una di fine per ogni flusso, con
  l'esito (`done`, `error`, `client_gone`), gli strumenti, la lunghezza della risposta e la durata,
  senza il testo dei messaggi nel back-end.

| ID | Verifica | Come |
|----|----------|------|
| CA-94 | Agente con un modello finto in streaming: ordine e contenuto degli eventi (testo, strumento riuscito e in errore, chiamata non interpretabile, limite, rifiuto del router, revisore che respinge e poi approva, riassunto); `done` uguale al risultato di `run_turn`. | automatica |
| CA-95 | `POST /chat/stream` con grafo finto: `text/event-stream`, eventi e `done`; controlli preliminari in JSON coi codici di `/chat`; errori del modello ed errore imprevisto come evento `error`; righe di log; OpenAPI. | automatica |
| CA-96 | Router, revisore e riassunto costruiti con `disable_streaming`; l'agente no. | automatica |
| CA-97 | Lettore SSE e `AgentClient.chat_stream`: eventi, `error`, risposta d'errore JSON, agente spento, flusso interrotto, `done` malformato, tempo superato. | automatica |
| CA-98 | `POST /chats/{chat_id}/messages/stream` con agente finto: domanda come primo evento, eventi inoltrati, risposta e stato salvati alla fine uguali a `/messages`; errori prima del flusso in JSON; `error` durante il flusso con domanda salvata e stato invariato; righe di log; contratto aggiornato. | automatica |
| CA-99 | JavaScript con Node: lettore SSE su pezzi spezzati, `sendMessageStream` (eventi, `done`, `error`, interruzione, errore JSON, rete), testi nuovi. | automatica |
| CA-100 | Nel browser con back-end e agente finti: testo a pezzi prima della fine, strumento indicato durante l'attesa, avviso di riscrittura del revisore, messaggi salvati alla fine, errore durante il flusso con la domanda salvata, pagina usabile. | browser |
| CA-101 | Con LM Studio: `POST /chat/stream` «Quanto fa 17 * 23?» → `tool_start` e `tool_end` di `calculate`, `done` con «391». | reale |
| CA-102 | Con LM Studio, PostgreSQL, agente, back-end e front-end, dal browser: il testo compare prima della fine del turno, lo strumento è indicato durante l'attesa, la risposta salvata resta dopo la ricarica. | reale |
| CA-103 | `/chat`, `/chats/{chat_id}/messages` e la CLI invariati: la suite esistente passa senza modifiche ai suoi test. | automatica |
| CA-104 | README con lo streaming (endpoint, eventi, decisione sulla bozza, diagnosi). | revisione |
