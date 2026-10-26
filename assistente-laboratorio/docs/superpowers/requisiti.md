# Requisiti — Assistente del laboratorio

Data: 2026-10-26
Stato: bozza da approvare

Questo documento fissa **che cosa** deve fare l'applicazione. Il **come** (architettura,
moduli, dettagli del grafo) sarà descritto nella specifica, che rimanda a questi requisiti.

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
- **RF-4** La sessione si chiude con il comando `esci`, con Ctrl+D (fine input) o con
  Ctrl+C, mostrando un saluto e senza traccia d'errore. Gli input vuoti vengono ignorati.

### Strumento orologio

- **RF-5** È disponibile un solo strumento, `ora_corrente`, con un unico parametro
  obbligatorio `fuso`: nome di fuso orario IANA (es. `Europe/Rome`, `Asia/Tokyo`).
- **RF-6** Lo strumento restituisce il fuso richiesto e la data/ora corrente in quel fuso
  in formato ISO 8601 con offset, es.
  `{"fuso": "Asia/Tokyo", "data_ora": "2026-10-27T00:47:12+09:00"}`.
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
- **RNF-6** L'applicazione si avvia sia in locale sia con Docker Compose; dal container
  raggiunge LM Studio sull'host.
- **RNF-7** Dipendenze motivate e con versioni fissate (`requirements.txt` per l'app,
  `requirements-dev.txt` per i test).
- **RNF-8** Tutti i comandi documentati (installazione, avvio, test, Docker, diagnosi)
  funzionano in PowerShell su Windows e sono stati verificati.
- **RNF-9** Il progetto vive interamente in `assistente-laboratorio/`.

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

## 6. Fuori ambito

Rimandati alle lezioni successive o esclusi:

- MCP, RAG, workflow aggiuntivi, altri strumenti oltre all'orologio;
- interfacce grafiche o web, servizi cloud;
- persistenza della cronologia tra sessioni;
- comandi del terminale diversi da `esci` (es. azzeramento o stampa della cronologia);
- streaming delle risposte;
- containerizzazione di LM Studio.

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
