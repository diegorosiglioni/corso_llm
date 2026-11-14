// Texts of the page, error messages and date format: pure functions, tested with Node.

import { BackendError } from "./api.js";

export const TEXTS = {
  loading: "Caricamento…",
  noChats: 'Nessuna chat. Premi "Nuova chat" per iniziare.',
  noSelection: "Seleziona una chat o creane una nuova.",
  noMessages: "Nessun messaggio: scrivi la prima domanda.",
  noMessageYet: "nessun messaggio",
  deleteLabel: (title) => `Elimina la chat ${title}`,
  confirmDelete: (title) =>
    `Eliminare la chat "${title}"? Anche i suoi messaggi saranno cancellati.`,
};

// The detail of the back-end without a final period: the messages add their own.
function clean(detail) {
  return (detail || "").trim().replace(/\.+$/, "");
}

// Italian message for an error of the back-end client (specification of step 8, §5).
export function errorMessage(error, backendUrl) {
  if (!(error instanceof BackendError)) {
    return `Errore imprevisto nella pagina: ${clean(error && error.message) || error}.`;
  }
  const detail = clean(error.detail);
  if (error.code === "network") {
    return `Il back-end non risponde (${backendUrl}). Controlla che sia avviato e riprova.`;
  }
  if (error.code === "timeout") {
    return "Il back-end non ha risposto in tempo. Riprova.";
  }
  const known = {
    "503 agent_unavailable":
      "L'assistente non è raggiungibile in questo momento. La domanda è salvata nella chat: " +
      "riprova più tardi.",
    "504 agent_timeout":
      "L'assistente non ha risposto in tempo. La domanda è salvata nella chat: riprova.",
    "502 agent_error":
      `L'assistente ha risposto con un errore: ${detail}. ` +
      "La domanda è salvata nella chat: riprova.",
    "503 database_unavailable": "L'archivio delle chat non è disponibile. Riprova tra poco.",
    "404 chat_not_found": "Questa chat non esiste più.",
    "400 invalid_request": `Richiesta non valida: ${detail}.`,
  };
  const message = known[`${error.status} ${error.code}`];
  if (message) {
    return message;
  }
  return `Errore del back-end (${error.status})${detail ? `: ${detail}` : ""}.`;
}

// Date and time in Italian in the time zone of the browser (or `timeZone`); today only the time.
export function formatDate(value, { now = new Date(), timeZone = undefined } = {}) {
  const date = new Date(value);
  const day = new Intl.DateTimeFormat("it-IT", {
    timeZone, day: "2-digit", month: "2-digit", year: "numeric",
  });
  const time = new Intl.DateTimeFormat("it-IT", { timeZone, hour: "2-digit", minute: "2-digit" });
  if (day.format(date) === day.format(now)) {
    return time.format(date);
  }
  return `${day.format(date)} ${time.format(date)}`;
}

// The line under the title of a chat in the list.
export function chatSubtitle(chat, options = {}) {
  return chat.last_message_at ? formatDate(chat.last_message_at, options) : TEXTS.noMessageYet;
}
