# Specifica — Correzioni dell'audit (I1, M1, M2, M3)

Data: 2026-11-03
Stato: approvata
Specifica di base: [`2026-10-26-assistente-laboratorio-design.md`](2026-10-26-assistente-laboratorio-design.md)
(§3, §9, §12). Requisiti: [`../requisiti.md`](../requisiti.md) (RNF-5, RNF-6, RNF-7).

Questa specifica cambia quattro decisioni della specifica di base emerse dall'audit del
2026-11-03. Il comportamento dell'applicazione non cambia.

## 1. Problemi

| ID | Problema | Evidenza dell'audit |
|----|----------|---------------------|
| I1 | Sono fissate solo le dipendenze dirette e l'immagine base usa un tag mobile: l'immagine Docker gira con versioni che i test non hanno mai provato. | `pip freeze` del venv e dell'immagine: 9 versioni diverse (es. pydantic 2.14.1 e 2.14.2, langsmith 0.14.12 e 0.14.17). |
| M1 | `tests/conftest.py` importa `httpx`, che non è dichiarato: arriva solo come dipendenza di langchain-core. Inoltre `openai` 3.37 si aspetta `httpx2.Request`. | `tests/conftest.py:3,40-43`; `openai/_exceptions.py:107`. |
| M2 | `LMSTUDIO_BASE_URL` del `.env` non ha effetto: in Docker la sovrascrive `compose.yaml`, in locale Python non legge `.env`. README e specifica di base dicono il contrario. | `compose.yaml:7`; README:129-131 contro README:55; specifica di base §9 contro §3. |
| M3 | `.dockerignore` esclude `__pycache__/` solo alla radice del contesto: l'immagine contiene 8 `.pyc` compilati su Windows, con il percorso locale. | `ls -la /app/assistente/__pycache__` nel container. |

## 2. Decisioni

### 2.1 Versioni fissate con `constraints.txt` (I1)

- Nuovo file `constraints.txt`: il `pip freeze` completo del venv in cui passano la suite e le
  prove reali (49 pacchetti), preceduto da una riga di commento. Contiene anche le dipendenze
  dirette, alle stesse versioni dei requirements: se un giorno divergono, pip si ferma con un
  conflitto invece di installare una combinazione mai provata.
- `requirements.txt` inizia con `-c constraints.txt`. I vincoli valgono quindi anche per
  `requirements-dev.txt`, che include `requirements.txt`, e per il Dockerfile. I comandi
  d'installazione restano invariati.
- `requirements*.txt` continuano a elencare solo le dipendenze dirette, ciascuna con il suo
  motivo (RNF-7). Le indirette sono fissate solo in `constraints.txt`.
- Rigenerazione, da PowerShell in `assistente-laboratorio/`:

  ```powershell
  @("# Versioni verificate: rigenerare con il comando del README, sezione Installazione.") + (.\.venv\Scripts\python.exe -m pip freeze) | Out-File -Encoding ascii constraints.txt
  ```

  Per cambiare una versione: si aggiornano i requirements, si svuota `constraints.txt`, si
  reinstalla, si ripetono le verifiche (§4) e si rigenera il file.
- Immagine base: `python:3.13.18-slim-trixie@sha256:ae14d4ce8771606477a81446e7ef429edd6762305fc50c84507c1041fa8285d1`,
  la stessa su cui sono passate le prove Docker del 2026-11-03. Gli aggiornamenti si fanno a
  mano: si cambiano tag e digest e si ripetono le prove.
- Il Dockerfile copia `constraints.txt` insieme a `requirements.txt`, prima del pacchetto, così
  il livello delle dipendenze resta in cache.

Sostituisce: nel piano del 2026-10-26, «Si fissano le dipendenze dirette; le transitive le
risolve pip»; nella specifica di base, l'immagine `python:3.13-slim` (§9) e il rischio
«Versioni delle dipendenze» (§12).

### 2.2 `httpx2` dichiarato nei test (M1)

- `tests/conftest.py` costruisce `openai.APIConnectionError` con `httpx2.Request`.
- `requirements-dev.txt` dichiara `httpx2==2.16.0`, con il motivo.
- Nessun file del progetto importa più `httpx`.

### 2.3 Indirizzo di LM Studio nel container (M2)

- `compose.yaml`: `LMSTUDIO_BASE_URL: ${LMSTUDIO_BASE_URL_DOCKER:-http://host.docker.internal:1234/v1}`.
  Senza la variabile il comportamento resta quello attuale.
- `.env.example`: la riga `LMSTUDIO_BASE_URL` viene tolta; si aggiunge, commentata,
  `LMSTUDIO_BASE_URL_DOCKER=http://host.docker.internal:1234/v1`, da usare se LM Studio non è
  raggiungibile su `host.docker.internal:1234`.
- Un `.env` già esistente continua a funzionare: la sua `LMSTUDIO_BASE_URL` resta ignorata nel
  container, come oggi.
- In locale non cambia nulla: le variabili si impostano nella shell (specifica di base §3).

Sostituisce: nella specifica di base, il blocco `.env.example` (§3), il blocco `compose.yaml`
e la frase «lo stesso `.env` serve sia in locale sia in Docker» (§9).

### 2.4 Cache Python fuori dall'immagine (M3)

- `.dockerignore`: `**/__pycache__/` e `**/*.pyc` al posto di `__pycache__/`.

Sostituisce: nella specifica di base, l'elenco di `.dockerignore` (§9).

## 3. Documentazione

- README: in «Installazione» un paragrafo su `constraints.txt` con il comando di rigenerazione;
  in «Docker» la frase su `.env` corretta e `LMSTUDIO_BASE_URL_DOCKER` spiegata.
- `CLAUDE.md`: la riga sulle dipendenze cita anche `constraints.txt`, perché cambia la struttura.
- Specifica di base: nei punti sostituiti una nota «Rivisto il 2026-11-03» che rimanda a questo
  file.
- Handoff: il punto aperto sulla porta 1234 fissata in `compose.yaml` viene segnato come risolto.

## 4. Verifica

Ogni correzione ha un controllo che fallisce prima della modifica e passa dopo.

| Correzione | Controllo | Prima | Dopo |
|------------|-----------|-------|------|
| I1 | confronto del `pip freeze` di venv e immagine | 9 versioni diverse | differiscono solo i 5 pacchetti dei test, presenti solo nel venv |
| I1 | `pip install -r requirements-dev.txt` nel venv | — | nessun pacchetto da installare o cambiare |
| M1 | `import httpx` nel progetto | `tests/conftest.py:3` | nessuno; i 3 test che usano l'errore finto restano verdi |
| M2 | `docker compose config` con `LMSTUDIO_BASE_URL_DOCKER=http://host.docker.internal:9999/v1` | l'URL resta su `:1234` | l'URL usa `:9999`; senza la variabile resta su `:1234` |
| M3 | `ls -A /app/assistente` nel container | contiene `__pycache__` | non lo contiene |

Dopo ogni incremento: `pytest` (60 passed), `pip check`, `docker compose build` e la prova reale
via pipe nel container («Che ore sono a Tokyo?»). Dopo l'incremento 1 anche `pytest -m reale -v`.

## 5. Fuori ambito

Gli altri punti dell'audit (M4–M13), strumenti di lock non concordati (pip-tools, uv) e
l'aggiornamento delle versioni.
