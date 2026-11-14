// HTTP client of the back-end: the only service the page talks to.
// Contract: frontend/backend-openapi.json (OpenAPI of the back-end).

// An error of a request. status 0: the back-end was not reached (code "network") or did not
// answer in time (code "timeout"); otherwise the HTTP status with `error` and `detail` of the
// body {"error", "detail"} (null when the body is not like that).
export class BackendError extends Error {
  constructor(status, code, detail) {
    super(detail || code || `HTTP ${status}`);
    this.name = "BackendError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

function parseJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

const isObject = (value) => value !== null && typeof value === "object" && !Array.isArray(value);

// The error of a body {"error", "detail"} (code and detail null when the body is not like that).
function errorFromBody(status, body) {
  const code = isObject(body) && typeof body.error === "string" ? body.error : null;
  const detail = isObject(body) && typeof body.detail === "string" ? body.detail : null;
  return new BackendError(status, code, detail);
}

function errorFrom(status, text) {
  return errorFromBody(status, parseJson(text));
}

// The global fetch called without the client as `this` (browsers reject that call).
const globalFetch = (...args) => globalThis.fetch(...args);

// Server-Sent Events from `chunks`, pieces of text cut anywhere (even inside a line): yields
// {event, data}, `data` decoded from JSON (undefined when it is not JSON). Same rules as iter_sse
// of the agent client: an event ends at an empty line, its "data" lines are joined with "\n", an
// event without a name is "message", comments and unknown fields are ignored, an event without
// data or not ended by an empty line (a cut stream) is dropped.
export async function* readEvents(chunks) {
  let buffer = "";
  let event = "";
  let data = [];
  for await (const chunk of chunks) {
    buffer += chunk;
    let end;
    while ((end = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, end).replace(/\r$/, "");
      buffer = buffer.slice(end + 1);
      if (line === "") {
        if (data.length > 0) {
          yield { event: event || "message", data: parseJson(data.join("\n")) };
        }
        event = "";
        data = [];
        continue;
      }
      if (line.startsWith(":")) {
        continue;
      }
      const colon = line.indexOf(":");
      const name = colon >= 0 ? line.slice(0, colon) : line;
      let value = colon >= 0 ? line.slice(colon + 1) : "";
      if (value.startsWith(" ")) {
        value = value.slice(1);
      }
      if (name === "event") {
        event = value;
      } else if (name === "data") {
        data.push(value);
      }
    }
  }
}

// The text of a response body (a ReadableStream of bytes), piece by piece; the reader is
// released when the caller stops reading.
async function* bodyText(body) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) {
        const rest = decoder.decode();
        if (rest) {
          yield rest;
        }
        return;
      }
      yield decoder.decode(value, { stream: true });
    }
  } finally {
    reader.cancel().catch(() => {});
  }
}

// Events of the stream of the back-end passed to the page; "done" and "error" end it.
const FORWARDED_EVENTS = new Set(["question", "text", "reset", "tool_start", "tool_end"]);

// A stream that ended without "done" or "error", or with data that are not valid.
const interrupted = (detail) => new BackendError(200, "stream_interrupted", detail);

export class BackendClient {
  // `fetch` is a parameter so that the tests can pass a fake one. `sendTimeoutMs` is longer than
  // the 600 s the back-end waits for the agent, so that its 504 answer can arrive.
  constructor(baseUrl, { fetch = globalFetch, timeoutMs = 10_000, sendTimeoutMs = 660_000 } = {}) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.fetch = fetch;
    this.timeoutMs = timeoutMs;
    this.sendTimeoutMs = sendTimeoutMs;
  }

  listChats() {
    return this.request("GET", "/chats");
  }

  createChat() {
    return this.request("POST", "/chats", {});
  }

  getChat(id) {
    return this.request("GET", `/chats/${encodeURIComponent(id)}`);
  }

  deleteChat(id) {
    return this.request("DELETE", `/chats/${encodeURIComponent(id)}`);
  }

  // The question saved and the answer of the agent: {question, answer}.
  sendMessage(id, text) {
    const path = `/chats/${encodeURIComponent(id)}/messages`;
    return this.request("POST", path, { content: text }, this.sendTimeoutMs);
  }

  // The same question through POST /chats/{id}/messages/stream (specification of the streaming,
  // §7): onEvent({event, data}) for "question", "text", "reset", "tool_start" and "tool_end" as
  // they arrive; resolves with the data of "done" ({question, answer}). An error answer before
  // the stream → BackendError with its status, as `request`; an "error" event → BackendError(200,
  // error, detail); a stream that ends without its last event, or with data that are not valid →
  // BackendError(200, "stream_interrupted"); network or sendTimeoutMs → BackendError(0, ...).
  async sendMessageStream(id, text, onEvent) {
    const path = `/chats/${encodeURIComponent(id)}/messages/stream`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.sendTimeoutMs);
    const failed = () => new BackendError(0, controller.signal.aborted ? "timeout" : "network", null);
    const fetchFunction = this.fetch;
    try {
      let response;
      let errorText;
      try {
        response = await fetchFunction(this.baseUrl + path, {
          method: "POST",
          signal: controller.signal,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: text }),
        });
        if (!response.ok) {
          errorText = await response.text();
        }
      } catch {
        throw failed();
      }
      if (!response.ok) {
        throw errorFrom(response.status, errorText);
      }
      const events = readEvents(bodyText(response.body));
      try {
        for (;;) {
          let next;
          try {
            next = await events.next();
          } catch {
            throw controller.signal.aborted ? failed() : interrupted("flusso interrotto");
          }
          if (next.done) {
            throw interrupted("flusso chiuso prima della fine della risposta");
          }
          const { event, data } = next.value;
          if (event === "error") {
            const error = errorFromBody(200, data);
            throw error.code ? error : interrupted("evento 'error' non valido");
          }
          if (event !== "done" && !FORWARDED_EVENTS.has(event)) {
            continue; // unknown events are ignored
          }
          if (!isObject(data)) {
            throw interrupted(`dati non validi nell'evento '${event}'`);
          }
          if (event === "done") {
            if (!isObject(data.question) || !isObject(data.answer)) {
              throw interrupted("evento 'done' non valido");
            }
            return data;
          }
          onEvent({ event, data }); // an error of the page goes to the caller as it is
        }
      } finally {
        await events.return(); // stops reading and releases the connection
      }
    } finally {
      clearTimeout(timer);
    }
  }

  // JSON body of a 2xx answer (null for 204), otherwise a BackendError.
  async request(method, path, body = undefined, timeoutMs = this.timeoutMs) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const init = { method, signal: controller.signal };
    if (body !== undefined) {
      init.headers = { "Content-Type": "application/json" };
      init.body = JSON.stringify(body);
    }
    const fetchFunction = this.fetch;
    let response;
    let text;
    try {
      response = await fetchFunction(this.baseUrl + path, init);
      text = await response.text();
    } catch {
      throw new BackendError(0, controller.signal.aborted ? "timeout" : "network", null);
    } finally {
      clearTimeout(timer);
    }
    if (!response.ok) {
      throw errorFrom(response.status, text);
    }
    if (response.status === 204 || text === "") {
      return null;
    }
    const data = parseJson(text);
    if (data === undefined) {
      throw new BackendError(response.status, null, "risposta non in formato JSON");
    }
    return data;
  }
}
