// Messages of the page (specification of step 8, §5) and date format (CA-83).
import assert from "node:assert/strict";
import { test } from "node:test";

import { BackendError } from "../../frontend/static/api.js";
import { TEXTS, chatSubtitle, errorMessage, formatDate } from "../../frontend/static/texts.js";

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
