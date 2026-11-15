// Texts of the page, error messages, date format and the other pure functions of the page,
// tested with Node.

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
  waiting: (seconds) => `L'assistente sta rispondendo… (${seconds} s)`,
  draftLabel: "Bozza: la risposta può ancora cambiare",
  toolRunning: (name) => `Uso lo strumento ${name}…`,
};

// The detail of the back-end without a final period: the messages add their own.
function clean(detail) {
  return (detail || "").trim().replace(/\.+$/, "");
}

// An error inside a stream of the back-end: status 200 and always a code ("error" event or
// stream_interrupted); a 2xx answer that is not JSON has no code.
const inStream = (error) => error.status === 200 && error.code !== null;

// Italian message for an error of the back-end client (specification of step 8, §5, and of the
// streaming, §7).
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
      `L'assistente non è riuscito a rispondere${detail ? ` (${detail})` : ""}. ` +
      "La domanda è salvata nella chat: riprova.",
    "503 database_unavailable": "L'archivio delle chat non è disponibile. Riprova tra poco.",
    "404 chat_not_found": "Questa chat non esiste più.",
    "400 invalid_request": `Richiesta non valida: ${detail}.`,
    "200 stream_interrupted":
      "La risposta si è interrotta prima della fine. La domanda è salvata nella chat: riprova.",
  };
  // an error inside a stream has the code of the answer without streaming
  const key = Object.keys(known).find((candidate) => {
    const [status, code] = candidate.split(" ");
    return code === error.code && (Number(status) === error.status || inStream(error));
  });
  if (key) {
    return known[key];
  }
  if (inStream(error)) {
    return `Errore del back-end durante la risposta${detail ? `: ${detail}` : ""}.`;
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

// Errors after which the question is saved in the chat: the back-end reached the agent.
const AGENT_ERRORS = new Set(["503 agent_unavailable", "504 agent_timeout", "502 agent_error"]);

// True when the back-end saved the question before failing (the reloaded chat shows it): an
// error of the agent, or any error inside a stream, which starts after the saving.
export function questionSaved(error) {
  if (!(error instanceof BackendError)) {
    return false;
  }
  return inStream(error) || AGENT_ERRORS.has(`${error.status} ${error.code}`);
}

// The name of a tool, marked when it failed.
const toolName = (tool) => `${tool.name}${tool.ok === false ? " (errore)" : ""}`;

// The line under an answer: "Strumenti usati: calculate, convert_units (errore)"; "" without tools.
export function toolsSummary(tools) {
  if (!tools || tools.length === 0) {
    return "";
  }
  return `Strumenti usati: ${tools.map(toolName).join(", ")}`;
}

// Arguments and result of one tool, in JSON, for the details under an answer.
export function toolDetail(tool) {
  const lines = [
    toolName(tool),
    `argomenti: ${JSON.stringify(tool.args ?? {})}`,
    `risultato: ${JSON.stringify(tool.result ?? null)}`,
  ];
  return lines.join("\n");
}

// --- the answer that is arriving (specification of the streaming, §7) ---

// The answer arriving before any event.
export const EMPTY_DRAFT = Object.freeze({ text: "", tools: Object.freeze([]), notice: "" });

// The notice shown when the reviewer sends the answer back to the agent.
export function reviewNotice(detail) {
  const reason = clean(detail);
  return `Il revisore ha chiesto di riscrivere la risposta${reason ? `: ${reason}` : ""}.`;
}

// The answer arriving after one event of the stream: `text` since the last reset, the tools of
// the turn ({id, name, args, running} until their result, then with result and ok as well) and
// the notice of the reviewer. A new object: `draft` is not changed.
export function applyEvent(draft, { event, data }) {
  switch (event) {
    case "text":
      return { ...draft, text: draft.text + (data.delta ?? "") };
    case "reset": {
      const notice = data.reason === "review" ? reviewNotice(data.detail) : draft.notice;
      return { ...draft, text: "", notice };
    }
    case "tool_start": {
      const tool = { id: data.id, name: data.name, args: data.args, running: true };
      return { ...draft, tools: [...draft.tools, tool] };
    }
    case "tool_end": {
      const tool = {
        id: data.id, name: data.name, args: data.args, result: data.result, ok: data.ok,
        running: false,
      };
      const index = draft.tools.findIndex((other) => other.running && other.id === data.id);
      const tools = index < 0
        ? [...draft.tools, tool]
        : draft.tools.map((other, position) => (position === index ? tool : other));
      return { ...draft, tools };
    }
    default:
      return draft; // "question" and the others do not change the answer
  }
}

// True when the answer arriving has something to show.
export function draftVisible(draft) {
  return draft.text !== "" || draft.tools.length > 0 || draft.notice !== "";
}

// The line of a tool in the answer arriving: running, then as under a saved answer.
export function draftToolLine(tool) {
  return tool.running ? TEXTS.toolRunning(tool.name) : toolDetail(tool);
}

// The messages to show while `pendingText` waits for its answer: the back-end saves the question
// before calling the agent, so a chat read meanwhile already ends with it and it would be twice.
export function visibleMessages(messages, pendingText = null) {
  const last = messages[messages.length - 1];
  if (pendingText !== null && last && last.role === "user" && last.content === pendingText) {
    return messages.slice(0, -1);
  }
  return messages;
}
