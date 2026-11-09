# Handoff — Assistente del laboratorio

Data: 2026-11-03
Stato: piano di base completato (Task 1–10, 28/10); correzioni dell'audit del 2026-11-03 (I1, M1,
M2, M3) completate e pubblicate su `origin/main` (`5854213`). Punti M4–M13 dell'audit aperti.

Documenti di riferimento:
- [`requisiti.md`](requisiti.md) (approvati);
- base: [`specs/2026-10-26-assistente-laboratorio-design.md`](specs/2026-10-26-assistente-laboratorio-design.md)
  (approvata, con le note «Rivisto il 2026-11-03») e
  [`plans/2026-10-26-assistente-laboratorio.md`](plans/2026-10-26-assistente-laboratorio.md);
- correzioni dell'audit: [`specs/2026-11-03-correzioni-audit-design.md`](specs/2026-11-03-correzioni-audit-design.md)
  (approvata) e [`plans/2026-11-03-correzioni-audit.md`](plans/2026-11-03-correzioni-audit.md).

Comandi completi in [`../../README.md`](../../README.md).

## Che cosa c'è

Applicazione Python da terminale che conversa con `google/gemma-4-e2b` servito da LM Studio
sull'host, attraverso un grafo LangGraph esplicito (nodi `modello`, `strumenti`, `limite`,
funzione `instrada`). Cronologia tenuta da `Sessione` per la sola sessione, strumento
`ora_corrente` con fuso IANA, avvio locale e con Docker Compose.

Moduli in `assistente/`: `config.py`, `modello.py`, `strumenti.py`, `grafo.py`, `sessione.py`,
`terminale.py`; `__main__.py` li collega. Test in `tests/` (`test_reale.py` con marcatore `reale`).

Dipendenze dirette in `requirements.txt` (app) e `requirements-dev.txt` (test); tutte le versioni
verificate, anche le indirette, in `constraints.txt`, richiamato da `requirements.txt` con `-c`.
Immagine Docker su `python:3.13.18-slim-trixie`, fissata per digest.

## Correzioni dell'audit (2026-11-03)

| ID | Problema | Correzione | Commit |
|----|----------|------------|--------|
| I1 | Fissate solo le dipendenze dirette e immagine base con tag mobile: nell'immagine 9 versioni mai provate dai test | `constraints.txt` (i 49 pacchetti del venv verificato) e immagine fissata per tag e digest | `04eaef9` |
| M1 | `tests/conftest.py` importava `httpx`, non dichiarato; `openai` 3.37 si aspetta `httpx2.Request` | `httpx2.Request`, con `httpx2==2.16.0` in `requirements-dev.txt` | `444ce5e` |
| M2 | `LMSTUDIO_BASE_URL` del `.env` senza effetto: nel container la sovrascriveva `compose.yaml` con la porta 1234 fissa | `LMSTUDIO_BASE_URL: ${LMSTUDIO_BASE_URL_DOCKER:-http://host.docker.internal:1234/v1}`; `.env.example` senza `LMSTUDIO_BASE_URL` | `ce2db84` |
| M3 | `.dockerignore` escludeva `__pycache__/` solo alla radice: nell'immagine 8 `.pyc` compilati su Windows | `**/__pycache__/` e `**/*.pyc` | `5854213` |

Il codice in `assistente/` non è cambiato. Specifica e piano delle correzioni: commit `708b40a` e
`878d21b`.

## Verifiche

### Piano di base (26–28/10)

| CA | Come | Esito |
|----|------|-------|
| CA-1 | `pytest` con LM Studio fermo (26/10); `pytest -v` il 28/10 → 60 passed, 2 deselected | ✅ |
| CA-2, CA-3, CA-4 | `pytest -m reale -v` il 28/10 → 2 passed | ✅ |
| CA-5 | `lms server stop` / `start` nella stessa sessione (26/10): errore mostrato, poi cronologia intatta | ✅ |
| CA-6 | test automatico con modello finto | ✅ |
| CA-7 | senza `LMSTUDIO_MODELLO` → «Configurazione non valida: Manca LMSTUDIO_MODELLO.», exit 1 (locale e Docker) | ✅ |
| CA-8 | `docker compose build`; pipe con `-T` e sessione interattiva: chiamata `Asia/Tokyo`, orario corretto | ✅ |
| CA-9 | `esci`, Ctrl+Z+Invio, Ctrl+C al prompt e durante l'attesa del modello (uscita immediata), in locale; `esci` e Ctrl+C in Docker | ✅ |
| CA-10 | `git status --ignored`: `.env`, `.venv/`, cache solo ignorati | ✅ |

Prove aggiuntive del 28/10 con il modello reale:
- `MAX_PASSI=1` + «Che ore sono a Tokyo?» → limite al primo passaggio, strumento non eseguito,
  messaggio di RF-10; i turni successivi funzionano e ricordano la cronologia.
- Sei città in una domanda → il modello chiede le sei chiamate in un solo messaggio: 2 passaggi.
- Sei città «una alla volta» con `MAX_PASSI=5` → quattro chiamate eseguite, limite al quinto
  passaggio.

Limite delle prove: dimostrano che `google/gemma-4-e2b` usa lo strumento con queste domande, non
che lo faccia sempre. Il modello arrotonda l'orario al minuto in modo non uniforme.

### Correzioni dell'audit (03/11)

| Controllo | Prima | Dopo |
|-----------|-------|------|
| `Compare-Object` del `pip freeze` di venv e immagine | 9 versioni diverse, più i 5 pacchetti dei test | solo i 5 pacchetti dei test, presenti solo nel venv |
| `pip install -r requirements-dev.txt` nel venv | — | 49 «Requirement already satisfied», nessuna installazione |
| venv nuovo installato da zero | — | `pip freeze` identico a `constraints.txt` |
| vincolo divergente (`langgraph==1.2.16` in una copia di `constraints.txt`) | — | `ERROR: ResolutionImpossible`, exit 1 |
| `import httpx` nel progetto | `tests/conftest.py:3` | nessuno |
| `docker compose config` con `LMSTUDIO_BASE_URL_DOCKER=http://host.docker.internal:9999/v1` | resta `:1234` | `:9999`; con la variabile vuota o assente `:1234` |
| `ls -A /app/assistente` nel container | contiene `__pycache__` | solo gli 8 `.py` |

Dopo ogni incremento: `pytest` → 60 passed, 2 deselected; `pip check` pulito; `docker compose build`
riuscito; nel container `Python 3.13.18`, utente `assistente`, in `/app` solo `assistente`,
`constraints.txt` e `requirements.txt`; senza `LMSTUDIO_MODELLO` exit 1; «Che ore sono a Tokyo?»
via pipe → chiamata `ora_corrente` con `Asia/Tokyo` e orario riportato come restituito. Dopo
l'incremento delle dipendenze `pytest -m reale -v` → 2 passed.

Prove in più: un `.env` nato dal vecchio `.env.example` (con `LMSTUDIO_BASE_URL=http://localhost:1234/v1`)
lascia nel container `http://host.docker.internal:1234/v1`; con `LMSTUDIO_BASE_URL_DOCKER` su `:9999`
l'app usa quell'indirizzo, mostra l'errore di connessione e la sessione continua.

Revisione finale: autorevisione dell'esecutore sul diff `708b40a..5854213`, senza revisore
indipendente; nessun problema critico o importante, due minori (vedi «Punti aperti»).

## Come riprendere

Da PowerShell in `assistente-laboratorio/`:

```powershell
& "$HOME\.lmstudio\bin\lms.exe" server start
& "$HOME\.lmstudio\bin\lms.exe" load google/gemma-4-e2b --context-length 8192 -y
$env:LMSTUDIO_BASE_URL = "http://localhost:1234/v1"
$env:LMSTUDIO_MODELLO = "google/gemma-4-e2b"
.\.venv\Scripts\python.exe -m pytest            # senza modello
.\.venv\Scripts\python.exe -m pytest -m reale -v
.\.venv\Scripts\python.exe -m assistente
docker compose build
"Che ore sono a Tokyo?", "esci" | docker compose run --rm -T assistente
```

Le variabili valgono solo nella finestra di PowerShell in cui si impostano; senza, le prove reali
falliscono con un messaggio esplicito. Docker legge invece `.env` (copiato da `.env.example`): nel
container `LMSTUDIO_BASE_URL` vale `http://host.docker.internal:1234/v1`, oppure il valore di
`LMSTUDIO_BASE_URL_DOCKER` se è impostata.

Per cambiare una versione: aggiornare i requirements, svuotare `constraints.txt`, reinstallare,
ripetere le verifiche e rigenerarlo con il comando del README (sezione «Installazione»).
L'immagine base si aggiorna a mano: nuovo tag e digest nel `Dockerfile`, poi le prove Docker.

## Significato di `MAX_PASSI`

Limita le **chiamate al modello per turno** (RF-9, specifica §6), non le chiamate agli strumenti.
Il contatore riparte da zero a ogni domanda. Un turno con strumento usa 2 passaggi; i giri di
strumenti possibili sono `MAX_PASSI − 1`, e in un giro il modello può chiedere più chiamate.
Un limite sul numero di chiamate agli strumenti sarebbe un requisito nuovo.

## Decisioni prese durante l'esecuzione

Piano di base (26–28/10):
- Lavoro su `main` senza worktree, come chiede `CLAUDE.md`.
- Logger `httpx2` (usato da `openai` 3.37) portato a WARNING: le righe HTTP comparivano a INFO.
- Messaggio di configurazione prefissato da «Configurazione non valida: ».
- Lo strumento accetta solo nomi presenti in `zoneinfo.available_timezones()` (confronto esatto),
  così il comportamento è lo stesso su Windows e in Docker.
- `recursion_limit` non impostato: il default di LangGraph 1.2.17 è 10007; coperto da
  `test_limite_alto_senza_errore_di_ricorsione`.
- Le `invalid_tool_calls` sono trattate come chiamate e ricevono una risposta d'errore, contro
  la lettera della specifica §6 e a favore di RF-7; specifica annotata.
- Eccezioni diverse da `openai.APIError` non intercettate (specifica §8).

Correzioni dell'audit (03/11):
- Ancora su `main` senza worktree; push solo su richiesta.
- README, sezione «Docker»: corretta solo la frase su `.env`; resta «LM Studio resta sull'host;
  nel container gira solo l'applicazione.».
- Nessun test pytest per Compose, `.dockerignore` e vincoli: le prove Docker restano separate e
  manuali (`CLAUDE.md`, specifica delle correzioni §4).
- Immagine base fissata per digest: niente aggiornamenti di sicurezza automatici (specifica delle
  correzioni §2.1).
- Patch di Python diverse tra venv (3.13.14) e immagine (3.13.18): la specifica fissa l'immagine
  provata nell'audit e non aggiorna il venv.

## Punti aperti

- **Audit del 2026-11-03, punti M4–M13:** non affrontati, fuori ambito della specifica delle
  correzioni. La loro descrizione non è nel repository: va ripresa dal resoconto dell'audit.
- **Minori della revisione finale del 03/11:**
  - `README.md:158` cita ancora l'immagine `python:3.13-slim`; il `Dockerfile` fissa
    `python:3.13.18-slim-trixie@sha256:ae14…85d1`;
  - README, diagnosi «LM Studio non raggiungibile dal container»: il comando di prova usa
    `host.docker.internal:1234` fisso e il testo cita `LMSTUDIO_BASE_URL`; con
    `LMSTUDIO_BASE_URL_DOCKER` impostata va adattato a mano.
- **Da provare dopo le correzioni:**
  - `docker compose run --rm assistente` interattivo con i tasti reali (`esci`, Ctrl+C);
  - una conversazione riuscita con LM Studio su un'altra porta o un altro host, tramite
    `LMSTUDIO_BASE_URL_DOCKER`;
  - l'avvio locale interattivo (il codice dell'app non è cambiato, ma non è stato rilanciato);
  - `docker compose build --no-cache` e la build su un'altra architettura;
  - la procedura per cambiare una versione;
  - un revisore indipendente sul diff `708b40a..5854213`.
- **Testo con `MAX_PASSI=1`:** «il limite di 1 passaggi» (messaggio e log). Correzione proposta,
  non fatta: tocca un testo fissato nella specifica.
- **Minori rimandati dalla revisione finale del 28/10:**
  - con `MAX_PASSI` oltre ~5000 o `LANGGRAPH_DEFAULT_RECURSION_LIMIT` basso si avrebbe un errore di
    LangGraph invece del messaggio di RF-10;
  - `compose.yaml` fissa la porta 1234 in `LMSTUDIO_BASE_URL`, sovrascrivendo `.env`; *(risolto il 2026-11-03 con `LMSTUDIO_BASE_URL_DOCKER`, vedi `specs/2026-11-03-correzioni-audit-design.md`)*
  - container senza init (`docker stop` attende 10 s); possibile `init: true`;
  - su Windows con stdout rediretto, caratteri fuori da cp1252 nella risposta possono causare
    `UnicodeEncodeError`.
- Le caselle `- [ ]` dei due piani non sono state spuntate.

## Fuori ambito (lezioni successive)

Altri strumenti, MCP, RAG, workflow aggiuntivi, persistenza della cronologia, streaming,
interfacce grafiche. Ogni estensione parte da requisiti e specifica, con il metodo Superpowers.
