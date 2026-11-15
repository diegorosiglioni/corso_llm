# Specifica — Revisione e integrazione del lavoro autonomo (`auto-claude`)

Data: 2026-11-15
Stato: approvata dall'utente il 2026-11-15
Piano: [`../plans/2026-11-15-revisione-integrazione.md`](../plans/2026-11-15-revisione-integrazione.md)
(fasi F1–F3); il piano delle correzioni (F4) comprenderà anche F5 e F6.
Riferimenti: [`../../../PROGRESS.md`](../../../PROGRESS.md) (diario del loop, sezioni degli step 4–9 e
dello streaming), [`../lezione6.md`](../lezione6.md) (traccia), specifiche
`2026-11-14-*-design.md` in questa cartella, `CLAUDE.md` (regole di Git e modalità autonoma).

## 1. Scopo

Il 2026-11-14 un loop autonomo ha realizzato sul branch `auto-claude` gli step 4–9 della lezione 6
e lo streaming facoltativo: 35 commit (`290ce59`…`30bad78`), 94 file, circa 19.900 righe aggiunte
(5.300 di codice, 8.700 di test, il resto documentazione). Specifiche, piani e scelte sono stati
decisi senza nessuno che li leggesse; nessun commit è pubblicato.

Obiettivo dell'utente: **poter pubblicare su `main` in sicurezza**, senza scadenze. Questa
specifica descrive come arrivarci: revisione indipendente, prove reali ripetute, rilettura delle
scelte con l'utente, correzioni approvate, integrazione con avanzamento rapido e sistemazione dei
file del loop.

Stato di partenza verificato il 2026-11-15:
- `pytest` senza modello: `1003 passed, 90 deselected` in 86 s;
- `docker compose up -d --build`: quattro servizi attivi (`agent` e `postgres` healthy), pagina e
  `GET /chats` rispondono 200, agente non raggiungibile dall'host, `/status` dall'interno del
  container `ok` (MCP con 7 strumenti, modello `google/gemma-4-e2b`);
- branch: `dev` locale a `428cc8a` (un commit avanti a `origin/dev`, mai pubblicato); `main`
  locale, `origin/dev` e `origin/main` a `d3b511e`; catena lineare
  `d3b511e → 428cc8a → auto-claude`, quindi l'avanzamento rapido è possibile; branch locale
  `backup-locale` (`99d7334`, storia separata) non toccato da questo lavoro.

## 2. Obiettivi, non obiettivi, anti-obiettivi

Obiettivi:
- ogni step 4–9 e lo streaming letti da un revisore con contesto pulito, con un elenco di problemi
  verificati;
- prove reali ripetute (LM Studio, PostgreSQL, Edge e Chrome, streaming con Compose);
- scelte prese in autonomia che toccano il comportamento approvate o cambiate dall'utente;
- problemi confermati corretti in sessione, con l'approvazione dell'utente;
- `dev` portato su `auto-claude` con avanzamento rapido, poi push di `dev` e `main` **solo su
  richiesta dell'utente**;
- file del loop sistemati (CLAUDE.md, `loop.sh`, `PROMPT.md`, `TODO.md`).

Non obiettivi:
- nuove funzioni oltre la traccia della lezione 6, refactoring non legati a un problema
  confermato, miglioramenti di stile non richiesti;
- riscrivere la storia di `auto-claude` (messaggi o hash dei commit);
- toccare `backup-locale` o `lezione3/`.

Anti-obiettivi (il lavoro fallisce anche se «funziona»):
- pubblicare con un problema grave aperto, con un problema importante né corretto né accettato
  dall'utente come debito noto, o con una scelta del loop mai vista dall'utente;
- correzioni fatte senza il via libera dell'utente, o dal loop autonomo;
- contare come superata una prova reale fallita, o simularne l'esito;
- `--force`, merge automatici o push non richiesti.

## 3. Vincoli

- Regole di `CLAUDE.md`: Conventional Commits in italiano per i commit nuovi, `git status` e
  controllo del diff prima di ogni commit, staging selettivo, niente credenziali versionate.
- Tutto il lavoro, documenti compresi, si fa su `auto-claude`: un commit su `dev` prima
  dell'integrazione farebbe divergere i branch e impedirebbe l'avanzamento rapido.
- Prove reali attivate esplicitamente e separate dai test con il modello simulato; nel resoconto
  si distingue sempre che cosa è simulato e che cosa è reale.
- LM Studio resta sull'host; il modello è quello restituito da `GET /v1/models`
  (`google/gemma-4-e2b`).

## 4. Approcci

| Approccio | Come | Pro | Contro |
|-----------|------|-----|--------|
| **1 · Revisione per step + controlli trasversali (scelto)** | Quattro revisori con contesto pulito, ognuno su un gruppo di step e la sua specifica, più un elenco comune di controlli trasversali | Ogni problema si collega a una specifica e a un punto del diario; costo contenuto | I problemi trasversali sono visti a pezzi (mitigato dall'elenco comune, §6.1) |
| 2 · Revisione per tema | Quattro revisori su tutto il codice: correttezza, sicurezza, test, aderenza alle specifiche | Più forte sui problemi trasversali | Ogni revisore legge tutto: circa il doppio dei token, problemi mescolati tra step |
| 3 · Revisione unica | Una passata su tutto il diff più le prove reali | Costa molto meno | Su 20.000 righe vede poco: debole per l'obiettivo «sicuro» |
| Integrazione a tappe (scartata) | Correggere e pubblicare uno step alla volta | Valore pubblicato prima | Richiede di riscrivere `auto-claude` per inserire le correzioni prima degli step successivi, cioè cambiare gli hash che l'utente ha deciso di tenere |

L'utente ha scelto l'approccio 1 con i controlli trasversali (2026-11-15).

## 5. Decisioni

Prese con l'utente il 2026-11-15, salvo dove è indicato «scelta del progettista».

| Tema | Decisione | Motivo |
|------|-----------|--------|
| Che cosa significa «sicuro» | I quattro criteri di uscita del §7 | Definiti con l'utente |
| Chi corregge | Claude in sessione, dopo il via libera dell'utente su ogni correzione; niente loop autonomo | Il loop rifarebbe lavoro non letto |
| Messaggi dei commit del loop | Restano come sono (33 su 35 non seguono i Conventional Commits); l'eccezione si annota in `PROGRESS.md` | Riscriverli cambierebbe gli hash citati nel diario e in CLAUDE.md |
| Integrazione | Una sola, alla fine, con `git merge --ff-only`; push solo su richiesta | Regole di Git di `CLAUDE.md` |
| Specifiche | Due giri: questa specifica ora; una seconda specifica breve per le correzioni, dopo revisione, prove e rilettura | Le correzioni dipendono da ciò che si troverà |
| Prova dell'avviso del revisore nel browser | Al massimo tre tentativi con il modello vero; se non si ottiene, resta coperta dai test con il modello simulato ed è scritta come «non dimostrata con il modello vero» | Con `gemma-4-e2b` un rifiuto del revisore non è deterministico |
| Prove reali instabili (scelta del progettista) | Una prova reale che fallisce si ripete una volta: se passa, è «instabile» e annotata; se fallisce di nuovo, diventa un problema da valutare (§6.1) | Con un modello piccolo un fallimento non è per forza un difetto, ma non si nasconde |
| Rapporto della revisione (scelta del progettista) | Un file `docs/superpowers/reviews/2026-11-15-auto-claude.md`, versionato su `auto-claude` | I problemi devono restare consultabili mentre si correggono |
| Gravità dei problemi | Tre livelli: **grave**, **importante**, **minore** (§6.1), assegnati da Claude nella verifica; l'utente può cambiarli con un motivo scritto nel rapporto | Serve una soglia chiara per il criterio di uscita |
| Che cosa si corregge | Un problema **grave** confermato si corregge sempre prima del push; uno **importante** si corregge oppure l'utente lo accetta come debito noto, scritto in `TODO.md` con il motivo; i **minori** si correggono solo se l'utente lo chiede | Deciso dall'utente il 2026-11-15 |
| Revisione delle correzioni (scelta del progettista, delegata dall'utente) | Un revisore con contesto pulito sul diff delle correzioni di F4; un problema grave o importante trovato si corregge e si rivede solo quella correzione; dopo due giri senza chiudere, ci si ferma e si chiede all'utente | Le correzioni possono toccare più step e nessuno le avrebbe lette oltre a chi le scrive |
| Problemi nel codice già pubblicato (scelta del progettista, delegata dall'utente) | I problemi nel codice degli step 1–3 (già su `main`) vanno in una sezione a parte del rapporto e non bloccano l'integrazione; finiscono in `TODO.md`, salvo che l'utente voglia correggerli subito. Eccezione: un problema grave che il lavoro del loop rende raggiungibile in modo nuovo (per esempio attraverso il servizio HTTP o il back-end) conta come gli altri | Quel codice è già pubblicato: integrare non cambia il suo rischio, salvo nuove vie per raggiungerlo |

## 6. Fasi

Ordine: F1 e F2 in parallelo → F3 → F4 → F5 → F6. Ogni fase si chiude con una sezione in
`PROGRESS.md` (che cosa è stato eseguito, con quale esito, che cosa resta).

### 6.1 F1 · Revisione indipendente

Quattro revisori con contesto pulito (subagenti in sola lettura), lanciati insieme. Ognuno riceve
il proprio intervallo di commit, la specifica del suo step, la traccia (`lezione6.md`), le sezioni
di `PROGRESS.md` del suo step e l'elenco dei controlli trasversali. Legge il diff dell'intervallo
e il codice **nello stato finale di `auto-claude`** (gli step successivi possono aver cambiato i
file), più test e README per la sua parte.

| Gruppo | Commit (intervallo `da..a`) | Specifiche | Area principale |
|--------|-----------------------------|------------|-----------------|
| A · Step 4 e 5 | `290ce59..3aa8ea1` | `preferenze`, `prompt-mcp` | `mcp_server.py`, `mcp_client.py`, `preferences.py`, `prompts.py`, `commands.py`, `terminal.py`, `data/` |
| B · Step 6 | `3aa8ea1..83475a4` | `servizio-http` | `agent.py`, `api.py`, `service.py`, `api_client.py`, `session.py`, `__main__.py` |
| C · Step 7 e 9 | `83475a4..26df4da` e `c27fbc5..8efaa19` | `backend-chat`, `compose` | `backend/`, `docker/`, `compose.yaml`, `.env.example` |
| D · Step 8 e streaming | `26df4da..c27fbc5` e `8efaa19..c53cc0a` | `frontend-chat`, `streaming` | `frontend/`, streaming in `agent.py`, `api.py`, `api_client.py`, `backend/api.py` |

Il commit `290ce59` (setup del loop) e i due commit di documentazione finali (`b07ed36`,
`30bad78`) non sono revisionati come codice: li tratta F6.

Che cosa controlla ogni revisore:
- aderenza a traccia e specifica (ogni evidenza richiesta dalla traccia è dimostrata da un test o
  da una prova reale registrata);
- correttezza: casi d'errore, concorrenza, risorse non chiuse, comportamento con input limite;
- test: provano davvero ciò che dichiarano (non solo il modello simulato che restituisce ciò che
  il test si aspetta), nessun test che dipende da servizi attivi senza marcatore;
- README e CLAUDE.md per la sua parte: comandi coerenti con il codice.

Controlli trasversali (in ogni revisione, per la propria area):
- segreti o credenziali versionati (`.env`, password in `compose.yaml`, README, test, log);
- porte: pubblicate solo su `127.0.0.1`, agente non esposto;
- CORS limitato a `CORS_ORIGINS`;
- errori tra i servizi: timeout, codici HTTP, messaggi, stato salvato coerente dopo un errore;
- input non controllati che arrivano a SQL, shell, file system o HTML (nel front-end: testo
  inserito come HTML);
- dipendenze nuove motivate e con versione fissata in `requirements*.txt` e `constraints.txt`;
- confini tra pacchetti (`assistant` non importa `backend`; `frontend` non importa `backend`);
- log senza dati sensibili.

Forma dei risultati (uno per problema): gravità, file e riga, che cosa succede e in quale scenario
concreto, riferimento alla specifica o alla traccia, correzione suggerita in una riga. Nessuna
modifica ai file. Gravità:
- **grave**: dati persi o corrotti, credenziali esposte, servizio esposto oltre il previsto,
  servizio che non parte, evidenza della traccia non soddisfatta;
- **importante**: comportamento sbagliato in un caso realistico, errore non gestito che arriva
  all'utente, test che non prova ciò che dichiara, comando documentato che non funziona;
- **minore**: semplificazioni, nomi, duplicazioni, testi.

Un problema in codice che esisteva già a `428cc8a` (step 1–3) si segnala a parte, come
«codice già pubblicato» (regola del §5), indicando se il lavoro del loop lo rende raggiungibile in
modo nuovo.

Verifica: Claude controlla ogni problema sul codice (e, se serve, con un test o un comando) e lo
segna **confermato**, **falso positivo** (con il motivo) o **da decidere** (dipende da una scelta
dell'utente). Il rapporto del §5 raccoglie tutto, compresi i falsi positivi.

### 6.2 F2 · Prove reali di riferimento

In parallelo a F1 (i revisori non usano LM Studio). Prima: `docker compose down` (Compose occupa le
porte 8001 e 8080 usate dalle prove), container `assistente-postgres` avviato (porta 5433),
variabili di LM Studio e `TEST_DATABASE_URL` impostate come in `CLAUDE.md`.

1. Suite reale completa: `pytest -m real -v` (65 prove, circa 40 minuti; compresi back-end,
   front-end con Edge e streaming).
2. Pagina con Chrome: `BROWSER_CHANNEL=chrome`, `pytest -m browser` (25 prove, modello simulato) e
   `pytest tests/test_real.py -m real -k frontend` (modello vero).
3. Streaming con Compose: `docker compose up -d --build`, conversazione dalla pagina su
   `http://127.0.0.1:8080` con una domanda che usa uno strumento; evidenze: bozza che compare e si
   aggiorna, strumento indicato, risposta salvata alla fine (presente dopo il ricaricamento),
   chiamata visibile in `docker compose logs agent`.
4. Avviso del revisore con il modello vero: fino a tre tentativi con una domanda in due parti
   (regola del §5).

Gli esiti, con le prove instabili, vanno in `PROGRESS.md`; un fallimento confermato diventa un
problema del rapporto di F1.

### 6.3 F3 · Rilettura guidata con l'utente

Una scheda per ogni scelta presa dal loop che tocca il comportamento, con il testo prima e dopo e
il motivo annotato nel diario:
1. ambito del router allargato in `assistant/data/scope.txt` (spiegazioni di informatica e IA,
   riassunti della conversazione);
2. testi dei prompt cambiati per far passare le prove reali (Step 4 e 5);
3. dipendenze nuove: `fastapi`, `uvicorn`, `httpx`, `SQLAlchemy`, `psycopg[binary]`,
   `playwright` (solo test);
4. `POSTGRES_PASSWORD` obbligatoria per ogni comando `docker compose`;
5. bozza mostrata durante lo streaming, con il revisore attivo;

più i problemi di F1 segnati «da decidere» e i problemi importanti confermati. Per ognuno
l'utente decide: tenere, cambiare (come), oppure accettare come debito noto (non per i problemi
gravi, che si correggono sempre). Le decisioni vanno in `PROGRESS.md`.

### 6.4 F4 · Correzioni

Seconda specifica breve (`2026-11-1x-correzioni-auto-claude-design.md`) con l'elenco delle
correzioni da fare: problemi gravi confermati, problemi importanti che l'utente non ha accettato
come debito, scelte da cambiare decise in F3, problemi minori che l'utente vuole correggere. Dopo
l'approvazione, un piano; poi le correzioni in sessione, con un test che fallisce prima di ogni
correzione di comportamento, commit su `auto-claude` in Conventional Commits. Alla fine, revisione
del diff delle correzioni da un revisore con contesto pulito (regola del §5). Se non c'è nulla da
correggere, F4 si salta e lo si scrive.

### 6.5 F5 · Sistemazione dei file del loop

Su `auto-claude`, prima dell'integrazione, così che entri nello stesso avanzamento rapido:
- `CLAUDE.md`: la sezione «Modalità autonoma» diventa una nota storica di due righe (che cosa ha
  fatto il loop, dove sono `PROGRESS.md` e l'archivio); restano valide le regole normali (lavoro su
  `dev`, approvazioni);
- `loop.sh` e `PROMPT.md` → `_archivio/` con `git mv`; la regola `*.sh` di `.gitattributes` resta
  (innocua);
- `TODO.md`: punti fatti riassunti in «Già fatto», nessun punto aperto oltre a quelli decisi in F3
  come debito noto;
- `PROGRESS.md`: nota sui messaggi dei commit del loop; «Stato attuale» aggiornato;
- `docs/superpowers/prossimo-prompt.txt` aggiornato o archiviato;
- README: `assistente-postgres` descritto come container separato da Compose, usato solo dalle
  prove reali del back-end (porta 5433); il container resta.

### 6.6 F6 · Verifica finale e integrazione

1. Se dopo F2 è cambiato codice (non solo documentazione): test senza modello, suite reale
   completa, pagina con Edge e Chrome e streaming con Compose ripetuti. Altrimenti bastano i test
   senza modello e valgono gli esiti di F2.
2. Controllo dei criteri del §7; resoconto all'utente.
3. `git switch dev`, `git merge --ff-only auto-claude`, test senza modello su `dev`.
4. Solo su richiesta dell'utente: `git push origin dev`, `git push origin dev:main`,
   `git fetch origin main:main`. Il push porta online anche `428cc8a`. Se l'avanzamento rapido di
   `main` viene rifiutato: fermarsi e chiedere.
5. Dopo il push, su conferma dell'utente: cancellare il branch locale `auto-claude` (o tenerlo).

## 7. Criteri di uscita («sicuro»)

1. **Revisione chiusa**: nessun problema grave confermato aperto, né nel lavoro del loop né nelle
   correzioni (con l'eccezione del §5 per il codice già pubblicato); ogni problema importante
   corretto o accettato dall'utente come debito noto in `TODO.md`; ogni altro problema corretto,
   falso positivo motivato o lasciato con la decisione dell'utente.
2. **Scelte approvate**: le cinque scelte del §6.3 e i punti «da decidere» hanno una decisione
   dell'utente.
3. **Prove ripetute**: dopo l'ultima modifica al codice, test senza modello tutti verdi, suite
   reale completa senza fallimenti confermati, pagina con Edge e Chrome, streaming con Compose; le
   prove instabili sono elencate.
4. **Integrazione pulita**: solo avanzamento rapido, test verdi su `dev`, push eseguito solo su
   richiesta.

## 8. Costi stimati

| Fase | Tempo | Token | Note |
|------|-------|-------|------|
| F1 | 30–45 min | 1–2 milioni | Quattro revisori più la verifica dei problemi |
| F2 | 60–75 min | pochi | Soprattutto attesa del modello |
| F3 | 30–60 min dell'utente | circa 100.000 | |
| F4 | dipende dai problemi | dipende, più 200.000–400.000 per la revisione delle correzioni | Specifica e piano propri |
| F5 | 15–30 min | pochi | |
| F6 | 10 min senza codice cambiato, circa 75 min con le prove ripetute | pochi | |

## 9. Lasciato al costruttore del piano

- Testo dei prompt dei revisori (entro §6.1) e formato esatto del rapporto.
- Domande e passi della conversazione nella prova dello streaming con Compose, e strumento per
  guidare la pagina (a mano o con uno script Playwright temporaneo fuori dalla repository).
- Domanda in due parti per l'avviso del revisore.
- Suddivisione in commit della documentazione di ogni fase.

## 10. Rischi

- Falsi positivi della revisione: mitigati dalla verifica di ogni problema (§6.1).
- Prove reali instabili con un modello piccolo: regola del §5; un'instabilità ripetuta su una
  stessa prova si segnala all'utente.
- Prove reali lunghe che si sovrappongono a Compose acceso: F2 spegne Compose prima di iniziare.
- Correzioni che toccano più step: la seconda specifica le elenca con i file coinvolti; i test
  senza modello girano dopo ogni correzione.
