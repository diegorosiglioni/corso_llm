# Assistente del laboratorio

Progetto del corso «Deep Learning e LLM: costruire chatbot e agenti».
La cartella del progetto è `"C:\Users\diegorosiglioni\Desktop\paolo\test_paolo"`; all'inizio contiene soltanto questo file.
Requisiti, specifica e piano: `assistente-laboratorio/docs/superpowers/`.
Stato corrente e prossimo passo: `assistente-laboratorio/docs/superpowers/handoff.md` (leggerlo per primo).

## Struttura e comandi
- Codice in `assistente-laboratorio/assistant/`: `config.py`, `model.py`, `tools.py`,
  `graph.py`, `session.py`, `terminal.py`; solo `__main__.py` collega i moduli.
- Test in `assistente-laboratorio/tests/`; il modello finto (`FakeModel`) e gli aiuti comuni
  sono in `conftest.py`. Le prove con LM Studio stanno in `test_real.py` (marcatore `real`).
- Dipendenze dirette in `requirements.txt` (app) e `requirements-dev.txt` (test); tutte le
  versioni verificate in `constraints.txt`, richiamato da `requirements.txt`.
- Comandi da PowerShell in `assistente-laboratorio/`, senza attivare l'ambiente:
  - ambiente: `py -3.13 -m venv .venv` e `.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`
  - test senza modello: `.\.venv\Scripts\python.exe -m pytest`
  - prove reali (LM Studio attivo, variabili impostate): `.\.venv\Scripts\python.exe -m pytest -m real -v`
  - avvio locale: `.\.venv\Scripts\python.exe -m assistant`
  - Docker: `docker compose build` e `docker compose run --rm assistant` (non `up`)

## Obiettivo
Un'applicazione da terminale in Python che conversa con un modello locale e:
- organizza il flusso in un grafo LangGraph esplicito (stato, nodi, instradamento riconoscibili);
- usa un modello servito da LM Studio, che resta sul computer host;
- conserva la cronologia della conversazione per la durata della sessione (la cronologia non è persistente);
- offre uno strumento orologio con fuso orario esplicito, richiesto dal modello tramite tool calling
  ed eseguito davvero dal programma;
- (lezione 5) collega un server MCP locale (FastMCP, stdio) che espone convertitore di unità,
  calcolatrice sicura, catalogo locale e note persistenti su SQLite, scoperti con `tools/list`;
- si avvia anche con Docker Compose.

## Confini
- Implementare solo i requisiti concordati. MCP e i quattro strumenti della lezione 5 sono
  concordati; altri strumenti, altri server MCP, workflow e RAG arriveranno nelle lezioni
  successive: non anticiparli.
- Niente interfacce grafiche, servizi cloud o framework non concordati.
- Lavorare solo dentro `assistente-laboratorio/`. La repository contiene altre lezioni:
  non leggerle per copiarne il codice e non modificarle.
- Lavorare nel branch corrente; nessun branch o worktree nuovo se non richiesto.
- Non modificare la cartella lezione3 che è solo una parte passata

## Scelte tecniche
- Python, codice sincrono e moduli piccoli, con una separazione semplice tra
  grafo, collegamento al modello, strumenti e interfaccia da terminale. L'asincronia del client
  MCP resta confinata nel suo modulo, che offre metodi sincroni.
- Lingua: codice in inglese (identificatori, moduli, variabili d'ambiente, nomi e argomenti degli
  strumenti, chiavi JSON, commenti); in italiano prompt di sistema, testi del terminale,
  descrizioni degli strumenti e messaggi d'errore; documentazione e commit in italiano.
- LM Studio sull'host, raggiunto tramite la sua API compatibile con OpenAI.
- Indirizzo del server e identificativo del modello solo da variabili d'ambiente.
  L'identificativo è quello restituito dal server (`GET /v1/models`), mai inventato.
- Un file di configurazione di esempio senza credenziali; il file reale resta fuori da Git.
- Docker Compose per l'applicazione; LM Studio non va containerizzato.
- Dipendenze motivate, concordate e con versioni fissate.
- Comandi documentati anche per PowerShell (Windows).

## Metodo: Superpowers
- Usare le skill di Superpowers per brainstorming, specifica, piano, implementazione e verifica.
- Non scrivere codice prima che io abbia approvato la specifica e poi il piano.
- Salvare specifica e piano in `assistente-laboratorio/docs/superpowers/`.
- Procedere per incrementi piccoli, ciascuno verificato prima del commit.

## Test e verifiche
- Test automatici ripetibili che non richiedono un modello attivo (grafo, cronologia,
  instradamento, strumento con istante controllato).
- Prove reali con LM Studio e con Docker tenute separate e attivate esplicitamente.
- Una risposta simulata non dimostra che il modello locale sappia usare lo strumento.
- Nel resoconto indicare che cosa è stato eseguito, con quale esito, e che cosa resta da provare.

## Git
- Conventional Commits in italiano, per esempio `feat(grafo): ...`, `test(strumenti): ...`,
  `docs: ...`.
- Prima di ogni commit: `git status`, controllo del diff, staging selettivo dei soli file pertinenti.
- Mai versionare credenziali, `.env`, ambienti virtuali, cache o pesi dei modelli.
- Push soltanto su mia richiesta.

## Documentazione
- Tenere aggiornato il README con configurazione, avvio, test e diagnosi, riportando solo
  comandi verificati.
- Aggiornare questo file quando cambiano convenzioni stabili (struttura, comandi di test,
  regole di lavoro), non per annotare l'avanzamento.
- Non tenere conto della la cartella lezione3 