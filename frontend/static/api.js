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

function errorFrom(status, text) {
  const body = parseJson(text);
  const isObject = body !== null && typeof body === "object";
  const code = isObject && typeof body.error === "string" ? body.error : null;
  const detail = isObject && typeof body.detail === "string" ? body.detail : null;
  return new BackendError(status, code, detail);
}

// The global fetch called without the client as `this` (browsers reject that call).
const globalFetch = (...args) => globalThis.fetch(...args);

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
