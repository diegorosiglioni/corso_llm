# Specifica — Lezione 6, Step 4: resource MCP delle preferenze dell'utente

Data: 2026-11-14
Stato: scritta in modalità autonoma (branch `auto-claude`): l'approvazione è sostituita dal piano
in [`../../../PROGRESS.md`](../../../PROGRESS.md) (regola di `CLAUDE.md`, «Modalità autonoma»).
Requisiti: [`../requisiti.md`](../requisiti.md), §12 (RF-39…RF-44, CA-46…CA-52).
Specifiche precedenti: [`2026-11-13-riassunto-design.md`](2026-11-13-riassunto-design.md) (Step 3)
e quelle che richiama; [`2026-11-09-strumenti-mcp-design.md`](2026-11-09-strumenti-mcp-design.md)
(server e client MCP).
Fonte didattica: `LLM_Lez_6.pdf`, Blocco B e Step 4; riassunto in [`../lezione6.md`](../lezione6.md).

Il server MCP locale espone, oltre ai sette strumenti, una **resource** `utente://preferenze`
(`application/json`) letta da un file `preferenze.json`: lingua delle risposte, fuso orario
predefinito e stile (sintetico o dettagliato). L'host (l'applicazione) la legge **una sola volta,
a inizio sessione, prima della prima domanda**, ne ricava un testo e lo mette **in cima** al prompt
di sistema dell'agente. La resource non è uno strumento: non passa da `tools/list`, non arriva a
`bind_tools` e il modello non la chiama. Se non è disponibile, l'host usa i valori predefiniti e lo
segnala nel log. Obiettivo della traccia: modificando il file, il comportamento della sessione
successiva cambia senza toccare il codice. Dove non dice altro, valgono le specifiche precedenti.

## 1. Decisioni

Tutte «scelta del progettista» (modalità autonoma: opzione consigliata o più standard).

| Tema | Decisione | Motivo |
|------|-----------|--------|
| Formato del file | Oggetto JSON con tre chiavi in inglese: `language` (testo libero, per esempio `"italiano"`), `timezone` (nome IANA), `style` (`"sintetico"` o `"dettagliato"`) | Chiavi JSON in inglese come da `CLAUDE.md`; i valori li scrive l'utente, quindi in italiano come nella traccia |
| Valori predefiniti | `language="italiano"`, `timezone="Europe/Rome"`, `style="sintetico"` | Coincidono con il comportamento di oggi («Rispondi in italiano, in modo breve») |
| File di esempio | `assistant/data/preferenze.json`, con i valori predefiniti; sostituibile con la variabile `PREFERENCES_FILE` | Stesso schema di `scope.txt` / `SCOPE_FILE`; nell'immagine Docker c'è già, perché `assistant/` viene copiata |
| Chi valida | Il **server** controlla solo che il file esista e sia un oggetto JSON (altrimenti errore MCP); l'**host** controlla i tre campi e sostituisce con il predefinito quelli mancanti o non validi | Il server resta un fornitore di dati; l'host deve comunque gestire «resource non disponibile», e così un solo campo sbagliato non fa perdere gli altri |
| Quando il server legge il file | A ogni `resources/read` (nessuna cache) | Una resource rappresenta lo stato attuale del dato |
| Quando l'host legge la resource | Una volta, in `_converse`, dopo la discovery degli strumenti e prima di costruire il grafo | Traccia: «`resources/read` una volta, prima della prima domanda» |
| Testo nel prompt | L'host non incolla il JSON grezzo ma un blocco di righe italiane costruito dai valori validati (§5) | Un modello piccolo segue meglio istruzioni esplicite; i valori sono già controllati |
| Chi riceve le preferenze | Solo l'agente, in cima al suo prompt di sistema; router, revisore e riassunto no | La traccia parla del prompt di sistema dell'agente; router e revisore non giudicano lingua e stile |
| `SYSTEM_PROMPT` | La prima riga «Rispondi in italiano, in modo breve.» diventa «Rispondi nella lingua e nello stile indicati nelle preferenze dell'utente.»; dalla riga di `get_current_time` si toglie l'esempio `Europe/Rome` | Altrimenti il prompt contraddirebbe le preferenze (lingua, stile, fuso) |
| Ordine nel messaggio di sistema | preferenze, riga vuota, `SYSTEM_PROMPT`, poi il riassunto in fondo (`with_summary`, invariato) | «In cima» come chiede la traccia; un solo `SystemMessage` (Gemma rifiuta il secondo) |
| Errori del client | Nuova eccezione `ResourceUnavailableError` in `mcp_client.py` | Il log e il codice distinguono la resource dagli strumenti (`ToolUnavailableError`) |
| Log del server | Successo: `INFO event=resource_read uri=utente://preferenze`; errori come `ResourceError(..., log_level=logging.INFO)` | Come le note (`event=note_added`) e come `ToolError`: niente traccia Rich nel terminale per un errore atteso; il WARNING lo scrive l'host |
| Docker | `compose.yaml` e `Dockerfile` non cambiano | Il file di esempio è nell'immagine; per un file diverso si usa `PREFERENCES_FILE` con un percorso dentro il container (documentato nel README all'ultimo punto dello step) |

## 2. Struttura

```
assistant/
├── preferences.py       # NUOVO: valori predefiniti, lettura del file (server), validazione,
│                        #        testo del prompt e caricamento con log (host)
├── data/preferenze.json # NUOVO: file di esempio con i valori predefiniti
├── config.py            # + preferences_file (PREFERENCES_FILE)
├── mcp_server.py        # + resource utente://preferenze; argomento --preferences-file
├── mcp_client.py        # + ResourceUnavailableError, McpClient.read_resource;
│                        #   server_command riceve anche il file delle preferenze
├── graph.py             # + parametro preferences di build_graph; SYSTEM_PROMPT ritoccato
└── __main__.py          # lettura della resource in _converse; riga di avvio
```

`router.py`, `reviewer.py`, `summary.py`, `session.py`, `terminal.py`, `tools.py`, i moduli degli
strumenti MCP, `compose.yaml` e `Dockerfile` non cambiano.

## 3. Configurazione (`config.py`)

- `PREFERENCES_FILE`: percorso del file delle preferenze, default
  `DEFAULT_PREFERENCES_FILE = str(Path(__file__).parent / "data" / "preferenze.json")`.
- **Non** viene letto né validato da `load_config`: un file mancante o sbagliato non impedisce
  l'avvio (RF-42), a differenza di `SCOPE_FILE`.
- `Config` riceve in fondo `preferences_file: str = DEFAULT_PREFERENCES_FILE`.
- `.env.example`: righe di commento dopo quelle di `SCOPE_FILE`:
  ```
  # File delle preferenze dell'utente (default: quello del pacchetto, assistant/data/preferenze.json):
  # PREFERENCES_FILE=assistant/data/preferenze.json
  ```

## 4. File e lettura sul server

`assistant/data/preferenze.json` (UTF-8):

```json
{
  "language": "italiano",
  "timezone": "Europe/Rome",
  "style": "sintetico"
}
```

`preferences.read_preferences_file(path) -> str`:
- legge il file in `utf-8-sig` (BOM ammesso) e lo interpreta con `json.loads`;
- file mancante o illeggibile → `ValueError("File delle preferenze non leggibile: '<path>' (<motivo>).")`;
- JSON non valido → `ValueError("File delle preferenze non valido: '<path>' (<motivo>).")`;
- valore che non è un oggetto → `ValueError("File delle preferenze non valido: '<path>' (serve un oggetto JSON).")`;
- altrimenti restituisce `json.dumps(dati, ensure_ascii=False)` (JSON normalizzato, su una riga).

### Server (`mcp_server.py`)

- `build_server(notes, catalog, preferences_file)`: nuovo parametro posizionale.
- Resource:
  ```python
  @server.resource(
      "utente://preferenze", name="preferenze", mime_type="application/json",
      description="Preferenze dell'utente: lingua delle risposte, fuso orario predefinito e stile.",
  )
  def preferences() -> str: ...
  ```
  che chiama `read_preferences_file(preferences_file)`; un `ValueError` diventa
  `ResourceError(str(error), log_level=logging.INFO)`; in caso di successo scrive
  `INFO event=resource_read uri=utente://preferenze`.
- `main`: nuovo argomento obbligatorio `--preferences-file PATH`.
- Costanti `PREFERENCES_URI = "utente://preferenze"` in `preferences.py`, usata da server e host.

Verificato il 2026-11-14 con `fastmcp` 4.1.6 (script usa e getta, fuori dal progetto): la resource
compare in `list_resources()` con nome e `mimeType`, non in `list_tools()`; `read_resource` restituisce
una lista di `TextResourceContents` con `text`; un `ResourceError` e un URI inesistente arrivano al
client come `mcp.shared.exceptions.MCPError` («Resource not found: '…'»).

## 5. Host

### Validazione (`preferences.py`)

```python
@dataclass(frozen=True)
class Preferences:
    language: str = "italiano"
    timezone: str = "Europe/Rome"
    style: str = "sintetico"

DEFAULT_PREFERENCES = Preferences()
STYLES = {"sintetico": "breve ed essenziale, in poche frasi",
          "dettagliato": "completo, con spiegazioni ed esempi quando servono"}
```

`parse_preferences(text) -> tuple[Preferences, list[FieldProblem]]`, con
`FieldProblem(field, problem, value)` (`problem` = `missing` oppure `invalid`):
- testo che non è un oggetto JSON → `ValueError` (per l'host equivale a «non disponibile»);
- `language`: stringa che, tolti gli spazi, non è vuota, non supera 40 caratteri e non contiene a
  capo;
- `timezone`: stringa in `zoneinfo.available_timezones()` (come lo strumento orologio);
- `style`: `"sintetico"` o `"dettagliato"` (confronto esatto, dopo aver tolto gli spazi);
- un campo assente → `missing`, un campo presente ma non valido → `invalid`; in entrambi i casi vale
  il predefinito di quel campo. Le chiavi sconosciute sono ignorate.

### Testo del prompt

`preferences_prompt(p) -> str`:

```
Preferenze dell'utente (resource utente://preferenze):
- lingua delle risposte: <language>;
- fuso orario predefinito: <timezone>; se l'utente chiede data o ora senza indicare un luogo o un fuso, usa get_current_time con questo fuso, senza chiederlo;
- stile delle risposte: <style> (<descrizione da STYLES>).
```

`with_preferences(prompt, preferences_text) -> str`: `preferences_text + "\n\n" + prompt`, oppure
`prompt` se `preferences_text` è vuoto.

### Caricamento con log

`load_preferences(client) -> Preferences`, chiamata da `_converse`:
1. `text = client.read_resource(PREFERENCES_URI)`; `ResourceUnavailableError` →
   `WARNING resources/read uri=utente://preferenze status=unavailable error="<motivo>" fallback=defaults <valori>`
   e restituisce `DEFAULT_PREFERENCES`.
2. `parse_preferences(text)`; `ValueError` → stessa riga `status=unavailable`, predefiniti.
3. Per ogni campo con un problema:
   `WARNING resources/read uri=utente://preferenze field=<campo> problem=missing|invalid value=<valore JSON> fallback=<predefinito>`.
4. Riga finale: `INFO resources/read uri=utente://preferenze status=ok|partial <valori>`
   (`partial` se almeno un campo ha preso il predefinito).

`<valori>` = `language=<json> timezone=<nome> style=<nome>` (la lingua con `json.dumps(...,
ensure_ascii=False)`, perché può contenere spazi). Tutte le righe cominciano con `resources/read`
(logger `assistant.preferences`): si distinguono a colpo d'occhio dalle righe degli strumenti
(`step=… variant=… call_id=…`).

### Client (`mcp_client.py`)

- `class ResourceUnavailableError(Exception)`: resource non leggibile (errore MCP, sessione chiusa,
  tempo scaduto, nessun contenuto testuale).
- `McpClient.read_resource(uri) -> str`: usa `_submit(lambda c: c.read_resource(uri))`; un
  `ToolUnavailableError` diventa `ResourceUnavailableError` con lo stesso motivo; restituisce la
  concatenazione dei `text` dei contenuti testuali; nessun testo → `ResourceUnavailableError("nessun
  contenuto testuale")`.
- `server_command(notes_db, log_level, preferences_file)`: aggiunge
  `--preferences-file <percorso>` agli argomenti.
- `create_mcp_tools` non cambia: legge solo `tools/list`, quindi la resource non può diventare uno
  strumento.

### Grafo (`graph.py`)

- `build_graph(..., preferences: str)`: nuovo parametro obbligatorio per nome, il testo di
  `preferences_prompt`.
- `llm_node` invoca il modello con
  `SystemMessage(with_summary(with_preferences(SYSTEM_PROMPT, preferences), summary))`.
- `SYSTEM_PROMPT`, prime righe:
  ```
  Sei l'assistente del laboratorio. Rispondi nella lingua e nello stile indicati nelle preferenze dell'utente.
  Usa gli strumenti invece di inventare i risultati:
  - get_current_time per data e ora, con un fuso IANA;
  ```
  il resto è invariato.

### Avvio (`__main__.py`)

- `server_command(notes_db, config.log_level, Path(config.preferences_file).resolve())`: percorso
  assoluto, perché il server parte con un'altra cartella di lavoro.
- `_converse`: dopo la discovery e il controllo dei nomi, `preferences = load_preferences(client)`;
  poi `build_graph(..., preferences=preferences_prompt(preferences))`. `create_model` riceve gli
  stessi `tools` di oggi.
- La riga di avvio diventa `scope_file=… max_reviews=… summary_max_messages=…
  summary_keep_messages=… preferences_file=<percorso>`.

### Esempio di log

```
INFO assistant.__main__: tools=[get_current_time (local), convert_units (mcp), ...]
INFO assistant.__main__: scope_file=… max_reviews=2 summary_max_messages=20 summary_keep_messages=6 preferences_file=…\preferenze.json
INFO assistant.mcp_server: event=resource_read uri=utente://preferenze
INFO assistant.preferences: resources/read uri=utente://preferenze status=ok language="italiano" timezone=America/New_York style=sintetico
...
INFO assistant.graph: step=1/5 variant=local tool=get_current_time call_id=… arguments={'timezone': 'America/New_York'}
```

Con il file mancante:

```
WARNING assistant.preferences: resources/read uri=utente://preferenze status=unavailable error="File delle preferenze non leggibile: '…' (No such file or directory)." fallback=defaults language="italiano" timezone=Europe/Rome style=sintetico
```

## 6. Dipendenze

Nessuna nuova (`fastmcp` 4.1.6 e `tzdata` già fissati).

## 7. Test

### Senza modello (`pytest`)

- `test_preferences.py` (nuovo):
  - `read_preferences_file`: file di esempio → JSON con i tre predefiniti; BOM ammesso; file
    mancante, JSON non valido, lista JSON → `ValueError` con il percorso;
  - `parse_preferences`: tutto valido; ciascun campo mancante (`missing`) e non valido (`invalid`:
    lingua vuota, troppo lunga o con a capo; fuso `Mars/Base`; stile `lungo`) → predefinito solo per
    quel campo; chiavi sconosciute ignorate; testo non JSON o non oggetto → `ValueError`;
  - `preferences_prompt`: contiene lingua, fuso, stile e la sua descrizione, `get_current_time`;
  - `with_preferences`: preferenze in cima; testo vuoto → prompt invariato;
  - `load_preferences` con `FakeMcpClient`: resource valida → `status=ok` e una lettura; un campo
    sbagliato → WARNING `field=…` e `status=partial`; resource assente → WARNING `status=unavailable
    … fallback=defaults` e `DEFAULT_PREFERENCES`.
- `test_mcp_server.py` (server reale via stdio): `utente://preferenze` compare in `resources/list`
  con nome `preferenze` e `mimeType` `application/json`, e non in `tools/list` (i nomi restano i
  sette); lettura → JSON del file passato con `--preferences-file`; file mancante → errore MCP con il
  messaggio italiano.
- `test_mcp_client.py` (server reale via stdio): `read_resource` → testo JSON del file; URI
  inesistente e file mancante → `ResourceUnavailableError`; dopo la chiusura →
  `ResourceUnavailableError`.
- `conftest.py`: `FakeMcpClient(specs, ..., resources=None)` con `read_resource(uri)` che restituisce
  il testo registrato o solleva `ResourceUnavailableError`, e annota gli URI in `resource_reads`;
  `fake_graph(..., preferences="")`.
- `test_graph.py`: con `preferences` non vuoto il primo messaggio di sistema dell'agente comincia con
  il testo delle preferenze, poi `SYSTEM_PROMPT`, poi il riassunto; router e revisore non lo
  ricevono.
- `test_main.py`: la resource è letta una sola volta anche in una sessione di più turni; i nomi degli
  strumenti dati al modello non cambiano (la resource non entra in `bind_tools`); resource assente →
  sessione avviata con i predefiniti e WARNING; la riga di avvio contiene `preferences_file=`.
- `test_config.py`: default e `PREFERENCES_FILE` personalizzato; un file inesistente non è un errore
  di configurazione.

### Prove reali con LM Studio (`pytest -m real`)

`open_session` (fixture di `test_real.py`) riceve anche il file delle preferenze, avvia il server con
`--preferences-file` e costruisce il grafo con `load_preferences`.

- **Fuso predefinito** (CA-50): file temporaneo con `timezone="America/New_York"`; «Che ore sono?» →
  nel log `get_current_time` con `timezone` = `America/New_York`, la risposta riporta l'ora di
  quello strumento e non chiede il fuso.
- **Lingua e stile** (CA-51): due sessioni consecutive sulla stessa domanda in ambito («Ciao, che
  cosa sai fare?»), la prima con le preferenze predefinite e la seconda con `language="inglese"`:
  la seconda risposta è in inglese (più parole comuni inglesi che italiane, conteggio su un elenco
  fisso nel test), la prima in italiano.
- **Esistenti** (CA-52): le 15 prove precedenti passano con le preferenze predefinite.

Una prova reale eseguita una volta dimostra il comportamento con quelle domande, non che il modello
segua sempre le preferenze. Se LM Studio non è raggiungibile, il punto si segna `[!]` (modalità
autonoma), senza simularne l'esito.

## 8. Incrementi

Coincidono con i punti dello Step 4 in `TODO.md`; ognuno verificato con `pytest` prima del commit.

1. Questa specifica e i requisiti §12.
2. `preferences.py` (lettura del file), `data/preferenze.json`, resource nel server,
   `--preferences-file`, `server_command`; test del server. Dato che `server_command` cambia firma,
   `__main__.py` passa già il percorso (con `PREFERENCES_FILE` in `config.py`), per non lasciare la
   suite rossa.
3. `ResourceUnavailableError`, `McpClient.read_resource`, `FakeMcpClient.read_resource`; test del
   client.
4. Validazione, testo del prompt, `load_preferences`, `SYSTEM_PROMPT`, parametro `preferences` di
   `build_graph`, lettura in `_converse`; test.
5. Prove reali, README (sezione preferenze e diagnosi), `CLAUDE.md` (struttura), requisiti §12 con
   gli esiti.

## 9. Rischi

- **Il modello ignora il fuso predefinito** e chiede il fuso o usa `Europe/Rome`: il testo delle
  preferenze lo dice esplicitamente e l'esempio è tolto da `SYSTEM_PROMPT`; la prova reale lo
  verifica. La descrizione dello strumento orologio non cambia.
- **Revisore con risposte non in italiano**: il suo prompt è in italiano e non giudica lo stile;
  potrebbe comunque rifiutare una risposta in inglese a una domanda in italiano. Se succede nella
  prova reale, si riporta l'esito così com'è.
- **Lingua come testo libero**: l'utente può scrivere qualsiasi lingua; il limite di 40 caratteri su
  una riga impedisce di usare il campo per istruzioni lunghe nel prompt.
- **Preferenze lette solo a inizio sessione**: una modifica del file vale dalla sessione successiva
  (è il comportamento richiesto).
- **Docker**: il file predefinito sta nell'immagine; modificarlo richiede `docker compose build`,
  oppure un file montato e `PREFERENCES_FILE`.

## 10. Fuori ambito

Prompt MCP e comandi `/prompts` e `/prompt` (Step 5), servizio HTTP e passi successivi; scrittura
delle preferenze dal modello o dall'utente in conversazione; resource template, sottoscrizioni e
notifiche di cambiamento; preferenze per router, revisore e riassunto; rilettura delle preferenze
durante la sessione.
