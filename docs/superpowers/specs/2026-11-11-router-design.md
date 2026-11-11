# Specifica — Lezione 6, Step 1: router (conversazione o fuori ambito)

Data: 2026-11-11
Stato: in revisione
Requisiti: [`../requisiti.md`](../requisiti.md), §9 (RF-23…RF-27, CA-23…CA-29).
Specifiche precedenti: [`2026-11-09-strumenti-mcp-design.md`](2026-11-09-strumenti-mcp-design.md)
(lezione 5) e quelle che richiama.
Fonte didattica: `LLM_Lez_6.pdf`, slide 3 («Il grafo dopo i primi tre step») e slide 4
(«Step 1 · Router»); riassunto in [`../lezione6.md`](../lezione6.md).

Questa specifica aggiunge al grafo esistente un nodo router LLM, posto prima dell'agente, e un
nodo di rifiuto. Il resto dell'applicazione (strumenti, MCP, sessione, terminale, Docker) non
cambia. Dove non dice altro, valgono le specifiche precedenti.

## 1. Decisioni

| Tema | Decisione | Motivo |
|------|-----------|--------|
| Ambito | Testo in `assistant/data/scope.txt`, versionato; `SCOPE_FILE` lo sostituisce | Requisito 1 della slide 4; un testo di più righe si gestisce male in una variabile d'ambiente; il file è già nell'immagine Docker |
| Criterio | In ambito: gli argomenti degli strumenti, più saluti, ringraziamenti, domande sull'assistente, presentazioni dell'utente e domande su quanto detto nella conversazione | Scelta dell'utente; la categoria si chiama «conversazione»; CA-4 e lo step 3 usano il nome dell'utente |
| Strumenti e router | Il router riceve solo il testo dell'ambito: niente elenco, nomi o schemi degli strumenti, niente `bind_tools` | Requisito 4: se servono strumenti lo decide l'agente, come prima |
| Ingresso del router | Cronologia filtrata: domande dell'utente e risposte testuali dell'assistente | Capisce i seguiti («E a Roma?») senza vedere le chiamate agli strumenti |
| Output strutturato | `with_structured_output(RouteDecision, method="json_schema")` | LM Studio vincola la generazione allo schema; nessun «strumento» fittizio |
| Output non valido | Si lascia passare: `conversation` con un WARNING nei log | Un guasto del router non blocca le domande legittime e resta visibile |
| Rifiuto | Nodo senza LLM, testo fisso con il motivo del router | Nessuna chiamata in più; l'ambito non viene ripetuto nel codice |
| Modello | Lo stesso di LM Studio (`LMSTUDIO_MODEL`) con un prompt di sistema diverso | Slide 3: «Lo stesso modello viene usato con prompt di sistema diversi» |
| Organizzazione | Modulo nuovo `router.py`; in `graph.py` solo i due nodi e l'arco | Moduli piccoli; revisore e riassunto (step 2–3) troveranno `graph.py` leggibile |

## 2. Grafo

Grafo alla fine dello Step 1. Sono nuovi i nodi `router` e `refusal` e l'arco condizionale che li
collega; da `llm` in poi il grafo è quello della lezione 5.

```
START → [router] ─ conversation ─→ [llm] ──route──┬─ nessuna tool_call ──────────→ END
           │                         ▲             ├─ tool_call, steps < max_steps → [tools] ─┐
           │                         └─────────────┼──────────────────────────────────────────┘
           │                                       └─ tool_call, steps ≥ max_steps → [limit] → END
           └─ out_of_scope ─→ [refusal] → END
```

Rispetto alla slide 3 mancano `Riassunto` (step 3) e `Revisore` (step 2): non vengono anticipati.

## 3. Struttura

```
assistant/
├── config.py        # + scope_file, scope; lettura di SCOPE_FILE
├── router.py        # NUOVO: RouteDecision, ROUTER_PROMPT, router_messages, refusal_text
├── model.py         # + create_router_model(config)
├── graph.py         # + campi di stato, nodi router e refusal, route_after_router
├── __main__.py      # + modello del router e ambito passati al grafo
└── data/
    └── scope.txt    # NUOVO: testo dell'ambito
```

`session.py`, `terminal.py`, `tools.py` e i moduli MCP non cambiano.

## 4. Ambito (`assistant/data/scope.txt`) e configurazione

Contenuto iniziale di `scope.txt` (UTF-8):

```
L'assistente del laboratorio si occupa solo di:
- data e ora attuali in un fuso orario;
- conversioni tra unità di misura (lunghezza, massa, temperatura, volume);
- calcoli aritmetici;
- corsi del catalogo del laboratorio (ricerca e dettaglio: codice, titolo, sede, durata);
- note dell'utente (salvare, elencare, eliminare);
- saluti, ringraziamenti e domande sull'assistente e su che cosa sa fare;
- presentazioni dell'utente e domande su quanto detto in questa conversazione.
Ogni altra richiesta è fuori ambito.
```

In `config.py`:
- `SCOPE_FILE`: percorso del file dell'ambito. Se manca o è vuota vale il `scope.txt` del
  pacchetto, risolto rispetto al modulo (`Path(__file__).parent / "data" / "scope.txt"`) e non
  rispetto alla cartella di avvio. Un percorso relativo indicato dall'utente vale rispetto alla
  cartella di avvio, come `NOTES_DB`.
- `load_config` legge il file e aggiunge a `Config` due campi: `scope_file: str` (percorso usato)
  e `scope: str` (testo, senza spazi iniziali e finali).
- Errori, aggiunti agli altri problemi del messaggio «Configurazione non valida: …» (exit 1):
  - file mancante o illeggibile → `SCOPE_FILE non leggibile: '<percorso>' (<motivo>).`;
  - file vuoto o di soli spazi → `SCOPE_FILE vuoto: '<percorso>'.`

Con Docker si usa il `scope.txt` contenuto nell'immagine (`COPY assistant/` già presente). Per
cambiare l'ambito si modifica il file e si ricostruisce l'immagine; montare un file diverso nel
container non è previsto in questo step.

## 5. Router (`router.py`)

### Schema

```python
class RouteDecision(BaseModel):
    category: Literal["conversation", "out_of_scope"] = Field(
        description="conversation se il messaggio rientra nell'ambito, altrimenti out_of_scope")
    reason: str = Field(description="Motivo della scelta, in una frase breve in italiano")
```

Chiavi e valori in inglese (sono identificatori: RNF-10); descrizioni in italiano, perché le legge
il modello.

### Prompt

`ROUTER_PROMPT` è un modello di testo con il segnaposto `{scope}`. Testo di partenza, che si può
ritoccare durante la prova reale senza cambiare il comportamento richiesto:

```
Sei il router dell'assistente del laboratorio. Non rispondi all'utente: decidi soltanto se il suo
ultimo messaggio rientra nell'ambito dell'assistente.

Ambito:
{scope}

Usa la conversazione precedente solo per capire i messaggi brevi che la continuano (per esempio
«E a Roma?» dopo una domanda sull'ora a Tokyo).
- conversation: l'ultimo messaggio rientra nell'ambito;
- out_of_scope: l'ultimo messaggio non rientra nell'ambito.
Nel motivo spiega la scelta in una frase breve, in italiano.
```

Il prompt non nomina gli strumenti e non chiede quale usare.

### Funzioni

- `router_messages(history)`: restituisce, nell'ordine, le `HumanMessage` e le `AIMessage` che
  hanno testo e nessuna `tool_calls` (né `invalid_tool_calls`). Scarta `ToolMessage`, `AIMessage`
  di sole richieste di strumenti e messaggi di sistema. Non modifica la cronologia.
- `refusal_text(reason)`: `Mi dispiace, questa domanda è fuori dal mio ambito: {motivo}. Chiedimi
  pure che cosa so fare.` Il motivo viene ripulito da spazi e da un punto finale; se resta vuoto il
  testo diventa `Mi dispiace, questa domanda è fuori dal mio ambito. Chiedimi pure che cosa so
  fare.`

## 6. Modello del router (`model.py`)

`create_router_model(config) -> Runnable`: una `ChatOpenAI` con gli stessi parametri di
`create_model` (indirizzo, modello, `temperature=0`, `timeout=120`, `max_retries=1`), seguita da
`.with_structured_output(RouteDecision, method="json_schema")`. Nessun `bind_tools`. Restituisce
un'istanza di `RouteDecision`.

## 7. Grafo (`graph.py`)

### Stato

```python
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    steps: int        # chiamate del modello dell'agente nel turno
    category: str     # NUOVO: categoria decisa dal router nel turno
    reason: str       # NUOVO: motivo del router
```

`Session` continua a invocare il grafo con `messages` e `steps`; `category` e `reason` li scrive il
router a ogni turno e non vengono conservati tra un turno e l'altro (la sessione tiene solo
`messages`). Il router non incrementa `steps`: il limite dei passaggi riguarda solo l'agente.

### Firma

`build_graph(model, tools, max_steps, *, router_model, scope)`: i parametri esistenti restano
nella stessa posizione; i nuovi sono obbligatori e per nome.

### Nodo `router`

1. Invoca `router_model` con `[SystemMessage(ROUTER_PROMPT.format(scope=scope))] +
   router_messages(state["messages"])`.
2. Se il risultato è una `RouteDecision`, scrive `category` e `reason` e registra:
   `INFO node=router category=<categoria> reason=<motivo tra virgolette> next_node=<llm|refusal>`.
   Il motivo è scritto con `json.dumps(..., ensure_ascii=False)`, così resta su una riga e mantiene
   le lettere accentate.
3. Ripiego: se l'output non è valido (eccezione di parsing o di validazione dell'output, oppure
   risultato che non è una `RouteDecision`), scrive `category="conversation"` e
   `reason=""` e registra
   `WARNING node=router fallback=invalid_output error=<errore> category=conversation next_node=llm`.
   L'elenco preciso delle eccezioni intercettate si fissa nel piano, verificando quelle sollevate
   da `langchain-openai` 1.7.2 con `json_schema`; `openai.APIError` non è tra queste.
4. Gli errori di collegamento con LM Studio (`openai.APIError`) non vengono intercettati: arrivano
   al terminale come oggi, che mostra «Errore: LM Studio…»; la cronologia non cambia.

### Instradamento

`route_after_router(state) -> Literal["llm", "refusal"]`: `llm` se `category == "conversation"`,
altrimenti `refusal`. Archi: `START → router`; `router → llm | refusal` (condizionale);
`refusal → END`. Gli archi esistenti da `llm` in poi non cambiano.

### Nodo `refusal`

Registra `INFO node=refusal` e aggiunge `AIMessage(refusal_text(state["reason"]))`. Va a `END`.
Il modello dell'agente non viene chiamato. Il rifiuto entra nella cronologia come un turno
normale; la sessione lo mostra come qualsiasi altra risposta.

### Esempi di log

```
INFO assistant.graph: node=router category=conversation reason="chiede l'ora a Tokyo" next_node=llm
INFO assistant.graph: step=1/5 node=llm
...
INFO assistant.graph: node=router category=out_of_scope reason="domanda sul calcio" next_node=refusal
INFO assistant.graph: node=refusal
```

Evidenza del percorso fuori ambito: `next_node=refusal` e nessuna riga `node=llm` nel turno.

## 8. Avvio (`__main__.py`)

Dopo la creazione del modello dell'agente, `main` crea `create_router_model(config)` e chiama
`build_graph(model, tools, config.max_steps, router_model=..., scope=config.scope)`. Accanto al log
`tools=[…]` registra `scope_file=<percorso>`.

## 9. Dipendenze

`requirements.txt` aggiunge `pydantic==2.14.1` (già in `constraints.txt` come dipendenza
indiretta di `langchain-core`): `router.py` la importa direttamente. Nessun'altra dipendenza.

## 10. Test

### Con il modello simulato (`pytest`, senza LM Studio)

- `conftest.py`: `fake_graph(model, tools=None, max_steps=5, router=None)`; senza `router` usa un
  router finto che risponde sempre `RouteDecision(category="conversation", reason="test")`, così i
  test esistenti non cambiano. Per i casi nuovi le risposte del router si preparano con il
  `FakeModel` esistente (una `RouteDecision` oppure un'eccezione).
- `test_config.py`: ambito predefinito letto dal pacchetto; `SCOPE_FILE` personalizzato; file
  mancante e file vuoto → `ConfigError`, insieme agli altri problemi.
- `test_router.py` (nuovo): il filtro toglie `ToolMessage` e `AIMessage` con `tool_calls` e tiene
  i messaggi testuali in ordine; il prompt contiene l'ambito e non nomina gli strumenti; lo schema
  rifiuta una categoria diversa dalle due; `refusal_text` con motivo, con punto finale e vuoto.
- `test_graph.py`:
  - in ambito: il router riceve prompt con l'ambito più la cronologia filtrata; l'agente viene
    chiamato; i log contengono categoria, motivo e `next_node=llm`;
  - fuori ambito: la risposta è il rifiuto con il motivo; il modello dell'agente non viene mai
    chiamato (`calls == []`); nei log c'è `node=refusal` e non c'è `node=llm`;
  - ripiego: un errore di parsing del router porta all'agente con il WARNING
    `fallback=invalid_output`;
  - il router non consuma passaggi (`steps` invariato dopo il router);
  - il grafo compilato contiene i nodi `router` e `refusal`.
- `test_session.py`: un `APIError` sollevato dal router lascia la cronologia invariata.
- `test_main.py`: il grafo creato da `main` passa dal router; `SCOPE_FILE` inesistente → messaggio
  ed exit 1.

### Prove reali con LM Studio (`pytest -m real`)

Le fixture di `test_real.py` costruiscono il grafo con il router reale.

- **Nuove** (CA-27): «Che ore sono a Tokyo?» → `category=conversation`, poi `node=llm`;
  «Chi ha vinto i Mondiali del 2006?» → testo di rifiuto, nessuna riga `node=llm`, nessuna
  chiamata a strumenti; «Ciao!» → `category=conversation`.
- **Esistenti** (CA-28): le 9 prove della lezione 4 e 5 passano dal router e controllano che non
  rifiuti domande in ambito; «E a Roma?» (CA-3) verifica la cronologia filtrata e «Mi chiamo
  Paolo» / «Come mi chiamo?» (CA-4) le presentazioni.
- **Manuale** (CA-29): `python -m assistant` e `docker compose build` + `docker compose run --rm
  assistant` con una domanda in ambito e una fuori ambito; i due percorsi sono visibili nei log.

Una prova reale eseguita una volta dimostra il comportamento con quelle domande, non che il
modello si comporti sempre così. Un esito negativo viene riportato così com'è.

## 11. Incrementi

Ognuno verificato con `pytest` prima del commit.

1. Ambito: `scope.txt`, `SCOPE_FILE` in `config.py`, test.
2. `router.py`: schema, prompt, filtro, testo di rifiuto; `pydantic` in `requirements.txt`; test.
3. Grafo: stato, nodi `router` e `refusal`, instradamento, ripiego; `conftest.py`; test.
4. `create_router_model`, cablaggio in `__main__.py`, log `scope_file`; test.
5. Prove reali: fixture aggiornate, prove nuove, esecuzione di tutta la suite `real`.
6. Docker e documentazione: prova manuale locale e con Docker; README, `.env.example`,
   `CLAUDE.md`, `requisiti.md`, handoff.

## 12. Documentazione

- `README.md`: che cosa fa il router; `SCOPE_FILE` e come cambiare l'ambito (anche con Docker);
  esempi di log dei due percorsi; numero aggiornato di test.
- `.env.example`: riga commentata `# SCOPE_FILE=assistant/data/scope.txt`.
- `CLAUDE.md`: struttura (`router.py`, `scope.txt`); in «Confini» lo Step 1 della lezione 6 è
  concordato, gli step successivi no.
- `requisiti.md` §9 e `handoff.md` aggiornati con l'esito delle verifiche.

## 13. Rischi

- **`json_schema` con `gemma-4-e2b`**: il funzionamento dell'output strutturato con questo
  modello in LM Studio va verificato nella prova reale. Se non funziona, ci si ferma e si
  riprende la decisione con l'utente (le alternative erano `function_calling` e il parsing a
  mano).
- **Falsi rifiuti o falsi passaggi**: un modello piccolo può sbagliare la classificazione. Le
  prove reali esistenti fanno da controllo; il testo dell'ambito e del prompt si può ritoccare
  senza cambiare il codice di instradamento.
- **Latenza**: ogni turno fa una chiamata in più al modello.
- **Contesto**: la cronologia filtrata cresce con la sessione; il riassunto arriverà con lo
  step 3.

## 14. Fuori ambito

Revisore (step 2), riassunto (step 3), resource e prompt MCP (step 4–5), servizio HTTP, back-end,
front-end e Compose a più container (step 6–9), streaming. Più di due categorie, un modello
diverso per il router, un ambito montato da fuori nel container Docker, la conservazione della
decisione del router tra un turno e l'altro.
