# Specifica — Assistente del laboratorio

Data: 2026-10-26
Stato: approvata
Requisiti di riferimento: [`../requisiti.md`](../requisiti.md) (RF, RNF, RT, CA)

Questa specifica descrive **come** soddisfare i requisiti. Non li ripete: li cita per codice.

## 1. Approccio

Grafo LangGraph costruito a mano (`StateGraph`) con nodi e instradamento espliciti.
La cronologia è tenuta da una piccola classe `Sessione` dell'applicazione, che a ogni turno
passa al grafo la cronologia più la nuova domanda e salva il risultato **solo se il turno
riesce** (RF-2, RF-13). Non si usa il checkpointer di LangGraph né agenti precostruiti
(RNF-2).

Alternative scartate:
- *Checkpointer `InMemorySaver`*: idiomatico, ma un turno fallito lascia il messaggio
  dell'utente nello stato e richiede logica di pulizia. Resta l'opzione naturale se in
  futuro servirà persistenza: cambierebbe solo `Sessione`.
- *`create_react_agent`*: nasconde stato, nodi e instradamento, in contrasto con RNF-2.

## 2. Struttura

```
assistente-laboratorio/
├── assistente/
│   ├── __init__.py
│   ├── __main__.py      # avvio: config → logging → modello → grafo → sessione → terminale
│   ├── config.py        # Configurazione + carica_configurazione(env)
│   ├── modello.py       # crea_modello(config, strumenti)
│   ├── strumenti.py     # crea_ora_corrente(adesso)
│   ├── grafo.py         # Stato, nodi, instrada, costruisci_grafo(...)
│   ├── sessione.py      # Sessione
│   └── terminale.py     # avvia(sessione, leggi, scrivi)
├── tests/
│   ├── conftest.py          # ModelloFinto e fixture comuni
│   ├── test_config.py
│   ├── test_strumenti.py
│   ├── test_grafo.py
│   ├── test_sessione.py
│   ├── test_terminale.py
│   ├── test_main.py         # avvio con configurazione errata → codice di uscita 1
│   └── test_reale.py        # marcato "reale", escluso di default
├── docs/superpowers/        # requisiti, specifica, piano
├── Dockerfile
├── compose.yaml
├── .dockerignore
├── .env.example
├── .gitignore
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

Dipendenze dei moduli: solo `__main__.py` importa e collega gli altri moduli
applicativi. `grafo.py`, `sessione.py` e `terminale.py` ricevono ciò che usano come
parametri (modello e strumenti, grafo, sessione), quindi i test possono passare oggetti
finti. `modello.py` dipende solo da `config.py`.

## 3. Configurazione (`config.py`)

```python
@dataclass(frozen=True)
class Configurazione:
    base_url: str        # LMSTUDIO_BASE_URL  (obbligatoria)
    modello: str         # LMSTUDIO_MODELLO   (obbligatoria)
    max_passi: int = 5   # MAX_PASSI          (intero >= 1)
    log_level: str = "INFO"  # LOG_LEVEL      (DEBUG, INFO, WARNING, ERROR)

class ErroreConfigurazione(Exception): ...

def carica_configurazione(env: Mapping[str, str]) -> Configurazione: ...
```

- `env` è un parametro (in produzione `os.environ`), così i test non toccano l'ambiente reale.
- Valori vuoti o fatti solo di spazi contano come mancanti.
- `LMSTUDIO_BASE_URL` deve iniziare con `http://` o `https://`.
- `ErroreConfigurazione` riporta **tutti** i problemi trovati in un solo messaggio
  (es. «Manca LMSTUDIO_MODELLO. MAX_PASSI deve essere un intero ≥ 1, ricevuto 'zero'.»).
- Nessun caricamento di `.env` in Python (niente `python-dotenv`): in locale le variabili si
  impostano nella shell, in Docker le legge Compose (RNF-5).

`.env.example`:
```
LMSTUDIO_BASE_URL=http://localhost:1234/v1
LMSTUDIO_MODELLO=google/gemma-4-e2b
MAX_PASSI=5
LOG_LEVEL=INFO
```

## 4. Collegamento al modello (`modello.py`)

```python
def crea_modello(config: Configurazione, strumenti: list[BaseTool]) -> Runnable:
    return ChatOpenAI(
        base_url=config.base_url,
        model=config.modello,
        api_key="lm-studio",   # segnaposto: LM Studio non richiede chiavi
        temperature=0,
        timeout=120,
        max_retries=1,
    ).bind_tools(strumenti)
```

- `temperature=0`: risposte più ripetibili e tool calling più stabile nelle prove.
- `timeout=120` s: il primo caricamento di un modello locale può essere lento.
- `max_retries=1`: con LM Studio spento l'errore arriva in pochi secondi invece che dopo
  i tentativi predefiniti.
- Il modulo non contiene logica: si verifica solo con le prove reali.

## 5. Strumento orologio (`strumenti.py`)

```python
def crea_ora_corrente(
    adesso: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> BaseTool: ...
```

Restituisce un tool LangChain di nome `ora_corrente` con un unico parametro `fuso: str`
(RF-5), la cui descrizione per il modello è:
«Restituisce data e ora correnti nel fuso orario indicato. `fuso` è un nome IANA,
per esempio "Europe/Rome" o "Asia/Tokyo".»

Comportamento:
- `adesso()` restituisce un istante con fuso (UTC); lo strumento lo converte con
  `zoneinfo.ZoneInfo(fuso)`.
- Successo (RF-6): `{"fuso": "Asia/Tokyo", "data_ora": "2026-10-27T00:47:12+09:00"}`,
  con `data_ora` troncata ai secondi.
- Errore (RF-7): fuso vuoto, sconosciuto (`ZoneInfoNotFoundError`) o malformato
  (`ValueError`, es. percorsi come `../x`) →
  `{"errore": "Fuso orario sconosciuto: 'Tokio'. Usa un nome IANA, es. 'Asia/Tokyo'."}`.
  Lo strumento non solleva eccezioni per input non validi.
- Il dizionario viene serializzato in JSON dal nodo `strumenti`.
- Il database dei fusi viene dal pacchetto `tzdata`, necessario su Windows e nelle immagini
  `slim`.

## 6. Grafo (`grafo.py`)

### Stato

```python
class Stato(TypedDict):
    messaggi: Annotated[list[AnyMessage], add_messages]  # cronologia + turno corrente
    passi: int                                           # chiamate al modello nel turno
```

### Topologia

```
START → [modello] ──instrada──┬─ nessuna tool_call ──────────────→ END
            ▲                 ├─ tool_call e passi < max_passi ──→ [strumenti] ─┐
            └─────────────────┼─────────────────────────────────────────────────┘
                              └─ tool_call e passi ≥ max_passi ──→ [limite] → END
```

```python
def costruisci_grafo(modello: Runnable, strumenti: list[BaseTool], max_passi: int): ...
def instrada(stato: Stato, max_passi: int) -> Literal["strumenti", "limite", "fine"]: ...
```

`costruisci_grafo` restituisce il grafo compilato. I nodi sono funzioni create dentro
`costruisci_grafo` (chiusure su `modello`, strumenti e `max_passi`).

### Nodi

**`modello`**
1. Calcola `passo = stato["passi"] + 1` e logga `passaggio {passo}/{max_passi} → modello`
   (INFO).
2. Invoca il modello con `[SystemMessage(PROMPT_SISTEMA)] + stato["messaggi"]`.
   Il prompt di sistema non viene salvato nello stato.
3. Se la risposta contiene `invalid_tool_calls` (argomenti non interpretabili), li logga
   come WARNING.
4. Restituisce `{"messaggi": [risposta], "passi": passo}`.

`PROMPT_SISTEMA` (costante del modulo):
«Sei l'assistente del laboratorio. Rispondi in italiano, in modo breve. Per qualsiasi
domanda sulla data o sull'ora usa lo strumento ora_corrente con un nome di fuso IANA
(per esempio Europe/Rome); non inventare l'orario.»

**`strumenti`**
Per ogni `tool_call` dell'ultimo `AIMessage`:
1. Logga `passaggio {passi}/{max_passi} chiamata {nome} {argomenti}` (INFO), dove
   `passi` è il passaggio del modello che ha richiesto lo strumento (RF-11).
2. Se lo strumento non esiste → risultato `{"errore": "Strumento sconosciuto: '{nome}'."}`.
3. Altrimenti lo invoca con gli argomenti; se l'invocazione solleva un'eccezione (es.
   argomenti mancanti o di tipo sbagliato) →
   `{"errore": "Argomenti non validi per '{nome}': {dettaglio}. Uso: {descrizione dello strumento}"}`.
   La descrizione di `ora_corrente` contiene gli esempi di nomi IANA, quindi anche un fuso
   mancante riceve l'indicazione del formato corretto (RF-7).
4. Logga `passaggio {passi}/{max_passi} risultato {nome} {risultato}` (INFO; WARNING se
   contiene `errore`).
5. Aggiunge `ToolMessage(content=json.dumps(risultato, ensure_ascii=False), tool_call_id=..., name=nome)`.

Il nodo non incrementa `passi`: il limite conta le chiamate al modello (RF-9).

**`limite`**
1. Per ogni `tool_call` pendente dell'ultimo `AIMessage` aggiunge un `ToolMessage` con
   `{"errore": "Non eseguito: limite di passaggi raggiunto."}`, così la cronologia resta
   valida per l'API (ogni chiamata ha la sua risposta).
2. Aggiunge `AIMessage("Ho raggiunto il limite di {max_passi} passaggi senza una risposta finale.")`.
3. Logga il raggiungimento del limite (WARNING).

**`instrada`**
Funzione pura sull'ultimo messaggio:
(qui «`tool_call`» comprende anche le `invalid_tool_calls`, vedi la nota sotto)
- nessuna `tool_call` → `"fine"` (→ `END`);
- `tool_call` presenti e `passi < max_passi` → `"strumenti"`;
- `tool_call` presenti e `passi ≥ max_passi` → `"limite"`.

Nota (revisione finale, 2026-10-26): le `invalid_tool_calls` (argomenti non interpretabili)
sono trattate come chiamate. Il nodo `strumenti` risponde a ciascuna con
`{"errore": "Argomenti non interpretabili per '{nome}': '{argomenti}'. Uso: {descrizione}"}` e il
modello può correggersi (RF-7). Anche il nodo `limite` risponde a quelle pendenti. Senza questa
risposta langchain-openai rimanderebbe al server una chiamata senza risposta, e la cronologia
non sarebbe più valida nei turni successivi.

Con `max_passi = 5` il modello viene chiamato al più 5 volte per turno; se alla quinta
chiede ancora uno strumento, il turno termina nel nodo `limite`.

## 7. Sessione (`sessione.py`)

```python
class Sessione:
    def __init__(self, grafo): ...
    @property
    def messaggi(self) -> list[AnyMessage]: ...   # copia, sola lettura
    def invia(self, testo: str) -> str: ...
```

`invia`:
1. Invoca il grafo con `{"messaggi": self._messaggi + [HumanMessage(testo)], "passi": 0}`.
   `passi` riparte da zero a ogni turno.
2. Se l'invocazione solleva un'eccezione, la lascia propagare **senza** modificare la
   cronologia (RF-13).
3. Altrimenti sostituisce la cronologia con `risultato["messaggi"]` e restituisce il testo
   dell'ultimo messaggio; se il testo è vuoto restituisce
   «(Il modello non ha fornito una risposta.)».

## 8. Terminale (`terminale.py`) e avvio (`__main__.py`)

```python
def avvia(sessione: Sessione, leggi=input, scrivi=print) -> None: ...
```

Ciclo:
- `leggi("Tu> ")`; spazi iniziali e finali rimossi; input vuoto → nuovo giro.
- `esci` (senza distinzione tra maiuscole e minuscole), `EOFError` (Ctrl+D / Ctrl+Z+Invio
  su Windows) o `KeyboardInterrupt` (Ctrl+C) → `scrivi("Arrivederci!")` e ritorno (RF-4).
- Altrimenti `scrivi("Assistente> " + sessione.invia(testo))`.
- `openai.APIError` (copre connessione rifiutata, timeout ed errori HTTP del server) →
  `scrivi("Errore: LM Studio non ha risposto correttamente ({dettaglio}). Riprova.")`,
  logga i dettagli a livello DEBUG e continua (RF-13).
- Altre eccezioni non vengono intercettate: sono difetti del programma e devono essere
  visibili.

`__main__.py` espone `main(env: Mapping[str, str] = os.environ) -> int` e termina con
`sys.exit(main())`, così l'avvio è testabile:
1. `carica_configurazione(os.environ)`; su `ErroreConfigurazione` stampa il messaggio su
   stderr e restituisce 1 (RF-14).
2. Configura `logging` su stderr con formato
   `%(asctime)s %(levelname)s %(name)s: %(message)s` e livello `config.log_level` (RF-12).
   I logger delle librerie (`httpx`, `openai`) restano a WARNING, salvo `LOG_LEVEL=DEBUG`.
3. Crea strumenti, modello, grafo e sessione; stampa una riga iniziale con modello e
   indirizzo e l'istruzione «scrivi 'esci' per uscire»; avvia il terminale.

Esempio di sessione a livello INFO:
```
Tu> che ore sono a Tokyo?
2026-10-26 16:52:03 INFO assistente.grafo: passaggio 1/5 → modello
2026-10-26 16:52:04 INFO assistente.grafo: passaggio 1/5 chiamata ora_corrente {'fuso': 'Asia/Tokyo'}
2026-10-26 16:52:04 INFO assistente.grafo: passaggio 1/5 risultato ora_corrente {'fuso': 'Asia/Tokyo', 'data_ora': '2026-10-27T00:52:04+09:00'}
2026-10-26 16:52:04 INFO assistente.grafo: passaggio 2/5 → modello
Assistente> A Tokyo sono le 00:52 del 27 ottobre.
```

## 9. Docker

**`Dockerfile`**
- Base `python:3.13-slim` (stessa versione minore usata in locale).
- `PYTHONUNBUFFERED=1`, `PYTHONDONTWRITEBYTECODE=1`.
- Copia e installa prima `requirements.txt` (cache dei livelli), poi il pacchetto
  `assistente/`.
- Esegue come utente non root.
- `CMD ["python", "-m", "assistente"]`.
- Test, documentazione e dipendenze di sviluppo non entrano nell'immagine.

**`compose.yaml`**
```yaml
services:
  assistente:
    build: .
    env_file: .env
    environment:
      LMSTUDIO_BASE_URL: http://host.docker.internal:1234/v1
    extra_hosts:
      - "host.docker.internal:host-gateway"
    stdin_open: true
    tty: true
```
- `environment` prevale su `.env`: lo stesso `.env` serve sia in locale sia in Docker.
- `extra_hosts` rende `host.docker.internal` disponibile anche su Linux; su Docker Desktop
  è già presente.
- L'avvio interattivo è `docker compose run --rm assistente`: `docker compose up` non
  collega correttamente l'input del terminale.

**`.dockerignore`**: `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `tests/`, `docs/`,
`.git`.

Da verificare nella prova reale: se dal container LM Studio non risponde, potrebbe servire
attivare in LM Studio l'opzione per servire anche sulla rete locale. L'esito verrà riportato
nel README, nella sezione di diagnosi.

## 10. Test

**`pytest.ini`**
```ini
[pytest]
testpaths = tests
addopts = -m "not reale"
markers =
    reale: prove con LM Studio attivo (eseguire con: pytest -m reale)
```

**Modello finto** (`tests/conftest.py`): oggetto con `invoke(messaggi) -> AIMessage` che
restituisce in ordine una lista di risposte programmate (con o senza `tool_calls`) e
registra i messaggi ricevuti. Basta per il grafo perché il grafo usa solo `invoke`.
Per simulare un errore di LM Studio, una variante solleva `openai.APIConnectionError`.

| File | Cosa verifica | Requisiti |
|------|---------------|-----------|
| `test_strumenti.py` | Istante fisso → orario atteso a Tokyo, Roma in estate (+02:00) e in inverno (+01:00); fuso sconosciuto, vuoto o malformato → `errore`; nome e parametri del tool | RF-5…7 |
| `test_grafo.py` | `instrada` su tutti i casi; risposta senza strumenti → 1 passo; ciclo modello → strumenti → modello con `ToolMessage` corretto e secondo invio al modello che lo contiene; strumento sconosciuto e argomenti errati → `ToolMessage` di errore; limite → messaggio di RF-10, ogni `tool_call` con risposta, modello chiamato esattamente `max_passi` volte; prompt di sistema inviato ma non salvato; log delle chiamate (`caplog`) | RF-8…12, CA-6 |
| `test_sessione.py` | Il secondo turno invia al modello anche i messaggi del primo; `passi` riparte da zero; turno fallito → eccezione e cronologia invariata; risposta vuota → testo segnaposto | RF-2, RF-13 |
| `test_config.py` | Valori validi e default; variabili mancanti o vuote; `MAX_PASSI` non intero o < 1; `LOG_LEVEL` non valido; messaggio con tutti i problemi | RF-14, CA-7 |
| `test_main.py` | `main()` con `LMSTUDIO_MODELLO` mancante → restituisce 1 e scrive il motivo su stderr, senza contattare LM Studio | RF-14, CA-7 |
| `test_terminale.py` | `esci`, `EOFError`, `KeyboardInterrupt` → saluto; input vuoto ignorato; `APIError` → messaggio e il ciclo continua | RF-4, RF-13, CA-9 |
| `test_reale.py` | Con LM Studio attivo e le variabili impostate: domanda su Tokyo → nella cronologia c'è una chiamata `ora_corrente` con `Asia/Tokyo`, il relativo `ToolMessage`, e la risposta contiene ore e minuti di `data_ora` (es. `00:52` o `0:52`) (CA-2); «E a Roma?» → chiamata con `Europe/Rome` (CA-3); nome ricordato senza strumento (CA-4) | RT-2, RT-4 |

`test_reale.py` fallisce con un messaggio chiaro se le variabili mancano: viene eseguito
solo su richiesta esplicita, quindi un salto silenzioso nasconderebbe il problema.

Se il controllo di ore e minuti fallisce perché il modello scrive l'orario in un'altra
forma (es. «mezzanotte e 52»), l'esito viene riportato con la risposta effettiva, non
nascosto (RT-4).

**Prove manuali** (procedura nel README): CA-5 (LM Studio fermato e riavviato durante la
sessione), CA-7 dal terminale, CA-8 (Docker), CA-9 con tasti reali, CA-10 (`git status`).

## 11. Documentazione e Git

- `README.md`: requisiti dell'host (Python 3.13, LM Studio con il modello caricato e il
  server avviato, Docker Desktop), configurazione, avvio locale e Docker, test automatici,
  prove reali, diagnosi (come leggere `GET /v1/models`, LM Studio non raggiungibile, modello
  che non usa lo strumento). Tutti i comandi in PowerShell e verificati prima di essere
  scritti.
- `.gitignore` (in `assistente-laboratorio/`): `.env`, `.venv/`, `__pycache__/`, `*.pyc`,
  `.pytest_cache/`.
- `CLAUDE.md` viene aggiornato alla fine con struttura e comandi di test stabili.
- Commit piccoli secondo le convenzioni di `CLAUDE.md`, ciascuno dopo la verifica del proprio
  incremento.

## 12. Rischi noti

- **Tool calling di `gemma-4-e2b`**: è un modello piccolo; potrebbe non chiamare lo strumento,
  usare un fuso non IANA o non riportare correttamente l'orario. Mitigazioni: prompt di
  sistema esplicito, `temperature=0`, messaggio d'errore dello strumento che suggerisce il
  formato corretto. L'esito reale viene riportato così com'è (RT-4); un eventuale cambio di
  modello si fa solo con `LMSTUDIO_MODELLO`.
- **Raggiungibilità di LM Studio dal container**: dipende da come LM Studio è in ascolto
  sull'host; si verifica con CA-8.
- **Versioni delle dipendenze**: le versioni esatte vengono scelte e verificate nel piano;
  le API di LangGraph e langchain-openai usate sono quelle di base (`StateGraph`,
  `add_messages`, `ChatOpenAI.bind_tools`, `@tool`).
