# Specifica — Lezione 6, Step 9: Docker Compose, un container per componente

Data: 2026-11-14
Stato: scritta in modalità autonoma (branch `auto-claude`): l'approvazione è sostituita dal piano
in [`../../../PROGRESS.md`](../../../PROGRESS.md) (regola di `CLAUDE.md`, «Modalità autonoma»).
Requisiti: [`../requisiti.md`](../requisiti.md), §17 (RF-76…RF-80, CA-88…CA-93).
Specifiche precedenti: [`2026-11-14-frontend-chat-design.md`](2026-11-14-frontend-chat-design.md)
(Step 8), [`2026-11-14-backend-chat-design.md`](2026-11-14-backend-chat-design.md) (Step 7),
[`2026-11-14-servizio-http-design.md`](2026-11-14-servizio-http-design.md) (Step 6) e quelle che
richiamano.
Fonte didattica: `LLM_Lez_6.pdf`, Step 9; riassunto in [`../lezione6.md`](../lezione6.md).

I tre servizi Python (agente, back-end, front-end) ricevono **ciascuno il proprio Dockerfile** e
`compose.yaml` li avvia insieme a **PostgreSQL con l'immagine ufficiale**: il browser apre il
front-end, il front-end chiama il back-end sulla sua porta pubblicata, il back-end salva in PostgreSQL
e chiama l'agente sulla rete interna di Compose; l'agente non è pubblicato e raggiunge LM Studio
sull'host. Nessun codice Python cambia: lo step è solo immagini, Compose, test e documentazione.

```
host: browser ──→ 127.0.0.1:8080  frontend  (pagina e /config.js)
         └──────→ 127.0.0.1:8001  backend ──→ postgres:5432   (volume postgres-data)
                                     └─────→ agent:8000 ──→ host.docker.internal:1234 (LM Studio)
                                               └─ server MCP stdio (sottoprocesso)  (volume notes-data)
```

## 1. Decisioni

Tutte «scelta del progettista» (modalità autonoma: opzione consigliata o più standard).

| Tema | Decisione | Motivo |
|------|-----------|--------|
| Dove stanno i Dockerfile | Cartella **`docker/`**: `agent.Dockerfile`, `backend.Dockerfile`, `frontend.Dockerfile`; contesto di build la **radice** della repository. Il `Dockerfile` attuale diventa `docker/agent.Dockerfile` (`git mv`) | La traccia chiede «tre con il proprio Dockerfile». Il contesto deve essere la radice perché back-end e front-end importano il pacchetto `assistant` (client dell'agente e configurazione, specifiche degli Step 7 e 8); `<nome>.Dockerfile` in una cartella è la convenzione riconosciuta da Docker e dagli editor; i pacchetti `backend/` e `frontend/` restano senza file Docker dentro |
| Immagine base | La stessa per i tre: `python:3.13.18-slim-trixie` fissata per digest (quella attuale) | Già verificata nelle lezioni precedenti; versione e digest fissati come chiede `CLAUDE.md` |
| Dipendenze | In tutte e tre le immagini `pip install -r requirements.txt` (con `constraints.txt`), come **primi livelli identici** | Decisione dello Step 7: il back-end usa `assistant/api_client.py` e gli stessi file di dipendenze. Con le prime istruzioni identiche Docker costruisce il livello delle dipendenze una volta e lo riusa nelle altre due immagini; dividere `requirements.txt` per servizio sarebbe un cambiamento più grande, senza un requisito che lo chieda |
| Codice copiato | Agente: `assistant/`. Back-end: `assistant/` e `backend/`. Front-end: `assistant/` e `frontend/` | Ogni immagine contiene solo i pacchetti del suo servizio più la libreria comune `assistant`; copiarla intera è più robusto che elencarne i moduli usati (un import nuovo non rompe l'immagine) |
| Utente | Utente non root **`app`** nelle tre immagini (uid 1000, lo stesso dell'utente `assistant` di prima) | Pratica consigliata; con lo stesso uid il volume `notes-data` già esistente resta scrivibile |
| Comando predefinito | Agente: `python -m assistant.service`. Back-end: `python -m backend`. Front-end: `python -m frontend` | La traccia chiede l'agente «come servizio HTTP»; la CLI usa la stessa immagine dell'agente con `command: python -m assistant` in Compose |
| Indirizzo nel container | `ENV AGENT_HOST=0.0.0.0`, `BACKEND_HOST=0.0.0.0`, `FRONTEND_HOST=0.0.0.0` nell'immagine, ripetuti in `compose.yaml` | I predefiniti dei servizi (`127.0.0.1`) non sarebbero raggiungibili da fuori del container. Nell'immagine perché un `docker run -p` funzioni da solo; in Compose perché `environment` vince su `env_file` e un `.env` locale con `127.0.0.1` non deve rompere i container |
| Porte | `EXPOSE 8000` (agente), `8001` (back-end), `8080` (front-end): i predefiniti dei servizi | Nessuna configurazione in più; la stessa porta dentro e fuori |
| Servizi di `compose.yaml` | **`frontend`**, **`backend`**, **`agent`**, **`postgres`**; la CLI **`assistant`** resta, con `profiles: ["cli"]` | `docker compose up` avvia esattamente i quattro servizi della traccia; un servizio con un profilo non parte con `up`, ma `docker compose run --rm assistant` lo avvia comunque (con `agent` come dipendenza), quindi il comando documentato dagli Step 6 in poi continua a funzionare |
| Come le API arrivano al back-end | **Porta pubblicata** `127.0.0.1:8001:8001`: il browser chiama direttamente il back-end, con il CORS dello Step 8 | Decisione dello Step 8 (niente proxy da scrivere); la traccia ammette «porta pubblicata o proxy». I predefiniti di `BACKEND_URL` (`http://127.0.0.1:8001`) e `CORS_ORIGINS` (`http://127.0.0.1:8080`, `http://localhost:8080`) valgono già dal punto di vista del browser sull'host |
| Esposizione | `frontend` su `127.0.0.1:8080`, `backend` su `127.0.0.1:8001`; **`agent` e `postgres` senza `ports`** | La traccia: «l'agente non è esposto». PostgreSQL serve solo al back-end, sulla rete interna. Solo `127.0.0.1`: niente accessi da altri computer, come nei servizi locali |
| PostgreSQL | Immagine ufficiale **`postgres:18.6`** (quella delle prove degli Step 7 e 8), volume **`postgres-data`** in `/var/lib/postgresql` | Versione già verificata; dalla 18 l'immagine conserva i dati sotto `/var/lib/postgresql` (cartella per versione), che è il punto di montaggio consigliato |
| Credenziali | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` nel **`.env`** (escluso da Git), con valori d'esempio in `.env.example`; `compose.yaml` costruisce `DATABASE_URL` del back-end (`postgresql://…@postgres:5432/…`) per interpolazione; `POSTGRES_PASSWORD` obbligatoria (`${POSTGRES_PASSWORD:?…}`: senza, Compose si ferma con un messaggio) | La traccia: «credenziali in `.env` escluso da Git». Un solo posto per la password, letto sia da `postgres` sia da `backend` |
| Avvio a database pronto | `postgres` con `healthcheck` `pg_isready`; `backend` con `depends_on: postgres: condition: service_healthy` | La traccia: «back-end avviato a database pronto». Senza, il back-end uscirebbe con «Database non raggiungibile» al primo avvio, mentre PostgreSQL inizializza i dati |
| Dipendenze tra servizi | `backend` dipende da `agent` con `service_started`; `frontend` da `backend` con `service_started` | Il back-end funziona anche con l'agente spento (lo segnala a ogni invio, Step 7) e la pagina anche con il back-end spento (Step 8): aspettare `healthy` bloccherebbe l'avvio senza motivo |
| Variabili dei servizi | `agent` e `assistant` leggono `env_file: .env` (modello, soglie, ambito, preferenze); `backend`, `frontend` e `postgres` ricevono in `environment` solo le loro variabili, interpolate dal `.env` | L'agente usa molte variabili; il back-end e il front-end poche. Così la password del database non entra nei container del front-end (resta visibile nell'ambiente dell'agente, che legge tutto il `.env`: rischio §9) |
| Test senza Docker | `tests/test_docker.py`: controlli statici dei tre Dockerfile (testo) e di `compose.yaml` letto con **`docker compose config --format json`** (saltato col motivo se la CLI di Docker manca) | I controlli statici fermano gli errori più probabili (porta sbagliata, `127.0.0.1` nel container, agente pubblicato) senza costruire immagini; `docker compose config` interpreta il file come Docker (interpolazione, profili) senza il demone e senza aggiungere un parser YAML ai test |
| Prove con Docker | A mano (comandi `docker`), esiti nel diario, come le prove Docker delle lezioni precedenti | `CLAUDE.md`: prove con Docker separate e attivate esplicitamente; costruire tre immagini e attendere LM Studio dura minuti |

## 2. Struttura

```
docker/
├── agent.Dockerfile      # servizio HTTP dell'agente (e CLI con un altro comando), server MCP stdio
├── backend.Dockerfile    # back-end (python -m backend)
└── frontend.Dockerfile   # front-end (python -m frontend)
compose.yaml              # frontend, backend, agent, postgres; assistant (CLI) nel profilo cli
.env.example              # + POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
tests/test_docker.py      # Dockerfile e compose.yaml senza costruire immagini
```

`.dockerignore` resta uno solo nella radice (vale per tutti e tre: contesto comune).

## 3. Dockerfile (`docker/*.Dockerfile`)

Forma comune (le prime quattro istruzioni identiche nei tre file, per condividere i livelli):

```dockerfile
FROM python:3.13.18-slim-trixie@sha256:…
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY assistant/ assistant/
COPY <pacchetto>/ <pacchetto>/      # backend/ o frontend/; nessuno per l'agente
ENV <SERVIZIO>_HOST=0.0.0.0
USER app
EXPOSE <porta>
CMD ["python", "-m", "<modulo>"]
```

- **Agente**: cartella `/app/data` creata e assegnata ad `app` prima di `USER` (il volume
  `notes-data`, alla prima creazione, ne eredita il proprietario); il server MCP parte come
  sottoprocesso con lo stesso interprete (`server_command`), quindi nello stesso container senza
  configurazione in più.
- **Back-end**: nessuna cartella di dati (i dati stanno in PostgreSQL).
- **Front-end**: i file statici sono nel pacchetto (`frontend/static/`); `backend-openapi.json` è
  copiato ma non servito (il servizio serve solo `/config.js` e `static/`).

## 4. `compose.yaml`

```yaml
name: assistente-laboratorio
services:
  frontend:   # build docker/frontend.Dockerfile; ports 127.0.0.1:8080:8080; FRONTEND_HOST, LOG_LEVEL
  backend:    # build docker/backend.Dockerfile; ports 127.0.0.1:8001:8001;
              # DATABASE_URL da POSTGRES_*, AGENT_URL=http://agent:8000, BACKEND_HOST, LOG_LEVEL;
              # depends_on postgres (service_healthy), agent (service_started)
  agent:      # build docker/agent.Dockerfile; env_file .env; LMSTUDIO_BASE_URL da
              # LMSTUDIO_BASE_URL_DOCKER (host.docker.internal), extra_hosts host-gateway;
              # healthcheck /status (quello attuale); volume notes-data; nessuna porta
  postgres:   # image postgres:18.6; POSTGRES_*; healthcheck pg_isready; volume postgres-data;
              # nessuna porta
  assistant:  # profiles [cli]; stessa build dell'agente; command python -m assistant;
              # AGENT_URL=http://agent:8000; depends_on agent (service_healthy); stdin_open, tty
volumes:
  notes-data: {}
  postgres-data: {}
```

- `CORS_ORIGINS` e `BACKEND_URL` non si impostano: i predefiniti coincidono con gli indirizzi visti
  dal browser sull'host. Chi cambia le porte pubblicate li imposta nel `.env` (passati con
  `${CORS_ORIGINS:-}` e `${BACKEND_URL:-}`: vuoti → predefiniti dei servizi).
- `LOG_LEVEL` passato a `backend` e `frontend` con `${LOG_LEVEL:-INFO}`.
- L'agente non è pubblicato: dal computer host `http://127.0.0.1:8000` non risponde; OpenAPI e
  `/status` dell'agente si consultano dentro la rete (`docker compose exec agent …`).

## 5. Configurazione nuova

| Variabile (`.env`) | Usata da | Esempio in `.env.example` | Regole |
|--------------------|----------|---------------------------|--------|
| `POSTGRES_USER` | `postgres`, `backend` | `lab` | predefinito `lab` se manca |
| `POSTGRES_PASSWORD` | `postgres`, `backend` | `cambiami` | obbligatoria: senza, `docker compose` si ferma con «Manca POSTGRES_PASSWORD nel file .env» |
| `POSTGRES_DB` | `postgres`, `backend` | `assistente` | predefinito `assistente` se manca |

La password entra nell'indirizzo del database: deve essere senza caratteri da codificare negli URL
(`@`, `:`, `/`, `%`, `#`), detto nel README e in `.env.example`.

## 6. Log ed evidenze

Nessuna riga di log nuova. Le evidenze della traccia si leggono con i comandi di Compose:
`docker compose ps` (quattro servizi attivi, `healthy` per `agent` e `postgres`), `docker compose
logs agent` (`variant=mcp tool=calculate`, `api response=chat … tools=calculate`), `docker compose
logs backend` (`send_message … status=201`), e la riga d'avvio del back-end con la password nascosta
(`postgresql+psycopg://lab:***@postgres:5432/assistente`).

## 7. Test

### Senza Docker (`pytest`)

`tests/test_docker.py`:
- per ognuno dei tre Dockerfile: stessa riga `FROM` con digest, prime istruzioni identiche, installazione
  da `requirements.txt` con `constraints.txt` copiato, pacchetti copiati (`assistant/` e quello del
  servizio), `USER` non root prima di `CMD`, `EXPOSE` uguale alla porta predefinita della
  configurazione del servizio (`DEFAULT_AGENT_PORT`, `DEFAULT_BACKEND_PORT`,
  `DEFAULT_FRONTEND_PORT`), `ENV <SERVIZIO>_HOST=0.0.0.0`, `CMD` col modulo del servizio; i moduli
  di `CMD` esistono (`importlib.util.find_spec`);
- `compose.yaml` con `docker compose config --format json` (un `.env` temporaneo con credenziali
  finte, passato con `--env-file`; saltato se la CLI di Docker manca): quattro servizi senza
  profilo, la CLI solo nel profilo `cli`; `agent` e `postgres` senza porte pubblicate, `backend` e
  `frontend` su `127.0.0.1` con le porte predefinite; Dockerfile giusto per ogni servizio; `postgres`
  con immagine `postgres:18.6`, volume e `healthcheck`; `backend` con `depends_on` `postgres`
  `service_healthy`, `DATABASE_URL` verso `postgres:5432` con le credenziali del `.env`,
  `AGENT_URL=http://agent:8000`; password mancante → `docker compose config` fallisce col messaggio.

### Con Docker (a mano, esiti nel diario)

- Punto 1: le tre immagini costruite (`docker build -f docker/<servizio>.Dockerfile .`) e avviate una
  per una: agente con LM Studio → `GET /status` `200` con gli strumenti MCP elencati (server stdio nel
  container); back-end verso il PostgreSQL del container dello Step 7 (`host.docker.internal:5433`) →
  `GET /chats` `200`; front-end → `/config.js` e pagina; utente `app` nei tre container.
- Punto 3 (prova reale dello step): `docker compose up -d --build`, `docker compose ps` con i quattro
  servizi attivi; agente non raggiungibile da `127.0.0.1:8000`; dalla pagina su
  `http://127.0.0.1:8080` (Edge con Playwright) nuova chat, «Quanto fa 17 * 23?» → «391» con
  `calculate`, visibile in `docker compose logs agent`; `docker compose down` e `docker compose up -d`
  → la chat c'è ancora (volume `postgres-data`). Se Docker o LM Studio non sono raggiungibili, il
  punto si segna `[!]`.

## 8. Incrementi

Coincidono con i punti dello Step 9 in `TODO.md`; ognuno verificato con `pytest` prima del commit.

1. Questa specifica e i requisiti §17; i tre Dockerfile in `docker/` (`Dockerfile` spostato);
   `compose.yaml` aggiornato solo nei percorsi dei Dockerfile (l'immagine dell'agente ha ora il
   servizio come comando, la CLI lo imposta in Compose); test statici dei Dockerfile; prove a mano
   delle tre immagini.
2. `compose.yaml` a quattro servizi (più la CLI nel profilo `cli`), `.env.example` con le credenziali
   di PostgreSQL; test con `docker compose config`.
3. Prova reale con Compose; README (sezione Docker, diagnosi) e `CLAUDE.md` (comandi Docker); esiti
   in requisiti §17 e nel diario.

## 9. Rischi

- **Password nell'ambiente dell'agente**: `env_file: .env` passa all'agente tutto il `.env`, anche
  `POSTGRES_PASSWORD`, che non usa. Accettato: elencare una per una le variabili dell'agente sarebbe
  fragile; i container girano solo su questo computer.
- **Porte occupate**: 8001 o 8080 usate da processi locali (gli stessi servizi avviati a mano) fanno
  fallire `docker compose up`. Il README lo mette in «Diagnosi».
- **Volume di PostgreSQL già inizializzato**: `POSTGRES_PASSWORD` vale solo alla prima creazione del
  volume; cambiarla dopo dà «password authentication failed» nel back-end. Diagnosi nel README
  (`docker volume rm assistente-laboratorio_postgres-data` cancella le chat).
- **Immagini più grandi del necessario**: back-end e front-end contengono anche le dipendenze
  dell'agente (LangGraph, fastmcp…); il livello è condiviso, quindi lo spazio su disco cresce poco.
- **LM Studio su un'altra porta**: invariato, `LMSTUDIO_BASE_URL_DOCKER` nel `.env`.

## 10. Fuori ambito

Streaming (facoltativo), proxy delle API nel front-end, HTTPS, immagini per altre architetture,
registri di immagini, orchestratori diversi da Compose, migrazioni del database, backup del volume.
