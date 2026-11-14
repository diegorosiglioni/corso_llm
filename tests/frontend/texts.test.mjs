// Messages of the page (specification of step 8, §5), date format and the other pure functions
// of the page (CA-83).
import assert from "node:assert/strict";
import { test } from "node:test";

import { BackendError } from "../../frontend/static/api.js";
import {
  EMPTY_DRAFT, TEXTS, applyEvent, chatSubtitle, draftToolLine, draftVisible, errorMessage,
  formatDate, questionSaved, reviewNotice, toolDetail, toolsSummary, visibleMessages,
} from "../../frontend/static/texts.js";

const URL = "http://127.0.0.1:8001";
const message = (status, code, detail = null) =>
  errorMessage(new BackendError(status, code, detail), URL);

test("back-end not reachable", () => {
  assert.equal(
    message(0, "network"),
    "Il back-end non risponde (http://127.0.0.1:8001). Controlla che sia avviato e riprova.",
  );
});

test("time over in the browser", () => {
  assert.equal(message(0, "timeout"), "Il back-end non ha risposto in tempo. Riprova.");
});

test("agent not reachable, 503", () => {
  assert.equal(
    message(503, "agent_unavailable", "agente non raggiungibile"),
    "L'assistente non è raggiungibile in questo momento. La domanda è salvata nella chat: " +
      "riprova più tardi.",
  );
});

test("agent too slow, 504", () => {
  assert.equal(
    message(504, "agent_timeout", "x"),
    "L'assistente non ha risposto in tempo. La domanda è salvata nella chat: riprova.",
  );
});

test("agent error, 502, with the detail", () => {
  assert.equal(
    message(502, "agent_error", "l'agente ha risposto con un errore (model_unavailable): spento."),
    "L'assistente ha risposto con un errore: l'agente ha risposto con un errore " +
      "(model_unavailable): spento. La domanda è salvata nella chat: riprova.",
  );
});

test("database not available, 503", () => {
  assert.equal(
    message(503, "database_unavailable", "database non disponibile; dettagli nel log"),
    "L'archivio delle chat non è disponibile. Riprova tra poco.",
  );
});

test("chat not found, 404", () => {
  assert.equal(
    message(404, "chat_not_found", "la chat 9 non esiste"), "Questa chat non esiste più.",
  );
});

test("invalid request, 400", () => {
  assert.equal(
    message(400, "invalid_request", "il messaggio è vuoto"),
    "Richiesta non valida: il messaggio è vuoto.",
  );
});

test("every other answer: status and detail if there is one", () => {
  assert.equal(message(422, null), "Errore del back-end (422).");
  assert.equal(
    message(500, "internal_error", "errore interno del back-end; dettagli nel log"),
    "Errore del back-end (500): errore interno del back-end; dettagli nel log.",
  );
  assert.equal(
    message(200, null, "risposta non in formato JSON"),
    "Errore del back-end (200): risposta non in formato JSON.",
  );
  assert.equal(message(503, "other_code"), "Errore del back-end (503).");
  assert.equal(message(404, null), "Errore del back-end (404)."); // not the body of the back-end
});

test("an error that is not of the back-end", () => {
  assert.equal(
    errorMessage(new TypeError("x is undefined"), URL),
    "Errore imprevisto nella pagina: x is undefined.",
  );
});

const ROME = { timeZone: "Europe/Rome", now: new Date("2026-11-14T15:00:00Z") };

test("formatDate: today only the time, in the local time zone", () => {
  assert.equal(formatDate("2026-11-14T10:05:00Z", ROME), "11:05");
});

test("formatDate: another day with date and time", () => {
  assert.equal(formatDate("2026-11-13T22:30:00Z", ROME), "13/11/2026 23:30");
  // 23:30 UTC on the 14th is already the 15th in Rome
  assert.equal(formatDate("2026-11-14T23:30:00Z", ROME), "15/11/2026 00:30");
});

test("chatSubtitle: date of the last message or 'nessun messaggio'", () => {
  assert.equal(chatSubtitle({ last_message_at: "2026-11-14T10:05:00Z" }, ROME), "11:05");
  assert.equal(chatSubtitle({ last_message_at: null }, ROME), "nessun messaggio");
});

test("fixed texts of the specification", () => {
  assert.equal(TEXTS.noChats, 'Nessuna chat. Premi "Nuova chat" per iniziare.');
  assert.equal(TEXTS.noSelection, "Seleziona una chat o creane una nuova.");
  assert.equal(TEXTS.noMessages, "Nessun messaggio: scrivi la prima domanda.");
  assert.equal(TEXTS.loading, "Caricamento…");
  assert.equal(TEXTS.deleteLabel("Conversioni"), "Elimina la chat Conversioni");
});

test("waiting line with the seconds", () => {
  assert.equal(TEXTS.waiting(0), "L'assistente sta rispondendo… (0 s)");
  assert.equal(TEXTS.waiting(42), "L'assistente sta rispondendo… (42 s)");
});

test("questionSaved: only after an error of the agent", () => {
  const saved = (status, code) => questionSaved(new BackendError(status, code, null));
  assert.equal(saved(503, "agent_unavailable"), true);
  assert.equal(saved(504, "agent_timeout"), true);
  assert.equal(saved(502, "agent_error"), true);
  assert.equal(saved(0, "network"), false);
  assert.equal(saved(0, "timeout"), false);
  assert.equal(saved(400, "invalid_request"), false);
  assert.equal(saved(404, "chat_not_found"), false);
  assert.equal(saved(422, null), false);
  assert.equal(saved(503, "database_unavailable"), false);
  assert.equal(saved(500, "internal_error"), false);
  assert.equal(questionSaved(new TypeError("x")), false);
});

const CALCULATE = { name: "calculate", args: { expression: "17 * 23" }, result: 391, ok: true };
const FAILED = {
  name: "convert_units", args: { value: 1, from: "m", to: "kg" },
  result: { error: "unità incompatibili" }, ok: false,
};

test("toolsSummary: names in order, failed ones marked, empty without tools", () => {
  assert.equal(toolsSummary([CALCULATE]), "Strumenti usati: calculate");
  assert.equal(
    toolsSummary([CALCULATE, FAILED]), "Strumenti usati: calculate, convert_units (errore)",
  );
  assert.equal(toolsSummary([]), "");
  assert.equal(toolsSummary(undefined), "");
});

test("toolDetail: name, arguments and result in JSON", () => {
  assert.equal(
    toolDetail(CALCULATE),
    'calculate\nargomenti: {"expression":"17 * 23"}\nrisultato: 391',
  );
  assert.equal(
    toolDetail(FAILED),
    'convert_units (errore)\nargomenti: {"value":1,"from":"m","to":"kg"}\n' +
      'risultato: {"error":"unità incompatibili"}',
  );
  assert.equal(toolDetail({ name: "x" }), "x\nargomenti: {}\nrisultato: null");
});

test("visibleMessages: the saved question waiting for its answer is not shown twice", () => {
  const old = { id: 1, role: "assistant", content: "Ciao" };
  const question = { id: 2, role: "user", content: "Quanto fa 17 * 23?" };
  assert.deepEqual(visibleMessages([old, question], "Quanto fa 17 * 23?"), [old]);
  assert.deepEqual(visibleMessages([old, question], null), [old, question]);
  assert.deepEqual(visibleMessages([old, question], "altra domanda"), [old, question]);
  assert.deepEqual(visibleMessages([old], "Ciao"), [old]); // an answer is never removed
  assert.deepEqual(visibleMessages([], "Ciao"), []);
});

// --- streaming (specification of the streaming, §7; CA-99) ---

test("errors inside a stream: the messages of the codes without streaming", () => {
  assert.equal(
    message(200, "agent_unavailable", "agente non raggiungibile"),
    "L'assistente non è raggiungibile in questo momento. La domanda è salvata nella chat: " +
      "riprova più tardi.",
  );
  assert.equal(
    message(200, "agent_timeout", "x"),
    "L'assistente non ha risposto in tempo. La domanda è salvata nella chat: riprova.",
  );
  assert.equal(
    message(200, "agent_error", "l'agente ha risposto con un errore (model_unavailable): spento."),
    "L'assistente ha risposto con un errore: l'agente ha risposto con un errore " +
      "(model_unavailable): spento. La domanda è salvata nella chat: riprova.",
  );
  assert.equal(
    message(200, "database_unavailable", "x"),
    "L'archivio delle chat non è disponibile. Riprova tra poco.",
  );
  assert.equal(message(200, "chat_not_found", "x"), "Questa chat non esiste più.");
});

test("stream interrupted, and the other errors inside a stream", () => {
  assert.equal(
    message(200, "stream_interrupted", "flusso interrotto"),
    "La risposta si è interrotta prima della fine. La domanda è salvata nella chat: riprova.",
  );
  assert.equal(
    message(200, "internal_error", "errore interno del back-end; dettagli nel log"),
    "Errore del back-end durante la risposta: errore interno del back-end; dettagli nel log.",
  );
  assert.equal(message(200, "other_code"), "Errore del back-end durante la risposta.");
  // stream_interrupted happens only inside a stream
  assert.equal(message(500, "stream_interrupted"), "Errore del back-end (500).");
});

test("questionSaved: after every error inside a stream", () => {
  const saved = (status, code) => questionSaved(new BackendError(status, code, null));
  assert.equal(saved(200, "stream_interrupted"), true);
  assert.equal(saved(200, "agent_error"), true);
  assert.equal(saved(200, "internal_error"), true);
  assert.equal(saved(200, null), false); // a 2xx answer that is not JSON, not a stream
});

test("texts of the answer arriving", () => {
  assert.equal(TEXTS.draftLabel, "Bozza: la risposta può ancora cambiare");
  assert.equal(TEXTS.toolRunning("calculate"), "Uso lo strumento calculate…");
  assert.equal(
    reviewNotice("La risposta non dà il risultato."),
    "Il revisore ha chiesto di riscrivere la risposta: La risposta non dà il risultato.",
  );
  assert.equal(reviewNotice(""), "Il revisore ha chiesto di riscrivere la risposta.");
  assert.equal(reviewNotice(undefined), "Il revisore ha chiesto di riscrivere la risposta.");
});

// The answer arriving after `events` ([event, data] pairs), from the empty one.
const draftAfter = (...events) =>
  events.reduce((draft, [event, data]) => applyEvent(draft, { event, data }), EMPTY_DRAFT);

const START = { id: "c1", name: "calculate", args: { expression: "17 * 23" } };
const END = { ...START, result: 391, ok: true };

test("applyEvent: the text pieces are joined", () => {
  assert.deepEqual(draftAfter(["text", { delta: "17 * 23 " }], ["text", { delta: "fa 391." }]), {
    text: "17 * 23 fa 391.", tools: [], notice: "",
  });
});

test("applyEvent: a tool running, then with its result", () => {
  const running = draftAfter(["tool_start", START]);
  assert.deepEqual(running.tools, [{ ...START, running: true }]);
  assert.equal(draftToolLine(running.tools[0]), "Uso lo strumento calculate…");
  const ended = applyEvent(running, { event: "tool_end", data: END });
  assert.deepEqual(ended.tools, [{ ...END, running: false }]);
  assert.equal(
    draftToolLine(ended.tools[0]), 'calculate\nargomenti: {"expression":"17 * 23"}\nrisultato: 391',
  );
  const failed = draftAfter(["tool_start", START], ["tool_end", { ...END, ok: false }]);
  assert.match(draftToolLine(failed.tools[0]), /^calculate \(errore\)\n/);
});

test("applyEvent: tools matched by id, a result without its start is added", () => {
  const second = { id: "c2", name: "convert_units", args: {} };
  const draft = draftAfter(
    ["tool_start", START], ["tool_start", second], ["tool_end", { ...second, result: 1, ok: true }],
  );
  assert.deepEqual(draft.tools.map((tool) => [tool.id, tool.running]), [["c1", true], ["c2", false]]);
  const alone = draftAfter(["tool_end", END]);
  assert.deepEqual(alone.tools, [{ ...END, running: false }]);
});

test("applyEvent: reset for tools empties the text without a notice", () => {
  const draft = draftAfter(["text", { delta: "Calcolo" }], ["reset", { reason: "tools", detail: "" }]);
  assert.deepEqual(draft, { text: "", tools: [], notice: "" });
});

test("applyEvent: reset of the reviewer empties the text and shows the reason", () => {
  const draft = draftAfter(
    ["tool_start", START], ["tool_end", END], ["text", { delta: "Bozza" }],
    ["reset", { reason: "review", detail: "manca il risultato" }], ["text", { delta: "391" }],
  );
  assert.equal(draft.text, "391");
  assert.equal(draft.notice, "Il revisore ha chiesto di riscrivere la risposta: manca il risultato.");
  assert.equal(draft.tools.length, 1); // the tools of the turn stay
  // a later reset for tools keeps the notice
  const later = applyEvent(draft, { event: "reset", data: { reason: "tools", detail: "" } });
  assert.equal(later.notice, draft.notice);
});

test("applyEvent: other events do not change the answer, which is never changed in place", () => {
  const draft = draftAfter(["text", { delta: "a" }]);
  assert.equal(applyEvent(draft, { event: "question", data: { id: 1 } }), draft);
  assert.deepEqual(EMPTY_DRAFT, { text: "", tools: [], notice: "" });
  applyEvent(draft, { event: "text", data: { delta: "b" } });
  assert.equal(draft.text, "a");
});

test("draftVisible: only with text, tools or a notice", () => {
  assert.equal(draftVisible(EMPTY_DRAFT), false);
  assert.equal(draftVisible(draftAfter(["text", { delta: "a" }])), true);
  assert.equal(draftVisible(draftAfter(["tool_start", START])), true);
  assert.equal(draftVisible(draftAfter(["reset", { reason: "review", detail: "x" }])), true);
  assert.equal(draftVisible(draftAfter(["reset", { reason: "tools", detail: "" }])), false);
});
