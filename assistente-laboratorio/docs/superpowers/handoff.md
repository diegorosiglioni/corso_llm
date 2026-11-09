# Handoff — Assistente del laboratorio

Data: 2026-11-09
Stato: **lezione 5 progettata, implementazione da iniziare.** Requisiti §8 e specifica approvati il
2026-11-09; piano scritto e committato, nessun task eseguito. Il codice è ancora quello della
lezione 4 (pacchetto `assistente`, strumento `ora_corrente`).

## Riprendere da qui

**Prossimo passo:** eseguire il piano
[`plans/2026-11-09-strumenti-mcp.md`](plans/2026-11-09-strumenti-mcp.md) dal Task 1, con
`superpowers:executing-plans` (esecuzione nella sessione, consigliata) oppure
`superpowers:subagent-driven-development`. La modalità va confermata dall'utente.

Leggere prima, in quest'ordine:
1. `../../../CLAUDE.md`: regole del progetto (convenzione di lingua aggiornata il 2026-11-09).
2. [`specs/2026-11-09-strumenti-mcp-design.md`](specs/2026-11-09-strumenti-mcp-design.md): il
   **come**.
3. [`plans/2026-11-09-strumenti-mcp.md`](plans/2026-11-09-strumenti-mcp.md): 12 task, con i vincoli
   globali, la «Review Focus» e gli scostamenti dalla specifica.
4. [`requisiti.md`](requisiti.md) §8 (RF-15…RF-22, RNF-10, CA-11…CA-22) e le note «Rivisto il
   2026-11-09».

Da sapere prima di cominciare:
- **Il `.env` dell'utente va aggiornato a mano dopo il Task 1:** `LMSTUDIO_MODELLO` →
  `LMSTUDIO_MODEL`, `MAX_PASSI` → `MAX_STEPS`. Non modificarlo: chiederlo all'utente. Senza
  l'aggiornamento la prova Docker esce con «Manca LMSTUDIO_MODEL.».
- **LM Studio attivo** (modello `google/gemma-4-e2b`) serve nei Task 1, 9, 10 e 11.
- **`LLM_Lez_5.pdf`** è nella cartella, non tracciato: non aggiungerlo a Git senza chiedere.
  Lettura: il rendering delle pagine non è disponibile (manca `pdftoppm`); usare
  `pdftotext -layout LLM_Lez_5.pdf <scratchpad>/lez5.txt` (Git Bash). Il file prodotto è in
  cp1252.
- **In Git Bash `python` apre il REPL di Windows** e blocca il comando. Usare sempre
  `.venv/Scripts/python.exe` (o `py -3.13`).
- Valore di partenza della suite: `pytest` → `60 passed, 2 deselected`.

## Lezione 5: decisioni prese con l'utente (2026-11-09)

Fonte: `LLM_Lez_5.pdf`, «MCP: dalle funzioni agli strumenti condivisi». Il laboratorio chiede uno
strumento esposto via MCP, con discovery, invocazione, log correlati ed evidenze (slide 29–30).
L'utente ha chiesto i quattro strumenti del blocco 5: convertitore di unità, calcolatrice sicura,
catalogo locale, note persistenti.

| Tema | Decisione |
|------|-----------|
| Esposizione | Un solo server FastMCP (stdio) con 7 strumenti: `convert_units`, `calculate`, `search_catalog`, `get_item`, `add_note`, `list_notes`, `delete_note`. L'orologio resta locale. |
| Asincronia | Sessione MCP unica in un thread con il suo event loop; il resto dell'app resta sincrono. |
| Libreria | `fastmcp==4.1.6` per server e client, con un adattatore scritto nel progetto. |
| Conferme | Nel risultato dello strumento; eliminazione solo per id esatto; log di ogni modifica. Nessuna conferma dell'utente nel terminale. |
| Lingua | Codice in inglese, compreso l'esistente (pacchetto `assistant`, `get_current_time(timezone)`, variabili `LMSTUDIO_MODEL`/`MAX_STEPS`/`NOTES_DB`). In italiano prompt di sistema, testi del terminale, descrizioni degli strumenti, messaggi d'errore, documentazione e commit. |
| Fuori ambito | RAG, workflow, «Giorni e scadenze», «Meteo», variante FastAPI, resources/prompts MCP, Streamable HTTP, più server, riconnessione automatica. |

L'utente ha prima chiesto i prompt in inglese, poi ha precisato: **prompt di sistema e messaggi in
italiano, nomi nel codice in inglese**. Vale la seconda indicazione.

### Fatti verificati durante la progettazione

Verificati sui wheel scaricati da PyPI e nel venv attuale, senza installare nulla:
- Ultime versioni al 2026-11-09: `mcp` 2.3.0, `fastmcp` 4.1.6, `langchain-mcp-adapters` 0.3.2.
- In `mcp` 2.x `FastMCP` è stato rinominato `MCPServer`; `mcp.server.fastmcp` solleva un errore.
- `langchain-mcp-adapters` 0.3.2 richiede `mcp<2`, quindi non si combina con `fastmcp` 4, che
  richiede `mcp>=2.3`. Da qui la scelta dell'adattatore scritto nel progetto.
- API di `fastmcp` 4.1.6:
  - `fastmcp.client.transports.StdioTransport(command, args, env=None, cwd=None, keep_alive=None, log_file=None)`;
  - `Client.list_tools()`;
  - `Client.call_tool(name, arguments, *, timeout=None, raise_on_error=True)`, che restituisce
    `CallToolResult(content, structured_content, meta, data, is_error)`;
  - `fastmcp.exceptions.ToolError`.
- In `mcp-types` 2.3.0, `Tool` ha `input_schema` (snake_case), non `inputSchema`.
- Con langchain-core 1.7.0, `StructuredTool(args_schema=<dict JSON Schema>, metadata=…)`:
  - lo schema arriva così com'è in `convert_to_openai_tool`;
  - `invoke` non valida gli argomenti;
  - `metadata` viene conservato.
- `fastmcp` 4.1.6 porta molte dipendenze indirette (starlette, uvicorn, rich, authlib,
  pydantic-settings, …). Il Task 7 verifica che nessuna versione già fissata cambi.

## Commit del 2026-11-09 (solo locali, nessun push)

| Commit | Contenuto |
|--------|-----------|
| `6af978c` | handoff: correzioni dell'audit (modifica rimasta in sospeso dalla sessione precedente) |
| `be631ef` | README: immagine base citata corretta (`python:3.13.18-slim-trixie`) |
| `1d6ddd4` | requisiti della lezione 5 |
| `f069d6e` | specifica della lezione 5 |
| `518f279` | `CLAUDE.md`: obiettivo, confini, asincronia confinata, convenzione di lingua |
| `6027bcc` | piano di implementazione |
| (successivo) | stati di requisiti, specifica e piano; questo handoff |

`origin/main` è fermo a `5854213`.

## Che cosa c'è oggi (lezione 4, più le correzioni dell'audit)

Applicazione Python da terminale che conversa con `google/gemma-4-e2b` servito da LM Studio
sull'host, attraverso un grafo LangGraph esplicito: nodi `modello`, `strumenti`, `limite` e
funzione `instrada`. La cronologia la tiene `Sessione` per la sola sessione. C'è lo strumento
`ora_corrente` con fuso IANA; l'app si avvia in locale e con Docker Compose.

- Moduli in `assistente/`: `config.py`, `modello.py`, `strumenti.py`, `grafo.py`, `sessione.py`,
  `terminale.py`; li collega `__main__.py`. Test in `tests/`, con `test_reale.py` marcato `reale`.
- Dipendenze dirette in `requirements.txt` e `requirements-dev.txt`; tutte le versioni verificate
  in `constraints.txt` (49 pacchetti), richiamato con `-c`. Immagine
  `python:3.13.18-slim-trixie`, fissata per digest.
- `MAX_PASSI` limita le **chiamate al modello per turno**, non le chiamate agli strumenti. Un
  turno con uno strumento usa 2 passaggi.

Documenti precedenti:
- base: [`specs/2026-10-26-assistente-laboratorio-design.md`](specs/2026-10-26-assistente-laboratorio-design.md),
  [`plans/2026-10-26-assistente-laboratorio.md`](plans/2026-10-26-assistente-laboratorio.md);
- audit: [`specs/2026-11-03-correzioni-audit-design.md`](specs/2026-11-03-correzioni-audit-design.md),
  [`plans/2026-11-03-correzioni-audit.md`](plans/2026-11-03-correzioni-audit.md).

### Verifiche già fatte

| Ambito | Esito |
|--------|-------|
| CA-1…CA-10 (26–28/10) | tutte ✅: suite con LM Studio spento; prove reali `pytest -m reale` 2 passed; LM Studio fermato e riavviato; Docker; `esci`/Ctrl+Z/Ctrl+C; `git status --ignored` |
| Prove extra con il modello reale (28/10) | `MAX_PASSI=1` → limite al primo passaggio; sei città in una domanda → sei chiamate in un messaggio; «una alla volta» con limite 5 → quattro chiamate e poi il limite |
| Audit I1, M1, M2, M3 (03/11) | ✅: `constraints.txt` e immagine fissata (`04eaef9`); `httpx2` nei test (`444ce5e`); `LMSTUDIO_BASE_URL_DOCKER` in Compose (`ce2db84`); niente `.pyc` nell'immagine (`5854213`) |

Limite delle prove reali: dimostrano che `gemma-4-e2b` usa lo strumento con quelle domande, non che
lo faccia sempre. Il modello arrotonda l'orario al minuto in modo non uniforme.

### Decisioni di esecuzione ancora valide

- Lavoro su `main` senza worktree; push solo su richiesta.
- Logger `httpx`, `httpx2`, `openai` a WARNING salvo `LOG_LEVEL=DEBUG`. Con la lezione 5 si
  aggiungono `mcp` e `fastmcp`.
- Messaggio di configurazione prefissato da «Configurazione non valida: ».
- Fuso accettato solo se è in `zoneinfo.available_timezones()` (confronto esatto).
- `recursion_limit` di LangGraph non impostato (default 10007).
- Le `invalid_tool_calls` ricevono una risposta d'errore, come le chiamate.
- Eccezioni diverse da `openai.APIError` non intercettate dal terminale.
- Nessun test pytest per Compose e `.dockerignore`: le prove Docker restano manuali.

## Punti aperti

- **Lezione 5:** tutto il piano (Task 1–12).
- **Audit del 2026-11-03, punti M4–M13:** non affrontati. La descrizione non è nel repository: va
  ripresa dal resoconto dell'audit.
- **Minori ancora aperti:**
  - README, diagnosi «LM Studio non raggiungibile dal container»: il comando di prova usa
    `host.docker.internal:1234` fisso; con `LMSTUDIO_BASE_URL_DOCKER` va adattato a mano;
  - testo con `MAX_PASSI=1`: «il limite di 1 passaggi» (correzione proposta, non fatta);
  - con `MAX_PASSI` oltre ~5000 si avrebbe un errore di LangGraph invece del messaggio di RF-10;
  - container senza init (`docker stop` attende 10 s); possibile `init: true`;
  - su Windows con stdout rediretto, caratteri fuori da cp1252 possono causare `UnicodeEncodeError`.
    Va tenuto d'occhio con le note che contengono «€» o accenti.
- **Mai provati dopo l'audit:**
  - `docker compose run` interattivo con i tasti reali;
  - LM Studio su un'altra porta tramite `LMSTUDIO_BASE_URL_DOCKER`;
  - `docker compose build --no-cache`;
  - la procedura per cambiare una versione;
  - un revisore indipendente sul diff `708b40a..5854213`.
- Le caselle `- [ ]` dei piani del 26/10 e del 03/11 non sono state spuntate.

## Comandi (stato attuale, prima del Task 1)

Da PowerShell in `assistente-laboratorio/`:

```powershell
& "$HOME\.lmstudio\bin\lms.exe" server start
& "$HOME\.lmstudio\bin\lms.exe" load google/gemma-4-e2b --context-length 8192 -y
$env:LMSTUDIO_BASE_URL = "http://localhost:1234/v1"
$env:LMSTUDIO_MODELLO = "google/gemma-4-e2b"
.\.venv\Scripts\python.exe -m pytest            # senza modello: 60 passed, 2 deselected
.\.venv\Scripts\python.exe -m pytest -m reale -v
.\.venv\Scripts\python.exe -m assistente
docker compose build
"Che ore sono a Tokyo?", "esci" | docker compose run --rm -T assistente
```

Dopo il Task 1 i nomi diventano `LMSTUDIO_MODEL`, `-m real`, `-m assistant` e il servizio
`assistant`; il piano e il README aggiornato riportano i comandi nuovi. Le variabili valgono solo
nella finestra di PowerShell in cui si impostano. Docker legge `.env`, dove nel container
`LMSTUDIO_BASE_URL` vale `http://host.docker.internal:1234/v1`, oppure `LMSTUDIO_BASE_URL_DOCKER`
se è impostata.
