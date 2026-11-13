# Riassunto della cronologia (lezione 6, Step 3) — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** all'inizio di ogni turno un nodo `summary` comprime la cronologia quando supera
`SUMMARY_MAX_MESSAGES`: aggiorna un riassunto nello stato, toglie i messaggi vecchi con
`RemoveMessage` e conserva almeno gli ultimi `SUMMARY_KEEP_MESSAGES`, tagliando sempre all'inizio
di un turno.

**Architecture:** modulo nuovo `assistant/summary.py` (prompt e funzioni pure, sullo schema di
`router.py` e `reviewer.py`); `config.py` legge le due soglie; `model.py` crea il modello del
riassunto (testo libero, senza strumenti); `graph.py` aggiunge il campo `summary`, il nodo
`summary` e l'arco `START → summary → router`, e l'agente legge il riassunto in fondo al prompt di
sistema; `Session` conserva il riassunto tra i turni; `__main__.py` collega. Router, revisore,
terminale, strumenti, MCP, `scope.txt` e `compose.yaml` non cambiano.

**Tech Stack:** Python 3.13, LangGraph 1.2.17, langchain-core 1.7.0, langchain-openai 1.7.2,
pytest. Nessuna dipendenza nuova.

**Spec:** [`../specs/2026-11-13-riassunto-design.md`](../specs/2026-11-13-riassunto-design.md);
requisiti in [`../requisiti.md`](../requisiti.md) §11 (RF-34…RF-38, CA-38…CA-45).

## Global Constraints

- Codice, identificatori, chiavi dei log e nomi dei test in inglese; prompt, testi per l'utente e
  messaggi d'errore in italiano.
- Nodo esatto: `summary`; campo di stato `summary: str`, **sostituito** a ogni compressione.
- `SUMMARY_MAX_MESSAGES`: intero ≥ 1, default `20`. `SUMMARY_KEEP_MESSAGES`: intero ≥ 1, default
  `6`, minore di `SUMMARY_MAX_MESSAGES`. Errori esatti, aggiunti agli altri problemi nel messaggio
  unico «Configurazione non valida: …»:
  - `SUMMARY_MAX_MESSAGES deve essere un intero ≥ 1, ricevuto '<valore>'.`
  - `SUMMARY_KEEP_MESSAGES deve essere un intero ≥ 1, ricevuto '<valore>'.`
  - `SUMMARY_KEEP_MESSAGES deve essere minore di SUMMARY_MAX_MESSAGES, ricevuti '<keep>' e '<max>'.`
    (solo se entrambi i valori sono validi; `<keep>` e `<max>` sono i valori interi in uso,
    default compresi).
- Si riassume quando `len(messages)` (domanda appena arrivata compresa) **supera** la soglia.
- Log esatti (logger `assistant.graph`), `<json>` = `json.dumps(testo, ensure_ascii=False)`:
  - `INFO node=summary messages=<n>/<max> skipped=below_threshold next_node=router`
  - `INFO node=summary messages=<n>/<max> skipped=nothing_to_compress next_node=router`
  - `WARNING node=summary messages=<n>/<max> fallback=empty_summary next_node=router`
  - `INFO node=summary messages_before=<n> messages_after=<n - cut> removed=<cut> next_node=router`
  - `DEBUG node=summary summary=<json>`
  - all'avvio: `scope_file=<percorso> max_reviews=<n> summary_max_messages=<n> summary_keep_messages=<n>`.
- Il nodo non consuma `steps`; viene eseguito una volta per turno. Router e revisore non ricevono
  il riassunto. `openai.APIError` di chi riassume non viene intercettato: arriva al terminale,
  cronologia e riassunto invariati.
- Non anticipare gli step successivi (resource e prompt MCP, HTTP, back-end, front-end, Compose a
  più container) né i punti dell'handoff fuori dalla traccia.
- Comandi da PowerShell nella radice: `.\.venv\Scripts\python.exe -m pytest …`. In Git Bash usare
  `.venv/Scripts/python.exe`, mai `python`.
- Commit su `dev`, Conventional Commits in italiano, con la riga
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; prima di ogni commit `git status`,
  controllo del diff, staging selettivo (`LLM_Lez_6.pdf` resta non tracciato). Nessun push senza
  richiesta.
- Test con il modello simulato e prove reali separati: i primi in `pytest` (senza LM Studio), le
  seconde solo in `test_real.py` con il marcatore `real`. Nei controlli sui log l'agente si
  riconosce da `step=N/M node=llm`.

## Decisioni prese nel piano

- **`test_real.py` nel Task 4.** La nuova firma di `build_graph` rompe `open_session`: la fixture
  si aggiorna nello stesso commit del grafo (solo il collegamento del modello del riassunto e
  delle soglie di `config`). La prova reale nuova arriva nel Task 5.
- **Prova di sessione su quattro turni.** Con soglie 4 e 3 la compressione avviene al terzo turno
  e di nuovo al quarto: chi riassume, al quarto, riceve il riassunto del terzo. È la prova che
  `Session` lo porta da un turno all'altro (specifica §11, `test_session.py`).
- **«Il grafo creato da `main` passa dal nodo `summary`»** si verifica come per il revisore:
  modelli finti al posto delle `create_*`, `run` sostituito che invia un messaggio, e nel log la
  riga `node=summary messages=1/20 skipped=below_threshold`.

## Review Focus

1. Turno successivo a una compressione: il router vede solo i messaggi conservati e il suo prompt
   non contiene il riassunto; il revisore riceve ancora `review_messages(domanda, risposta)`;
   l'agente riceve il riassunto → `test_router_and_reviewer_never_see_the_summary` (Task 4).
2. L'agente fallisce nello stesso turno dopo una compressione: cronologia e riassunto della
   sessione invariati; al turno ripetuto chi riassume viene richiamato →
   `test_agent_error_after_compression_keeps_history_and_summary` (Task 4).
3. Soglia al confine: `n = max` non comprime, `n = max + 1` sì →
   `test_threshold_boundary` (Task 4).
4. Riassunto con a capo e virgolette: una sola riga DEBUG; riassunto di soli spazi trattato come
   vuoto → `test_summary_is_logged_on_one_line_at_debug`, caso `"  \n "` di
   `test_empty_summary_compresses_nothing` (Task 4).
5. Turni vecchi con riscrittura del revisore, rifiuto del router e avviso di `limit`: nella
   trascrizione restano domande, risposta finale riscritta, testo del rifiuto e avviso; non bozze,
   indicazioni, tool_call né risultati → `test_summary_input_with_rewrite_refusal_and_limit`
   (Task 2).

---

### Task 1: soglie in configurazione

**Files:**
- Modify: `assistant/config.py`, `.env.example`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config.summary_max_messages: int = 20` e `Config.summary_keep_messages: int = 6`,
  ultimi campi, dopo `max_reviews` (`load_config` li valorizza sempre).

- [ ] **Step 1: test che falliscono** in `tests/test_config.py`, sezione
  `# --- summary (lesson 6, step 3) ---`:

```python
def test_summary_thresholds_default_and_override():
    config = load_config(VALID)
    assert (config.summary_max_messages, config.summary_keep_messages) == (20, 6)
    config = load_config({**VALID, "SUMMARY_MAX_MESSAGES": " 4 ", "SUMMARY_KEEP_MESSAGES": "2"})
    assert (config.summary_max_messages, config.summary_keep_messages) == (4, 2)

@pytest.mark.parametrize("name", ["SUMMARY_MAX_MESSAGES", "SUMMARY_KEEP_MESSAGES"])
@pytest.mark.parametrize("value", ["abc", "0", "-1", "2.5"])
def test_invalid_summary_threshold(name, value):
    assert error({**VALID, name: value}) == (
        f"{name} deve essere un intero ≥ 1, ricevuto '{value}'."
    )

@pytest.mark.parametrize(("env", "keep", "maximum"), [
    ({"SUMMARY_KEEP_MESSAGES": "20"}, 20, 20),
    ({"SUMMARY_MAX_MESSAGES": "4", "SUMMARY_KEEP_MESSAGES": "5"}, 5, 4),
    ({"SUMMARY_MAX_MESSAGES": "3"}, 6, 3),
])
def test_keep_must_be_below_max(env, keep, maximum):
    assert error({**VALID, **env}) == (
        "SUMMARY_KEEP_MESSAGES deve essere minore di SUMMARY_MAX_MESSAGES, "
        f"ricevuti '{keep}' e '{maximum}'."
    )

def test_summary_problems_listed_with_the_others():
    assert error({"SUMMARY_MAX_MESSAGES": "0", "SUMMARY_KEEP_MESSAGES": "x"}) == (
        "Manca LMSTUDIO_BASE_URL. Manca LMSTUDIO_MODEL. "
        "SUMMARY_MAX_MESSAGES deve essere un intero ≥ 1, ricevuto '0'. "
        "SUMMARY_KEEP_MESSAGES deve essere un intero ≥ 1, ricevuto 'x'."
    )
```

- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_config.py -v` → i nuovi
  FALLISCONO.

- [ ] **Step 3: implementare.** In `config.py` i due campi con commento
  (`# SUMMARY_MAX_MESSAGES (integer >= 1)`, `# SUMMARY_KEEP_MESSAGES (integer >= 1, < max)`) e la
  lettura subito dopo `MAX_REVIEWS`, con la stessa logica; il confronto `keep ≥ max` solo se
  nessuno dei due ha dato un problema. In `.env.example` le righe `SUMMARY_MAX_MESSAGES=20` e
  `SUMMARY_KEEP_MESSAGES=6` dopo `MAX_REVIEWS=2`.

- [ ] **Step 4:** `.\.venv\Scripts\python.exe -m pytest` → tutto verde.

- [ ] **Step 5: commit** `feat(config): soglie SUMMARY_MAX_MESSAGES e SUMMARY_KEEP_MESSAGES`.

### Task 2: modulo `summary.py`

**Files:**
- Create: `assistant/summary.py`
- Test: `tests/test_summary.py`

**Interfaces:**
- Consumes: `router_messages` (`assistant.router`), `is_feedback` (`assistant.reviewer`).
- Produces:
  - `SUMMARY_PROMPT: str` (testo esatto della specifica §5);
  - `is_user_question(message: AnyMessage) -> bool`;
  - `cut_index(messages: list[AnyMessage], keep: int) -> int`;
  - `summary_input(previous: str, old: list[AnyMessage]) -> list[BaseMessage]`;
  - `with_summary(prompt: str, summary: str) -> str`.

- [ ] **Step 1: test che falliscono** in `tests/test_summary.py`. Aiuti: `D(t) = HumanMessage(t)`,
  `R(t) = AIMessage(t)`, `tool_call()` da `conftest`, `tool_result(id="c1")` =
  `ToolMessage('{"datetime": "2026-11-13T10:00:00+09:00"}', tool_call_id=id, name="get_current_time")`,
  `feedback_message("manca")` da `reviewer`.

```python
@pytest.mark.parametrize(("messages", "keep", "expected"), [
    ([D("d1"), R("r1"), D("d2")], 2, 0),                                        # corta
    ([D("d1"), R("r1"), D("d2"), tool_call(), tool_result(), R("r2"), D("d3")], 2, 2),  # su R2 → D2
    ([D("d1"), R("r1"), D("d2"), tool_call(), tool_result(), R("r2"), D("d3")], 3, 2),  # su Tool
    ([D("d1"), R("r1"), D("d2"), tool_call(), tool_result(), R("r2"), D("d3")], 4, 2),  # su tool_call
    ([D("d1"), R("r1"), D("d2"), R("bozza"), feedback_message("m"), R("r2"), D("d3")], 3, 2),  # su indicazione
    ([D("d1"), R("r1"), D("d2"), R("bozza"), feedback_message("m"), R("r2"), D("d3")], 4, 2),  # su bozza
    ([D("d1"), R("r1"), D("d2"), R("r2"), D("d3")], 3, 2),                      # già su una domanda
    ([D("d1"), R("bozza"), feedback_message("m"), R("r1"), D("d2")], 2, 0),     # un turno e la domanda
    ([D("d1")], 1, 0),
])
def test_cut_index(messages, keep, expected):
    cut = cut_index(messages, keep)
    assert cut == expected
    kept = messages[cut:]
    assert len(kept) >= keep or cut == 0
    assert cut == 0 or is_user_question(kept[0])                                 # CA-41
    kept_calls = {c["id"] for m in kept if isinstance(m, AIMessage) for c in m.tool_calls}
    assert all(m.tool_call_id in kept_calls for m in kept if isinstance(m, ToolMessage))

def test_is_user_question():
    assert is_user_question(D("ciao"))
    assert not is_user_question(feedback_message("manca"))
    assert not is_user_question(R("ciao"))

def test_summary_input_first_time():
    old = [D("Mi chiamo Paolo"), R("Piacere, Paolo."), D("Ore?"), tool_call(), tool_result(),
           R("Sono le 10.")]
    sent = summary_input("", old)
    assert sent[0] == SystemMessage(SUMMARY_PROMPT) and len(sent) == 2
    assert sent[1] == HumanMessage(
        "Riassunto precedente:\n(nessuno)\n\nNuovi messaggi:\n"
        "Utente: Mi chiamo Paolo\nAssistente: Piacere, Paolo.\nUtente: Ore?\nAssistente: Sono le 10."
    )

def test_summary_input_with_previous_summary_and_empty_answer():
    sent = summary_input("L'utente si chiama Paolo.", [D("ciao"), R("  ")])
    assert sent[1].content == (
        "Riassunto precedente:\nL'utente si chiama Paolo.\n\nNuovi messaggi:\nUtente: ciao"
    )

def test_summary_input_with_rewrite_refusal_and_limit():          # Review Focus 5
    old = [D("d1"), R("bozza"), feedback_message("manca"), R("riscritta"),
           D("Mondiali?"), R(refusal_text("fuori ambito")),
           D("d3"), tool_call(), tool_result(), R("Ho raggiunto il limite di 1 passaggi senza una risposta finale.")]
    text = summary_input("", old)[1].content
    assert "Assistente: riscritta" in text and "bozza" not in text and "Revisione:" not in text
    assert f"Assistente: {refusal_text('fuori ambito')}" in text
    assert "Assistente: Ho raggiunto il limite" in text and "datetime" not in text

def test_with_summary():
    assert with_summary("P", "") == "P"
    assert with_summary("P", "S") == "P\n\nRiassunto della conversazione precedente:\nS"
```

- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_summary.py -v` → FALLISCONO
  (`ModuleNotFoundError`).

- [ ] **Step 3: implementare `assistant/summary.py`.** Docstring del modulo nello stile di
  `router.py`. `cut_index` come la specifica §5 (tre passi). `summary_input`: trascrizione da
  `router_messages(old)`, una riga `Utente: <text.strip()>` per ogni `HumanMessage`,
  `Assistente: <text.strip()>` per ogni `AIMessage` con testo non vuoto, unite da `"\n"`.

- [ ] **Step 4:** `.\.venv\Scripts\python.exe -m pytest` → tutto verde.

- [ ] **Step 5: commit** `feat(riassunto): modulo summary.py con taglio e trascrizione`.

### Task 3: modello del riassunto

**Files:**
- Modify: `assistant/model.py`
- Test: `tests/test_model.py`

**Interfaces:**
- Produces: `create_summary_model(config: Config) -> Runnable`: `_chat(config)` così com'è, senza
  `bind_tools` né output strutturato; restituisce un `AIMessage`.

- [ ] **Step 1: test che fallisce:**

```python
def test_create_summary_model_needs_no_server():
    model = create_summary_model(load_config(VALID))
    assert isinstance(model, ChatOpenAI) and model.model_name == "google/gemma-4-e2b"
```

- [ ] **Step 2:** `.\.venv\Scripts\python.exe -m pytest tests/test_model.py -v` → FALLISCE
  (`ImportError`).
- [ ] **Step 3:** implementare (docstring: «Same model as the agent, without tools: free text.»).
- [ ] **Step 4:** `.\.venv\Scripts\python.exe -m pytest` → tutto verde.
- [ ] **Step 5: commit** `feat(modello): modello del riassunto senza strumenti`.

### Task 4: nodo `summary` nel grafo, sessione e avvio (un solo commit)

La nuova firma di `build_graph` rompe `conftest.py`, `__main__.py` e `test_real.py` finché non
sono aggiornati: tutto in un commit.

**Files:**
- Modify: `assistant/graph.py`, `assistant/session.py`, `assistant/__main__.py`,
  `tests/conftest.py`, `tests/test_real.py` (solo `open_session`)
- Test: `tests/test_graph.py`, `tests/test_session.py`, `tests/test_main.py`

**Interfaces:**
- Consumes: Task 1 (`Config.summary_max_messages`, `Config.summary_keep_messages`), Task 2
  (`cut_index`, `summary_input`, `with_summary`), Task 3 (`create_summary_model`).
- Produces:
  - `State` con `summary: str` (specifica §7), dopo `messages`;
  - `build_graph(model, tools, max_steps, *, router_model, scope, reviewer_model, max_reviews,
    summary_model, summary_max_messages, summary_keep_messages)`;
  - `Session.summary` (proprietà, `str`, iniziale `""`); `Session.send` invoca il grafo con
    `{"messages", "summary": self._summary, "steps": 0, "reviews": 0}` e, se il turno riesce,
    aggiorna `_messages` e `_summary = result["summary"]`;
  - in `conftest.py`: `fake_graph(model, tools=None, max_steps=5, router=None, scope=TEST_SCOPE,
    reviewer=None, max_reviews=2, summary_model=None, summary_max_messages=20,
    summary_keep_messages=6)`; `summary_model=None` → `FakeModel([])`.

- [ ] **Step 1: aggiornare gli aiuti.** In `conftest.py` i nuovi parametri di `fake_graph`. In
  `test_session.py` `RecordingGraph` registra `state["summary"]` in `incoming_summaries` e
  restituisce anche `"summary": state["summary"]`. In `test_main.py` `test_missing_scope_file_exits_1`
  sostituisce anche `create_summary_model` con `_must_not_call`.

- [ ] **Step 2: test nuovi in `tests/test_graph.py`**, sezione
  `# --- summary (lesson 6, step 3) ---`, con questi aiuti:

```python
def summarized_turn(summarizer, history, summary="", model=None, max_messages=4, keep=2, **kw):
    model = model or FakeModel([AIMessage("risposta")])
    return fake_graph(model, summary_model=summarizer, summary_max_messages=max_messages,
                      summary_keep_messages=keep, **kw).invoke(
        {"messages": history, "summary": summary, "steps": 0, "reviews": 0})

def summary_lines(caplog, level=None): ...   # messaggi che iniziano con "node=summary"

def five():   # [D1, R1, D2, R2, D3]: con keep=2 il taglio è 2
def seven():  # [D1 "Mi chiamo Paolo", R1, D2, tool_call(), ToolMessage c1, R2, D3]: con keep=2 il taglio è 2
```

```python
@pytest.mark.parametrize(("max_messages", "calls"), [(5, 0), (4, 1)])
def test_threshold_boundary(caplog, max_messages, calls):            # CA-39, Review Focus 3
    summarizer = FakeModel([AIMessage("S")])
    result = summarized_turn(summarizer, five(), max_messages=max_messages)
    assert len(summarizer.calls) == calls
    if calls == 0:
        assert summary_lines(caplog) == [
            "node=summary messages=5/5 skipped=below_threshold next_node=router"]
        assert contents(result["messages"])[:5] == contents(five()) and result["summary"] == ""

def test_compression_over_the_threshold(caplog):                     # CA-40
    history, summarizer = seven(), FakeModel([AIMessage("L'utente si chiama Paolo.")])
    model = FakeModel([AIMessage("Ti chiami Paolo.")])
    result = summarized_turn(summarizer, history, model=model)
    assert summarizer.calls == [summary_input("", history[:2])]
    assert summary_lines(caplog, logging.INFO) == [
        "node=summary messages_before=7 messages_after=5 removed=2 next_node=router"]
    assert contents(result["messages"]) == contents(history[2:]) + ["Ti chiami Paolo."]
    assert result["summary"] == "L'utente si chiama Paolo."
    assert model.calls[0][0] == SystemMessage(
        with_summary(SYSTEM_PROMPT, "L'utente si chiama Paolo."))

def test_second_summary_replaces_the_first():                        # CA-40
    summarizer = FakeModel([AIMessage("Nuovo.")])
    result = summarized_turn(summarizer, five(), summary="Vecchio.")
    assert summarizer.calls[0][1].content.startswith("Riassunto precedente:\nVecchio.\n\n")
    assert result["summary"] == "Nuovo."

def test_one_long_turn_has_nothing_to_compress(caplog):              # CA-41
    history = [HumanMessage("d1"), tool_call(), ToolMessage("{}", tool_call_id="c1",
               name="get_current_time"), AIMessage("r1"), HumanMessage("d2")]
    summarizer = FakeModel([])
    summarized_turn(summarizer, history)
    assert summarizer.calls == []
    assert summary_lines(caplog) == [
        "node=summary messages=5/4 skipped=nothing_to_compress next_node=router"]

@pytest.mark.parametrize("text", ["", "  \n "])
def test_empty_summary_compresses_nothing(caplog, text):             # CA-42, Review Focus 4
    model = FakeModel([AIMessage("risposta")])
    result = summarized_turn(FakeModel([AIMessage(text)]), five(), model=model)
    assert summary_lines(caplog, logging.WARNING) == [
        "node=summary messages=5/4 fallback=empty_summary next_node=router"]
    assert contents(result["messages"]) == contents(five()) + ["risposta"]
    assert result["summary"] == "" and model.calls[0][0] == SystemMessage(SYSTEM_PROMPT)

def test_summary_is_logged_on_one_line_at_debug(caplog):             # Review Focus 4
    caplog.set_level(logging.DEBUG, logger="assistant.graph")
    text = 'Si chiama "Paolo".\nVuole le ore.'
    summarized_turn(FakeModel([AIMessage(text)]), five())
    assert f"node=summary summary={json.dumps(text, ensure_ascii=False)}" in summary_lines(
        caplog, logging.DEBUG)

def test_summary_does_not_consume_steps(caplog):
    result = summarized_turn(FakeModel([AIMessage("S")]), five(), max_steps=1)
    assert result["steps"] == 1 and "step=1/1 node=llm" in caplog.text

def test_graph_starts_with_the_summary_node():
    drawn = fake_graph(FakeModel([])).get_graph()
    assert "summary" in drawn.nodes
    assert {(e.source, e.target) for e in drawn.edges} >= {
        ("__start__", "summary"), ("summary", "router")}
```

  (`contents` = lista dei `content`; il `caplog` di ogni test è a INFO sul logger
  `assistant.graph`, salvo dove indicato.)

- [ ] **Step 3: test nuovi in `tests/test_session.py`** (sezione `# --- summary (lesson 6, step 3) ---`):

```python
def small_session(model, summarizer, **kw):
    return Session(fake_graph(model, summary_model=summarizer, summary_max_messages=4,
                              summary_keep_messages=3, **kw))

def test_summary_carries_over_between_turns():
    model = FakeModel([AIMessage(t) for t in ("r1", "r2", "r3", "r4")])
    summarizer = FakeModel([AIMessage("S1"), AIMessage("S2")])
    s = small_session(model, summarizer)
    for text in ("d1", "d2", "d3"):
        s.send(text)
    assert s.summary == "S1" and contents(s.messages) == ["d2", "r2", "d3", "r3"]
    s.send("d4")
    assert summarizer.calls[1][1].content.startswith("Riassunto precedente:\nS1\n\n")
    assert s.summary == "S2"
    assert model.calls[-1][0] == SystemMessage(with_summary(SYSTEM_PROMPT, "S2"))

def test_router_and_reviewer_never_see_the_summary():               # Review Focus 1
    router, reviewer = ConversationRouter(), ApprovingReviewer()
    model = FakeModel([AIMessage(t) for t in ("r1", "r2", "r3")])
    s = small_session(model, FakeModel([AIMessage("S1")]), router=router, reviewer=reviewer)
    for text in ("d1", "d2", "d3"):
        s.send(text)
    sent = router.calls[-1]
    assert sent[0] == SystemMessage(ROUTER_PROMPT.format(scope=TEST_SCOPE))
    assert contents(sent[1:]) == ["d2", "r2", "d3"]           # kept messages only, no summary
    assert reviewer.calls[-1] == review_messages("d3", "r3")

def test_summary_error_leaves_history_and_summary_untouched():       # CA-42
    s = small_session(FakeModel([AIMessage("r1"), AIMessage("r2")]),
                      FakeModel([lm_studio_error()]))
    s.send("d1"); s.send("d2")
    with pytest.raises(openai.APIConnectionError):
        s.send("d3")
    assert contents(s.messages) == ["d1", "r1", "d2", "r2"] and s.summary == ""

def test_agent_error_after_compression_keeps_history_and_summary():  # Review Focus 2
    model = FakeModel([AIMessage("r1"), AIMessage("r2"), lm_studio_error(), AIMessage("r3")])
    summarizer = FakeModel([AIMessage("S1"), AIMessage("S1 bis")])
    s = small_session(model, summarizer)
    s.send("d1"); s.send("d2")
    with pytest.raises(openai.APIConnectionError):
        s.send("d3")
    assert contents(s.messages) == ["d1", "r1", "d2", "r2"] and s.summary == ""
    s.send("d3")
    assert len(summarizer.calls) == 2 and s.summary == "S1 bis"

def test_summary_restarts_empty():
    graph = RecordingGraph()
    s = Session(graph)
    s.send("uno")
    assert graph.incoming_summaries == [""]
```

  I messaggi passati per il grafo hanno un id assegnato dal reducer: si confrontano per contenuto
  (`contents`); i messaggi costruiti dalle funzioni (`summary_input`, `review_messages`,
  `SystemMessage`) si confrontano interi, perché da entrambe le parti non hanno id.

- [ ] **Step 4: test nuovi in `tests/test_main.py`** (sezione `# --- summary (lesson 6, step 3) ---`),
  sullo schema dei test del revisore:
  - `test_summary_model_and_thresholds_reach_the_graph` (parametrizzato: `{}` → 20 e 6;
    `{"SUMMARY_MAX_MESSAGES": "8", "SUMMARY_KEEP_MESSAGES": "3"}` → 8 e 3):
    `received[0]["summary_model"] is summarizer` e le due soglie;
  - `test_graph_built_by_main_goes_through_the_summary_node`: come
    `test_graph_built_by_main_goes_through_the_reviewer`, con `create_summary_model` →
    `FakeModel([])`; nel log `node=summary messages=1/20 skipped=below_threshold next_node=router`;
  - `test_summary_thresholds_are_logged`: nel log
    `scope_file={DEFAULT_SCOPE_FILE} max_reviews=2 summary_max_messages=20 summary_keep_messages=6`.

- [ ] **Step 5:** `.\.venv\Scripts\python.exe -m pytest tests/test_graph.py tests/test_session.py tests/test_main.py -v`
  → i nuovi FALLISCONO (firma di `fake_graph`, `Session.summary`).

- [ ] **Step 6: implementare.**
  - `graph.py`: campo `summary` nello `State`; parametri nuovi di `build_graph`; `summary_node`
    esattamente come la specifica §7 (cinque casi, nell'ordine), con
    `previous = state.get("summary", "")`; `llm_node` usa
    `SystemMessage(with_summary(SYSTEM_PROMPT, state.get("summary", "")))`; archi
    `START → summary` e `summary → router` al posto di `START → router`; schema nella docstring
    del modulo aggiornato come la specifica §2.
  - `session.py`: `_summary`, proprietà `summary`, `send` come in **Interfaces**.
  - `__main__.py`: `create_summary_model(config)` e le due soglie passati a `build_graph`; la riga
    di avvio estesa con `summary_max_messages=%d summary_keep_messages=%d`; docstring del modulo
    con il modello del riassunto.
  - `test_real.py`, `open_session`: `summary_model=create_summary_model(config)`,
    `summary_max_messages=config.summary_max_messages`,
    `summary_keep_messages=config.summary_keep_messages`.

- [ ] **Step 7:** `.\.venv\Scripts\python.exe -m pytest` → tutto verde; annotare il numero
  (prima: 249 passed, 14 deselected). `.\.venv\Scripts\python.exe -m pytest -m real --collect-only -q`
  → 14 prove raccolte senza errori di import.

- [ ] **Step 8: commit** `feat(grafo): nodo summary all'inizio del turno`.

### Task 5: prove reali con LM Studio

**Files:**
- Modify: `tests/test_real.py`

**Interfaces:**
- Consumes: `open_session` (Task 4), `Session.summary`, `is_user_question` (Task 2).

Prerequisiti: LM Studio con `google/gemma-4-e2b` (contesto 8192), `LMSTUDIO_BASE_URL` e
`LMSTUDIO_MODEL` impostate; `SUMMARY_MAX_MESSAGES` e `SUMMARY_KEEP_MESSAGES` **non** impostate
(le prove esistenti usano i default).

- [ ] **Step 1: prova nuova** (CA-43), sezione `# --- lesson 6, step 3: summary (CA-43) ---`:

```python
COMPRESSION = re.compile(
    r"node=summary messages_before=(\d+) messages_after=(\d+) removed=\d+ next_node=router")

def summary_lines(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith("node=summary")]

def test_first_turn_information_survives_compression(config, tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="assistant.graph")
    small = dataclasses.replace(config, summary_max_messages=4, summary_keep_messages=2)
    with open_session(small, tmp_path / "notes.sqlite3") as (session, _):
        session.send("Mi chiamo Paolo")
        first = summary_lines(caplog)
        session.send("Che ore sono a Tokyo?")
        reply = session.send("Come mi chiamo?")
        messages, summary = session.messages, session.summary
    lines = summary_lines(caplog)
    assert first == ["node=summary messages=1/4 skipped=below_threshold next_node=router"], first
    sizes = [tuple(map(int, m.groups())) for m in map(COMPRESSION.fullmatch, lines) if m]
    assert sizes and all(before > after for before, after in sizes), lines
    last = max(i for i, m in enumerate(messages) if is_user_question(m))
    assert not any("Paolo" in m.text for m in messages[:last]), messages  # only the summary has it
    assert "Paolo" in summary, summary
    assert "Paolo" in reply, (reply, summary, lines)
```

- [ ] **Step 2: eseguire prima la prova nuova, da sola:**
  `.\.venv\Scripts\python.exe -m pytest -m real -v -k survives_compression`. Annotare le righe
  `node=summary` e il testo di `session.summary` (dall'output del fallimento o con `-s` e un
  `print` temporaneo non committato). Se fallisce, riportare all'utente quale controllo non passa
  (riassunto senza il nome, nome ripetuto nei messaggi conservati, risposta senza il nome, rifiuto
  del router) prima di ritoccare `SUMMARY_PROMPT`; un ritocco del prompt solo dopo averne parlato.

- [ ] **Step 3: eseguire tutta la suite reale:** `.\.venv\Scripts\python.exe -m pytest -m real -v`
  → atteso `15 passed` (CA-44); annotare la durata. Controllare che nelle prove esistenti
  compaiano solo righe `skipped=below_threshold`.

- [ ] **Step 4:** `.\.venv\Scripts\python.exe -m pytest` → ancora verde.

- [ ] **Step 5: commit** `test(riassunto): prova reale del riassunto con LM Studio`.

### Task 6: prova manuale, Docker e documentazione

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `docs/superpowers/requisiti.md`,
  `docs/superpowers/handoff.md`, `docs/superpowers/specs/2026-11-13-riassunto-design.md` (solo il
  collegamento al piano e lo stato)

- [ ] **Step 1: prova manuale locale** (CA-45), con `NOTES_DB` in una cartella temporanea:
  `$env:SUMMARY_MAX_MESSAGES="4"; $env:SUMMARY_KEEP_MESSAGES="2"`, poi
  `"Mi chiamo Paolo", "Che ore sono a Tokyo?", "Come mi chiamo?", "esci" | .\.venv\Scripts\python.exe -m assistant`
  → riga di avvio con `summary_max_messages=4 summary_keep_messages=2`, righe `node=summary`
  (almeno una `messages_before=… messages_after=… removed=…`), risposta con «Paolo». Togliere poi
  le due variabili (`Remove-Item Env:SUMMARY_MAX_MESSAGES, Env:SUMMARY_KEEP_MESSAGES`). Copiare
  le righe reali per il README.

- [ ] **Step 2: prova Docker** (CA-45): `docker compose build`, poi la stessa pipe verso
  `docker compose run --rm -T -e SUMMARY_MAX_MESSAGES=4 -e SUMMARY_KEEP_MESSAGES=2 assistant` →
  stesse righe e risposta con «Paolo».

- [ ] **Step 3: README.** Che cosa fa il riassunto; `SUMMARY_MAX_MESSAGES` e
  `SUMMARY_KEEP_MESSAGES` nella tabella della configurazione; grafo aggiornato (`START → summary
  → router`); esempi di log reali (Step 1–2) e, dai formati verificati nei test e dichiarati come
  tali, `nothing_to_compress` ed `empty_summary`; numero di test dall'ultimo `pytest`; numero e
  durata delle prove reali. Solo comandi eseguiti in questo piano.

- [ ] **Step 4: `CLAUDE.md`.** Struttura: `summary.py`; «Obiettivo»: nodo riassunto all'inizio
  del turno (lezione 6, Step 3); «Confini»: lo Step 3 è concordato e implementato, gli step
  successivi (resource e prompt MCP, servizio HTTP, back-end, front-end, Compose a più container)
  no.

- [ ] **Step 5: `requisiti.md`, `handoff.md`, specifica.** §11 invariato salvo lo stato delle
  verifiche; `handoff.md`: stato dello Step 3, tabella CA-38…CA-45 con comando ed esito reale,
  decisioni prese durante l'esecuzione, punti aperti, prossimo passo (Step 4 da avviare con un
  nuovo brainstorming); nella specifica il collegamento al piano.

- [ ] **Step 6: verifica finale:** `.\.venv\Scripts\python.exe -m pytest` (riportare il numero),
  `git status --ignored` (nessun file indesiderato; `LLM_Lez_6.pdf` non tracciato).

- [ ] **Step 7: commit** `docs(riassunto): README, CLAUDE.md e handoff dello step 3`.

## Copertura della specifica

| Specifica / CA | Task |
|----------------|------|
| §4 soglie, CA-38 | 1 |
| §5 prompt e funzioni; CA-41 (taglio) | 2 |
| §6 modello | 3 |
| §7 stato, nodo, agente, archi, log; §8 sessione; §9 avvio; CA-39…CA-42 | 4 |
| §11 prove reali, CA-43, CA-44 | 5 |
| CA-45 (manuale, Docker), §13 documentazione | 6 |
