# Revisione e integrazione di `auto-claude` — piano delle fasi F1–F3

> **Per chi esegue:** eseguire con superpowers:executing-plans, un task alla volta; i passi usano
> le caselle (`- [ ]`). Questo piano non modifica codice: produce un rapporto, gli esiti delle
> prove reali e le decisioni dell'utente, che diventano l'ingresso della specifica delle
> correzioni (F4).

**Obiettivo:** sapere con evidenze che cosa va corretto prima di pubblicare `auto-claude` su `main`.

**Architettura:** quattro revisori con contesto pulito (subagenti in sola lettura) lavorano in
background mentre nella sessione girano le prove reali; poi Claude verifica ogni problema, scrive
il rapporto e guida l'utente nella rilettura delle scelte del loop.

**Strumenti:** Agent (subagenti `general-purpose`), pytest (marcatori `real` e `browser`),
Playwright con Edge e Chrome, Docker Compose, LM Studio (`google/gemma-4-e2b`), PostgreSQL nel
container `assistente-postgres` (porta 5433).

**Specifica:** [`../specs/2026-11-15-revisione-integrazione-design.md`](../specs/2026-11-15-revisione-integrazione-design.md)

## Vincoli globali

- Branch `auto-claude` per tutto; nessun commit su `dev` o `main`, nessun push, nessun merge.
- Nessuna modifica a codice, test, configurazione o README in questo piano: solo
  `docs/superpowers/reviews/2026-11-15-auto-claude.md` e `PROGRESS.md`.
- I revisori non modificano file e non eseguono prove reali né comandi Docker; possono eseguire
  test senza modello (`pytest` con selezione) per verificare un dubbio.
- Gravità: **grave**, **importante**, **minore** (specifica §6.1); un grave confermato si corregge
  sempre, un importante si corregge o l'utente lo accetta come debito noto (§5).
- Problemi nel codice già esistente a `428cc8a`: sezione «Codice già pubblicato», non bloccano,
  salvo un grave reso raggiungibile in modo nuovo dal lavoro del loop (§5).
- Prova reale fallita: si ripete una volta; se passa è «instabile», se fallisce di nuovo diventa un
  problema del rapporto (§5).
- Commit nuovi in Conventional Commits in italiano, con `git status`, controllo del diff e staging
  selettivo; i messaggi dei commit del loop non si toccano.
- Comandi da PowerShell nella radice della repository, Python dall'ambiente:
  `.\.venv\Scripts\python.exe`.
- Nel resoconto si distingue sempre modello simulato da modello vero.

## Punti di attenzione

Condizioni che nessun task «prova» da solo ma che possono falsare il risultato:
1. Compose acceso durante le prove reali: le porte 8001 e 8080 occupate fanno fallire le prove del
   back-end e del front-end; Task 1 spegne Compose e controlla le porte.
2. LM Studio che scarica il modello per inattività a metà suite: Task 2 controlla
   `GET /v1/models` prima di ripetere una prova fallita.
3. Un revisore che segnala come problema una scelta già documentata nel diario: in verifica
   (Task 6) si cerca la scelta in `PROGRESS.md` e nella specifica; se c'è, il problema diventa
   «da decidere», non «confermato».
4. Un revisore che segnala come nuovo un problema degli step 1–3: in verifica si controlla con
   `git blame` o `git show 428cc8a:<file>` se il codice esisteva già.
5. Problemi duplicati tra gruppi (stesso file toccato da più step): nel rapporto si uniscono in un
   solo problema con tutti i gruppi che l'hanno visto.

---

### Task 0: Specifica e piano nel repository

**File:** `docs/superpowers/specs/2026-11-15-revisione-integrazione-design.md`,
`docs/superpowers/plans/2026-11-15-revisione-integrazione.md`

- [ ] **Passo 1:** `git status` e `git diff --stat`: solo i due file nuovi.
- [ ] **Passo 2:** commit.

```bash
git add docs/superpowers/specs/2026-11-15-revisione-integrazione-design.md docs/superpowers/plans/2026-11-15-revisione-integrazione.md
git commit -m "docs(revisione): specifica e piano della revisione e integrazione di auto-claude"
```

### Task 1: Ambiente per le prove reali

- [ ] **Passo 1:** `docker compose down` (i volumi restano). Atteso: quattro container rimossi;
  `docker compose ps` vuoto.
- [ ] **Passo 2:** porte libere: `Get-NetTCPConnection -LocalPort 8000,8001,8080 -State Listen`
  non restituisce nulla (errore «No matching» accettato).
- [ ] **Passo 3:** `docker start assistente-postgres`, poi
  `docker exec assistente-postgres pg_isready -U lab -d assistente`. Atteso:
  «accepting connections».
- [ ] **Passo 4:** `Invoke-RestMethod http://localhost:1234/v1/models`: la lista contiene
  `google/gemma-4-e2b`.
- [ ] **Passo 5:** variabili della sessione di PowerShell usata per i Task 3–5:

```powershell
$env:LMSTUDIO_BASE_URL = "http://localhost:1234/v1"
$env:LMSTUDIO_MODEL = "google/gemma-4-e2b"
$env:TEST_DATABASE_URL = "postgresql://lab:labprova@127.0.0.1:5433/assistente"
```

### Task 2: Revisori in background (F1)

**Interfacce:**
- Produce: quattro resoconti testuali, uno per gruppo, nel formato del Passo 2; li usa il Task 5.

- [ ] **Passo 1:** lanciare in un solo messaggio quattro Agent `general-purpose` con
  `run_in_background`, descrizione «Revisione gruppo A/B/C/D», usando il modello del Passo 2 e i
  dati di questa tabella:

| Gruppo | Intervalli di commit | Specifiche (`docs/superpowers/specs/`) | Sezioni di `PROGRESS.md` | File principali |
|--------|----------------------|----------------------------------------|--------------------------|-----------------|
| A · Step 4 e 5 | `290ce59..3aa8ea1` | `2026-11-14-preferenze-design.md`, `2026-11-14-prompt-mcp-design.md` | «Step 4», «Step 5» | `assistant/mcp_server.py`, `mcp_client.py`, `preferences.py`, `prompts.py`, `commands.py`, `terminal.py`, `assistant/data/` |
| B · Step 6 | `3aa8ea1..83475a4` | `2026-11-14-servizio-http-design.md` | «Step 6» | `assistant/agent.py`, `api.py`, `service.py`, `api_client.py`, `session.py`, `__main__.py` |
| C · Step 7 e 9 | `83475a4..26df4da`, `c27fbc5..8efaa19` | `2026-11-14-backend-chat-design.md`, `2026-11-14-compose-design.md` | «Step 7», «Step 9» | `backend/`, `docker/`, `compose.yaml`, `.env.example`, `.dockerignore` |
| D · Step 8 e streaming | `26df4da..c27fbc5`, `8efaa19..c53cc0a` | `2026-11-14-frontend-chat-design.md`, `2026-11-14-streaming-design.md` | «Step 8», «Facoltativo · Streaming» | `frontend/`, streaming in `assistant/agent.py`, `api.py`, `api_client.py`, `backend/api.py` |

- [ ] **Passo 2:** modello del prompt (sostituire i campi tra `<…>`):

```text
Sei un revisore di codice esperto di Python, FastAPI, LangGraph, SQLAlchemy, JavaScript del
browser e Docker. Lavori in sola lettura sulla repository
C:\Users\diegorosiglioni\Desktop\paolo\test_paolo, branch auto-claude: non modificare file, non
fare commit, non eseguire prove reali (marcatori real e browser), Docker o servizi. Puoi eseguire
test senza modello con .\.venv\Scripts\python.exe -m pytest <selezione> per chiarire un dubbio.

Contesto: il codice è stato scritto da un loop autonomo senza revisione umana. Il tuo gruppo è
<gruppo>. Leggi: CLAUDE.md; docs/superpowers/lezione6.md (traccia del docente, parte del tuo
step); le specifiche <specifiche>; le sezioni <sezioni> di PROGRESS.md (piano, decisioni ed esiti
del loop); il diff di <intervalli> (git diff <da> <a>, git log <da>..<a>); il codice nello stato
finale di auto-claude per <file principali>, con test e README della tua parte. Guarda anche i
punti di contatto con gli step vicini (contratti tra CLI, agente, back-end e front-end).

Controlla:
1. aderenza a traccia e specifica: ogni evidenza richiesta dalla traccia è dimostrata da un test o
   da una prova reale registrata nel diario;
2. correttezza: casi d'errore, concorrenza, risorse non chiuse, input limite;
3. test: provano davvero ciò che dichiarano; nessun test che dipende da servizi attivi senza
   marcatore;
4. README e CLAUDE.md della tua parte: comandi coerenti con il codice;
5. controlli trasversali per la tua area: segreti o credenziali versionati; porte pubblicate solo
   su 127.0.0.1 e agente non esposto; CORS limitato a CORS_ORIGINS; errori tra i servizi (timeout,
   codici HTTP, messaggi, stato salvato coerente dopo un errore); input che arrivano a SQL, shell,
   file system o HTML senza controllo; dipendenze nuove motivate e fissate in requirements*.txt e
   constraints.txt; confini tra pacchetti (assistant non importa backend, frontend non importa
   backend); log senza dati sensibili.

Una scelta già motivata nella specifica o nel diario non è un difetto in sé: se la ritieni
sbagliata, segnalala con "scelta documentata" e il motivo. Se il problema è in codice che esisteva
già prima di 428cc8a (git show 428cc8a:<file>), segnalo con "codice già pubblicato" e di' se il
lavoro del loop lo rende raggiungibile in modo nuovo.

Gravità: grave = dati persi o corrotti, credenziali esposte, servizio esposto oltre il previsto,
servizio che non parte, evidenza della traccia non soddisfatta; importante = comportamento
sbagliato in un caso realistico, errore non gestito che arriva all'utente, test che non prova ciò
che dichiara, comando documentato che non funziona; minore = semplificazioni, nomi, duplicazioni,
testi.

Rispondi in italiano con un elenco di problemi, dal più grave, ciascuno così:
- Gravità: grave | importante | minore
- Dove: file:riga
- Che cosa succede: scenario concreto (input o stato → risultato sbagliato)
- Riferimento: sezione della specifica o della traccia, oppure "nessuno"
- Etichette: "scelta documentata" e/o "codice già pubblicato", se valgono
- Correzione suggerita: una riga
Chiudi con l'elenco delle evidenze della traccia del tuo step e, per ognuna, il test o la prova
reale che la dimostra. Se non trovi problemi, dillo.
```

- [ ] **Passo 3:** non leggere i file di output dei subagenti; attendere le notifiche di fine e
  proseguire intanto con i Task 3–5.

### Task 3: Suite reale completa con Edge (F2, punto 1)

- [ ] **Passo 1:** in background, dalla sessione del Task 1:
  `.\.venv\Scripts\python.exe -m pytest -m real -v 2>&1 | Tee-Object <scratchpad>\real-edge.txt`.
  Atteso: `65 passed` (circa 40 minuti).
- [ ] **Passo 2:** per ogni prova fallita: controllare `GET /v1/models` (punto di attenzione 2),
  poi ripeterla una volta con `pytest "<nodeid>" -m real -v`. Passa → «instabile»; fallisce →
  problema per il rapporto, con l'uscita del test.
- [ ] **Passo 3:** annotare esiti, durata e prove instabili (servono al Task 5).

### Task 4: Pagina con Chrome (F2, punto 2)

Dopo il Task 3 (le prove reali del front-end usano le stesse porte).

- [ ] **Passo 1:** `$env:BROWSER_CHANNEL = "chrome"`, poi
  `.\.venv\Scripts\python.exe -m pytest -m browser -v`. Atteso: `25 passed` (modello simulato).
- [ ] **Passo 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_real.py -m real -k frontend -v`.
  Atteso: tutte le prove `frontend` passate, compresa `test_frontend_stream_from_the_browser`
  (modello vero).
- [ ] **Passo 3:** `Remove-Item Env:BROWSER_CHANNEL`; esiti annotati con la regola delle prove
  instabili.

### Task 5: Streaming con Compose e avviso del revisore (F2, punti 3 e 4)

- [ ] **Passo 1:** `docker compose up -d --build`; `docker compose ps`: `agent` e `postgres`
  healthy, `backend` e `frontend` Up.
- [ ] **Passo 2:** script temporaneo `<scratchpad>\compose_stream.py` (fuori dalla repository),
  eseguito con `.\.venv\Scripts\python.exe`: Playwright con Edge su `http://127.0.0.1:8080`, stessi
  selettori di `tests/test_real.py::test_frontend_stream_from_the_browser` (`Nuova chat`,
  `#message-input`, `#draft`, `#messages .message-text`, `#error`). Domanda «Quanto fa 17 * 23?».
  Atteso: `#draft` visibile durante la risposta; poi due messaggi, `#draft` assente, `#error`
  nascosto, risposta con «391» e `calculate` tra gli strumenti; dopo `page.reload()` la chat ha
  ancora i due messaggi.
- [ ] **Passo 3:** `docker compose logs agent` contiene la chiamata a `calculate` del turno.
- [ ] **Passo 4:** avviso del revisore, fino a tre tentativi nello stesso script, ognuno in una
  chat nuova, con domande in più parti (per esempio «Quanto fa 17 * 23, quanti metri sono 3 miglia
  e che ore sono a Tokyo?»). Successo: nel log di `agent` una riga `node=reviewer`
  `coherent=false` e, nella pagina, l'avviso del revisore nella bozza prima della risposta finale.
  Senza successo dopo tre tentativi: «non dimostrato con il modello vero», coperto da CA-99 e
  CA-100 (modello simulato).
- [ ] **Passo 5:** `docker compose down`; `docker stop assistente-postgres`.

### Task 6: Verifica dei problemi e rapporto (F1)

Dopo le quattro notifiche del Task 2.

**File:** crea `docs/superpowers/reviews/2026-11-15-auto-claude.md`; modifica `PROGRESS.md`.

**Interfacce:**
- Consuma: i quattro resoconti del Task 2, gli esiti dei Task 3–5.
- Produce: il rapporto, letto da Task 7 e dalla specifica delle correzioni; ogni problema ha un
  identificativo `R-<gruppo><numero>` (per esempio `R-C3`), usato in tutti i documenti successivi.

- [ ] **Passo 1:** per ogni problema: aprire il codice a quella riga, verificare lo scenario
  (lettura, un test senza modello o un comando se serve), applicare i punti di attenzione 3–5,
  assegnare stato (**confermato**, **falso positivo** con motivo, **da decidere**) e gravità
  definitiva.
- [ ] **Passo 2:** scrivere il rapporto con queste sezioni:
  1. Sintesi: numeri per gravità e stato, esiti delle prove reali (simulato e reale separati);
  2. Problemi confermati, dal più grave: identificativo, gravità, gruppo, `file:riga`, scenario,
     riferimento, correzione suggerita;
  3. Da decidere (scelte documentate e dubbi);
  4. Codice già pubblicato (step 1–3), con l'indicazione «raggiungibile in modo nuovo» o no;
  5. Falsi positivi, con il motivo;
  6. Evidenze della traccia per step, con il test o la prova che le dimostra;
  7. Prove reali del 2026-11-15: comandi, esiti, prove instabili, che cosa resta non dimostrato.
- [ ] **Passo 3:** in `PROGRESS.md`, nuova sezione «Revisione e integrazione (2026-11-15)» con:
  che cosa è stato eseguito, esiti, rimando al rapporto; «Stato attuale» aggiornato (prossimo:
  rilettura con l'utente).
- [ ] **Passo 4:** `git status`, `git diff`, commit:

```bash
git add docs/superpowers/reviews/2026-11-15-auto-claude.md PROGRESS.md
git commit -m "docs(revisione): rapporto della revisione e delle prove reali di auto-claude"
```

- [ ] **Passo 5:** resoconto all'utente: problemi gravi e importanti confermati per primi, poi i
  numeri del resto, esiti delle prove; nessuna correzione.

### Task 7: Rilettura guidata con l'utente (F3)

**Interfacce:**
- Consuma: il rapporto del Task 6.
- Produce: una decisione per ogni scheda (tenere, cambiare e come, debito noto), registrata in
  `PROGRESS.md`; è l'ingresso della specifica delle correzioni.

- [ ] **Passo 1:** una scheda per messaggio, ognuna con: che cosa ha deciso il loop, testo o
  codice prima e dopo (`git diff 428cc8a auto-claude -- <file>`), motivo dal diario, effetto per
  chi usa l'applicazione, mia raccomandazione. Ordine:
  1. ambito del router in `assistant/data/scope.txt`;
  2. testi dei prompt cambiati per le prove reali (Step 4 e 5: righe del diario «testi cambiati»,
     diff di `assistant/prompts.py` e dei prompt di sistema);
  3. dipendenze nuove: `fastapi`, `uvicorn`, `httpx`, `SQLAlchemy`, `psycopg[binary]`,
     `playwright`, con motivo e versione;
  4. `POSTGRES_PASSWORD` obbligatoria per ogni comando `docker compose`;
  5. bozza mostrata durante lo streaming con il revisore attivo, con l'esito del Task 5, passo 4;
  6. poi i problemi «da decidere» e gli importanti confermati del rapporto, uno per scheda o a
     gruppi se l'utente preferisce.
- [ ] **Passo 2:** dopo ogni risposta, annotare la decisione nella sezione «Revisione e
  integrazione» di `PROGRESS.md` (identificativo, decisione, motivo dell'utente); i debiti noti
  vanno anche nel rapporto, con il motivo.
- [ ] **Passo 3:** a schede finite, commit:

```bash
git add PROGRESS.md docs/superpowers/reviews/2026-11-15-auto-claude.md
git commit -m "docs(revisione): decisioni dell'utente sulle scelte del loop e sui problemi"
```

### Task 8: Passaggio alle correzioni (F4)

- [ ] **Passo 1:** elenco delle correzioni: gravi confermati, importanti non accettati come debito,
  scelte da cambiare (Task 7), minori richiesti.
- [ ] **Passo 2:** se l'elenco non è vuoto: brainstorming breve e specifica
  `docs/superpowers/specs/2026-11-1x-correzioni-auto-claude-design.md`, da approvare; poi piano con
  writing-plans, che comprende anche la revisione delle correzioni, la sistemazione dei file del
  loop (F5) e la verifica finale con l'integrazione (F6) della specifica di oggi.
- [ ] **Passo 3:** se l'elenco è vuoto: annotarlo in `PROGRESS.md` e scrivere un piano breve solo
  per F5 e F6.
