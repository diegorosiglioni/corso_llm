# Requisiti — Assistente del laboratorio

Data: 2026-10-26, rivisti il 2026-11-09 (lezione 5)
Stato: §1–§7 approvati il 2026-10-26; revisioni del 2026-11-09 e §8 in revisione

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
e laboratorio. Stato: in revisione.

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
