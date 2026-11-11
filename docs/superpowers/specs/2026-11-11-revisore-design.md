# Specifica — Lezione 6, Step 2: revisore (la risposta è coerente con la domanda?)

Data: 2026-11-11
Stato: approvata il 2026-11-11
Requisiti: [`../requisiti.md`](../requisiti.md), §10 (RF-28…RF-33, CA-30…CA-37).
Piano: da scrivere (`../plans/2026-11-11-revisore.md`), con la skill writing-plans.
Specifiche precedenti: [`2026-11-11-router-design.md`](2026-11-11-router-design.md) (Step 1) e
quelle che richiama.
Fonte didattica: `LLM_Lez_6.pdf`, slide 3 («Il grafo dopo i primi tre step») e slide dello
Step 2; riassunto in [`../lezione6.md`](../lezione6.md).

Questa specifica aggiunge al grafo dello Step 1 un nodo revisore LLM, posto dopo la risposta
finale dell'agente, e un arco che riporta all'agente le risposte non coerenti, fino a un limite.
Strumenti, MCP, router, terminale e Docker non cambiano. Dove non dice altro, valgono le
specifiche precedenti.

## 1. Decisioni

| Tema | Decisione | Motivo |
|------|-----------|--------|
| Che cosa si rivede | Solo la risposta finale dell'agente (`llm` senza tool_call); non il rifiuto del router né l'avviso di `limit` | Slide 3: Agente → Revisore; rifiuto e avviso sono testi del programma, non dell'agente |
| Ingresso del revisore | Solo la domanda dell'utente e la risposta proposta, in un unico messaggio | Requisito 1 alla lettera; compito chiaro per un modello piccolo; niente strumenti né risultati |
| Output strutturato | `with_structured_output(ReviewDecision, method="json_schema")`, campi `reason` e `coherent` | Stesso meccanismo del router, verificato con `gemma-4-e2b`; il motivo prima del verdetto aiuta il giudizio |
| Motivo nella cronologia | `HumanMessage` con `name="reviewer"`; resta nella cronologia della sessione insieme alla bozza rifiutata | Requisito 3; un messaggio utente mantiene l'alternanza richiesta dai template di chat (un `SystemMessage` a metà conversazione rischia di essere rifiutato) |
| Limite | `MAX_REVIEWS` (intero ≥ 1, default 2) = chiamate al revisore nel turno; contatore `reviews` nello stato | Requisito 4; con 2 si ha al più una riscrittura |
| `MAX_STEPS` | Non si azzera dopo un rifiuto: resta il limite totale delle chiamate all'agente nel turno | Significato invariato; costo massimo del turno prevedibile |
| Output non valido | La risposta si considera coerente, con un WARNING; la revisione conta nel limite | Un revisore difettoso non blocca né ripete le risposte; resta visibile nei log |
| Errori di LM Studio | Non intercettati: arrivano al terminale come per agente e router | Comportamento esistente; cronologia invariata |
| Modello | Lo stesso di LM Studio (`LMSTUDIO_MODEL`), prompt diverso, nessuno strumento | Slide 3: stesso modello, prompt di sistema diversi |
| Organizzazione | Modulo nuovo `reviewer.py`, gemello di `router.py`; in `graph.py` il nodo e l'arco | Moduli piccoli, schema già usato nello Step 1 |

## 2. Grafo

Grafo alla fine dello Step 2. Sono nuovi il nodo `reviewer` e i due archi che lo collegano; il
caso «nessuna tool_call» di `route` porta al revisore invece che a END. Router, rifiuto, strumenti
e limite dei passaggi non cambiano.

```
START → [router] ─ conversation ─→ [llm] ──route──┬─ nessuna tool_call ──────────→ [reviewer]
           │                         ▲             ├─ tool_call, steps < max_steps → [tools] ─┐
           │                         ├─────────────┼──────────────────────────────────────────┘
           │                         │             └─ tool_call, steps ≥ max_steps → [limit] → END
           │                         │
           │                         │   [reviewer] ──route_after_reviewer──┬─ coerente ──────────────────→ END
           │                         └──────────────────────────────────────┼─ non coerente, reviews < max ─→ [llm]
           │                                                                └─ non coerente, reviews ≥ max ─→ END (WARNING)
           └─ out_of_scope ─→ [refusal] → END
```

Rispetto alla slide 3 manca solo `Riassunto` (step 3): non viene anticipato.

## 3. Struttura

```
assistant/
├── config.py        # + max_reviews; lettura di MAX_REVIEWS
├── reviewer.py      # NUOVO: ReviewDecision, REVIEWER_PROMPT, ReviewerOutputError, funzioni pure
├── router.py        # router_messages scarta indicazioni del revisore e bozze rifiutate
├── model.py         # guard_structured_output generico; + create_reviewer_model(config)
├── graph.py         # + campi di stato, nodo reviewer, route_after_reviewer; route → reviewer
├── session.py       # il turno parte anche con reviews=0
└── __main__.py      # + modello del revisore e max_reviews passati al grafo; log max_reviews
```

`terminal.py`, `tools.py`, i moduli MCP, `scope.txt` e `compose.yaml` non cambiano.

## 4. Configurazione (`config.py`)

- `MAX_REVIEWS`: intero ≥ 1, default `2`, letto e validato come `MAX_STEPS`. Valore non intero o
  minore di 1 → `MAX_REVIEWS deve essere un intero ≥ 1, ricevuto '<valore>'.`, aggiunto agli altri
  problemi del messaggio «Configurazione non valida: …» (exit 1).
- `Config` riceve il campo `max_reviews: int = 2`, in fondo, dopo `scope`.
- `.env.example`: riga `MAX_REVIEWS=2` dopo `MAX_STEPS=5`. Docker la riceve tramite
  `env_file: .env`, già presente.

Significato: `MAX_REVIEWS` è il numero massimo di chiamate al revisore in un turno. Con un
revisore che rifiuta sempre l'agente risponde `MAX_REVIEWS` volte e riceve `MAX_REVIEWS - 1`
indicazioni.

## 5. Revisore (`reviewer.py`)

### Schema

```python
class ReviewDecision(BaseModel):
    reason: str = Field(
        description="Motivo della scelta, in una frase breve in italiano; se non è coerente, "
        "che cosa manca o che cosa è fuori tema")
    coherent: bool = Field(
        description="true se la risposta risponde a tutte le parti della domanda senza uscire "
        "dal tema, altrimenti false")
```

`reason` precede `coherent`: con `json_schema` il modello genera i campi in quest'ordine e scrive
il motivo prima del verdetto. Chiavi in inglese, descrizioni in italiano (le legge il modello).

### Prompt

`REVIEWER_PROMPT`, testo di partenza (si può ritoccare durante la prova reale senza cambiare il
comportamento richiesto):

```
Sei il revisore dell'assistente del laboratorio. Non rispondi all'utente: controlli soltanto se la
risposta proposta risponde alla domanda dell'utente.

La risposta è coerente se risponde a tutte le parti della domanda e non esce dal tema.
Non è coerente se ignora una parte della domanda, se parla d'altro o se è vuota.
Non giudicare lo stile, la lunghezza né l'esattezza dei dati: vengono da strumenti che tu non vedi.
Se la risposta spiega che una parte non si può soddisfare (per esempio un corso che non esiste),
quella parte ha comunque una risposta. Se l'utente saluta o si presenta, una risposta cortese e
pertinente è coerente; anche una domanda di chiarimento pertinente è coerente.
Nel motivo spiega la scelta in una frase breve, in italiano; se non è coerente, indica che cosa
manca o che cosa è fuori tema.
```

Il prompt non nomina gli strumenti.

### Funzioni e tipi

- `ReviewerOutputError(Exception)`: il revisore ha risposto senza una `ReviewDecision` valida.
- `is_feedback(message) -> bool`: vero per un `HumanMessage` con `name == "reviewer"`.
- `user_question(history) -> str`: testo dell'ultimo `HumanMessage` che non è un'indicazione del
  revisore. Alla seconda revisione la domanda resta quindi quella dell'utente.
- `review_messages(question, answer) -> list[BaseMessage]`:
  `[SystemMessage(REVIEWER_PROMPT), HumanMessage("Domanda dell'utente:\n<domanda>\n\nRisposta
  proposta:\n<risposta>")]`; una risposta vuota o di soli spazi è scritta `(vuota)`.
- `feedback_message(reason) -> HumanMessage` con `name="reviewer"` e testo:
  `Revisione: la risposta precedente non è coerente con la domanda: <motivo>. Scrivi una nuova
  risposta completa all'ultima domanda dell'utente. Usa i risultati degli strumenti già ottenuti
  e non ripetere le azioni già eseguite (per esempio una nota già salvata).`
  Il motivo è ripulito da spazi e da un punto finale; se resta vuoto, la prima frase diventa
  `Revisione: la risposta precedente non è coerente con la domanda.`

L'ultima frase dell'indicazione serve a evitare effetti duplicati (per esempio due `add_note`)
quando l'agente riscrive una risposta dopo aver usato uno strumento.

## 6. Ritocco del router (`router.py`)

`router_messages(history)` scarta le indicazioni del revisore (`is_feedback`) e la bozza rifiutata
che precede ciascuna di esse (l'`AIMessage` senza tool_call immediatamente prima, tra i messaggi
già tenuti). Esempio: `[domanda, bozza, indicazione, risposta, domanda2]` →
`[domanda, risposta, domanda2]`. Il router continua a vedere domande dell'utente e risposte
finali, alternate. Il resto del comportamento (anche le risposte vuote tenute) non cambia.

## 7. Modello del revisore (`model.py`)

- `guard_router_output(structured)` diventa `guard_structured_output(structured, error_type)`:
  stesse eccezioni intercettate (`INVALID_OUTPUT_ERRORS`), convertite in `error_type` con
  `raise … from error`. `openai.APIError` continua a passare.
- `create_router_model(config)`: comportamento invariato, usa `RouterOutputError`.
- `create_reviewer_model(config) -> Runnable`: `_chat(config)` (stessi parametri dell'agente),
  `.with_structured_output(ReviewDecision, method="json_schema")`, protetto con
  `ReviewerOutputError`. Nessun `bind_tools`. Restituisce un'istanza di `ReviewDecision`.

## 8. Grafo (`graph.py`)

### Stato

```python
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    steps: int          # chiamate del modello dell'agente nel turno
    category: str       # decisione del router
    reason: str         # motivo del router
    reviews: int        # NUOVO: chiamate al revisore nel turno
    coherent: bool      # NUOVO: ultima decisione del revisore
    review_reason: str  # NUOVO: motivo del revisore
```

`Session.send` invoca il grafo con `messages`, `steps=0` e `reviews=0`. `coherent` e
`review_reason` li scrive il revisore; come per il router non si conservano tra un turno e
l'altro (la sessione tiene solo `messages`). Il revisore non incrementa `steps`.

### Firma

`build_graph(model, tools, max_steps, *, router_model, scope, reviewer_model, max_reviews)`: i
parametri esistenti restano dove sono; i nuovi sono obbligatori e per nome.

### Nodo `reviewer`

1. `review = state["reviews"] + 1`; domanda = `user_question(state["messages"])`; risposta = testo
   dell'ultimo messaggio (l'`AIMessage` finale dell'agente).
2. Invoca `reviewer_model` con `review_messages(domanda, risposta)`.
3. Secondo l'esito:
   - **coerente** → `INFO node=reviewer review=<n>/<max> coherent=true reason=<motivo>
     next_node=end`;
   - **non coerente e `review < max_reviews`** → `INFO node=reviewer review=<n>/<max>
     coherent=false reason=<motivo> next_node=llm` e aggiunge `feedback_message(motivo)` ai
     messaggi;
   - **non coerente e `review ≥ max_reviews`** → `WARNING node=reviewer review=<n>/<max>
     coherent=false reason=<motivo> review_limit_reached next_node=end`; nessuna indicazione
     aggiunta; la risposta restituita è l'ultima dell'agente;
   - **output non valido** (`ReviewerOutputError` oppure risultato che non è una
     `ReviewDecision`, per esempio `None`) → `WARNING node=reviewer review=<n>/<max>
     fallback=invalid_output error=<errore> coherent=true next_node=end`; la risposta passa.
4. Restituisce `reviews=review`, `coherent` e `review_reason` (stringa vuota nel ripiego).
5. `openai.APIError` non viene intercettato: arriva al terminale; `Session` lascia la cronologia
   invariata.

Motivo ed errore sono scritti con `json.dumps(..., ensure_ascii=False)`, su una riga, come nel
router.

### Instradamento

- `route(state, max_steps) -> Literal["tools", "limit", "reviewer"]`: senza tool_call restituisce
  `"reviewer"` (prima `"end"`); gli altri casi non cambiano.
- `route_after_reviewer(state, max_reviews) -> Literal["llm", "end"]`: `"end"` se
  `state["coherent"]` oppure `state["reviews"] ≥ max_reviews`; altrimenti `"llm"`.
- Archi: `llm → tools | limit | reviewer` (condizionale); `reviewer → llm | END` (condizionale).
  Gli altri archi non cambiano.

### Esempio di log (domanda in due parti, prima risposta parziale)

```
INFO    node=router category=conversation reason="…" next_node=llm
INFO    step=1/5 node=llm
...
INFO    step=2/5 node=llm
INFO    node=reviewer review=1/2 coherent=false reason="Manca il risultato di 17 * 23." next_node=llm
INFO    step=3/5 node=llm
INFO    node=reviewer review=2/2 coherent=true reason="Risponde a entrambe le parti." next_node=end
```

## 9. Avvio (`__main__.py`)

`main` crea `create_reviewer_model(config)` e chiama `build_graph(..., reviewer_model=...,
max_reviews=config.max_reviews)`. La riga di avvio `scope_file=<percorso>` diventa
`scope_file=<percorso> max_reviews=<n>`.

## 10. Dipendenze

Nessuna nuova.

## 11. Test

### Con il modello simulato (`pytest`, senza LM Studio)

- `conftest.py`: `ApprovingReviewer`, che risponde sempre `ReviewDecision(reason="test",
  coherent=True)` e registra i messaggi ricevuti; `fake_graph(..., reviewer=None,
  max_reviews=2)` lo usa per default, così i test esistenti non cambiano. Per i casi nuovi le
  decisioni del revisore si preparano con `FakeModel` (una `ReviewDecision`, `None` o
  un'eccezione).
- `test_reviewer.py` (nuovo): `user_question` salta le indicazioni; `review_messages` contiene
  esattamente prompt, domanda e risposta, e `(vuota)` per una risposta vuota; `feedback_message`
  ha `name="reviewer"` e il motivo ripulito; lo schema rifiuta un oggetto senza `coherent`; il
  prompt non nomina strumenti.
- `test_router.py`: `router_messages` scarta bozza rifiutata e indicazione e mantiene
  l'alternanza.
- `test_graph.py`:
  - **approvata al primo passaggio** (CA-31): una chiamata all'agente e una al revisore,
    `reviews == 1`, log `review=1/2 coherent=true … next_node=end`, nessuna indicazione nei
    messaggi;
  - **domanda in due parti con risposta parziale** (CA-32): l'agente risponde prima solo a una
    parte, il revisore rifiuta e poi approva; la seconda chiamata all'agente termina con
    l'indicazione che contiene il motivo; la risposta finale è quella completa; log
    `review=1/2 coherent=false … next_node=llm` poi `review=2/2 coherent=true`;
  - **revisore che rifiuta sempre** (CA-33), con `max_reviews` 2 e 3: revisore e agente chiamati
    `max_reviews` volte, `max_reviews - 1` indicazioni, ultima risposta restituita, WARNING
    `review_limit_reached`;
  - il revisore riceve solo `review_messages(domanda, risposta)`, anche dopo un ciclo di strumenti
    e alla seconda revisione (CA-30);
  - ripiego su `ReviewerOutputError` e su `None` (CA-34);
  - rifiuto del router e avviso di `limit` non rivisti: `reviewer.calls == []` (CA-35);
  - il revisore non consuma `steps`; il limite dei passaggi raggiunto durante una riscrittura
    porta a `limit` (CA-35);
  - `route` senza tool_call → `"reviewer"` (aggiornamento dell'unico caso esistente che cambia);
    casi di `route_after_reviewer`; il grafo compilato contiene il nodo `reviewer`.
- `test_session.py`: bozza e indicazione restano nella cronologia dopo il turno; un
  `APIConnectionError` del revisore lascia la cronologia invariata (CA-34).
- `test_config.py`: `MAX_REVIEWS` predefinito 2, valore valido, `0` e `abc` rifiutati (CA-30).
- `test_model.py`: la protezione converte nel tipo d'errore indicato (router e revisore);
  `APIError` passa; `create_reviewer_model` si crea senza server.
- `test_main.py`: la riga di avvio contiene `max_reviews=2`; il grafo creato da `main` passa
  dal revisore.

### Prove reali con LM Studio (`pytest -m real`)

Le fixture di `test_real.py` costruiscono il grafo con il revisore reale e `config.max_reviews`.

- **Evidenza minima, con la prima risposta imposta** (CA-36): un involucro `PartialFirstAnswer`
  fa restituire alla prima chiamata dell'agente una risposta parziale fissa a «Che ore sono a
  Tokyo e quanto fa 17 * 23?» (solo l'ora); dalla seconda chiamata usa il modello reale. Revisore
  e riscrittura sono reali. Si verifica: riga `coherent=false` con un motivo non vuoto; poi una
  riga `coherent=true` entro `MAX_REVIEWS`; la risposta finale contiene «391». Nel resoconto si
  dice che la prima risposta è imposta.
- **Interamente reale** (CA-36): la stessa domanda senza involucro; la risposta finale contiene
  «391» e l'ora di Tokyo restituita da `get_current_time`; nei log almeno una riga
  `node=reviewer`; il numero di righe `node=reviewer` non supera `MAX_REVIEWS`.
- **Esistenti** (CA-37): le 12 prove precedenti passano con il revisore attivo (controllo dei
  falsi rifiuti e delle azioni ripetute, per esempio una sola `add_note` in CA-17).
- **Manuale** (CA-37): la domanda in due parti via pipe verso `python -m assistant` e verso
  `docker compose run --rm -T assistant` (dopo `docker compose build`); nei log le righe
  `node=reviewer`.

Il limite con un revisore che rifiuta sempre si verifica con il revisore simulato, come chiede la
traccia. Una prova reale eseguita una volta dimostra il comportamento con quelle domande, non che
il modello si comporti sempre così. Un esito negativo viene riportato così com'è.

Nei controlli sui log va cercato `step=N/M node=llm` per l'agente: `next_node=llm` compare anche
nelle righe del router e del revisore.

## 12. Incrementi

Ognuno verificato con `pytest` prima del commit.

1. `MAX_REVIEWS` in `config.py` e `.env.example`; test.
2. `reviewer.py` e ritocco di `router_messages`; test.
3. `model.py`: protezione generica e `create_reviewer_model`; test.
4. Grafo, `Session`, `__main__.py`, `conftest.py`: in un solo commit, perché la nuova firma di
   `build_graph` rompe gli altri tre finché non sono aggiornati; test.
5. Prove reali: fixture, `PartialFirstAnswer`, prove nuove, esecuzione di tutta la suite `real`.
6. Prova manuale locale e con Docker; documentazione.

## 13. Documentazione

- `README.md`: che cosa fa il revisore; `MAX_REVIEWS`; esempi di log (correzione, limite,
  ripiego); grafo aggiornato; numero di test; durata delle prove reali.
- `.env.example`: `MAX_REVIEWS=2`.
- `CLAUDE.md`: struttura (`reviewer.py`); obiettivo e «Confini»: lo Step 2 della lezione 6 è
  concordato, gli step successivi no.
- `requisiti.md` §10 e `handoff.md` aggiornati con l'esito delle verifiche.

## 14. Rischi

- **Campo `name` del messaggio utente**: `langchain-openai` lo invia a LM Studio. È ammesso
  dall'API OpenAI, ma il template di chat potrebbe trattarlo in modo inatteso. Se la prova reale
  lo mostra, il messaggio si marca in un altro modo (per esempio con l'`id`) senza cambiare il
  resto.
- **Falsi rifiuti**: un modello piccolo può giudicare incompleta una risposta giusta, soprattutto
  con domande brevi che continuano la conversazione («E a Roma?»), perché vede solo la domanda.
  Il danno è limitato dal limite: al massimo `MAX_REVIEWS - 1` riscritture, poi passa l'ultima
  risposta. Il prompt si può ritoccare senza cambiare il codice.
- **Falsi passaggi**: il revisore può approvare una risposta incompleta; la prova con la prima
  risposta imposta lo controlla.
- **Azioni ripetute**: una riscrittura dopo `add_note` o `delete_note` potrebbe ripetere
  l'azione; l'indicazione lo vieta e CA-17 lo controlla.
- **Latenza e contesto**: almeno una chiamata in più per turno; bozze e indicazioni restano nella
  cronologia e occupano contesto (8192 token). Il riassunto arriverà con lo step 3.
- **`MAX_STEPS` condiviso**: una riscrittura con strumenti può esaurire i passaggi e finire in
  `limit`; con i valori predefiniti (5 e 2) i casi delle prove ci stanno.

## 15. Fuori ambito

Riassunto (step 3), resource e prompt MCP (step 4–5), servizio HTTP, back-end, front-end e Compose
a più container (step 6–9), streaming. Un modello diverso per il revisore; la revisione del rifiuto
del router o dell'avviso di `limit`; la verifica dell'esattezza dei dati; la rimozione di bozze e
indicazioni dalla cronologia; la cronologia completa passata al revisore; l'azzeramento di `steps`
dopo un rifiuto.
