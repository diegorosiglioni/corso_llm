# Assistente del laboratorio — Piano di implementazione

> **Per gli agenti esecutori:** SOTTO-SKILL RICHIESTA: usare superpowers:subagent-driven-development
> (consigliata) o superpowers:executing-plans per eseguire il piano task per task. I passi usano
> le caselle (`- [ ]`) per il tracciamento.

**Obiettivo:** applicazione Python da terminale che conversa con `google/gemma-4-e2b` servito da
LM Studio sull'host, attraverso un grafo LangGraph esplicito con cronologia di sessione e strumento
orologio `ora_corrente`, avviabile anche con Docker Compose.

**Architettura:** `StateGraph` costruito a mano (nodi `modello`, `strumenti`, `limite`, funzione
`instrada`); la cronologia la tiene la classe `Sessione`, che la aggiorna solo a turno riuscito;
`__main__.py` è l'unico modulo che collega config, modello, strumenti, grafo, sessione e terminale.

**Tecnologie:** Python 3.13, LangGraph, langchain-openai (`ChatOpenAI` verso l'API compatibile
OpenAI di LM Studio), `zoneinfo` + `tzdata`, pytest, Docker Compose.

**Specifica:** [`../specs/2026-10-26-assistente-laboratorio-design.md`](../specs/2026-10-26-assistente-laboratorio-design.md)
(che rimanda a [`../requisiti.md`](../requisiti.md)). L'esecutore legge entrambe: il piano cita la
specifica per sezione (§) e non ne ripete i dettagli.

## Vincoli globali

- Tutto il lavoro sta in `assistente-laboratorio/`; `lezione3/` non si legge né si modifica.
- Branch corrente (`main`), nessun branch o worktree nuovo. Push solo su richiesta.
- Nessun codice applicativo prima dell'approvazione di questo piano.
- Python 3.13 (locale: 3.13.14; Docker: `python:3.13-slim`). Codice sincrono.
- Dipendenze (versioni più recenti su PyPI al 2026-10-26, da confermare con l'installazione del Task 1):

  | Pacchetto | Versione | Motivo |
  |-----------|----------|--------|
  | `langgraph` | 1.2.17 | `StateGraph`, `add_messages` (RNF-2) |
  | `langchain-core` | 1.7.0 | messaggi, `@tool`, `Runnable` (importato direttamente) |
  | `langchain-openai` | 1.7.2 | `ChatOpenAI` verso LM Studio (RNF-3) |
  | `openai` | 3.37.0 | `openai.APIError` intercettato nel terminale (importato direttamente) |
  | `tzdata` | 2026.5 | database dei fusi su Windows e nell'immagine `slim` |
  | `pytest` (solo dev) | 9.1.1 | test automatici |

  Se `pip` segnala un conflitto, si sceglie la versione più alta compatibile e si aggiorna questa
  tabella nello stesso commit. Si fissano le dipendenze dirette; le transitive le risolve `pip`.
- Variabili: `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODELLO` (obbligatorie), `MAX_PASSI` (default 5),
  `LOG_LEVEL` (default `INFO`). Identificativo del modello verificato con `GET /v1/models`:
  `google/gemma-4-e2b` (presente il 2026-10-26).
- Ambiente virtuale in `assistente-laboratorio/.venv`; i comandi si lanciano da
  `assistente-laboratorio/` usando `.\.venv\Scripts\python.exe` (niente `Activate.ps1`, così la
  execution policy di PowerShell non interferisce).
- Commit: Conventional Commits in italiano; prima di ogni commit `git status`, `git diff`, staging
  dei soli file elencati nel task. Mai `.env`, `.venv/`, cache.
- `CLAUDE.md` ha modifiche dell'utente non committate: non includerle nei commit dei task; nel
  Task 10 chiedere come trattarle prima di aggiornare il file.
- Il README riporta solo comandi eseguiti davvero, in PowerShell.
- Lessico fisso (testi visibili e log): vedi §6–§8 della specifica; i testi nuovi decisi qui sono
  scritti nei task.

## Attenzione in revisione

Casi che la specifica implica ma che nessun test elencato in §10 esercita; ciascuno ha il suo test
nel task indicato.

1. **`MAX_PASSI` alto (es. 20)** — l'utente si aspetta il messaggio di RF-10, non un
   `GraphRecursionError` di LangGraph per il limite di ricorsione predefinito. Il grafo compilato
   riceve `recursion_limit = 2 * max_passi + 2`. Test nel Task 7.
2. **Più `tool_calls` nello stesso messaggio** (es. «ore a Tokyo e a Roma?») — ogni chiamata
   riceve il suo `ToolMessage`, nell'ordine, con il suo `tool_call_id`. Test nel Task 7.
3. **LM Studio cade a metà turno** (dopo che lo strumento è già stato eseguito) — la cronologia
   resta quella precedente al turno, senza `AIMessage`/`ToolMessage` orfani. Test nel Task 7.
4. **Ctrl+C mentre si attende il modello** (non durante `input`) — saluto e uscita pulita, non una
   traccia d'errore. Test nel Task 4.
5. **Fuso con maiuscole sbagliate (`asia/tokyo`)** — su Windows `ZoneInfo` può accettarlo
   (filesystem non sensibile alle maiuscole) e su Linux no: il comportamento deve essere lo stesso
   in locale e in Docker. Lo strumento accetta solo nomi presenti in
   `zoneinfo.available_timezones()` (confronto esatto), quindi `asia/tokyo` → `errore`. Test nel
   Task 6.

---

## Mappa degli incrementi

| Incremento | Task | Esito verificabile |
|------------|------|--------------------|
| 1. Grafo con risposta fissa | 1 | il grafo, con un modello finto che dà una risposta fissa, produce la risposta e conta i passi |
| 2. LM Studio e cronologia | 2, 3, 4, 5 | `python -m assistente` conversa con LM Studio e ricorda i turni precedenti |
| 3. Orologio e instradamento | 6, 7, 8 | il modello chiama `ora_corrente`, il grafo la esegue e risponde; limite dei passaggi |
| 4. Docker Compose | 9 | la stessa conversazione dal container |
| 5. Verifica completa | 10 | tutti i CA verificati e riportati; README e CLAUDE.md aggiornati |

«Risposta fissa» nell'incremento 1 significa: il nodo `modello` riceve un modello iniettato e nei
test è un `ModelloFinto` con risposta programmata. Non si aggiunge codice di produzione a risposta
fissa che verrebbe poi buttato.

Prima del Task 1, dopo l'approvazione: commit del piano e dello stato della specifica
(`Stato: approvata`) con `docs: aggiunge il piano di implementazione dell'assistente`.

---

## Incremento 1 — Grafo con risposta fissa

### Task 1: Scheletro del progetto e grafo con il solo nodo `modello`

**File:**
- Crea: `assistente-laboratorio/.gitignore` (voci di §11), `requirements.txt`, `requirements-dev.txt`
  (`-r requirements.txt` + `pytest==9.1.1`), `pytest.ini`, `assistente/__init__.py` (vuoto),
  `assistente/grafo.py`, `tests/conftest.py`, `tests/test_grafo.py`, `README.md`
- Tutti i percorsi sono relativi ad `assistente-laboratorio/`.

**Interfacce:**
- Produce (`assistente/grafo.py`):
  - `class Stato(TypedDict)` come in §6.
  - `PROMPT_SISTEMA: str` con il testo esatto di §6.
  - `costruisci_grafo(modello: Runnable, max_passi: int)` → grafo compilato con `START → modello → END`.
    (Nel Task 7 la firma diventa quella finale di §6.)
  - logger `logging.getLogger(__name__)` (nome `assistente.grafo`).
- Produce (`tests/conftest.py`):
  - `class ModelloFinto` — `__init__(self, risposte: list[AIMessage | BaseException])`;
    `invoke(self, messaggi) -> AIMessage` registra una copia dei messaggi in `self.chiamate:
    list[list[BaseMessage]]`, poi restituisce la prossima risposta o, se è un'eccezione, la solleva.
  - `grafo_finto(modello, strumenti=(), max_passi=5)` — unico punto dei test che chiama
    `costruisci_grafo` (nel Task 7 si aggiorna solo qui).
  - `errore_lm_studio() -> openai.APIConnectionError`
    (`openai.APIConnectionError(request=httpx.Request("POST", "http://localhost:1234/v1/chat/completions"))`).

`pytest.ini`: come §10 più `pythonpath = .` (senza, i test non importano `assistente` perché
`tests/` non è un pacchetto).

- [ ] **Passo 1: ambiente e dipendenze**

```powershell
cd assistente-laboratorio
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
```
Atteso: installazione senza conflitti, `No broken requirements found.`
`requirements.txt` contiene tutte le dipendenze della tabella (escluso pytest), ognuna con un
commento di una riga sul motivo.

- [ ] **Passo 2: test che falliscono** (`tests/test_grafo.py`)

```python
def test_risposta_fissa_in_un_passo():
    modello = ModelloFinto([AIMessage("Ciao!")])
    risultato = grafo_finto(modello).invoke({"messaggi": [HumanMessage("salve")], "passi": 0})
    assert [m.content for m in risultato["messaggi"]] == ["salve", "Ciao!"]
    assert risultato["passi"] == 1
    assert len(modello.chiamate) == 1

def test_prompt_di_sistema_inviato_ma_non_salvato():
    # primo messaggio ricevuto dal modello: SystemMessage(PROMPT_SISTEMA), poi "salve"
    # nessun SystemMessage in risultato["messaggi"]

def test_log_del_passaggio(caplog):
    # caplog.set_level(logging.INFO, logger="assistente.grafo")
    # "passaggio 1/5 → modello" in caplog.text
```

- [ ] **Passo 3: eseguirli e vederli fallire**

Comando: `.\.venv\Scripts\python.exe -m pytest -v` — atteso: errore di import di `assistente.grafo`.

- [ ] **Passo 4: implementare `Stato`, `PROMPT_SISTEMA`, nodo `modello` (passi 1, 2 e 4 di §6) e
  `costruisci_grafo` in `assistente/grafo.py`.** Il nodo è una chiusura dentro `costruisci_grafo`.

- [ ] **Passo 5: test verdi** — stesso comando, atteso `3 passed`.

- [ ] **Passo 6: README iniziale** — scopo (2 righe), requisiti dell'host, installazione (comandi
  del Passo 1) e test automatici (`.\.venv\Scripts\python.exe -m pytest`), tutti appena eseguiti.

- [ ] **Passo 7: commit** (due commit, staging selettivo)

```powershell
git add assistente-laboratorio/.gitignore assistente-laboratorio/requirements.txt assistente-laboratorio/requirements-dev.txt assistente-laboratorio/pytest.ini assistente-laboratorio/README.md
git commit -m "build: aggiunge dipendenze fissate, configurazione dei test e README iniziale"
git add assistente-laboratorio/assistente assistente-laboratorio/tests
git commit -m "feat(grafo): aggiunge stato e nodo modello con risposta da modello iniettato"
```
Prima del commit `git status` non deve mostrare `.venv/` né `.pytest_cache/` (CA-10).

**Verifica dell'incremento 1**
- Senza modello: `pytest` → 3 test verdi.
- Con LM Studio / Docker: nessuna prova in questo incremento.

---

## Incremento 2 — Collegamento a LM Studio e cronologia

### Task 2: Configurazione

**File:** crea `assistente/config.py`, `tests/test_config.py`, `.env.example` (contenuto esatto di §3).

**Interfacce — produce:** `Configurazione`, `ErroreConfigurazione`,
`carica_configurazione(env: Mapping[str, str]) -> Configurazione` come in §3.

Regole decise qui (oltre a §3): valori ripuliti dagli spazi; `LOG_LEVEL` accettato senza
distinzione di maiuscole e salvato in maiuscolo; `MAX_PASSI`/`LOG_LEVEL` vuoti → default.
Messaggi, in quest'ordine, uniti da uno spazio:
- `Manca LMSTUDIO_BASE_URL.` / `LMSTUDIO_BASE_URL deve iniziare con http:// o https://, ricevuto 'localhost:1234'.`
- `Manca LMSTUDIO_MODELLO.`
- `MAX_PASSI deve essere un intero ≥ 1, ricevuto 'zero'.`
- `LOG_LEVEL deve essere uno tra DEBUG, INFO, WARNING, ERROR, ricevuto 'TRACE'.`

- [ ] **Passo 1: test che falliscono**

```python
VALIDO = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODELLO": "google/gemma-4-e2b"}

def test_valori_validi_e_default():
    c = carica_configurazione(VALIDO)
    assert c == Configurazione("http://localhost:1234/v1", "google/gemma-4-e2b", 5, "INFO")

def test_valori_facoltativi():          # MAX_PASSI="3", LOG_LEVEL="debug" → 3, "DEBUG"
def test_obbligatorie_mancanti_o_vuote():  # {} e {"LMSTUDIO_MODELLO": "   ", ...} → "Manca ..."
def test_url_senza_schema():            # "localhost:1234" → messaggio esatto sopra
@pytest.mark.parametrize("valore", ["zero", "0", "-1", "2.5"])
def test_max_passi_non_valido(valore):
def test_log_level_non_valido():
def test_tutti_i_problemi_in_un_messaggio():
    with pytest.raises(ErroreConfigurazione) as e:
        carica_configurazione({"MAX_PASSI": "zero"})
    assert str(e.value) == ("Manca LMSTUDIO_BASE_URL. Manca LMSTUDIO_MODELLO. "
                            "MAX_PASSI deve essere un intero ≥ 1, ricevuto 'zero'.")
```

- [ ] **Passo 2: vederli fallire** — `pytest tests/test_config.py -v`, atteso errore di import.
- [ ] **Passo 3: implementare `assistente/config.py`.**
- [ ] **Passo 4: test verdi** — `pytest -v` (tutta la suite).
- [ ] **Passo 5: commit** — `feat(config): legge e valida la configurazione dalle variabili d'ambiente`
  (`config.py`, `test_config.py`, `.env.example`).

### Task 3: Sessione con cronologia

**File:** crea `assistente/sessione.py`, `tests/test_sessione.py`.

**Interfacce:**
- Consuma: grafo compilato (`invoke(stato) -> dict`), tramite `grafo_finto` nei test.
- Produce: `Sessione(grafo)`, proprietà `messaggi -> list[AnyMessage]` (copia), `invia(testo: str) -> str`
  come in §7. Testo della risposta: `ultimo.text`; vuoto dopo `strip()` →
  `«(Il modello non ha fornito una risposta.)»`.

- [ ] **Passo 1: test che falliscono**

```python
def test_il_secondo_turno_invia_la_cronologia():
    modello = ModelloFinto([AIMessage("Piacere, Paolo."), AIMessage("Ti chiami Paolo.")])
    s = Sessione(grafo_finto(modello))
    assert s.invia("Mi chiamo Paolo") == "Piacere, Paolo."
    assert s.invia("Come mi chiamo?") == "Ti chiami Paolo."
    contenuti = [m.content for m in modello.chiamate[1][1:]]   # senza il SystemMessage
    assert contenuti == ["Mi chiamo Paolo", "Piacere, Paolo.", "Come mi chiamo?"]

def test_passi_ripartono_da_zero():      # grafo finto che registra lo stato in ingresso: passi == 0 a ogni turno
def test_turno_fallito_non_tocca_la_cronologia():
    # primo turno ok, secondo ModelloFinto solleva errore_lm_studio():
    # pytest.raises(openai.APIConnectionError); s.messaggi identica a prima (stessi contenuti, len 2)
    # terzo turno ok → il modello riceve i 2 messaggi del primo turno + la nuova domanda
@pytest.mark.parametrize("testo", ["", "   "])
def test_risposta_vuota(testo):          # → "(Il modello non ha fornito una risposta.)"
def test_messaggi_e_una_copia():         # s.messaggi.append(...) non cambia s.messaggi
```
Per `test_passi_ripartono_da_zero` basta un oggetto con `invoke(stato)` che registra `stato["passi"]`
e restituisce `{"messaggi": stato["messaggi"] + [AIMessage("ok")], "passi": 1}`.

- [ ] **Passo 2: vederli fallire.**
- [ ] **Passo 3: implementare `Sessione`.**
- [ ] **Passo 4: suite verde.**
- [ ] **Passo 5: commit** — `feat(sessione): conserva la cronologia solo per i turni riusciti`.

### Task 4: Terminale

**File:** crea `assistente/terminale.py`, `tests/test_terminale.py`.

**Interfacce:**
- Consuma: un oggetto con `invia(testo: str) -> str` (nei test `SessioneFinta`, definita nel file di test).
- Produce: `avvia(sessione, leggi=input, scrivi=print) -> None` come in §8, con
  `dettaglio = str(errore)`.
- Il `try` copre sia `leggi` sia `sessione.invia` (Attenzione in revisione n. 4).

Nei test `leggi` è creato da `ingressi(*righe)`: restituisce le righe in ordine, poi solleva
`EOFError`; un elemento eccezione viene sollevato. `scrivi` è `uscite.append`.

- [ ] **Passo 1: test che falliscono**

```python
def test_domanda_e_risposta():           # "ciao", poi EOF → ["Assistente> risposta a ciao", "Arrivederci!"]
@pytest.mark.parametrize("comando", ["esci", "ESCI", "  Esci  "])
def test_esci(comando):                  # nessuna chiamata a invia; ultima uscita "Arrivederci!"
def test_eof():                          # ingressi() → ["Arrivederci!"]
def test_ctrl_c_durante_input():         # ingressi(KeyboardInterrupt()) → ["Arrivederci!"]
def test_ctrl_c_durante_attesa_del_modello():   # invia solleva KeyboardInterrupt → ["Arrivederci!"]
def test_input_vuoto_ignorato():         # ingressi("", "   ", "esci") → invia mai chiamato
def test_errore_lm_studio_e_si_continua():
    # 1ª invia solleva errore_lm_studio(), 2ª risponde:
    # uscite[0] == "Errore: LM Studio non ha risposto correttamente (Connection error.). Riprova."
    # uscite[1] == "Assistente> ..."; il ciclo prosegue
def test_altre_eccezioni_non_intercettate():   # invia solleva RuntimeError → pytest.raises(RuntimeError)
```
Il prompt passato a `leggi` è `"Tu> "` (asserirlo in `test_domanda_e_risposta`).

- [ ] **Passo 2: vederli fallire.**
- [ ] **Passo 3: implementare `avvia`.**
- [ ] **Passo 4: suite verde.**
- [ ] **Passo 5: commit** — `feat(terminale): aggiunge il ciclo di conversazione da terminale`.

### Task 5: Modello LM Studio, avvio e prima prova reale

**File:** crea `assistente/modello.py`, `assistente/__main__.py`, `tests/test_main.py`,
`tests/test_reale.py`; modifica `README.md`.

**Interfacce:**
- Produce `crea_modello(config: Configurazione) -> Runnable` come §4 ma **senza** `bind_tools`
  (non ci sono ancora strumenti; nel Task 8 diventa `crea_modello(config, strumenti)`).
- Produce `main(env: Mapping[str, str] = os.environ) -> int` come §8, con queste precisazioni:
  usa `env` (non `os.environ`) per la configurazione; `logging.basicConfig(stream=sys.stderr, ...)`;
  restituisce 0 dopo la fine di `avvia`; riga iniziale esatta:
  `Assistente del laboratorio — modello {modello} su {base_url}. Scrivi 'esci' per uscire.`
  Fine file: `if __name__ == "__main__": sys.exit(main())`.
- `tests/test_reale.py`: modulo marcato `pytestmark = pytest.mark.reale`; fixture
  `sessione_reale` che costruisce l'app vera da `os.environ` e chiama
  `pytest.fail("Prova reale: imposta LMSTUDIO_BASE_URL e LMSTUDIO_MODELLO (" + messaggio + ")")`
  se la configurazione non è valida.

- [ ] **Passo 1: test che falliscono** (`tests/test_main.py`)

```python
def test_configurazione_mancante_esce_con_1(capsys, monkeypatch):
    monkeypatch.setattr(assistente.__main__, "crea_modello", _non_chiamare)  # fallisce se chiamato
    assert main({"LMSTUDIO_BASE_URL": "http://localhost:1234/v1"}) == 1
    err = capsys.readouterr().err
    assert "Manca LMSTUDIO_MODELLO." in err

def test_avvio_collega_i_moduli(capsys, monkeypatch):
    # monkeypatch di assistente.__main__.avvia con una funzione che registra la sessione ricevuta
    # main(VALIDO) == 0; la sessione è una Sessione; stdout contiene la riga iniziale esatta
    # (ChatOpenAI viene creato ma non contatta il server)
```

- [ ] **Passo 2: vederli fallire.**
- [ ] **Passo 3: implementare `modello.py` e `__main__.py`.**
- [ ] **Passo 4: suite verde** — `pytest -v`: tutti verdi, `test_reale.py` non selezionato.

- [ ] **Passo 5: prova reale automatica (CA-4, prima parte)** — in `test_reale.py`:

```python
def test_ricorda_il_nome(sessione_reale):
    sessione_reale.invia("Mi chiamo Paolo")
    risposta = sessione_reale.invia("Come mi chiamo?")
    assert "Paolo" in risposta, risposta
```
```powershell
$env:LMSTUDIO_BASE_URL = "http://localhost:1234/v1"
$env:LMSTUDIO_MODELLO = "google/gemma-4-e2b"
.\.venv\Scripts\python.exe -m pytest -m reale -v
```
Atteso: `1 passed`. Se fallisce, riportare la risposta effettiva (RT-4), non correggere il test.
Verificare anche che senza variabili la prova **fallisca** con il messaggio della fixture.

- [ ] **Passo 6: prove manuali dal terminale**
  - Conversazione reale con ingresso da pipe:
    `"Mi chiamo Paolo", "Come mi chiamo?", "esci" | .\.venv\Scripts\python.exe -m assistente`
    → due risposte, `Arrivederci!`; i log su stderr non contengono righe `httpx` a livello INFO.
  - CA-7: `Remove-Item Env:LMSTUDIO_MODELLO; .\.venv\Scripts\python.exe -m assistente; $LASTEXITCODE`
    → messaggio `Manca LMSTUDIO_MODELLO.` e `1`.
  - CA-5 (LM Studio non raggiungibile): `$env:LMSTUDIO_BASE_URL = "http://localhost:1299/v1"` e
    una domanda via pipe → messaggio `Errore: LM Studio non ha risposto correttamente (...)`,
    sessione attiva. La prova completa con arresto e riavvio di LM Studio nella stessa sessione
    si fa nel Task 10.

- [ ] **Passo 7: README** — sezioni «Configurazione» (`Copy-Item .env.example .env` e variabili in
  PowerShell), «Avvio locale», «Prove reali» (`-m reale`), «Diagnosi»
  (`Invoke-RestMethod http://localhost:1234/v1/models`, LM Studio non raggiungibile, `LOG_LEVEL=DEBUG`).
  Solo i comandi eseguiti nei passi 5–6.

- [ ] **Passo 8: commit** — `feat(modello): collega LM Studio e avvia la conversazione da terminale`
  (`modello.py`, `__main__.py`, `test_main.py`, `test_reale.py`, `README.md`).

**Verifica dell'incremento 2**
- Senza modello: suite predefinita verde (config, sessione, terminale, main, grafo).
- Con LM Studio: `pytest -m reale` (CA-4 senza strumenti), conversazione via pipe, CA-7, errore
  di connessione con porta errata.

---

## Incremento 3 — Strumento orologio e instradamento

### Task 6: Strumento `ora_corrente`

**File:** crea `assistente/strumenti.py`, `tests/test_strumenti.py`; in `tests/conftest.py` aggiunge
`ORA_FISSA = datetime(2026, 10, 26, 15, 47, 12, 345678, tzinfo=timezone.utc)`.

**Interfacce — produce:** `crea_ora_corrente(adesso: Callable[[], datetime] = ...) -> BaseTool`
come §5. Validazione: `fuso in zoneinfo.available_timezones()` (insieme calcolato una volta),
poi `adesso().astimezone(ZoneInfo(fuso)).isoformat(timespec="seconds")`. Con questo controllo
non servono `try` su `ZoneInfo`.

- [ ] **Passo 1: test che falliscono**

```python
def test_tokyo():
    assert crea_ora_corrente(lambda: ORA_FISSA).invoke({"fuso": "Asia/Tokyo"}) == \
        {"fuso": "Asia/Tokyo", "data_ora": "2026-10-27T00:47:12+09:00"}

def test_roma_inverno():   # ORA_FISSA (dopo il 25/10/2026) → "2026-10-26T16:47:12+01:00"
def test_roma_estate():    # datetime(2026, 7, 1, 10, 0, tzinfo=utc) → "2026-07-01T12:00:00+02:00"

@pytest.mark.parametrize("fuso", ["Tokio", "", "../x", "asia/tokyo"])
def test_fuso_non_valido(fuso):
    assert crea_ora_corrente(lambda: ORA_FISSA).invoke({"fuso": fuso}) == {
        "errore": f"Fuso orario sconosciuto: '{fuso}'. Usa un nome IANA, es. 'Asia/Tokyo'."}

def test_nome_parametri_e_descrizione():
    s = crea_ora_corrente()
    assert s.name == "ora_corrente"
    assert s.tool_call_schema.model_json_schema()["required"] == ["fuso"]
    assert set(s.args) == {"fuso"}
    assert "Europe/Rome" in s.description and "Asia/Tokyo" in s.description
```

- [ ] **Passo 2: vederli fallire.**
- [ ] **Passo 3: implementare `crea_ora_corrente`** (descrizione esatta di §5).
- [ ] **Passo 4: suite verde.**
- [ ] **Passo 5: commit** — `feat(strumenti): aggiunge lo strumento ora_corrente con fuso IANA`.

### Task 7: Instradamento, nodo `strumenti` e nodo `limite`

**File:** modifica `assistente/grafo.py`, `tests/conftest.py` (`grafo_finto`), `tests/test_grafo.py`,
`tests/test_sessione.py`; aggiunge in `conftest.py`
`chiamata(fuso: str | None = "Asia/Tokyo", id: str = "c1", nome: str = "ora_corrente") -> AIMessage`
(un `AIMessage` vuoto con una `tool_call`; `fuso=None` → `args={}`).

**Interfacce:**
- Consuma: `crea_ora_corrente(lambda: ORA_FISSA)` (Task 6).
- Produce: `costruisci_grafo(modello: Runnable, strumenti: list[BaseTool], max_passi: int)` e
  `instrada(stato: Stato, max_passi: int) -> Literal["strumenti", "limite", "fine"]` come §6;
  il grafo compilato viene restituito con `.with_config(recursion_limit=2 * max_passi + 2)`.
- Testi dei log decisi qui (gli altri sono in §6):
  `WARNING passaggio {passi}/{max_passi} argomenti non interpretabili: {invalid_tool_calls}` e
  `WARNING limite di {max_passi} passaggi raggiunto, chiamate non eseguite: {nomi}`.

- [ ] **Passo 1: aggiornare `grafo_finto`** alla nuova firma:
  `grafo_finto(modello, strumenti=None, max_passi=5)`, dove `None` diventa
  `[crea_ora_corrente(lambda: ORA_FISSA)]`. I test dei Task 1 e 3 restano invariati e devono
  restare verdi.

- [ ] **Passo 2: test che falliscono** (`tests/test_grafo.py`)

```python
@pytest.mark.parametrize("ultimo, passi, atteso", [
    (AIMessage("ok"), 1, "fine"),
    (chiamata(), 1, "strumenti"),
    (chiamata(), 4, "strumenti"),
    (chiamata(), 5, "limite"),
    (AIMessage("", invalid_tool_calls=[{"name": "ora_corrente", "args": "{fuso", "id": "c1",
                                        "error": "json", "type": "invalid_tool_call"}]), 1, "fine"),
])
def test_instrada(ultimo, passi, atteso):
    assert instrada({"messaggi": [ultimo], "passi": passi}, 5) == atteso

def test_ciclo_modello_strumento_modello():
    modello = ModelloFinto([chiamata(), AIMessage("A Tokyo sono le 00:47.")])
    r = grafo_finto(modello).invoke(...)
    tm = r["messaggi"][2]                      # ToolMessage
    assert tm.tool_call_id == "c1" and tm.name == "ora_corrente"
    assert json.loads(tm.content) == {"fuso": "Asia/Tokyo", "data_ora": "2026-10-27T00:47:12+09:00"}
    assert modello.chiamate[1][-1] == tm and r["passi"] == 2

def test_piu_chiamate_nello_stesso_messaggio():   # Tokyo (c1) + Europe/Rome (c2): due ToolMessage in ordine
def test_strumento_sconosciuto():                 # nome "meteo" → {"errore": "Strumento sconosciuto: 'meteo'."}
def test_argomenti_non_validi():                  # chiamata(fuso=None) → errore che inizia con
                                                  # "Argomenti non validi per 'ora_corrente':" e contiene "Europe/Rome"
def test_limite():
    modello = ModelloFinto([chiamata(id=f"c{i}") for i in range(5)])
    r = grafo_finto(modello, max_passi=5).invoke(...)
    assert len(modello.chiamate) == 5
    assert r["messaggi"][-1].content == "Ho raggiunto il limite di 5 passaggi senza una risposta finale."
    # ogni tool_call di ogni AIMessage ha un ToolMessage con lo stesso tool_call_id;
    # l'ultimo ToolMessage contiene {"errore": "Non eseguito: limite di passaggi raggiunto."}

def test_limite_alto_senza_errore_di_ricorsione():   # max_passi=20, 20 chiamate → messaggio di RF-10
def test_log_delle_chiamate(caplog):
    # INFO "passaggio 1/5 chiamata ora_corrente {'fuso': 'Asia/Tokyo'}"
    # INFO "passaggio 1/5 risultato ora_corrente {'fuso': 'Asia/Tokyo', 'data_ora': '2026-10-27T00:47:12+09:00'}"
    # WARNING per il risultato con "errore"; WARNING per il limite e per invalid_tool_calls
```

E in `tests/test_sessione.py`:

```python
def test_dopo_il_limite_la_sessione_continua():   # CA-6: turno al limite, poi AIMessage("ok");
                                                  # il 2° turno risponde "ok" e il modello riceve tutta la cronologia
def test_errore_dopo_lo_strumento_non_lascia_orfani():
    # ModelloFinto([chiamata(), errore_lm_studio()]): invia solleva; s.messaggi invariata (nessun ToolMessage)
```

- [ ] **Passo 3: vederli fallire.**
- [ ] **Passo 4: implementare** `instrada`, nodi `strumenti` e `limite`, passo 3 del nodo `modello`
  (warning su `invalid_tool_calls`), archi condizionali (`"fine"` → `END`, `strumenti` → `modello`,
  `limite` → `END`) e `recursion_limit`, seguendo §6. Il dizionario `nome → strumento` si costruisce
  una volta dentro `costruisci_grafo`.
- [ ] **Passo 5: suite verde.**
- [ ] **Passo 6: commit** — `feat(grafo): aggiunge instradamento, esecuzione degli strumenti e limite dei passaggi`.

### Task 8: Strumento collegato al modello e prove reali

**File:** modifica `assistente/modello.py`, `assistente/__main__.py`, `tests/test_reale.py`,
`tests/test_main.py` (solo se il collegamento cambia ciò che asserisce), `README.md`.

**Interfacce:**
- `crea_modello(config: Configurazione, strumenti: list[BaseTool]) -> Runnable` esattamente come §4
  (con `bind_tools`).
- `main` crea `strumenti = [crea_ora_corrente()]` e li passa a `crea_modello` e a `costruisci_grafo`.
- In `test_reale.py`, helper `chiamate_strumento(messaggi) -> list[dict]` (le `tool_calls` di tutti
  gli `AIMessage`).

- [ ] **Passo 1: prove reali** (aggiunte a `test_reale.py`)

```python
def test_ora_a_tokyo_e_poi_a_roma(sessione_reale):     # CA-2 e CA-3
    risposta = sessione_reale.invia("Che ore sono a Tokyo?")
    msg = sessione_reale.messaggi
    assert {"fuso": "Asia/Tokyo"} in [c["args"] for c in chiamate_strumento(msg)], msg
    data_ora = ...   # dal ToolMessage di ora_corrente
    h, m = data_ora.hour, data_ora.minute
    assert f"{h:02d}:{m:02d}" in risposta or f"{h}:{m:02d}" in risposta, risposta
    n = len(sessione_reale.messaggi)
    sessione_reale.invia("E a Roma?")
    assert {"fuso": "Europe/Rome"} in [c["args"] for c in chiamate_strumento(sessione_reale.messaggi[n:])]

def test_nome_senza_strumento(sessione_reale):        # CA-4 completo: "Paolo" e nessuna chiamata allo strumento
```

- [ ] **Passo 2: implementare** il collegamento in `modello.py` e `__main__.py`.
- [ ] **Passo 3: suite predefinita verde** (nessun test richiede LM Studio).
- [ ] **Passo 4: `pytest -m reale -v`** con le variabili impostate. Riportare l'esito così com'è:
  se `gemma-4-e2b` non chiama lo strumento, usa un fuso non IANA o scrive l'orario in un'altra
  forma, annotare la risposta effettiva nel resoconto (RT-4) senza ammorbidire le asserzioni.
- [ ] **Passo 5: prova manuale con log**:
  `"Che ore sono a Tokyo?", "E a Roma?", "esci" | .\.venv\Scripts\python.exe -m assistente`
  → su stderr le righe `chiamata ora_corrente {'fuso': 'Asia/Tokyo'}` e `{'fuso': 'Europe/Rome'}`
  (CA-2, CA-3 dal log).
- [ ] **Passo 6: README** — sezione «Strumento orologio» (che cosa fa, come leggere i log) e in
  «Diagnosi» il caso «il modello non usa lo strumento» con l'esito osservato.
- [ ] **Passo 7: commit** — `feat(modello): collega lo strumento orologio al modello LM Studio`.

**Verifica dell'incremento 3**
- Senza modello: strumento con istante fisso, `instrada`, ciclo, errori dello strumento, limite
  (CA-6), cronologia dopo limite ed errori.
- Con LM Studio: `pytest -m reale` (CA-2, CA-3, CA-4) e conversazione via pipe con log.

---

## Incremento 4 — Docker Compose

### Task 9: Immagine e Compose

**File:** crea `Dockerfile`, `compose.yaml`, `.dockerignore` (contenuti di §9); modifica `README.md`.

- [ ] **Passo 1: scrivere i tre file** secondo §9 (utente non root creato con `useradd`,
  `WORKDIR /app`, `pip install --no-cache-dir -r requirements.txt`, poi `COPY assistente/ assistente/`).
- [ ] **Passo 2: build** — `docker compose build` (con `.env` copiato da `.env.example`). Atteso: build riuscita.
- [ ] **Passo 3: verifiche senza LM Studio**
  - contenuto dell'immagine: `docker compose run --rm -T assistente ls -A /app` → solo `assistente`
    e `requirements.txt` (niente `tests`, `docs`, `.env`);
  - utente: `docker compose run --rm -T assistente whoami` → non `root`;
  - configurazione errata: `docker compose run --rm -T -e LMSTUDIO_MODELLO= assistente; $LASTEXITCODE`
    → `Manca LMSTUDIO_MODELLO.` e `1`.
- [ ] **Passo 4: raggiungibilità di LM Studio dal container**
  `docker compose run --rm -T assistente python -c "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:1234/v1/models').read()[:200])"`
  → JSON con `google/gemma-4-e2b`. Se fallisce: chiedere all'utente di attivare in LM Studio il
  servizio sulla rete locale, ripetere e annotare l'esito per la «Diagnosi».
- [ ] **Passo 5: CA-8 con ingresso da pipe**
  `"Che ore sono a Tokyo?", "esci" | docker compose run --rm -T assistente`
  → log con `ora_corrente {'fuso': 'Asia/Tokyo'}` e risposta con l'orario. L'avvio interattivo
  `docker compose run --rm assistente` resta da provare a mano con l'utente (Task 10).
- [ ] **Passo 6: README** — sezione «Docker» (build, avvio interattivo, perché non `up`, diagnosi
  della raggiungibilità) con i comandi eseguiti.
- [ ] **Passo 7: commit** — `build(docker): aggiunge Dockerfile e Docker Compose per l'assistente`
  (`.env` non deve comparire in `git status`).

**Verifica dell'incremento 4**
- Senza modello: suite predefinita ancora verde; build, contenuto immagine, utente, configurazione errata.
- Con LM Studio e Docker: raggiungibilità da container e CA-8 via pipe.

---

## Incremento 5 — Verifica completa

### Task 10: Criteri di accettazione, documentazione e revisione

**File:** modifica `README.md`, `CLAUDE.md` (radice del repository; vedi Vincoli globali).

- [ ] **Passo 1: CA-1 e CA-5 con LM Studio fermo** — chiedere conferma all'utente prima di fermare
  il server (`lms server stop`, CLI presente in `~\.lmstudio\bin`), poi:
  - `pytest -v` → tutto verde con LM Studio fermo (CA-1);
  - sessione interattiva con l'utente: domanda con LM Studio fermo → messaggio d'errore;
    `lms server start` (e modello caricato); domanda successiva → risposta, e una domanda che
    richiede la cronologia precedente → corretta (CA-5).
- [ ] **Passo 2: CA-9 e CA-7 con tasti reali** (con l'utente): `esci`, Ctrl+Z+Invio, Ctrl+C in
  locale e `docker compose run --rm assistente` interattivo (CA-8). Nessuna traccia d'errore.
- [ ] **Passo 3: prove automatiche finali** — `pytest -v` e `pytest -m reale -v`; registrare gli esiti.
- [ ] **Passo 4: CA-10** — `git status --ignored assistente-laboratorio` mostra `.env`, `.venv/`,
  cache solo come ignorati.
- [ ] **Passo 5: README** — rilettura completa: ogni comando è stato eseguito in questo piano;
  eliminare o correggere quelli che non lo sono.
- [ ] **Passo 6: `CLAUDE.md`** — dopo aver chiesto come trattare le modifiche non committate
  dell'utente, aggiornare «Struttura, dipendenze e comandi»: struttura, `.venv`, comandi di test
  (`pytest`, `pytest -m reale`), avvio locale e Docker.
- [ ] **Passo 7: revisione** — superpowers:requesting-code-review sull'intero lavoro; applicare le
  correzioni con superpowers:receiving-code-review, ciascuna con test e commit propri.
- [ ] **Passo 8: commit** — `docs: completa README e CLAUDE.md con comandi verificati`.
- [ ] **Passo 9: resoconto** — tabella CA-1…CA-10 con: comando eseguito, esito (anche parziale o
  fallito, con l'output reale), che cosa resta da provare. Nessun push.

**Verifica dell'incremento 5**
- Senza modello: suite completa con LM Studio fermo.
- Con LM Studio e Docker: `-m reale`, CA-5, CA-8 interattivo, CA-9 con tasti reali.
