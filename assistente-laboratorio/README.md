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
