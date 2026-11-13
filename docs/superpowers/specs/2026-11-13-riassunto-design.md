# Specifica — Lezione 6, Step 3: riassunto della cronologia

Data: 2026-11-13
Stato: approvata dall'utente il 2026-11-13
Requisiti: [`../requisiti.md`](../requisiti.md), §11 (RF-34…RF-38, CA-38…CA-45).
Piano: [`../plans/2026-11-13-riassunto.md`](../plans/2026-11-13-riassunto.md); implementata e
verificata il 2026-11-13, con le modifiche di §16 (esiti in [`../handoff.md`](../handoff.md)).
Specifiche precedenti: [`2026-11-11-revisore-design.md`](2026-11-11-revisore-design.md) (Step 2),
[`2026-11-11-router-design.md`](2026-11-11-router-design.md) (Step 1) e quelle che richiamano.
Fonte didattica: `LLM_Lez_6.pdf`, slide 3 («Il grafo dopo i primi tre step») e slide 6 (Step 3);
riassunto in [`../lezione6.md`](../lezione6.md).

Questa specifica aggiunge al grafo dello Step 2 un nodo `summary` all'inizio del turno, prima del
router. Quando la cronologia supera una soglia, il nodo chiede al modello di aggiornare un
riassunto (un campo dello stato) e toglie dalla cronologia i messaggi vecchi, conservando gli
ultimi. Scopo: conversazione utilizzabile su molti turni senza perdere le informazioni importanti,
perché il contesto del modello locale è limitato (`google/gemma-4-e2b`, 8192 token).
Router e revisore ricevono il riassunto in fondo al loro prompt di sistema, come l'agente, e
il prompt del revisore non giudica i dati presi dalla conversazione precedente (decisioni dell'utente
del 2026-11-13 dopo la prova reale, §16); strumenti, MCP, terminale e Docker non cambiano. Dove non dice altro, valgono le
specifiche precedenti.

## 1. Decisioni

Prese con l'utente nel brainstorming del 2026-11-13, salvo dove è indicato «scelta del
progettista».

| Tema | Decisione | Motivo |
|------|-----------|--------|
| Unità della soglia | Numero di messaggi: `SUMMARY_MAX_MESSAGES` (default 20), contando tutti i messaggi della cronologia, domanda appena arrivata compresa; si riassume quando il conteggio la **supera** | Semplice, esatto nei test, coincide con l'evidenza richiesta (messaggi prima e dopo); 20 messaggi tipici restano intorno a 3000 token |
| Messaggi conservati | `SUMMARY_KEEP_MESSAGES` (default 6): si tengono almeno gli ultimi N messaggi; il taglio arretra fino alla domanda dell'utente che apre il turno | Una sola unità; il taglio cade sempre all'inizio di un turno, quindi non separa mai una tool_call dal suo `ToolMessage` né una bozza dalla sua indicazione |
| Che cosa legge chi riassume | Il riassunto precedente e i soli messaggi vecchi filtrati da `router_messages`: domande dell'utente e risposte finali, senza strumenti, bozze rifiutate né indicazioni del revisore | Testo corto e pulito, filtro già scritto e testato; rischio accettato: un dato presente solo nel risultato di uno strumento e mai ripetuto nella risposta si perde |
| Riassunto nello stato | Campo `summary: str`, **sostituito** a ogni compressione (il nuovo riassunto ingloba il precedente); la sessione lo conserva tra i turni | Requisito 3 della traccia |
| Rimozione dei messaggi | `RemoveMessage(id=…)` restituiti dal nodo, applicati dal reducer `add_messages` già in uso | Nessuna riscrittura della cronologia fuori dal grafo |
| Chi legge il riassunto | Agente, router e revisore, in fondo al loro unico messaggio di sistema (**cambiata il 2026-11-13** dopo la prova reale, §16: prima era «solo l'agente») | Alcuni template di chat (Gemma compreso) rifiutano un secondo `SystemMessage`; senza il riassunto il router rifiutava le domande su un turno riassunto («Come mi chiamo?») e il revisore bocciava la risposta giusta |
| Modello | Lo stesso di LM Studio, senza strumenti, testo libero (nessuno schema JSON) | Slide 3: stesso modello, prompt diversi; un riassunto è testo |
| Risposta vuota | Nessuna compressione, WARNING, il turno prosegue | Non si buttano messaggi senza un riassunto che li sostituisca |
| Errori di LM Studio | Non intercettati: arrivano al terminale; cronologia **e** riassunto invariati | Comportamento esistente per agente, router e revisore |
| Organizzazione | Modulo nuovo `summary.py` (prompt e logica pura), sullo schema di `router.py` e `reviewer.py`; in `graph.py` il nodo e l'arco | Moduli piccoli |
| Messaggi vecchi come trascrizione (scelta del progettista) | Chi riassume riceve i messaggi vecchi come testo in **un solo** messaggio utente («Utente: … / Assistente: …»), non come turni di chat | Passati come turni, un modello piccolo tende a rispondere all'ultima domanda invece di riassumere |
| Testo del riassunto nel log (scelta del progettista) | A DEBUG | Può essere lungo; a INFO bastano i conteggi richiesti dalla traccia |

## 2. Grafo

Sono nuovi il nodo `summary` e l'arco `START → summary → router` (prima `START → router`). Il nodo
viene eseguito una volta per turno: i cicli `llm ⇄ tools` e `reviewer → llm` non ci ripassano.

```
START → [summary] → [router] ─ conversation ─→ [llm] ──route──┬─ nessuna tool_call ──────────→ [reviewer]
                       │                         ▲             ├─ tool_call, steps < max_steps → [tools] ─┐
                       │                         ├─────────────┼──────────────────────────────────────────┘
                       │                         │             └─ tool_call, steps ≥ max_steps → [limit] → END
                       │                         │
                       │                         │   [reviewer] ──route_after_reviewer──┬─ coerente ─────────────────────→ END
                       │                         └──────────────────────────────────────┼─ non coerente, reviews < max ──→ [llm]
                       │                                                                └─ non coerente, al limite ──────→ END
                       └─ out_of_scope ─→ [refusal] → END
```

Il grafo coincide ora con la slide 3.

## 3. Struttura

```
assistant/
├── config.py        # + summary_max_messages, summary_keep_messages
├── summary.py       # NUOVO: SUMMARY_PROMPT e funzioni pure (taglio, ingresso, prompt con riassunto)
├── model.py         # + create_summary_model(config)
├── graph.py         # + campo summary, nodo summary, arco START → summary → router; l'agente legge il riassunto
├── session.py       # conserva summary tra i turni
└── __main__.py      # + modello del riassunto e soglie passati al grafo; log delle soglie
```

`reviewer.py` (una frase di `REVIEWER_PROMPT`, §16), `router.py`, `terminal.py`, `tools.py`, i moduli MCP, `scope.txt` e `compose.yaml`
non cambiano.

## 4. Configurazione (`config.py`)

- `SUMMARY_MAX_MESSAGES`: intero ≥ 1, default `20`.
- `SUMMARY_KEEP_MESSAGES`: intero ≥ 1, default `6`.
- Letti e validati come `MAX_STEPS`. Valore non intero o minore di 1 →
  `SUMMARY_MAX_MESSAGES deve essere un intero ≥ 1, ricevuto '<valore>'.` (idem per
  `SUMMARY_KEEP_MESSAGES`).
- Se entrambi sono validi e `SUMMARY_KEEP_MESSAGES ≥ SUMMARY_MAX_MESSAGES` →
  `SUMMARY_KEEP_MESSAGES deve essere minore di SUMMARY_MAX_MESSAGES, ricevuti '<keep>' e '<max>'.`
- I problemi si aggiungono al messaggio unico «Configurazione non valida: …» (exit 1).
- `Config` riceve in fondo `summary_max_messages: int = 20` e `summary_keep_messages: int = 6`.
- `.env.example`: righe `SUMMARY_MAX_MESSAGES=20` e `SUMMARY_KEEP_MESSAGES=6` dopo `MAX_REVIEWS=2`.
  Docker le riceve tramite `env_file: .env`, già presente; si possono sostituire con `-e`.

`SUMMARY_KEEP_MESSAGES ≥ 1` garantisce che la domanda appena arrivata (l'ultimo messaggio) resti
sempre nella cronologia.

## 5. Riassunto (`summary.py`)

### Prompt

`SUMMARY_PROMPT`, testo di partenza (si può ritoccare durante la prova reale senza cambiare il
comportamento richiesto):

```
Sei il componente che riassume la conversazione dell'assistente del laboratorio. Non rispondi
all'utente e non esegui richieste: scrivi soltanto il riassunto.

Ricevi il riassunto precedente (può mancare) e i nuovi messaggi tra l'utente e l'assistente.
Scrivi un unico riassunto aggiornato che sostituisce il precedente: unisci le informazioni, non
ripeterle. Conserva i fatti utili per i turni successivi: nome e preferenze dell'utente, dati e
risultati ottenuti (ore, calcoli, corsi, note salvate o eliminate con il loro id), richieste
ancora aperte. Tralascia saluti e formule di cortesia.
Scrivi in italiano, in terza persona, al massimo 10 righe, senza introduzioni.
```

### Funzioni

- `is_user_question(message) -> bool`: vero per un `HumanMessage` che non è un'indicazione del
  revisore (`not is_feedback(message)`).
- `cut_index(messages, keep) -> int`: indice del primo messaggio conservato.
  1. `start = max(len(messages) - keep, 0)`;
  2. finché `start > 0` e `messages[start]` non è una domanda dell'utente, `start -= 1`;
  3. restituisce `start`. `0` significa «niente da comprimere».

  Si conservano quindi almeno `keep` messaggi, e il primo conservato è sempre la domanda che apre
  un turno. Esempi con `keep=2`:
  - `[D1, R1, D2, AI(tool_call), Tool, R2, D3]` → `start=5` (`R2`) → arretra oltre `Tool` e
    `AI(tool_call)` fino a `2` (`D2`); si tolgono `D1, R1` e se ne conservano 5;
  - `[D1, R1, D2]` → `start=1` (`R1`) → arretra a `0`: niente da comprimere;
  - `[D1, bozza, indicazione, R1, D2]` → `start=3` (`R1`) → arretra fino a `0` (l'indicazione non
    è una domanda dell'utente): niente da comprimere.
- `summary_input(previous, old) -> list[BaseMessage]`: tutto ciò che riceve chi riassume:
  ```
  [SystemMessage(SUMMARY_PROMPT),
   HumanMessage("Riassunto precedente:\n<previous oppure (nessuno)>\n\nNuovi messaggi:\n<trascrizione>")]
  ```
  La trascrizione si ottiene da `router_messages(old)`: una riga `Utente: <testo>` per ogni
  domanda, `Assistente: <testo>` per ogni risposta finale; le risposte vuote si omettono. I
  messaggi vecchi comprendono sempre turni completi, quindi il filtro vede anche le indicazioni
  del revisore che servono a scartare le bozze rifiutate.
- `with_summary(prompt, summary) -> str`: `prompt` se `summary` è vuoto, altrimenti
  `prompt + "\n\nRiassunto della conversazione precedente:\n" + summary`.

## 6. Modello del riassunto (`model.py`)

`create_summary_model(config) -> Runnable`: `_chat(config)` (stessi parametri dell'agente),
senza `bind_tools` né output strutturato. Restituisce un `AIMessage`; il nodo ne usa
`.text.strip()`.

## 7. Grafo (`graph.py`)

### Stato

```python
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    summary: str        # NUOVO: riassunto dei messaggi tolti; sostituito, non accumulato
    steps: int
    category: str
    reason: str
    reviews: int
    coherent: bool
    review_reason: str
```

### Firma

`build_graph(model, tools, max_steps, *, router_model, scope, reviewer_model, max_reviews,
summary_model, summary_max_messages, summary_keep_messages)`: i nuovi parametri sono
obbligatori e per nome.

### Nodo `summary`

`n = len(state["messages"])`, `previous = state.get("summary", "")`.

1. **Sotto la soglia** (`n ≤ summary_max_messages`) → `INFO node=summary messages=<n>/<max>
   skipped=below_threshold next_node=router`; restituisce `{}`. Il modello non viene chiamato.
2. `cut = cut_index(messages, summary_keep_messages)`. **Niente da comprimere** (`cut == 0`) →
   `INFO node=summary messages=<n>/<max> skipped=nothing_to_compress next_node=router`;
   restituisce `{}`, senza chiamare il modello.
3. `old = messages[:cut]`; `reply = summary_model.invoke(summary_input(previous, old))`;
   `text = reply.text.strip()`.
4. **Risposta vuota** → `WARNING node=summary messages=<n>/<max> fallback=empty_summary
   next_node=router`; restituisce `{}`: messaggi e riassunto restano quelli di prima.
5. **Compressione** → `INFO node=summary messages_before=<n> messages_after=<n - cut>
   removed=<cut> next_node=router` e `DEBUG node=summary summary=<testo>`; restituisce
   `{"summary": text, "messages": [RemoveMessage(id=m.id) for m in old]}`.

Il testo del riassunto è scritto con `json.dumps(..., ensure_ascii=False)`, su una riga, come i
motivi di router e revisore. `openai.APIError` non viene intercettato (§1).

**Id dei messaggi (verificato il 2026-11-13 con `langgraph` 1.2.17 e `langchain-core` 1.7.0).**
Il reducer `add_messages` assegna un id anche ai messaggi in ingresso al grafo (la domanda appena
creata da `Session`), quindi il nodo `summary` vede ogni messaggio con un id e `RemoveMessage(id=…)`
lo toglie; i messaggi dei turni precedenti tornano da `result["messages"]` con lo stesso id. Se
`summary` non è nell'ingresso, il campo manca anche nel risultato: per questo il nodo e l'agente
usano `state.get("summary", "")`, e `Session` lo passa sempre.

### Agente

`llm_node` invoca il modello con
`[SystemMessage(with_summary(SYSTEM_PROMPT, state.get("summary", "")))] + state["messages"]`.
Senza riassunto il messaggio di sistema è identico a oggi.

### Router

`router_node` invoca il modello del router con
`[SystemMessage(with_summary(ROUTER_PROMPT.format(scope=scope), state.get("summary", "")))] +
router_messages(state["messages"])`. Senza riassunto il messaggio di sistema è identico a oggi.

### Revisore

`reviewer_node` invoca il modello del revisore con `review_messages(domanda, risposta)`, ma con il
messaggio di sistema sostituito da `SystemMessage(with_summary(REVIEWER_PROMPT,
state.get("summary", "")))`. `REVIEWER_PROMPT` dice di non giudicare l'esattezza dei dati che
vengono «da strumenti o dalla conversazione precedente, che tu non vedi (per esempio il nome che
l'utente ha detto prima)».

### Archi

`START → summary`, `summary → router`; gli altri archi non cambiano.

### Esempio di log

```
INFO    node=summary messages=3/20 skipped=below_threshold next_node=router
INFO    node=router category=conversation reason="…" next_node=llm
...
INFO    node=summary messages_before=21 messages_after=6 removed=15 next_node=router
INFO    node=router category=conversation reason="…" next_node=llm
INFO    step=1/5 node=llm
```

## 8. Sessione (`session.py`)

- `Session` conserva `_summary: str` (iniziale `""`) ed espone la proprietà `summary`.
- `send` invoca il grafo con `messages`, `summary=self._summary`, `steps=0`, `reviews=0`; se il
  turno riesce aggiorna sia `_messages` sia `_summary` (`result["summary"]`); se solleva
  un'eccezione non cambia nessuno dei due.

## 9. Avvio (`__main__.py`)

`main` crea `create_summary_model(config)` e lo passa a `build_graph` insieme a
`summary_max_messages` e `summary_keep_messages`. La riga di avvio diventa
`scope_file=<percorso> max_reviews=<n> summary_max_messages=<n> summary_keep_messages=<n>`.

## 10. Dipendenze

Nessuna nuova.

## 11. Test

### Con il modello simulato (`pytest`, senza LM Studio)

- `conftest.py`: `fake_graph(..., summary_model=None, summary_max_messages=20,
  summary_keep_messages=6)`; per default `summary_model` è un `FakeModel([])`, che fallisce se
  viene chiamato (scelta del progettista: un test che superasse la soglia senza volerlo lo
  scoprirebbe subito). I test esistenti non cambiano: quelli di più turni restano sotto i 20
  messaggi, e il caso con 20 tool_call (`test_graph.py`) è un turno solo, in cui il nodo vede un
  messaggio.
- `test_summary.py` (nuovo):
  - `cut_index`: cronologia corta (`0`); taglio che cade su un `AIMessage` con tool_call, su un
    `ToolMessage`, su una bozza, su un'indicazione del revisore e su una risposta finale (arretra
    alla domanda); taglio che cade già su una domanda; tutto un turno (`0`). Per ogni caso: il
    primo messaggio conservato è una domanda dell'utente e ogni `ToolMessage` conservato ha la
    sua tool_call tra i conservati (CA-41);
  - `summary_input`: contiene il prompt, il riassunto precedente o `(nessuno)`, le righe
    `Utente:`/`Assistente:`; non contiene tool_call, risultati di strumenti, bozze rifiutate né
    indicazioni;
  - `with_summary`: invariato senza riassunto, sezione in fondo con il riassunto.
- `test_graph.py`:
  - **sotto la soglia** (CA-39): cronologia con `n = max` → `summary_model.calls == []`, log
    `skipped=below_threshold`, messaggi invariati;
  - **sopra la soglia** (CA-40): cronologia preparata di più turni (con strumenti) e soglie
    piccole → una chiamata, log `messages_before=… messages_after=… removed=…` con i numeri
    attesi, messaggi tolti esattamente `messages[:cut]`, `summary` uguale al testo del modello;
    l'agente riceve il riassunto nel messaggio di sistema;
  - **secondo riassunto** (CA-40): con un riassunto già nello stato, chi riassume lo riceve e il
    campo viene sostituito, non concatenato;
  - **niente da comprimere** (CA-41): un unico turno lunghissimo → nessuna chiamata, log
    `skipped=nothing_to_compress`;
  - **risposta vuota** (CA-42): WARNING `fallback=empty_summary`, messaggi e riassunto invariati,
    il turno prosegue;
  - il nodo non consuma `steps`; il grafo compilato contiene `summary` e l'arco `START → summary`.
- `test_session.py`: il riassunto passa da un turno all'altro (una compressione al terzo turno con
  soglie piccole, poi un quarto turno: l'agente riceve ancora il riassunto); un `APIConnectionError`
  di chi riassume lascia invariati cronologia e riassunto (CA-42). `RecordingGraph`, il grafo
  finto dei test di `Session`, restituisce anche `summary` e registra quello che riceve (scelta del
  progettista: `Session` legge `result["summary"]` senza ripieghi, perché il grafo vero lo
  restituisce sempre quando lo riceve).
- `test_config.py`: default 20 e 6; valori validi; `abc`, `0`, `-1`, `2.5` rifiutati; `keep ≥
  max` rifiutato; tutti nel messaggio unico (CA-38).
- `test_model.py`: `create_summary_model` si crea senza server.
- `test_main.py`: la riga di avvio contiene `summary_max_messages=20 summary_keep_messages=6`;
  il grafo creato da `main` passa dal nodo `summary`.

### Prove reali con LM Studio (`pytest -m real`)

`open_session` costruisce il grafo con `create_summary_model(config)` e le soglie di `config`.

- **Evidenza minima** (CA-43): soglie impostate nel test (`dataclasses.replace(config,
  summary_max_messages=4, summary_keep_messages=2)`); tre turni: «Mi chiamo Paolo», «Che ore
  sono a Tokyo?», «Come mi chiamo?». Si verifica:
  - al primo turno la riga `messages=1/4 skipped=below_threshold`;
  - prima della risposta al terzo turno almeno una riga `messages_before=<a> messages_after=<b>
    removed=<c>` con `a > b`;
  - nessun messaggio della sessione che precede l'ultima domanda («Come mi chiamo?») contiene
    «Paolo»: il nome può arrivare all'agente solo dal riassunto;
  - `session.summary` contiene «Paolo» (diagnosi: se manca, il difetto è nel riassunto);
  - la risposta al terzo turno contiene «Paolo».

  Scelta del progettista: la bozza controllava `skipped=below_threshold` al secondo turno e la
  compressione al terzo. Se il revisore reale rifiuta la prima risposta, bozza e indicazione
  portano la cronologia a 5 messaggi e la compressione avviene già al secondo turno: la prova
  sarebbe fallita senza un difetto. Il primo turno (1 messaggio) è sempre sotto la soglia. Il
  controllo sui messaggi conservati sostituisce «"Mi chiamo Paolo" non è più tra i messaggi»: copre
  anche il caso in cui la risposta del secondo turno chiama l'utente per nome, che renderebbe la
  prova non dimostrativa; in quel caso la prova fallisce e l'esito si riporta così com'è.
- **Esistenti** (CA-44): le 14 prove precedenti passano; con la soglia predefinita non arrivano a
  20 messaggi, quindi nei loro log compaiono solo righe `skipped=below_threshold`.
- **Manuale** (CA-45): la stessa sequenza via pipe verso `python -m assistant` con
  `SUMMARY_MAX_MESSAGES=4` e `SUMMARY_KEEP_MESSAGES=2`, e verso
  `docker compose run --rm -T -e SUMMARY_MAX_MESSAGES=4 -e SUMMARY_KEEP_MESSAGES=2 assistant`
  (dopo `docker compose build`): nei log le righe `node=summary` e la risposta con «Paolo».

Una prova reale eseguita una volta dimostra il comportamento con quelle domande, non che il
modello riassuma sempre bene. Un esito negativo viene riportato così com'è. La prova nuova
aggiunge alcuni minuti alla suite reale (circa 32 minuti oggi).

## 12. Incrementi

Ognuno verificato con `pytest` prima del commit.

1. Soglie in `config.py` e `.env.example`; test.
2. `summary.py`; test.
3. `model.py`: `create_summary_model`; test.
4. Grafo, `Session`, `__main__.py`, `conftest.py`: in un solo commit, perché la nuova firma di
   `build_graph` rompe gli altri finché non sono aggiornati; test.
5. Prove reali: fixture, prova nuova, esecuzione di tutta la suite `real`.
6. Prova manuale locale e con Docker; documentazione.

## 13. Documentazione

- `README.md`: che cosa fa il riassunto; `SUMMARY_MAX_MESSAGES` e `SUMMARY_KEEP_MESSAGES`;
  esempi di log; grafo aggiornato; numero di test; durata delle prove reali.
- `.env.example`: le due righe nuove.
- `CLAUDE.md`: struttura (`summary.py`); obiettivo e «Confini»: lo Step 3 della lezione 6 è
  concordato, gli step successivi no.
- `requisiti.md` §11 e `handoff.md` aggiornati con l'esito delle verifiche.

## 14. Rischi

- **Informazioni perse nel riassunto**: un modello piccolo può tralasciare un fatto. Il prompt
  elenca che cosa conservare e si può ritoccare; la prova reale controlla il caso del nome.
- **Dati solo nei risultati degli strumenti**: chi riassume non li vede (decisione §1); se la
  risposta non li ha ripetuti, si perdono (per esempio l'id di una nota non citato).
- **Riassunto che cresce**: il prompt chiede al massimo 10 righe, ma non c'è un limite rigido.
- **Risposta invece di riassunto**: il modello potrebbe rispondere all'ultima domanda della
  trascrizione; lo limitano il prompt e la trascrizione in un unico messaggio.
- **Latenza**: una chiamata in più nei turni in cui si supera la soglia; con 20 e 6, dopo una
  compressione ne restano circa 6, quindi la successiva arriva dopo alcuni turni.
- **Router dopo la compressione**: vede i messaggi conservati e il riassunto (§16). Se il
  riassunto tralascia un fatto, una domanda su quel fatto può ancora essere rifiutata.

## 15. Fuori ambito

Resource e prompt MCP (step 4–5), servizio HTTP, back-end, front-end e Compose a più container
(step 6–9), streaming. Soglia in token; risultati degli
strumenti passati a chi riassume; un modello diverso per il riassunto; persistenza del riassunto
oltre la sessione; le correzioni minori rimandate degli Step 1 e 2 e gli altri punti annotati
nell'handoff fuori dalla traccia.

## 16. Modifica dopo la prova reale (2026-11-13)

La prima esecuzione di CA-43 (Task 5 del piano) ha mostrato la compressione corretta
(`messages_before=7 messages_after=5 removed=2`) e il riassunto «L'utente si è presentato come
Paolo.», ma il router, che allora non riceveva il riassunto, ha classificato «Come mi chiamo?»
`out_of_scope` («informazioni personali che l'assistente non può fornire»). Una frase aggiunta a
`ROUTER_PROMPT` non è bastata (rifiuto in 3 esecuzioni su 4). In una prova diretta sugli stessi
messaggi conservati, 4 chiamate per variante: router senza riassunto `out_of_scope` 4 su 4, con
il riassunto in fondo al prompt `conversation` 4 su 4; l'agente con il riassunto risponde «Ti
chiami Paolo.» 4 su 4. Decisione dell'utente: il router riceve il riassunto come l'agente
(`with_summary`), la frase aggiunta a `ROUTER_PROMPT` è tolta, il revisore resta invariato.

**Revisore (seconda modifica, stesso giorno).** Con il router corretto, la CA-43 è fallita ancora
due volte: l'agente rispondeva con il nome, il revisore bocciava la risposta («l'utente non ha
fornito il proprio nome», perché vede solo domanda e risposta) e l'agente la riscriveva in «Non mi
hai fornito il tuo nome.». Prova diretta («Come mi chiamo?» / «Ti chiami Paolo.», 4 chiamate per
variante): revisore attuale approva 0 su 4; con una frase nel prompt 3 su 4; con il riassunto 4
su 4; con entrambi 4 su 4. Decisione dell'utente: entrambi. La frase copre anche il caso senza
compressione (nome detto in un turno precedente ancora in cronologia, CA-4).
