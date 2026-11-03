# Correzioni dell'audit — Piano di implementazione

> **Per gli agenti esecutori:** SOTTO-SKILL RICHIESTA: usare superpowers:subagent-driven-development
> (consigliata) o superpowers:executing-plans per eseguire il piano task per task. I passi usano
> le caselle (`- [ ]`) per il tracciamento.

**Obiettivo:** versioni identiche nel venv e nell'immagine Docker, `httpx2` dichiarato nei test,
indirizzo di LM Studio configurabile nel container e niente cache Python nell'immagine, senza
cambiare il comportamento dell'applicazione.

**Architettura:** `constraints.txt` (il `pip freeze` del venv verificato) richiamato da
`requirements.txt`; immagine base fissata per tag e digest; interpolazione con default in
`compose.yaml`; pattern ricorsivi in `.dockerignore`. Il codice in `assistente/` non cambia.

**Tecnologie:** pip (file di vincoli `-c`), Docker Compose (`${VAR:-default}`), pytest.

**Specifica:** [`../specs/2026-11-03-correzioni-audit-design.md`](../specs/2026-11-03-correzioni-audit-design.md),
che modifica la specifica di base [`../specs/2026-10-26-assistente-laboratorio-design.md`](../specs/2026-10-26-assistente-laboratorio-design.md).
L'esecutore legge entrambe.

## Vincoli globali

- Tutto il lavoro sta in `assistente-laboratorio/`, più la riga di `CLAUDE.md` sulle dipendenze
  (CLAUDE.md:72 lo consente). `lezione3/` non si legge né si modifica.
- Branch `main`, nessun branch o worktree nuovo. Nessun push.
- Comandi da PowerShell in `assistente-laboratorio/`, con `.\.venv\Scripts\python.exe` senza
  attivare l'ambiente. `$tmp` è una cartella temporanea fuori dal repository (lo scratchpad
  della sessione).
- Versioni: quelle del venv attuale (Python 3.13.14), su cui il 2026-11-03 passano 60 test e 2
  prove reali. Nessun aggiornamento.
- Immagine base: `python:3.13.18-slim-trixie@sha256:ae14d4ce8771606477a81446e7ef429edd6762305fc50c84507c1041fa8285d1`.
- Il `.env` dell'utente non si modifica e non si stampa: dall'output di `docker compose config`
  si mostrano solo le righe con `LMSTUDIO_BASE_URL`.
- Prima di ogni commit: `git status --short`, `git add` dei soli file del task, `git diff --cached`
  letto per intero, poi il commit (Conventional Commits in italiano, con la riga `Co-Authored-By`).
- Servono LM Studio con `google/gemma-4-e2b` e Docker Desktop attivi. Variabili per le prove reali:
  `$env:LMSTUDIO_BASE_URL = "http://localhost:1234/v1"`, `$env:LMSTUDIO_MODELLO = "google/gemma-4-e2b"`.

## Attenzione in revisione

1. Installazione da zero su Windows (venv nuovo) con il comando documentato: deve installare
   esattamente le versioni di `constraints.txt`. Task 1, passo 6.
2. Requirements e constraints che divergono: pip deve fermarsi con un errore, non installare in
   silenzio. Task 1, passo 7.
3. `.env` già esistente, nato dal vecchio `.env.example` con `LMSTUDIO_BASE_URL=http://localhost:1234/v1`:
   nel container l'URL deve restare `http://host.docker.internal:1234/v1`. Task 3, passo 4.
4. `LMSTUDIO_BASE_URL_DOCKER` presente ma vuota: deve valere il default, non un URL vuoto (che
   farebbe uscire l'app con «Manca LMSTUDIO_BASE_URL»). Task 3, passo 4.
5. Dopo le modifiche a Dockerfile e Compose: configurazione errata nel container ancora con exit 1,
   utente non root, in `/app` solo `assistente`, `constraints.txt`, `requirements.txt`. Task 1,
   passo 9, e Task 4, passo 4.

---

## Prima del Task 1

Commit del piano e dello stato della specifica (`Stato: approvata`):
`docs: aggiunge il piano delle correzioni dell'audit`.

## Incremento 1 — Dipendenze (I1, M1)

### Task 1: `constraints.txt` e immagine base fissata (I1)

**File:**
- Crea: `assistente-laboratorio/constraints.txt`
- Modifica: `assistente-laboratorio/requirements.txt` (prime righe), `assistente-laboratorio/Dockerfile:1,9-10`
- Modifica: `assistente-laboratorio/README.md` (sezione «Installazione»), `CLAUDE.md:12`
- Modifica: specifica di base, §9 (riga «Base `python:3.13-slim`») e §12 («Versioni delle dipendenze»)

**Interfacce:**
- Produce: `constraints.txt`, richiamato da `requirements.txt` con `-c constraints.txt`. Il Task 2
  lo usa senza modificarlo: contiene già `httpx2==2.16.0`.

- [ ] **Passo 1: rosso.** Confronto tra venv e immagine attuale:
  `Compare-Object (.\.venv\Scripts\python.exe -m pip freeze) (docker compose run --rm -T assistente pip freeze)`.
  Atteso: oltre ai 5 pacchetti solo locali (`colorama`, `iniconfig`, `pluggy`, `Pygments`, `pytest`),
  9 coppie di versioni diverse (anyio, jsonpatch, jsonpointer, langgraph-checkpoint, langgraph-sdk,
  langsmith, pydantic, pydantic_core, websockets).
- [ ] **Passo 2: generare `constraints.txt`** con il comando della specifica §2.1, lo stesso che va
  nel README:
  `@("# Versioni verificate: rigenerare con il comando del README, sezione Installazione.") + (.\.venv\Scripts\python.exe -m pip freeze) | Out-File -Encoding ascii constraints.txt`.
  Atteso: 50 righe (commento più 49 pacchetti), tra cui `langgraph==1.2.17`, `pydantic==2.14.1`,
  `httpx2==2.16.0`, `pytest==9.1.1`.
- [ ] **Passo 3: `requirements.txt`.** Prime due righe:
  `# Tutte le versioni verificate, anche le indirette: vedi constraints.txt` e `-c constraints.txt`.
  Il resto non cambia.
- [ ] **Passo 4: `Dockerfile`.**
  - Riga 1: `FROM python:3.13.18-slim-trixie@sha256:ae14d4ce8771606477a81446e7ef429edd6762305fc50c84507c1041fa8285d1`.
  - Riga 9, commento: «… finché requirements.txt e constraints.txt non cambiano».
  - Riga 10: `COPY requirements.txt constraints.txt ./`.
- [ ] **Passo 5: venv invariato.**
  - `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt` → solo
    «Requirement already satisfied», nessun «Successfully installed».
  - `… -m pip check` → `No broken requirements found.`
  - `… -m pytest` → `60 passed, 2 deselected`.
- [ ] **Passo 6: installazione da zero (attenzione 1).**
  - `py -3.13 -m venv $tmp\venv-prova`
  - `& $tmp\venv-prova\Scripts\python.exe -m pip install -r requirements-dev.txt` → riuscita.
  - `Compare-Object (Get-Content constraints.txt | Select-Object -Skip 1) (& $tmp\venv-prova\Scripts\python.exe -m pip freeze)`
    → nessuna differenza.
  - Poi `Remove-Item -Recurse -Force $tmp\venv-prova`.
- [ ] **Passo 7: divergenza bloccata (attenzione 2).**
  - Copiare `requirements.txt` e `constraints.txt` in `$tmp\copia`.
  - Nella copia di `constraints.txt` cambiare `langgraph==1.2.17` in `langgraph==1.2.16`.
  - `.\.venv\Scripts\python.exe -m pip install --dry-run --no-index -r $tmp\copia\requirements.txt`
    → riga `ERROR:` e exit diverso da 0.
- [ ] **Passo 8: immagine.** `docker compose build` → exit 0.
- [ ] **Passo 9: verde (attenzione 5).**
  - Il confronto del passo 1 mostra solo i 5 pacchetti dei test, tutti con `<=`.
  - `docker compose run --rm -T assistente python --version` → `Python 3.13.18`.
  - `… ls -A /app` → `assistente`, `constraints.txt`, `requirements.txt`.
  - `… whoami` → `assistente`.
  - `docker compose run --rm -T -e LMSTUDIO_MODELLO= assistente` → «Configurazione non valida: Manca
    LMSTUDIO_MODELLO.», `$LASTEXITCODE` 1.
  - `"Che ore sono a Tokyo?", "esci" | docker compose run --rm -T assistente` → log
    `chiamata ora_corrente {'fuso': 'Asia/Tokyo'}` e risposta con l'orario restituito.
- [ ] **Passo 10: documenti.**
  - README, «Installazione», dopo il paragrafo sui requirements: `requirements.txt` richiama
    `constraints.txt`, che fissa tutte le versioni verificate, anche le indirette, così venv e
    immagine Docker installano gli stessi pacchetti. Poi il comando di rigenerazione del passo 2
    in un blocco PowerShell e la frase «Per cambiare una versione: aggiornare i requirements,
    svuotare `constraints.txt`, reinstallare, ripetere le verifiche e rigenerarlo.»
  - `CLAUDE.md:12` diventa: «Dipendenze dirette in `requirements.txt` (app) e `requirements-dev.txt`
    (test); tutte le versioni verificate in `constraints.txt`, richiamato da `requirements.txt`.»
  - Specifica di base §9 (immagine) e §12 (versioni): nota «*Rivisto il 2026-11-03: vedi
    [`2026-11-03-correzioni-audit-design.md`](2026-11-03-correzioni-audit-design.md) §2.1.*»
- [ ] **Passo 11: commit**, `build(dipendenze): fissa le versioni verificate con constraints.txt e l'immagine base`.
  File: `assistente-laboratorio/constraints.txt`, `assistente-laboratorio/requirements.txt`,
  `assistente-laboratorio/Dockerfile`, `assistente-laboratorio/README.md`, `CLAUDE.md`,
  `assistente-laboratorio/docs/superpowers/specs/2026-10-26-assistente-laboratorio-design.md`.

### Task 2: `httpx2` dichiarato nei test (M1)

**File:**
- Modifica: `assistente-laboratorio/tests/conftest.py:3,40-43`
- Modifica: `assistente-laboratorio/requirements-dev.txt`

**Interfacce:**
- Consuma: `constraints.txt` del Task 1, invariato.
- Invariata: `errore_lm_studio() -> openai.APIConnectionError`, usata da
  `test_turno_fallito_non_tocca_la_cronologia`, `test_errore_dopo_lo_strumento_non_lascia_orfani`
  e `test_errore_lm_studio_e_si_continua`.

- [ ] **Passo 1: rosso.**
  - `Select-String -Path assistente\*.py, tests\*.py -Pattern '^import httpx$', '^from httpx '`
    → una riga: `tests\conftest.py:3`.
  - `Select-String -Path requirements*.txt -Pattern 'httpx2'` → nessuna riga.
- [ ] **Passo 2: `conftest.py`.** `import httpx2` al posto di `import httpx`;
  `httpx2.Request("POST", "http://localhost:1234/v1/chat/completions")` al posto di `httpx.Request(...)`.
- [ ] **Passo 3: `requirements-dev.txt`.** Dopo `pytest==9.1.1`, le righe
  `# Richiesta finta per costruire openai.APIConnectionError nei test (openai 3.x usa httpx2)` e
  `httpx2==2.16.0`.
- [ ] **Passo 4: verde.**
  - Il primo comando del passo 1 non trova righe; il secondo trova `httpx2==2.16.0`.
  - `pip install -r requirements-dev.txt` → solo «already satisfied»; `pip check` pulito.
  - `pytest -v` → `60 passed, 2 deselected`, con i tre test dell'interfaccia `PASSED`.
- [ ] **Passo 5: chiusura dell'incremento 1.**
  - Con le variabili dei vincoli globali, `.\.venv\Scripts\python.exe -m pytest -m reale -v` → `2 passed`.
  - `docker compose build` → exit 0, poi la prova via pipe nel container come al Task 1, passo 9.
- [ ] **Passo 6: commit**, `test(conftest): usa httpx2, dichiarato, per l'errore finto di LM Studio`.
  File: `assistente-laboratorio/tests/conftest.py`, `assistente-laboratorio/requirements-dev.txt`.

## Incremento 2 — Docker (M2, M3)

### Task 3: indirizzo di LM Studio configurabile nel container (M2)

**File:**
- Modifica: `assistente-laboratorio/compose.yaml:6-7`, `assistente-laboratorio/.env.example`
- Modifica: `assistente-laboratorio/README.md:129-131` (sezione «Docker»)
- Modifica: specifica di base, §3 (blocco `.env.example`) e §9 (blocco `compose.yaml`, frase
  «lo stesso `.env` serve sia in locale sia in Docker»)
- Modifica: `assistente-laboratorio/docs/superpowers/handoff.md:88`

**Interfacce:**
- Produce: variabile facoltativa `LMSTUDIO_BASE_URL_DOCKER`, letta da Compose (dal `.env` o dalla
  shell), con default `http://host.docker.internal:1234/v1`. L'app continua a leggere solo
  `LMSTUDIO_BASE_URL`.

- [ ] **Passo 1: rosso.**
  - `$env:LMSTUDIO_BASE_URL_DOCKER = "http://host.docker.internal:9999/v1"`
  - `docker compose config | Select-String 'LMSTUDIO_BASE_URL'`
  - `Remove-Item Env:LMSTUDIO_BASE_URL_DOCKER`
  - Atteso oggi: `LMSTUDIO_BASE_URL: http://host.docker.internal:1234/v1` (la variabile non ha effetto).
- [ ] **Passo 2: `compose.yaml`.**
  - Riga 6, commento: «LM Studio sull'host; per un'altra porta o un altro host impostare
    LMSTUDIO_BASE_URL_DOCKER nel .env.»
  - Riga 7: `LMSTUDIO_BASE_URL: ${LMSTUDIO_BASE_URL_DOCKER:-http://host.docker.internal:1234/v1}`.
- [ ] **Passo 3: `.env.example`.**
  - Togliere `LMSTUDIO_BASE_URL=http://localhost:1234/v1`.
  - In fondo aggiungere
    `# Solo per Docker, se LM Studio non è raggiungibile su host.docker.internal:1234:` e
    `# LMSTUDIO_BASE_URL_DOCKER=http://host.docker.internal:1234/v1`.
- [ ] **Passo 4: verde (attenzione 3 e 4).** Ogni volta solo le righe `LMSTUDIO_BASE_URL` di
  `docker compose config`:
  - con `$env:LMSTUDIO_BASE_URL_DOCKER = "http://host.docker.internal:9999/v1"` → `…:9999/v1`;
  - con `docker compose --env-file $tmp\vuota.env config`, dove `vuota.env` contiene solo
    `LMSTUDIO_BASE_URL_DOCKER=` → `…:1234/v1`;
  - senza variabile, con il `.env` attuale dell'utente → `http://host.docker.internal:1234/v1`;
  - poi la prova via pipe nel container come al Task 1, passo 9.
- [ ] **Passo 5: documenti.**
  - README:129-131 diventa: «Compose legge `.env` (vedi «Configurazione») e nel container imposta
    `LMSTUDIO_BASE_URL` a `http://host.docker.internal:1234/v1`. Se LM Studio usa un'altra porta o
    un altro host, si imposta `LMSTUDIO_BASE_URL_DOCKER` nel `.env` (vedi `.env.example`).»
  - Specifica di base §3 e §9: nota «*Rivisto il 2026-11-03: vedi
    [`2026-11-03-correzioni-audit-design.md`](2026-11-03-correzioni-audit-design.md) §2.3.*»
  - `handoff.md:88`: in fondo alla riga, «*(risolto il 2026-11-03 con `LMSTUDIO_BASE_URL_DOCKER`,
    vedi `specs/2026-11-03-correzioni-audit-design.md`)*».
- [ ] **Passo 6: commit**, `fix(docker): rende configurabile l'indirizzo di LM Studio nel container`.
  File: `assistente-laboratorio/compose.yaml`, `assistente-laboratorio/.env.example`,
  `assistente-laboratorio/README.md`, la specifica di base, `assistente-laboratorio/docs/superpowers/handoff.md`.

### Task 4: cache Python fuori dall'immagine (M3)

**File:**
- Modifica: `assistente-laboratorio/.dockerignore:3`
- Modifica: specifica di base, §9 (elenco di `.dockerignore`)

- [ ] **Passo 1: rosso.** `docker compose run --rm -T assistente ls -A /app/assistente` → contiene
  `__pycache__`.
- [ ] **Passo 2: `.dockerignore`.** Riga 3: `**/__pycache__/` al posto di `__pycache__/`; nuova riga
  subito dopo: `**/*.pyc`.
- [ ] **Passo 3: build.** `docker compose build` → exit 0.
- [ ] **Passo 4: verde (attenzione 5).**
  - `… ls -A /app/assistente` → solo `__init__.py`, `__main__.py`, `config.py`, `grafo.py`,
    `modello.py`, `sessione.py`, `strumenti.py`, `terminale.py`.
  - `… ls -A /app` → `assistente`, `constraints.txt`, `requirements.txt`.
  - `… whoami` → `assistente`.
  - `-e LMSTUDIO_MODELLO=` → exit 1.
  - Prova via pipe nel container come al Task 1, passo 9.
  - `pytest` → `60 passed, 2 deselected`; `pip check` pulito.
- [ ] **Passo 5: documenti.** Specifica di base §9, elenco di `.dockerignore`: nota «*Rivisto il
  2026-11-03: pattern ricorsivi, vedi [`2026-11-03-correzioni-audit-design.md`](2026-11-03-correzioni-audit-design.md) §2.4.*»
- [ ] **Passo 6: commit**, `fix(docker): esclude le cache Python dall'immagine`.
  File: `assistente-laboratorio/.dockerignore`, la specifica di base.

## Chiusura

- `git log --oneline -6`: i cinque commit nuovi (piano e quattro correzioni) sopra `708b40a`.
- `git status --short` vuoto; `git status --short --ignored` mostra `.env`, `.venv/` e le cache
  solo come ignorati.
- Resoconto all'utente: comandi eseguiti, esiti e che cosa resta da provare, per esempio
  `docker compose run --rm assistente` interattivo con i tasti reali.
