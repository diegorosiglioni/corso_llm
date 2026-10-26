# Assistente del laboratorio

Applicazione Python da terminale che conversa con un modello locale servito da LM Studio,
organizzata in un grafo LangGraph esplicito.

Requisiti e specifica: [`docs/superpowers/`](docs/superpowers/).

## Requisiti dell'host

- Python 3.13 (con il launcher `py` su Windows)
- LM Studio con il modello caricato e il server avviato
- Docker Desktop (solo per l'avvio con Docker Compose)

## Installazione

Tutti i comandi si eseguono in PowerShell dalla cartella `assistente-laboratorio`.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
```

Si usa direttamente `.\.venv\Scripts\python.exe`, senza attivare l'ambiente: così la execution
policy di PowerShell non interferisce. `requirements.txt` contiene le dipendenze
dell'applicazione, `requirements-dev.txt` aggiunge quelle dei test.

## Test automatici

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Non richiedono LM Studio né la rete: il modello è sostituito da un modello finto con risposte
programmate.

## Configurazione

L'applicazione legge solo variabili d'ambiente:

| Variabile | Obbligatoria | Default | Significato |
|-----------|--------------|---------|-------------|
| `LMSTUDIO_BASE_URL` | sì | — | indirizzo dell'API di LM Studio, es. `http://localhost:1234/v1` |
| `LMSTUDIO_MODELLO` | sì | — | identificativo del modello restituito da `GET /v1/models` |
| `MAX_PASSI` | no | `5` | chiamate massime al modello in un turno (intero ≥ 1) |
| `LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING` o `ERROR` |

`.env.example` è il modello versionato; la copia reale `.env` resta fuori da Git ed è letta da
Docker Compose:

```powershell
Copy-Item .env.example .env
```

In locale Python non legge `.env`: le variabili si impostano nella sessione di PowerShell.

```powershell
$env:LMSTUDIO_BASE_URL = "http://localhost:1234/v1"
$env:LMSTUDIO_MODELLO = "google/gemma-4-e2b"
```

Se manca una variabile obbligatoria o un valore non è valido, l'applicazione non parte, elenca i
problemi su stderr ed esce con codice 1:

```powershell
Remove-Item Env:LMSTUDIO_MODELLO
.\.venv\Scripts\python.exe -m assistente
$LASTEXITCODE    # 1
```

## Avvio locale

Con LM Studio avviato, il modello caricato e le variabili impostate:

```powershell
.\.venv\Scripts\python.exe -m assistente
```

Si conversa al prompt `Tu>`. La sessione termina con `esci`, con Ctrl+Z seguito da Invio
(fine input su Windows) o con Ctrl+C. La cronologia vale solo per la sessione in corso.
La conversazione va su stdout, i log su stderr.

Per una prova non interattiva si possono passare le domande in ingresso:

```powershell
"Mi chiamo Paolo", "Come mi chiamo?", "esci" | .\.venv\Scripts\python.exe -m assistente
```

## Prove reali con LM Studio

Sono separate dai test automatici e partono solo su richiesta, con le variabili impostate:

```powershell
.\.venv\Scripts\python.exe -m pytest -m reale -v
```

Senza variabili le prove falliscono con un messaggio esplicito invece di essere saltate.
Una risposta simulata non dimostra che il modello locale sappia usare lo strumento: lo dimostra
solo questa prova.

## Strumento orologio

Il modello può richiedere, tramite tool calling, lo strumento `ora_corrente` con un unico
parametro `fuso`: un nome di fuso orario IANA (es. `Europe/Rome`, `Asia/Tokyo`). Il programma lo
esegue davvero e restituisce al modello, per esempio,
`{"fuso": "Asia/Tokyo", "data_ora": "2026-10-27T01:45:21+09:00"}`. Con un fuso sconosciuto
restituisce un messaggio d'errore con un esempio di nome valido, così il modello può correggersi.

In un turno il modello è chiamato al più `MAX_PASSI` volte; se all'ultimo passaggio chiede ancora
uno strumento, il turno termina con «Ho raggiunto il limite di 5 passaggi senza una risposta
finale.» e la sessione resta utilizzabile.

A livello `INFO` i log su stderr mostrano ogni passaggio, ogni chiamata e il suo risultato:

```
INFO assistente.grafo: passaggio 1/5 → modello
INFO assistente.grafo: passaggio 1/5 chiamata ora_corrente {'fuso': 'Asia/Tokyo'}
INFO assistente.grafo: passaggio 1/5 risultato ora_corrente {'fuso': 'Asia/Tokyo', 'data_ora': '2026-10-27T01:45:21+09:00'}
INFO assistente.grafo: passaggio 2/5 → modello
Tu> Assistente> Ora a Tokyo è le 01:45 del 27 ottobre 2026.
```

Le prove reali (`pytest -m reale`) verificano con il modello locale che la domanda su Tokyo produca
una chiamata con `Asia/Tokyo` e una risposta con l'orario restituito, che «E a Roma?» produca una
chiamata con `Europe/Rome` e che un nome detto in precedenza venga ricordato senza strumenti.

## Diagnosi

**Quali modelli serve LM Studio?** L'identificativo da usare in `LMSTUDIO_MODELLO` è quello
restituito dal server:

```powershell
(Invoke-RestMethod http://localhost:1234/v1/models).data.id
```

**LM Studio non raggiungibile.** L'assistente risponde
`Errore: LM Studio non ha risposto correttamente (Connection error.). Riprova.` e la sessione resta
attiva: la domanda fallita non entra nella cronologia, quindi si può riprovare dopo aver avviato
il server. Controllare che il server di LM Studio sia avviato e che `LMSTUDIO_BASE_URL` termini
con `/v1`.

**Più dettagli.** Con `$env:LOG_LEVEL = "DEBUG"` i log mostrano la traccia completa degli errori
e le richieste HTTP verso LM Studio.

**Il modello non usa lo strumento.** Nei log manca la riga `chiamata ora_corrente` e l'orario è
inventato, oppure il risultato contiene `errore` per un fuso non IANA. È un limite del modello, non
del programma: con `google/gemma-4-e2b` le prove reali del 2026-10-26 sono passate (chiamate con
`Asia/Tokyo` ed `Europe/Rome`, orario riportato correttamente). Un altro modello si prova cambiando
solo `LMSTUDIO_MODELLO` e ripetendo `pytest -m reale`.
