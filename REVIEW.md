# Revisione del progetto — 2026-11-16

Revisione di sola lettura sul branch `dev` (commit `0a2fc5e`): nessun file di codice è stato
modificato. Aree: codice, logica, strumenti e dipendenze, test, architettura.

## Punti da riprendere

Corretto finora: I-1. Spuntare quando un punto è chiuso o scartato; i dettagli sono
nelle sezioni sotto. Ogni correzione parte con specifica e piano (`CLAUDE.md`, «Metodo»).

- [x] **I-1** 🟠 Il ritentativo MCP ripete anche `add_note` e `delete_note` — corretto il 2026-11-16 (commit `9b95128`, `2152ba6`; specifica `docs/superpowers/specs/2026-11-16-ritentativo-mcp-design.md`): `call_tool` non viene più ripetuto
- [ ] **I-2** 🟠 Nessun linter, controllo dei tipi, CI, copertura; ~120 firme senza tipi (dipendenze nuove da concordare)
- [ ] **M-1** 🟡 `.env` intero nel container dell'agente (`DATABASE_URL` compresa) — `compose.yaml:55`, `108`
- [ ] **M-2** 🟡 Testi dell'utente nei log INFO — `assistant/graph.py:321-330`, `assistant/commands.py:189-193`
- [ ] **M-3** 🟡 Nessun `max_length` su `content`, `message`, `history` — `backend/api.py:84-91`, `assistant/api.py:113-116`
- [ ] **M-4** 🟡 `run_tool`: ogni eccezione diventa «argomenti non validi» — `assistant/graph.py:308-311`
- [ ] **M-5** 🟡 `ValueError` troppo largo per router e revisore (da verificare) — `assistant/model.py:17-22`
- [ ] **M-6** 🟡 Turno più lungo di `CHAT_TIMEOUT` nel caso peggiore — `assistant/model.py:33-34`
- [ ] **M-7** 🟡 Codice ripetuto: `Utf8JsonMiddleware` e contorno dell'API, lettura delle porte, `read_positive`
- [ ] **M-8** 🟡 `Config` con 13 argomenti posizionali — `assistant/config.py:141-147`
- [ ] **M-9** 🟡 `LMSTUDIO_BASE_URL` e `BACKEND_URL` validati solo sul prefisso
- [ ] **M-10** 🟡 Due finestre di concorrenza nel client MCP (da verificare, non riprodotte) — `assistant/mcp_client.py:287-301`
- [ ] **M-11** 🟡 Schema senza migrazioni — `backend/db.py:84-86`
- [ ] **M-12** 🟡 Elenchi senza paginazione — `backend/store.py:117-137`
- [ ] **M-13** 🟡 Compose: `healthcheck` e `restart` mancanti su alcuni servizi
- [ ] **M-14** 🟡 Dieci dipendenze dirette non all'ultima versione (nessuna vulnerabile)
- [ ] **M-15** 🟡 Stile: righe lunghe, funzioni complesse, `NotesStore.list`
- [ ] **R-C4 / R-D1** Debiti già noti: blocco per chat sull'invio

Ordine consigliato: I-1, I-2, M-1, M-2 con M-3, poi R-C4 / R-D1.

## Che cosa è stato eseguito

| Verifica | Esito |
|---|---|
| Lettura completa di `assistant/`, `backend/`, `frontend/` (Python e JavaScript), `compose.yaml`, `docker/`, file di configurazione | fatta |
| Test (`tests/`, ~13.000 righe) | **non letti riga per riga**: contati per file, eseguiti, campionati con `grep` |
| `.\.venv\Scripts\python.exe -m pytest` | 1074 passati, 93 esclusi (`real`, `browser`), 92 s |
| `pip freeze` contro `constraints.txt` | identici (103 pacchetti); `pip check` senza conflitti |
| `pip-audit -r constraints.txt --no-deps` | nessuna vulnerabilità nota |
| `pip list --outdated` | 36 pacchetti con una versione più recente (10 tra i diretti, vedi M-14) |
| `ruff check` con regole `E,W,F,B,UP,SIM,C90,PL,ANN,S`, riga a 100 | 169 segnalazioni, 121 delle quali annotazioni di tipo mancanti |
| Segreti: `git grep` e cronologia di `.env` | nessun segreto versionato; `.env` mai entrato in Git |
| Prove `real` (LM Studio), `browser` (Playwright), Docker | **non eseguite** |
| Copertura dei test | **non misurata** (`pytest-cov` non è tra le dipendenze) |

Skill: cercate con `find-skills`; tre scaricate in una cartella temporanea e usate come liste di
controllo (`python-code-review`, `fastapi`, `docker-compose-patterns`); una quarta,
`langgraph-fundamentals`, non si è scaricata. Nessuna è stata installata nel progetto o nel profilo utente.

## Riepilogo

Il progetto è in buono stato. Non ho trovato problemi critici: nessun bug che corrompa dati nel
percorso normale, nessun segreto nel codice, nessuna dipendenza vulnerabile. I punti forti sono la
separazione tra logica pura e collegamenti (ogni dipendenza esterna ha un finto nei test), la
gestione degli errori coerente (codice stabile + dettaglio in italiano, traceback solo nel log), e
una suite ampia e veloce.

I punti deboli sono di contorno: non c'è nessun controllo automatico oltre a `pytest` (né linter,
né controllo dei tipi, né CI, né copertura), il riavvio automatico del server MCP ripete anche le
chiamate che scrivono, e due servizi ripetono lo stesso codice di contorno dell'API.

| Area | Voto | Motivo in una riga |
|---|---|---|
| Codice | 8 | Moduli piccoli, nomi chiari, docstring utili; mancano annotazioni su ~120 firme e ci sono duplicazioni tra i due servizi |
| Logica | 8 | Casi limite curati (tagli del riassunto, id delle chiamate, limiti); restano il ritentativo MCP e le corse già note in `TODO.md` |
| Strumenti e dipendenze | 7 | Versioni fissate, verificate e senza vulnerabilità; nessun linter, type checker, CI o `pyproject.toml` |
| Test | 9 | 1074 test in 92 s senza modello, con finti per ogni confine; copertura non misurata, concorrenza non provata |
| Architettura | 8 | Agente senza stato, tre servizi con confini netti; back-end e front-end dipendono dal pacchetto `assistant` |

## Problemi

### 🔴 Critici

Nessuno.

### 🟠 Importanti

**I-1 · Il ritentativo dopo «connessione chiusa» ripete anche le chiamate che scrivono**
`assistant/mcp_client.py:266-285` · confidenza: alta sul comportamento, bassa sulla frequenza

`_submit` riavvia il server e ripete la richiesta una volta per qualsiasi richiesta, compresi
`add_note` e `delete_note`. Se il server muore dopo aver scritto su SQLite ma prima di rispondere,
`add_note` salva la nota due volte e `delete_note` torna «Nessuna nota con id N» per una nota che
ha appena eliminato: il modello dirà all'utente che l'eliminazione è fallita. Serve che il
processo muoia in quella finestra, quindi è raro, ma l'esito è un dato sbagliato senza traccia.

Fix proposto: ripetere solo le richieste senza effetti (`tools/list`, `prompts/*`,
`resources/read`); per `call_tool` riavviare e restituire l'errore, lasciando al modello la scelta.

```python
def _submit(self, request, timeout=None, *, retry=True):
    ...
    except _ConnectionClosed as closed:
        self._restart(closed.generation, closed.reason)
        if not retry:
            raise ToolUnavailableError(closed.reason) from None
# call_tool: self._submit(..., retry=False)
```

**I-2 · Nessun controllo automatico oltre a `pytest`**
radice della repository (mancano `pyproject.toml`, `.github/`, configurazione di ruff/mypy)

Stile, tipi e test dipendono da chi si ricorda di lanciarli. `ruff` trova 169 segnalazioni con un
insieme di regole ordinario; nessuna è un bug, ma 121 sono firme senza tipi (`client`, `graph`,
`session`, `agent` passati senza annotazione in `api.py`, `graph.py`, `commands.py`,
`backend/api.py`), cioè proprio i punti in cui i finti dei test e gli oggetti veri devono avere la
stessa forma. Un `Protocol` per `McpClient` e `AgentClient` renderebbe verificabile quell'accordo.

Fix proposto: un `pyproject.toml` con `[tool.ruff]` (riga a 100, come il codice usa già) e
`[tool.pytest.ini_options]`; `ruff` e `pytest-cov` in `requirements-dev.txt`; un workflow che
esegua `ruff check` e `pytest` a ogni push. Sono dipendenze nuove: per `CLAUDE.md` vanno concordate.

### 🟡 Minori

**M-1 · Il file `.env` intero entra nel container dell'agente**
`compose.yaml:55-58` e `108-111`, `.env.example:21`

`agent` e `assistant` caricano tutto `.env` e azzerano solo `POSTGRES_PASSWORD`. `.env.example`
propone nello stesso file `DATABASE_URL` con utente e password: chi la attiva la consegna anche
all'agente, che sta sulla stessa rete di `postgres`. Il codice non legge mai `.env` in locale (non
c'è `python-dotenv` nell'app), quindi quella riga in `.env.example` serve solo a questo.
Fix: elencare in `environment:` le sole variabili dell'agente, oppure azzerare anche
`DATABASE_URL`; spostare l'esempio di `DATABASE_URL` nel README.

**M-2 · Testi dell'utente nei log a livello INFO**
`assistant/graph.py:321-330` (argomenti e risultati degli strumenti, quindi il testo delle note),
`assistant/commands.py:189-193` (testo dei prompt)

Il back-end fa l'opposto di proposito (`hide_parameters=True`, `chars=%d` al posto del testo).
Fix: a INFO solo nome, id ed esito; argomenti e risultati a DEBUG.

**M-3 · Nessun limite di lunghezza sui testi in ingresso**
`backend/api.py:84-91` (`content`), `assistant/api.py:113-116` (`message`, `history`, `summary`)

Il titolo ha un limite (200), il messaggio no: un testo incollato per errore di qualche megabyte
viene salvato in PostgreSQL e mandato al modello. I servizi ascoltano solo su `127.0.0.1`, quindi
è un difetto di robustezza, non un'esposizione. Fix: `Field(max_length=…)` su `content` e `message`.

**M-4 · `run_tool` chiama «argomenti non validi» qualsiasi eccezione**
`assistant/graph.py:308-311`

`except Exception` copre anche un difetto interno dello strumento, e il modello riceve
l'indicazione di correggere argomenti che erano giusti; nel log resta `tool_error` senza traceback.
Fix: tenere quel testo per gli errori di validazione e registrare gli altri con `log.exception`.

**M-5 · `ValueError` tra gli errori di «risposta non valida» di router e revisore**
`assistant/model.py:17-22`, ricaduta in `assistant/graph.py:219-224` e `268-273` · da verificare,
confidenza media

Qualsiasi `ValueError` nato dentro `structured.invoke` diventa «risposta non valida» e il grafo
prosegue aperto: il router lascia passare la domanda, il revisore approva. La scelta di proseguire
è ragionevole e viene registrata a WARNING; il rischio è che un difetto di configurazione o di
libreria che solleva `ValueError` a ogni chiamata spenga router e revisore senza fermare nulla.
Fix: intercettare `pydantic.ValidationError` e `OutputParserException` al posto di `ValueError`,
dopo aver verificato quali eccezioni solleva davvero `langchain-openai` 1.7.2.

**M-6 · Il tempo massimo di un turno può superare quello di chi aspetta**
`assistant/model.py:33-34`, `assistant/api_client.py:21`

Ogni chiamata al modello aspetta 120 s con un ritentativo, e un turno ne contiene fino a 9
(riassunto, router, 5 passi, 2 revisioni): il caso peggiore supera di molto i 600 s di
`CHAT_TIMEOUT`. Il back-end risponde 504 e l'agente continua a lavorare per una risposta che
nessuno leggerà. Fix: un limite complessivo del turno nell'agente, sotto `CHAT_TIMEOUT`.

**M-7 · Codice di contorno ripetuto**
- `Utf8JsonMiddleware` identico in `assistant/api.py:465-491` e `backend/api.py:329-355`; uguali
  o quasi anche `ApiError`, `_json`, `_elapsed_ms`, `_log_error`, `_answer`.
- Lettura di una porta ripetuta tre volte: `assistant/config.py:127-137`,
  `backend/config.py:109-119`, `frontend/config.py:39-49`.
- `MAX_STEPS` e `MAX_REVIEWS` (`assistant/config.py:66-84`) riscrivono a mano `read_positive`,
  definita subito sotto (righe 86-98).

Fix: un modulo comune per i due servizi e una `read_port(env, name, default, problems)`.

**M-8 · `Config` costruita con 13 argomenti posizionali**
`assistant/config.py:141-147`

Diversi campi hanno lo stesso tipo: scambiarne due non dà errore. Fix: argomenti con nome.

**M-9 · Indirizzi validati in modo diverso**
`assistant/config.py:57` (`LMSTUDIO_BASE_URL`) e `frontend/config.py:32` (`BACKEND_URL`)
controllano solo il prefisso; `AGENT_URL` passa da `_is_valid_url` (riga 169). `http://` o una
porta non numerica vengono accettati e falliscono alla prima richiesta. Fix: usare `_is_valid_url`
per tutti e tre.

**M-10 · Due finestre di concorrenza nel client MCP** · da verificare, confidenza bassa
`assistant/mcp_client.py:287-293` e `297-301`

- `_run` legge `_client` e `_loop` senza lock mentre un altro thread può essere dentro `_restart`:
  se li legge tra la chiusura della sessione e l'arresto del loop, la richiesta finisce su un loop
  fermo (35 s di attesa, poi un secondo riavvio) o chiuso (`RuntimeError` fuori dal `try`, che
  `/status` mostra come 500). La finestra è di pochi microsecondi.
- Un `tools/list` di `/status` più lento di 5 s segna la sessione come da riavviare: il controllo
  di salute di Compose, ogni 30 s, può quindi far riavviare un server lento ma vivo.

Non li ho riprodotti. `test_concurrent_requests_restart_once` copre il riavvio unico, non questi
due casi.

**M-11 · Schema del database senza migrazioni**
`backend/db.py:84-86`

`create_all` crea le tabelle mancanti e non tocca le esistenti: una colonna aggiunta in futuro non
arriva nel volume `postgres-data` già creato. Per ora lo schema non è mai cambiato. Fix, quando
servirà: Alembic (dipendenza da concordare).

**M-12 · Elenchi senza paginazione**
`backend/store.py:117-127` e `129-137`

`list_chats` e `get_chat` restituiscono tutto. Con un utente va bene; è legato al debito R-C5.

**M-13 · Compose: solo `agent` e `postgres` hanno un controllo di salute, solo `backend` si riavvia**
`compose.yaml:24`, `42`, `47`

`frontend` e `backend` non hanno `healthcheck`; `agent`, `frontend` e `postgres` non hanno
`restart`. Dopo un riavvio di Docker Desktop torna su solo il back-end. Fix: `restart:
unless-stopped` sugli altri tre servizi e un `healthcheck` sul back-end (`GET /chats`).

**M-14 · Dipendenze dirette non all'ultima versione**
`requirements.txt`, `requirements-dev.txt`

Nessuna è vulnerabile o deprecata secondo `pip-audit`. Con una versione più recente: `openai`
3.37.0 → 3.51.0, `langchain-core` 1.7.0 → 1.8.1, `langchain-openai` 1.7.2 → 1.8.0, `langgraph`
1.2.17 → 1.2.22, `fastmcp` 4.1.6 → 4.2.0, `fastapi` 0.162.7 → 0.163.1, `pydantic` 2.14.1 → 2.14.3,
`tzdata` 2026.5 → 2026.6, `pytest` 9.1.1 → 9.2.0, `httpx2` 2.16.0 → 2.16.2. Non ho letto le note
di rilascio: non so se un aggiornamento rompa qualcosa. Il codice dipende da dettagli di versioni
precise (commenti «langchain-openai 1.7.2», «fastmcp 4.1.6»), quindi un aggiornamento va fatto con
le prove reali, non alla cieca. `constraints.txt` non ha gli hash dei pacchetti.

**M-15 · Stile**
16 righe oltre i 100 caratteri (massimo 127); 9 funzioni oltre la soglia di complessità di ruff
(`load_config`, `_message_from_json` tra le altre); `assistant/tools.py:10-13` ha una riga vuota
al posto di due dopo la classe; `NotesStore.list` (`assistant/notes.py:70`) copre il nome
`list` dentro la classe.

## Debiti già in `TODO.md` che la lettura conferma

Non li ripeto come problemi nuovi: sono descritti e accettati. Quelli che contano di più per la
correttezza sono **R-C4** (due invii contemporanei nella stessa chat: il secondo sovrascrive la
cronologia dell'agente, `backend/store.py:158-166`) e **R-D1** (pagina chiusa durante lo
streaming: la risposta a volte si salva e a volte no). Entrambi si chiudono con un blocco per chat
o un numero di versione sulla riga `chats`. **R-A9** (back-end e CLI importano `fastmcp` e
`langchain_core` per due dataclass) è la causa del voto di architettura non più alto: anche il
front-end, che serve file statici, installa tutte le dipendenze dell'agente.

## Che cosa funziona bene

- Calcolatrice su `ast` con insieme chiuso di nodi e limiti su lunghezza, esponente e grandezza
  (`assistant/calculator.py`): ho cercato un'espressione che la blocchi o che esca dai limiti e
  non l'ho trovata.
- SQL sempre con parametri; pagina sempre con `textContent`; CORS con origini elencate; container
  con utente non privilegiato e immagine base fissata per digest.
- `messages_from_json` controlla anche l'ordine chiamata/risposta, così una cronologia rotta viene
  rifiutata prima di arrivare a LM Studio.
- La password del database non compare mai in messaggi e log (`display_url`, errori senza URL).

## Azioni prioritarie

1. **I-1** — non ripetere `call_tool` dopo una connessione chiusa (poche righe, con un test).
2. **I-2** — `pyproject.toml` con ruff, `pytest-cov`, e un workflow che li esegua (da concordare).
3. **M-1** — togliere `env_file: .env` dall'agente o azzerare anche `DATABASE_URL`.
4. **M-2 e M-3** — testi dell'utente fuori dai log INFO; `max_length` su `content` e `message`.
5. **R-C4 / R-D1** — un blocco per chat sull'invio: è il debito noto con più effetto sui dati.
