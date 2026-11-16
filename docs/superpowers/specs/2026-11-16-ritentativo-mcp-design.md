# I-1 · Il ritentativo MCP non ripete le chiamate agli strumenti

Data: 2026-11-16. Punto I-1 di `REVIEW.md`. Modifica piccola: specifica breve.

## 1. Problema e scopo

Dopo una connessione chiusa, `McpClient._submit` (`assistant/mcp_client.py:266-285`) riavvia il
server e ripete la richiesta una volta, qualunque sia. Se il server muore dopo aver scritto su
SQLite e prima di rispondere, `add_note` salva la nota due volte e `delete_note` risponde «Nessuna
nota con id N» per una nota appena eliminata. Il caso è raro, ma l'esito è un dato sbagliato senza
traccia.

Scopo: il programma non ripete mai da solo una chiamata a uno strumento, e il modello non viene
invitato a ripeterla alla cieca.

Questa specifica sostituisce il paragrafo «Rischio accettato» della specifica di R-B3
(`2026-11-16-robustezza-servizio-design.md`, §3), che accettava la doppia scrittura.

## 2. Che cosa cambia

- **`call_tool`**: connessione chiusa → il client riavvia il server come oggi, **non ripete** la
  chiamata e solleva `ToolOutcomeUnknownError`. Vale anche se il riavvio fallisce: l'esito della
  chiamata resta incerto.
- **`tools/list`, `prompts/list`, `prompts/get`, `resources/read`**: invariati, una ripetizione
  dopo il riavvio. Non scrivono niente.
- **`ToolOutcomeUnknownError`**: nuova eccezione in `assistant/tools.py`, sottoclasse di
  `ToolUnavailableError`. Chi oggi intercetta `ToolUnavailableError` continua a funzionare.
- **Testo per il modello** (`run_tool` in `assistant/graph.py`), solo per questa eccezione:
  «Connessione con lo strumento caduta durante la chiamata ({motivo}): l'esito è incerto. Se la
  chiamata modificava dati, controlla lo stato (per esempio con list_notes) prima di ripeterla.»
  Il motivo è «Connection closed» oppure, se il riavvio è fallito, «server MCP non riavviato: …»
  (per questo il testo non afferma che il server è stato riavviato). L'esito nel log resta
  `transport_error`. Il testo attuale («Riprova o riavvia il
  servizio dell'agente») resta per gli altri errori di trasporto: per una scrittura, «Riprova»
  farebbe ripetere al modello ciò che il client non ripete più.
- **Tempo scaduto**: invariato (nessuna ripetizione, riavvio prima della richiesta successiva).
- **Log**: invariati (`mcp_restart`, `mcp_restarted`, `mcp_restart_failed`).

## 3. Approcci considerati

1. **Nessuna ripetizione per `call_tool`** — scelto. Poche righe, nessuna dipendenza da API non
   verificate, elimina il difetto per qualsiasi strumento presente e futuro.
2. Ripetere solo gli strumenti di sola lettura, riconosciuti dall'annotazione MCP `readOnlyHint`.
   Tiene invisibile la morte a riposo del server per cinque strumenti su sette, ma chiede
   annotazioni sul server, la loro lettura nel client e una regola per quando mancano. Scartato:
   più codice per un vantaggio piccolo.
3. Chiave di idempotenza sulle scritture. Scartato: cambia schema delle note e argomenti degli
   strumenti per un caso raro.

## 4. Costo accettato

Il client non distingue un server morto a riposo da uno morto durante la chiamata. Dopo una morte
a riposo, la prima chiamata a uno strumento (anche `calculate`) fallisce una volta con il testo
sopra e il modello decide se ripeterla; oggi quel caso non si vede. In Compose il controllo di
salute chiama `/status` ogni 30 s, che usa `tools/list` e quindi riavvia il server da solo: la
finestra è al massimo quella.

## 5. Fuori dallo scopo

- Le finestre di concorrenza di M-10.
- Cambiamenti al server MCP e agli strumenti.
- Il caso «sessione non presente» (`_client is None`), in cui la richiesta non parte: resta
  trattato come connessione chiusa.

## 6. Test (senza modello)

In `tests/test_mcp_client.py`, con il server di prova (`mcp_test_server.py`):
- `call_tool` con il server ucciso → `ToolOutcomeUnknownError`, una sola riga `mcp_restart`, e la
  chiamata successiva risponde dal processo nuovo. Sostituisce
  `test_call_tool_is_repeated_on_the_new_server`.
- La chiamata non viene ripetuta: `Client.call_tool` sostituito con una funzione che conta le
  chiamate e solleva «connessione chiusa» → contatore a 1.
- Riavvio fallito durante `call_tool` → `ToolOutcomeUnknownError`.
- `tools/list`, `prompts/list` e `resources/read` restano ripetuti (i test esistenti restano verdi).
- `ToolOutcomeUnknownError` è sottoclasse di `ToolUnavailableError`.

In `tests/test_graph.py`: uno strumento che solleva `ToolOutcomeUnknownError` → il messaggio per il
modello è quello del §2, senza «Riprova», con esito `transport_error`; `ToolUnavailableError`
semplice → testo attuale invariato.

Restano da provare a mano o con le prove `real`: il comportamento del modello davanti al nuovo
testo (se controlla con `list_notes` prima di ripetere).

## 7. Documentazione

README (sezione sul riavvio del server MCP e diagnosi), nota nella specifica di R-B3 §3 che rimanda
a questa, `REVIEW.md` (casella I-1), `PROGRESS.md`, `TODO.md`.
