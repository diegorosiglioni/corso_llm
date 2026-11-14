# Specifica — Lezione 6, Step 5: prompt MCP come comandi della CLI

Data: 2026-11-14
Stato: scritta in modalità autonoma (branch `auto-claude`): l'approvazione è sostituita dal piano
in [`../../../PROGRESS.md`](../../../PROGRESS.md) (regola di `CLAUDE.md`, «Modalità autonoma»).
Requisiti: [`../requisiti.md`](../requisiti.md), §13 (RF-45…RF-51, CA-53…CA-60).
Specifiche precedenti: [`2026-11-14-preferenze-design.md`](2026-11-14-preferenze-design.md) (Step 4)
e quelle che richiama; [`2026-11-09-strumenti-mcp-design.md`](2026-11-09-strumenti-mcp-design.md)
(server e client MCP).
Fonte didattica: `LLM_Lez_6.pdf`, Blocco B e Step 5; riassunto in [`../lezione6.md`](../lezione6.md).

Il server MCP locale espone, oltre ai sette strumenti e alla resource delle preferenze, due
**prompt**: `spiega(argomento, livello="base")` e `riassumi_conversazione(stile)`. Un prompt lo
attiva **l'utente**, non il modello né l'host: la CLI offre il comando `/prompts`, che mostra nome,
descrizione e argomenti di ogni prompt (`prompts/list`), e il comando `/prompt nome chiave=valore`,
che controlla gli argomenti rispetto a `prompts/list`, chiede i messaggi al server (`prompts/get`),
li aggiunge alla cronologia e li manda al grafo come una domanda qualsiasi: riassunto, router,
agente con gli strumenti e revisore. Un argomento obbligatorio mancante o un argomento sconosciuto
blocca la richiesta senza chiamare il server né il modello. MCP non definisce comandi: la loro
sintassi è una scelta di questa CLI. Dove non dice altro, valgono le specifiche precedenti.

## 1. Decisioni

Tutte «scelta del progettista» (modalità autonoma: opzione consigliata o più standard).

| Tema | Decisione | Motivo |
|------|-----------|--------|
| Nomi di prompt e argomenti | `spiega(argomento, livello)` e `riassumi_conversazione(stile)`, in italiano come nella traccia | Li scrive l'utente nel comando, come i valori delle preferenze; gli identificatori Python restano in inglese |
| Descrizioni degli argomenti | `Field(description=…)` come valore predefinito dei parametri, con annotazione `str` | Verificato con `fastmcp` 4.1.6: con `Annotated[str, Field(...)]` la libreria aggiunge alla descrizione una nota in inglese sullo schema JSON; con `str` e `Field` come default no, e `required` resta corretto |
| Valori ammessi | `livello` ∈ `base`, `intermedio`, `avanzato` (predefinito `base`); `stile` ∈ `sintetico`, `dettagliato` (obbligatorio, come nella traccia); `argomento` non vuoto, al massimo 200 caratteri, su una riga | `prompts/list` non sa esprimere un elenco di valori: lo dice la descrizione e il **server** lo controlla; gli stili sono gli stessi delle preferenze |
| Chi controlla che cosa | L'**host** controlla, rispetto a `prompts/list`, il nome del prompt, gli argomenti obbligatori e quelli sconosciuti (traccia, punto 4); il **server** controlla i valori | Verificato: il server ignora in silenzio gli argomenti sconosciuti, quindi il controllo nell'host serve davvero; i valori ammessi li conosce solo il server |
| Messaggi del prompt | Ogni prompt restituisce **un** messaggio `user` di solo testo | Un messaggio utente apre un turno come una domanda scritta a mano: riassunto, router e revisore lo trattano già così |
| Messaggi accettati dall'host | Ruoli `user` → `HumanMessage` e `assistant` → `AIMessage`, solo testo; elenco non vuoto e ultimo messaggio `user`; altrimenti errore senza chiamare il modello | L'host resta corretto anche con prompt di altri server, senza gestire contenuti che il grafo non saprebbe usare |
| Quando si chiama `prompts/list` | A ogni `/prompts` e a ogni `/prompt` (nessuna cache) | Tabella della traccia: i prompt li attiva l'utente, quindi nei log compaiono solo quando l'utente scrive un comando; l'elenco è sempre quello attuale del server |
| Sintassi del comando | `/prompt nome chiave=valore …`; i valori con spazi tra virgolette doppie; l'apostrofo è un carattere normale; nessun carattere di escape | Con `shlex` standard `argomento=l'IA` darebbe «virgolette non chiuse»; in italiano l'apostrofo è frequente. `shlex.shlex(posix=True)` con `quotes='"'` e `escape=''` |
| Parola del comando | `/prompts` e `/prompt` senza distinzione tra maiuscole e minuscole (come `esci`); nomi di prompt e argomenti esatti | Coerente con `esci`; i nomi sono identificatori del server |
| Altri comandi con `/` | Testo che comincia con `/` e non è un comando noto → «Comando sconosciuto», nessuna chiamata al modello | Un errore di battitura (`/promt`) non deve diventare una domanda al modello |
| Ambito del router | `scope.txt` si estende con le spiegazioni di concetti di informatica, programmazione e intelligenza artificiale e con i riassunti della conversazione | La traccia vuole il prompt «router compreso»: con l'ambito attuale «spiega Model Context Protocol» sarebbe fuori ambito. Aggirare il router per i prompt contraddirebbe la traccia |
| Messaggi mostrati | Il terminale mostra solo la risposta («Assistente> …»); il testo del prompt sta nei log | Il comportamento visibile resta quello di una domanda normale; i log bastano come evidenza |
| Errori del client | Nuova eccezione `PromptUnavailableError` in `mcp_client.py` | Come `ResourceUnavailableError`: prompt, resource e strumenti restano distinti nel codice e nei log |
| Moduli | Testi dei due prompt in `assistant/prompts.py` (logica pura, usata dal server, come `units.py`); comandi della CLI in `assistant/commands.py` (host) | Il server non importa codice dell'host e `terminal.py` resta piccolo |
| Docker | `compose.yaml` e `Dockerfile` non cambiano | I prompt sono codice del server, già nell'immagine |

## 2. Struttura

```
assistant/
├── prompts.py       # NUOVO: testi e valori ammessi dei prompt spiega e riassumi_conversazione
├── commands.py      # NUOVO: comandi /prompts e /prompt (analisi, controllo, log, messaggi)
├── data/scope.txt   # + spiegazioni di concetti e riassunti della conversazione
├── mcp_server.py    # + due prompt
├── mcp_client.py    # + PromptArgument, PromptSpec, PromptMessage, PromptUnavailableError,
│                    #   McpClient.list_prompts e get_prompt
├── session.py       # + Session.send_messages
├── terminal.py      # riconosce i comandi che cominciano con /
└── __main__.py      # passa i comandi al terminale; messaggio di benvenuto
```

`graph.py`, `router.py`, `reviewer.py`, `summary.py`, `preferences.py`, `config.py`, i moduli degli
strumenti, `compose.yaml` e `Dockerfile` non cambiano. Nessuna variabile d'ambiente nuova.

## 3. Prompt sul server

### Testi (`assistant/prompts.py`)

```python
LEVELS = {
    "base": "con parole semplici, senza dare per scontate conoscenze tecniche, e con un esempio concreto",
    "intermedio": "per chi conosce già le basi, con i termini tecnici essenziali",
    "avanzato": "in modo tecnico e preciso, con i dettagli di funzionamento e i limiti",
}
SUMMARY_STYLES = {
    "sintetico": "in pochi punti essenziali",
    "dettagliato": "turno per turno, con le domande, le risposte e i risultati ottenuti",
}
MAX_TOPIC_LENGTH = 200
```

- `explain_prompt(topic: str, level: str) -> str`: toglie gli spazi a `topic` e `level`;
  `topic` vuoto, più lungo di `MAX_TOPIC_LENGTH` o con un a capo → `ValueError` («L'argomento da
  spiegare è vuoto.», «L'argomento da spiegare supera 200 caratteri.», «L'argomento da spiegare deve
  stare su una riga.»); `level` non in `LEVELS` → `ValueError("Livello non valido: '<valore>'.
  Valori ammessi: base, intermedio, avanzato.")`. Testo:
  `Spiegami {topic} a livello {level}: {LEVELS[level]}.`
- `summary_prompt(style: str) -> str`: `style` (tolti gli spazi) non in `SUMMARY_STYLES` →
  `ValueError("Stile non valido: '<valore>'. Valori ammessi: sintetico, dettagliato.")`. Testo:
  `Riassumi la nostra conversazione fino a questo momento, {SUMMARY_STYLES[style]}. Usa solo quanto
  detto in questa conversazione, compreso l'eventuale riassunto dei turni precedenti, senza
  chiamare strumenti.`
- Costanti delle descrizioni, in italiano:
  - `EXPLAIN_DESCRIPTION = "Spiega un argomento al livello scelto."`;
  - `TOPIC_DESCRIPTION = "Argomento da spiegare (per esempio Model Context Protocol)."`;
  - `LEVEL_DESCRIPTION = "Livello della spiegazione: base, intermedio o avanzato (predefinito: base)."`;
  - `SUMMARY_DESCRIPTION = "Riassume i turni della conversazione corrente."`;
  - `STYLE_DESCRIPTION = "Stile del riassunto: sintetico o dettagliato."`.

### Server (`mcp_server.py`)

```python
@server.prompt(name="spiega", description=EXPLAIN_DESCRIPTION)
def explain(
    argomento: str = Field(description=TOPIC_DESCRIPTION),
    livello: str = Field("base", description=LEVEL_DESCRIPTION),
) -> str: ...

@server.prompt(name="riassumi_conversazione", description=SUMMARY_DESCRIPTION)
def summarize(stile: str = Field(description=STYLE_DESCRIPTION)) -> str: ...
```

I nomi dei parametri sono in italiano perché sono i nomi degli argomenti pubblicati (come i nomi dei
prompt). Ogni funzione chiama la logica pura; un `ValueError` diventa
`PromptError(str(error), log_level=logging.INFO)` (come `ToolError` e `ResourceError`); in caso di
successo scrive `INFO event=prompt_get name=<nome>`. Il valore restituito (stringa) diventa per
`fastmcp` un solo messaggio `user` con `TextContent`.

Verificato il 2026-11-14 con `fastmcp` 4.1.6 (script usa e getta, fuori dal progetto):
`list_prompts()` restituisce nome, descrizione e argomenti (`name`, `description`, `required`);
`livello` con default risulta `required=False`; `get_prompt` restituisce `GetPromptResult` con
`messages` (`role`, `content.text`); un `PromptError`, un argomento obbligatorio mancante («Missing
required arguments») e un prompt inesistente («Unknown prompt») arrivano al client come
`mcp.shared.exceptions.MCPError`; **un argomento sconosciuto è ignorato senza errore**; i prompt non
compaiono in `list_tools()`.

## 4. Client (`mcp_client.py`)

```python
@dataclass(frozen=True)
class PromptArgument:
    name: str
    description: str
    required: bool

@dataclass(frozen=True)
class PromptSpec:            # un prompt come pubblicato da prompts/list
    name: str
    description: str
    arguments: tuple[PromptArgument, ...]

@dataclass(frozen=True)
class PromptMessage:         # un messaggio restituito da prompts/get
    role: str                # "user" o "assistant"
    text: str

class PromptUnavailableError(Exception): ...
```

- `McpClient.list_prompts() -> list[PromptSpec]`: `_submit(lambda c: c.list_prompts())`; descrizioni
  assenti → `""`, argomenti assenti → `()`, `required` assente → `False`.
- `McpClient.get_prompt(name, arguments: dict[str, str]) -> list[PromptMessage]`:
  `_submit(lambda c: c.get_prompt(name, arguments))`; un contenuto che non è `TextContent` →
  `PromptUnavailableError("contenuto non testuale nel messaggio <n>")`.
- In entrambi un `ToolUnavailableError` di `_submit` (errore MCP, sessione chiusa, tempo scaduto)
  diventa `PromptUnavailableError` con lo stesso motivo. `PromptUnavailableError` non deriva da
  `ToolUnavailableError` né da `ResourceUnavailableError`.
- `create_mcp_tools` non cambia: legge solo `tools/list`, quindi un prompt non può diventare uno
  strumento.

`tests/conftest.py`: `FakeMcpClient(specs, fail_on_enter=False, resources=None, prompts=None)`, dove
`prompts` associa il nome a una coppia (`PromptSpec`, funzione `arguments → list[PromptMessage]`);
`list_prompts` e `get_prompt` registrano le chiamate (`prompt_lists`, `prompt_gets`); un nome
sconosciuto o una funzione che solleva `ValueError` → `PromptUnavailableError`.

## 5. Comandi della CLI (`assistant/commands.py`)

### Sintassi

| Comando | Effetto |
|---------|---------|
| `/prompts` | elenco dei prompt (`prompts/list`) |
| `/prompt nome chiave=valore …` | controllo, `prompts/get`, messaggi al grafo |
| altro testo che comincia con `/` | «Comando sconosciuto», nessuna chiamata |

Analisi di `/prompt` (prima di qualsiasi chiamata):
- parole separate da spazi; un valore tra virgolette doppie può contenere spazi e `=`; l'apostrofo è
  un carattere normale; nessun carattere di escape;
- prima parola dopo `/prompt` = nome del prompt; le altre = `chiave=valore`, divise al primo `=`.

Errori di sintassi (il testo dopo «Errore nel comando: »):

| Caso | Motivo |
|------|--------|
| virgolette non chiuse | `virgolette non chiuse` |
| nessun nome | `manca il nome del prompt` |
| parola senza `=` o chiave vuota | `argomento non nella forma chiave=valore: '<parola>'` |
| chiave ripetuta | `argomento ripetuto: '<chiave>'` |
| valore vuoto (`chiave=` o `chiave=""`) | `argomento senza valore: '<chiave>'` |
| `/prompts` con altre parole | `il comando /prompts non ha argomenti` |

### Controllo rispetto a `prompts/list`

Dopo l'analisi, `client.list_prompts()`; poi, nell'ordine:
- nome non pubblicato → `prompt sconosciuto: '<nome>' (disponibili: <nomi>)`;
- argomenti non dichiarati → `argomenti sconosciuti per '<nome>': '<a>', '<b>' (attesi: <nomi
  degli argomenti>)`;
- argomenti obbligatori assenti → `argomenti obbligatori mancanti per '<nome>': '<a>'`.

In tutti questi casi il terminale scrive `Errore nel comando: <motivo>. Scrivi /prompts per
l'elenco dei prompt.`, e né `prompts/get` né il modello vengono chiamati.

### Richiesta e messaggi

- `client.get_prompt(nome, argomenti)`; i messaggi diventano `HumanMessage` (`user`) e `AIMessage`
  (`assistant`). Elenco vuoto, un ruolo diverso o ultimo messaggio non `user` →
  `Errore: il prompt '<nome>' non è utilizzabile (<motivo>).`, nessuna chiamata al modello.
- `PromptUnavailableError` da `list_prompts` → `Errore: prompt non disponibili (<motivo>).`; da
  `get_prompt` (per esempio un valore rifiutato dal server) → `Errore: il prompt '<nome>' non è
  disponibile (<motivo>).`. In entrambi i casi nessuna chiamata al modello.
- Altrimenti i messaggi passano a `Session.send_messages(messages)`.

Interfaccia proposta (i dettagli restano all'implementazione):

```python
@dataclass(frozen=True)
class CommandResult:
    output: str | None = None                  # testo da mostrare (elenco o errore)
    messages: list[BaseMessage] | None = None  # messaggi da mandare al grafo

class PromptCommands:
    def __init__(self, client): ...
    def handle(self, text: str) -> CommandResult: ...   # text comincia con "/"
```

### Elenco di `/prompts`

```
Prompt disponibili:
- spiega: Spiega un argomento al livello scelto.
    argomento (obbligatorio): Argomento da spiegare (per esempio Model Context Protocol).
    livello (facoltativo): Livello della spiegazione: base, intermedio o avanzato (predefinito: base).
- riassumi_conversazione: Riassume i turni della conversazione corrente.
    stile (obbligatorio): Stile del riassunto: sintetico o dettagliato.
Uso: /prompt nome chiave=valore (valori con spazi tra virgolette doppie).
```

Un prompt senza argomenti mostra `    nessun argomento`; un server senza prompt → `Il server MCP non
offre prompt.`.

### Log (logger `assistant.commands`)

```
INFO prompts/list count=2 names=spiega,riassumi_conversazione
INFO prompts/get name=spiega arguments={"argomento": "Model Context Protocol", "livello": "base"} status=ok messages=1
INFO prompts/get name=spiega message=1/1 role=user text="Spiegami Model Context Protocol a livello base: …"
INFO prompt_command status=rejected reason="argomenti obbligatori mancanti per 'spiega': 'argomento'"
WARNING prompts/list status=unavailable error="sessione MCP chiusa"
WARNING prompts/get name=spiega arguments={"argomento": "MCP", "livello": "esperto"} status=unavailable error="Livello non valido: …"
```

Argomenti e testi in JSON (`json.dumps(..., ensure_ascii=False)`), su una riga. Le righe cominciano
con `prompts/list`, `prompts/get` o `prompt_command`: si distinguono da quelle degli strumenti e
della resource. Il server scrive `event=prompt_get name=<nome>`. Dopo `prompts/get` seguono le righe
consuete del grafo (`node=summary`, `node=router`, `step=… node=llm`, `node=reviewer`).

## 6. Sessione e terminale

- `Session.send_messages(messages: list[BaseMessage]) -> str`: come `send`, ma aggiunge alla
  cronologia tutti i messaggi ricevuti; cronologia e riassunto cambiano solo se il turno riesce.
  `send(text)` diventa `send_messages([HumanMessage(text)])`.
- `terminal.run(session, read=input, write=print, commands=None)`: un testo che comincia con `/` va a
  `commands.handle`; se il risultato ha `output` lo scrive; se ha `messages` scrive
  `"Assistente> " + session.send_messages(messages)`. Gli errori di LM Studio (`openai.APIError`)
  sono gestiti come per le domande normali. Con `commands=None` un comando dà `Comandi non
  disponibili.` (serve solo ai test che non li usano).
- `__main__._converse`: `run(session, commands=PromptCommands(client))`; il benvenuto diventa
  `… Scrivi /prompts per i prompt disponibili, 'esci' per uscire.`.

## 7. Ambito del router (`assistant/data/scope.txt`)

Nuova riga dopo quella delle note:

```
- spiegazioni di concetti di informatica, programmazione e intelligenza artificiale (per esempio modelli linguistici, agenti, Model Context Protocol);
```

e l'ultima riga dell'elenco diventa:

```
- l'utente che si presenta o dice qualcosa di sé, le domande su quanto detto in questa conversazione e i riassunti della conversazione.
```

Effetto voluto: anche una domanda scritta a mano su questi concetti è in ambito. Le domande
chiaramente fuori ambito (per esempio «Chi ha vinto i Mondiali del 2006?») restano fuori.

## 8. Dipendenze

Nessuna nuova (`fastmcp` 4.1.6 e `pydantic` già fissati; `shlex` è della libreria standard).

## 9. Test

### Senza modello (`pytest`)

- `test_prompts.py` (nuovo): testi con ciascun livello e stile; `livello`, `stile` e `argomento` non
  validi → `ValueError` con il messaggio italiano; spazi tolti.
- `test_mcp_server.py`: `prompts/list` con i due prompt, descrizioni, argomenti e `required`
  (`livello` facoltativo); i prompt non sono in `tools/list` (restano sette strumenti);
  `prompts/get` → un messaggio `user` col testo atteso, default `base`; valore non valido, argomento
  obbligatorio mancante e prompt inesistente → errore MCP; log `event=prompt_get`; una prova via
  stdio con `server_command`.
- `test_mcp_client.py` (server reale via stdio): `list_prompts` → `PromptSpec` con argomenti;
  `get_prompt` → `PromptMessage`; valore rifiutato, prompt inesistente, sessione chiusa →
  `PromptUnavailableError`; contenuto non testuale con un `_submit` sostituito; `FakeMcpClient`.
- `test_commands.py` (nuovo, con `FakeMcpClient`): analisi (virgolette doppie, apostrofo, `=` nel
  valore, maiuscole del comando, ogni errore di sintassi senza chiamate al client); elenco di
  `/prompts` (con e senza argomenti, nessun prompt, `prompts/list` non disponibile); `/prompt` con
  prompt sconosciuto, argomento sconosciuto, obbligatorio mancante → nessun `prompts/get`;
  messaggi convertiti, ruoli non ammessi e ultimo messaggio non `user` → errore; righe di log esatte.
- `test_session.py`: `send_messages` aggiunge tutti i messaggi; turno fallito → cronologia invariata.
- `test_terminal.py`: `/prompts` e `/prompt` passano dai comandi; comando bloccato → modello finto
  mai chiamato; comando sconosciuto; `commands=None`.
- `test_main.py` (client e modello finti): `/prompt spiega argomento="Model Context Protocol"
  livello=base` → il messaggio del prompt è nella cronologia e passa da riassunto, router, agente e
  revisore (righe di log del grafo); `prompts/list` e `prompts/get` compaiono solo dopo il comando.
- `test_config.py`: l'ambito predefinito (`scope.txt`) contiene le spiegazioni di concetti e i
  riassunti della conversazione.

### Prove reali con LM Studio (`pytest -m real`)

`open_session` restituisce anche i comandi (`PromptCommands` sul client reale).

- **Spiegazione** (CA-58): `/prompt spiega argomento="Model Context Protocol" livello=base` → nel log
  `prompts/get name=spiega … status=ok`, router `category=conversation`, `node=reviewer`; risposta non
  vuota, non un rifiuto, che nomina il protocollo («protocol» o «MCP», senza distinzione di
  maiuscole).
- **Riassunto** (CA-59): «Mi chiamo Paolo», «Quanto fa 17 * 23?», poi `/prompt
  riassumi_conversazione stile=sintetico` → router `conversation`, risposta con «Paolo» e «391».
- **Esistenti** (CA-60): le prove reali precedenti passano con l'ambito esteso (in particolare il
  rifiuto fuori ambito di CA-27).

Una prova reale eseguita una volta dimostra il comportamento con quelle domande, non che il modello
risponda sempre così. Se LM Studio non è raggiungibile, il punto si segna `[!]` (modalità autonoma),
senza simularne l'esito.

## 10. Incrementi

Coincidono con i punti dello Step 5 in `TODO.md`; ognuno verificato con `pytest` prima del commit.

1. Questa specifica e i requisiti §13.
2. `prompts.py`, i due prompt in `mcp_server.py`; test del server e della logica pura.
3. `PromptArgument`, `PromptSpec`, `PromptMessage`, `PromptUnavailableError`, `list_prompts`,
   `get_prompt`; `FakeMcpClient` con i prompt; test del client.
4. `commands.py` con `/prompts` e il comando sconosciuto, `terminal.run(..., commands=)`,
   `__main__.py` (comandi e benvenuto); test.
5. `/prompt`: analisi, controllo, `prompts/get`, conversione, log, `Session.send_messages`,
   `scope.txt`; test con client e modello finti.
6. Prove reali, README (sezione prompt e diagnosi), `CLAUDE.md` (struttura e comandi), requisiti
   §13 con gli esiti.

## 11. Rischi

- **Ambito più largo**: con la riga sulle spiegazioni il router lascia passare anche domande scritte
  a mano su concetti di informatica e IA. È la conseguenza voluta di «router compreso»; la prova
  reale CA-27 controlla che le domande chiaramente fuori ambito restino rifiutate.
- **Il revisore e il riassunto**: il revisore vede la domanda del prompt e la risposta, più il
  riassunto dello Step 3, ma non i turni recenti; `REVIEWER_PROMPT` gli dice già di non giudicare i
  dati della conversazione precedente. Se rifiuta un riassunto corretto, il limite `MAX_REVIEWS`
  chiude comunque il turno; la prova reale riporta l'esito così com'è.
- **Stile delle preferenze e livello del prompt**: con lo stile `sintetico` delle preferenze una
  spiegazione `avanzato` può restare breve; le preferenze valgono per tutta la sessione, il prompt
  per una richiesta.
- **Modello piccolo e formulazione**: lo Step 4 ha mostrato che una frase nel prompt di sistema può
  cambiare l'uso degli strumenti; qui il testo del prompt è un messaggio utente e il prompt di
  sistema non cambia, ma la suite reale completa va rieseguita (CA-60).
- **Prompt con più messaggi** (di altri server): il nodo riassunto taglia all'inizio di un messaggio
  utente, quindi potrebbe separare i messaggi di uno stesso prompt. I due prompt di questo server
  hanno un solo messaggio.

## 12. Fuori ambito

Servizio HTTP e passi successivi (la CLI come client dell'API arriva allo Step 6); completamento
automatico dei comandi o degli argomenti (`completion/complete`); notifiche di cambiamento dei
prompt; prompt con argomenti non testuali o messaggi con immagini e resource incorporate; prompt
suggeriti o scelti dal modello; comando di aiuto generale; altri prompt oltre ai due della traccia.
