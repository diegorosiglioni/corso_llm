# Assistente del laboratorio

Applicazione Python da terminale che conversa con un modello locale servito da LM Studio,
organizzata in un grafo LangGraph esplicito. Il modello usa un orologio locale e sette strumenti
offerti da un server MCP locale (FastMCP, stdio): convertitore di unità, calcolatrice, catalogo
dei corsi e note persistenti.

Requisiti e specifica: [`docs/superpowers/`](docs/superpowers/).

## Requisiti dell'host

- Python 3.13 (con il launcher `py` su Windows)
- LM Studio con il modello caricato e il server avviato
- Docker Desktop (solo per l'avvio con Docker Compose)

## Installazione

Tutti i comandi si eseguono in PowerShell dalla radice della repository.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
```

Si usa direttamente `.\.venv\Scripts\python.exe`, senza attivare l'ambiente: così la execution
policy di PowerShell non interferisce. `requirements.txt` contiene le dipendenze
dell'applicazione, `requirements-dev.txt` aggiunge quelle dei test.

`requirements.txt` richiama `constraints.txt`, che fissa tutte le versioni verificate, anche le
indirette: così venv e immagine Docker installano gli stessi pacchetti. Il file si rigenera dal
venv in cui passano test e prove reali:

```powershell
@("# Versioni verificate: rigenerare con il comando del README, sezione Installazione.") + (.\.venv\Scripts\python.exe -m pip freeze) | Out-File -Encoding ascii constraints.txt
```

Per cambiare una versione: aggiornare i requirements, svuotare `constraints.txt`, reinstallare,
ripetere le verifiche e rigenerarlo.

## Test automatici

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Non richiedono LM Studio né la rete: il modello è sostituito da un modello finto con risposte
programmate. I test del server MCP lo avviano davvero come sottoprocesso stdio, con l'archivio
delle note in una cartella temporanea (circa 1 s per test).

## Configurazione

L'applicazione legge solo variabili d'ambiente:

| Variabile | Obbligatoria | Default | Significato |
|-----------|--------------|---------|-------------|
| `LMSTUDIO_BASE_URL` | sì | — | indirizzo dell'API di LM Studio, es. `http://localhost:1234/v1` |
| `LMSTUDIO_MODEL` | sì | — | identificativo del modello restituito da `GET /v1/models` |
| `MAX_STEPS` | no | `5` | chiamate massime al modello in un turno (intero ≥ 1) |
| `LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING` o `ERROR` |
| `NOTES_DB` | no | `data/notes.sqlite3` | file SQLite delle note, relativo alla cartella di avvio |

`.env.example` è il modello versionato; la copia reale `.env` resta fuori da Git ed è letta da
Docker Compose:

```powershell
Copy-Item .env.example .env
```

**Un `.env` creato prima della lezione 5 va aggiornato a mano:** `LMSTUDIO_MODELLO` diventa
`LMSTUDIO_MODEL` e `MAX_PASSI` diventa `MAX_STEPS`. Con i nomi vecchi l'avvio con Docker si ferma
con «Configurazione non valida: Manca LMSTUDIO_MODEL.».

In locale Python non legge `.env`: le variabili si impostano nella sessione di PowerShell.

```powershell
$env:LMSTUDIO_BASE_URL = "http://localhost:1234/v1"
$env:LMSTUDIO_MODEL = "google/gemma-4-e2b"
```

Se manca una variabile obbligatoria o un valore non è valido, l'applicazione non parte, elenca i
problemi su stderr ed esce con codice 1:

```powershell
Remove-Item Env:LMSTUDIO_MODEL
.\.venv\Scripts\python.exe -m assistant
$LASTEXITCODE    # 1
```

## Avvio locale

Con LM Studio avviato, il modello caricato e le variabili impostate:

```powershell
.\.venv\Scripts\python.exe -m assistant
```

Si conversa al prompt `Tu>`. La sessione termina con `esci`, con Ctrl+Z seguito da Invio
(fine input su Windows) o con Ctrl+C. La cronologia vale solo per la sessione in corso.
La conversazione va su stdout, i log su stderr.

Per una prova non interattiva si possono passare le domande in ingresso:

```powershell
"Mi chiamo Paolo", "Come mi chiamo?", "esci" | .\.venv\Scripts\python.exe -m assistant
```

## Prove reali con LM Studio

Sono separate dai test automatici e partono solo su richiesta, con le variabili impostate:

```powershell
.\.venv\Scripts\python.exe -m pytest -m real -v
```

Senza variabili le prove falliscono con un messaggio esplicito invece di essere saltate.
Una risposta simulata non dimostra che il modello locale sappia usare lo strumento: lo dimostra
solo questa prova.

## Strumenti

Il modello richiede gli strumenti tramite tool calling; il programma li esegue davvero e gli
restituisce il risultato. Un errore dello strumento arriva al modello come `{"error": "…"}` con un
messaggio in italiano, così può correggersi.

**Locale** (eseguito nel processo dell'applicazione):

| Strumento | Esempio di domanda | Esempio di risultato |
|-----------|--------------------|----------------------|
| `get_current_time(timezone)` | «Che ore sono a Tokyo?» | `{"timezone": "Asia/Tokyo", "datetime": "2026-11-09T23:29:22+09:00"}` |

**MCP** (server `assistant.mcp_server`, avviato dall'applicazione come sottoprocesso stdio e
scoperto con `tools/list`; l'applicazione espone al modello solo i sette nomi attesi):

| Strumento | Esempio di domanda | Esempio di risultato |
|-----------|--------------------|----------------------|
| `convert_units(value, from_unit, to_unit)` | «Converti 10 km in miglia» | `{"value": 10, "from_unit": "km", "to_unit": "mi", "quantity": "lunghezza", "result": 6.21371}` |
| `calculate(expression)` | «Quanto fa 17 * 23?» | `{"expression": "17 * 23", "result": 391}` |
| `search_catalog(query, max_results=5)` | «Ci sono corsi di Python?» | `{"query": "python", "results": [{"code": "PY-101", …}, {"code": "PY-201", …}], "total": 2}` |
| `get_item(code)` | «Quante ore dura il corso di visione artificiale?» | il record completo di `DL-201`, con `"duration_hours": 32` |
| `add_note(text)` | «Ricordami di consegnare il report venerdì» | `{"id": 1, "text": "Consegnare il report venerdì", "created_at": "2026-11-09T14:41:15+00:00"}` |
| `list_notes(limit=10)` | «Quali note ho?» | `{"notes": [{"id": 1, …}], "total": 1}`, dalla più recente |
| `delete_note(note_id)` | «Elimina la nota 99» | `{"error": "Nessuna nota con id 99: nessuna nota eliminata."}` |

- **Convertitore:** lunghezza (mm, cm, m, km, in, ft, yd, mi), massa (mg, g, kg, t, oz, lb),
  temperatura (C, F, K) e volume (ml, l, gal USA); risultato a 6 cifre significative.
- **Calcolatrice:** solo numeri, `+ - * / // % **` e parentesi, analizzati con `ast` senza `eval`;
  al più 200 caratteri, esponenti fino a 100, numeri fino a 1e100.
- **Catalogo:** 8 corsi d'esempio **inventati**, in `assistant/data/catalog.json`. La ricerca vuole
  tutte le parole in codice, titolo o sede; il dettaglio si chiede con il codice esatto
  (maiuscole e spazi esterni ignorati).
- **Note:** SQLite nel file di `NOTES_DB` (in locale `data/notes.sqlite3`, ignorato da Git; in
  Docker il volume `notes-data`). Le note restano tra un avvio e l'altro; un'eliminazione richiede
  l'id esatto e restituisce la nota eliminata. Ogni modifica compare nel log del server
  (`event=note_added id=1`, `event=note_deleted id=1`). Per azzerarle: cancellare il file
  `data\notes.sqlite3`, oppure in Docker `docker volume rm assistente-laboratorio_notes-data`.
  `created_at` è in UTC.

Se il server MCP non parte, l'applicazione esce con «Server MCP non avviato: <motivo>». Se il
collegamento si interrompe durante la sessione, lo strumento risponde «Strumento non raggiungibile:
… Riprova o riavvia l'assistente.»: non c'è riconnessione automatica, va riavviata l'applicazione.

In un turno il modello è chiamato al più `MAX_STEPS` volte; se all'ultimo passaggio chiede ancora
uno strumento, il turno termina con «Ho raggiunto il limite di 5 passaggi senza una risposta
finale.» e la sessione resta utilizzabile.

A livello `INFO` i log su stderr mostrano all'avvio l'elenco degli strumenti con la variante, poi
ogni passaggio, ogni chiamata con variante e `call_id`, l'esito (`ok`, `tool_error`,
`transport_error`; WARNING se diverso da `ok`) e il messaggio restituito al modello. Le righe del
server MCP (`assistant.mcp_server`) si intercalano a quelle del grafo. Prova reale del 2026-11-09:

```
INFO __main__: tools=[get_current_time (local), convert_units (mcp), calculate (mcp), search_catalog (mcp), get_item (mcp), add_note (mcp), list_notes (mcp), delete_note (mcp)]
INFO assistant.graph: step=1/5 node=llm
INFO assistant.graph: step=1/5 variant=mcp tool=add_note call_id=WLCQjkfF0ugFhx6llQ79dfhJngEAAbRo arguments={'text': 'comprare il latte'}
INFO assistant.mcp_server: event=note_added id=1
INFO assistant.graph: step=1/5 execution=ok call_id=WLCQjkfF0ugFhx6llQ79dfhJngEAAbRo result={'id': 1, 'text': 'comprare il latte', 'created_at': '2026-11-09T14:49:40+00:00'}
INFO assistant.graph: tool_message.call_id=WLCQjkfF0ugFhx6llQ79dfhJngEAAbRo next_node=llm
INFO assistant.graph: step=2/5 node=llm
Tu> Assistente> Nota aggiunta: Ricordati di comprare il latte.
```

Le prove reali (`pytest -m real`, 9 prove) verificano con il modello locale: l'orario a Tokyo e
poi a Roma; un nome ricordato senza strumenti; `calculate` e `convert_units`; una sola `add_note`
per una richiesta di ricordare; `delete_note` su un id inesistente che non elimina nulla; le note
ritrovate dopo il riavvio del server; `search_catalog` seguito da `get_item`; una ricerca senza
risultati; i log correlati dallo stesso `call_id`.

## Docker

LM Studio resta sull'host; nel container gira solo l'applicazione. Compose legge `.env` (vedi
«Configurazione») e nel container imposta `LMSTUDIO_BASE_URL` a
`http://host.docker.internal:1234/v1`. Se LM Studio usa un'altra porta o un altro host, si imposta
`LMSTUDIO_BASE_URL_DOCKER` nel `.env` (vedi `.env.example`).

```powershell
Copy-Item .env.example .env      # solo la prima volta
docker compose build
docker compose run --rm assistant
```

L'avvio interattivo si fa con `docker compose run --rm`: `docker compose up` non collega
correttamente l'input del terminale. Per una prova non interattiva serve `-T`:

```powershell
"Che ore sono a Tokyo?", "esci" | docker compose run --rm -T assistant
```

L'immagine (`python:3.13.18-slim-trixie`, fissata per digest nel `Dockerfile`) contiene solo il
pacchetto `assistant` (con `assistant/data/catalog.json`) e le dipendenze dell'applicazione, ed
esegue come utente non root. Il server MCP gira nello stesso container, come sottoprocesso. Nel
container l'orario dei log è in UTC; l'orario restituito dallo strumento dipende solo dal fuso
richiesto.

Le note stanno nel volume `notes-data`, montato in `/app/data`: una nota salvata in un
`docker compose run --rm` si ritrova nel successivo. Il volume si elimina con
`docker volume rm assistente-laboratorio_notes-data`.

## Diagnosi

**Quali modelli serve LM Studio?** L'identificativo da usare in `LMSTUDIO_MODEL` è quello
restituito dal server:

```powershell
(Invoke-RestMethod http://localhost:1234/v1/models).data.id
```

**LM Studio non raggiungibile.** L'assistente risponde
`Errore: LM Studio non ha risposto correttamente (Connection error.). Riprova.` e la sessione resta
attiva: la domanda fallita non entra nella cronologia, quindi si può riprovare dopo aver avviato
il server. Controllare che il server di LM Studio sia avviato e che `LMSTUDIO_BASE_URL` termini
con `/v1`.

**Contesto del modello superato.** Se la richiesta supera il contesto caricato in LM Studio
(8192 token per `google/gemma-4-e2b` nella configurazione provata), l'assistente mostra
`Errore: LM Studio non ha risposto correttamente (Error code: 400 - ... exceeds the available context size ...). Riprova.`
Se la causa è una sola domanda troppo lunga, basta riformularla: la domanda rifiutata non entra
nella cronologia. Se invece è la cronologia della sessione a essere diventata troppo lunga, ogni
domanda successiva fallirà allo stesso modo: chiudere con `esci` e riavviare l'assistente (la
cronologia riparte da zero), oppure aumentare in LM Studio la lunghezza del contesto del modello.

**Più dettagli.** Con `$env:LOG_LEVEL = "DEBUG"` i log mostrano la traccia completa degli errori
e le richieste HTTP verso LM Studio.

### Strumenti MCP, livello per livello

**1. Il processo del server non parte.** L'applicazione esce con «Server MCP non avviato: …» (per
esempio «Connection closed»); il motivo dettagliato del sottoprocesso compare su stderr. Il server
si può avviare a mano: con l'ingresso chiuso deve uscire subito con codice 0, altrimenti mostra
l'errore (dipendenza mancante, modulo non trovato):

```powershell
$null | .\.venv\Scripts\python.exe -m assistant.mcp_server --notes-db data\notes.sqlite3
$LASTEXITCODE    # 0
```

**2. Il catalogo degli strumenti è vuoto o incompleto.** All'avvio la riga `tools=[…]` deve
elencare otto strumenti; un nome atteso ma assente produce il WARNING «strumento MCP consentito ma
assente dal catalogo». La discovery si prova da sola (deve stampare sette righe):

```powershell
@'
from pathlib import Path
from assistant.mcp_client import McpClient, server_command
command, args, cwd = server_command(Path("data/notes.sqlite3").resolve(), "WARNING")
with McpClient(command, args, cwd=cwd) as client:
    for tool in client.list_tools():
        print(tool.name, "-", tool.description[:50])
'@ | .\.venv\Scripts\python.exe -
```

Il catalogo dei corsi si controlla così:

```powershell
.\.venv\Scripts\python.exe -c "from assistant.catalog import Catalog; print(Catalog.load().search('python'))"
```

**3. Lo strumento è elencato ma il modello non lo chiama.** Nei log manca la riga `tool=<nome>` e
la risposta è inventata (per esempio un orario o un risultato di calcolo). È un limite del modello,
non del programma: con `google/gemma-4-e2b` le 9 prove reali del 2026-11-09 sono passate, ma un
modello piccolo con otto strumenti può sceglierne uno sbagliato. Un altro modello si prova
cambiando solo `LMSTUDIO_MODEL` e ripetendo `pytest -m real`.

**4. Il risultato è corretto ma la risposta è sbagliata.** La riga `execution=ok … result=…` mostra
il valore giusto e la risposta del modello lo riporta male (per esempio l'orario UTC di
`created_at` presentato come ora locale). Anche questo è un limite del modello: il risultato
restituito si legge nel log, con lo stesso `call_id` della chiamata.

**LM Studio non raggiungibile dal container.** Si verifica così:

```powershell
docker compose run --rm -T assistant python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:1234/v1/models').read()[:200])"
```

Deve stampare l'elenco dei modelli. Con Docker Desktop su Windows ha funzionato senza modificare
LM Studio; se fallisce, attivare in LM Studio l'opzione per servire anche sulla rete locale.

**Configurazione nel container.** Una variabile si può sovrascrivere per una sola esecuzione, per
esempio per verificare il messaggio di configurazione mancante:

```powershell
docker compose run --rm -T -e LMSTUDIO_MODEL= assistant
```
