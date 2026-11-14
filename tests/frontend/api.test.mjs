// BackendClient with a fake fetch: methods, paths, bodies, 204, errors, network, timeout (CA-83).
import assert from "node:assert/strict";
import { test } from "node:test";

import { BackendClient, BackendError, readEvents } from "../../frontend/static/api.js";

const CHAT = {
  id: 3, title: "Nuova chat", created_at: "2026-11-14T10:00:00Z", last_message_at: null,
};

// A fake fetch that records the calls and answers with `status` and `body` (text).
function fakeFetch(status, body = "") {
  const calls = [];
  const fetch = async (url, init) => {
    calls.push({ url, ...init });
    return { ok: status >= 200 && status < 300, status, text: async () => body };
  };
  return { fetch, calls };
}

const json = (value) => JSON.stringify(value);

function expectError(status, code, detail) {
  return (error) => {
    assert.ok(error instanceof BackendError);
    assert.deepEqual([error.status, error.code, error.detail], [status, code, detail]);
    return true;
  };
}

test("listChats: GET /chats", async () => {
  const { fetch, calls } = fakeFetch(200, json([CHAT]));
  const client = new BackendClient("http://backend:8001", { fetch });
  assert.deepEqual(await client.listChats(), [CHAT]);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "http://backend:8001/chats");
  assert.equal(calls[0].method, "GET");
  assert.equal(calls[0].body, undefined);
  assert.ok(calls[0].signal instanceof AbortSignal);
});

test("createChat: POST /chats with an empty JSON object", async () => {
  const { fetch, calls } = fakeFetch(201, json(CHAT));
  const client = new BackendClient("http://backend:8001/", { fetch });
  assert.deepEqual(await client.createChat(), CHAT);
  assert.equal(calls[0].url, "http://backend:8001/chats"); // final "/" of the address removed
  assert.equal(calls[0].method, "POST");
  assert.equal(calls[0].body, "{}");
  assert.deepEqual(calls[0].headers, { "Content-Type": "application/json" });
});

test("getChat: GET /chats/{id}", async () => {
  const detail = { ...CHAT, messages: [] };
  const { fetch, calls } = fakeFetch(200, json(detail));
  const client = new BackendClient("http://backend:8001", { fetch });
  assert.deepEqual(await client.getChat(3), detail);
  assert.equal(calls[0].url, "http://backend:8001/chats/3");
  assert.equal(calls[0].method, "GET");
});

test("deleteChat: DELETE /chats/{id}, 204 without body gives null", async () => {
  const { fetch, calls } = fakeFetch(204, "");
  const client = new BackendClient("http://backend:8001", { fetch });
  assert.equal(await client.deleteChat(3), null);
  assert.equal(calls[0].url, "http://backend:8001/chats/3");
  assert.equal(calls[0].method, "DELETE");
  assert.equal(calls[0].body, undefined);
});

test("identifiers are encoded in the path", async () => {
  const { fetch, calls } = fakeFetch(200, json(CHAT));
  await new BackendClient("http://b", { fetch }).getChat("1/2");
  assert.equal(calls[0].url, "http://b/chats/1%2F2");
});

test("error with the body of the back-end", async () => {
  const body = json({ error: "chat_not_found", detail: "la chat 9 non esiste" });
  const { fetch } = fakeFetch(404, body);
  await assert.rejects(
    new BackendClient("http://b", { fetch }).getChat(9),
    expectError(404, "chat_not_found", "la chat 9 non esiste"),
  );
});

const NOT_ERROR_BODIES = [
  ["text", 500, "Internal Server Error"],
  ["empty", 500, ""],
  ["422 of FastAPI", 422, json({ detail: [{ loc: ["path", "chat_id"], msg: "x" }] })],
  ["JSON not an object", 500, json(["x"])],
  ["JSON null", 503, "null"],
];

for (const [name, status, body] of NOT_ERROR_BODIES) {
  test(`error with a body that is not {error, detail}: ${name}`, async () => {
    const { fetch } = fakeFetch(status, body);
    await assert.rejects(
      new BackendClient("http://b", { fetch }).listChats(), expectError(status, null, null),
    );
  });
}

test("2xx answer that is not JSON", async () => {
  const { fetch } = fakeFetch(200, "<html>");
  await assert.rejects(
    new BackendClient("http://b", { fetch }).listChats(),
    expectError(200, null, "risposta non in formato JSON"),
  );
});

test("fetch that fails: status 0, code network", async () => {
  const fetch = async () => {
    throw new TypeError("Failed to fetch");
  };
  await assert.rejects(
    new BackendClient("http://b", { fetch }).listChats(), expectError(0, "network", null),
  );
});

test("no answer within the time: status 0, code timeout, request aborted", async () => {
  let received;
  const fetch = (url, init) => new Promise((resolve, reject) => {
    received = init.signal;
    init.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
  });
  const client = new BackendClient("http://b", { fetch, timeoutMs: 20 });
  await assert.rejects(client.listChats(), expectError(0, "timeout", null));
  assert.equal(received.aborted, true);
});

test("body that does not arrive within the time is a timeout too", async () => {
  const fetch = (url, init) => Promise.resolve({
    ok: true,
    status: 200,
    text: () => new Promise((resolve, reject) => {
      init.signal.addEventListener("abort", () => reject(new Error("aborted")));
    }),
  });
  const client = new BackendClient("http://b", { fetch, timeoutMs: 20 });
  await assert.rejects(client.listChats(), expectError(0, "timeout", null));
});

test("the default fetch is the global one, not called on the client", async (t) => {
  const calls = [];
  t.mock.method(globalThis, "fetch", async function (url) {
    calls.push({ url, self: this });
    return { ok: true, status: 200, text: async () => "[]" };
  });
  assert.deepEqual(await new BackendClient("http://b").listChats(), []);
  assert.equal(calls[0].url, "http://b/chats");
  assert.equal(calls[0].self instanceof BackendClient, false); // browsers reject that "this"
});

test("sendMessage: POST /chats/{id}/messages with the content", async () => {
  const answer = { question: { id: 1 }, answer: { id: 2 } };
  const { fetch, calls } = fakeFetch(201, json(answer));
  const client = new BackendClient("http://backend:8001", { fetch });
  assert.deepEqual(await client.sendMessage(3, "Quanto fa 17 * 23?"), answer);
  assert.equal(calls[0].url, "http://backend:8001/chats/3/messages");
  assert.equal(calls[0].method, "POST");
  assert.equal(calls[0].body, json({ content: "Quanto fa 17 * 23?" }));
  assert.deepEqual(calls[0].headers, { "Content-Type": "application/json" });
});

test("sendMessage: error of the agent with the body of the back-end", async () => {
  const body = json({ error: "agent_unavailable", detail: "agente non raggiungibile" });
  const { fetch } = fakeFetch(503, body);
  await assert.rejects(
    new BackendClient("http://b", { fetch }).sendMessage(3, "ciao"),
    expectError(503, "agent_unavailable", "agente non raggiungibile"),
  );
});

// A fetch that answers 200 "{}" after `delayMs`, or rejects when the request is aborted.
function slowFetch(delayMs) {
  return (url, init) => new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => resolve({ ok: true, status: 200, text: async () => "{}" }), delayMs,
    );
    init.signal.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("aborted", "AbortError"));
    });
  });
}

test("sendMessage waits sendTimeoutMs, the other requests timeoutMs", async () => {
  const client = new BackendClient("http://b", {
    fetch: slowFetch(80), timeoutMs: 20, sendTimeoutMs: 2_000,
  });
  assert.deepEqual(await client.sendMessage(3, "ciao"), {});
  await assert.rejects(client.listChats(), expectError(0, "timeout", null));
});

test("sendMessage: no answer within sendTimeoutMs is a timeout", async () => {
  const client = new BackendClient("http://b", {
    fetch: slowFetch(2_000), timeoutMs: 2_000, sendTimeoutMs: 20,
  });
  await assert.rejects(client.sendMessage(3, "ciao"), expectError(0, "timeout", null));
});

test("default times: 10 s, and 660 s for sending (the back-end waits the agent 600 s)", () => {
  const client = new BackendClient("http://b");
  assert.equal(client.timeoutMs, 10_000);
  assert.equal(client.sendTimeoutMs, 660_000);
});

// --- streaming (specification of the streaming, §7; CA-99) ---

// All the events of `chunks` read by readEvents.
async function eventsOf(chunks) {
  const events = [];
  for await (const event of readEvents(chunks)) {
    events.push(event);
  }
  return events;
}

test("readEvents: events cut anywhere, even inside a line", async () => {
  const text = 'event: text\ndata: {"delta": "17 * 23"}\n\nevent: done\ndata: {"a": 1}\n\n';
  const expected = [
    { event: "text", data: { delta: "17 * 23" } },
    { event: "done", data: { a: 1 } },
  ];
  for (const size of [1, 2, 5, 7, text.length]) {
    const chunks = [];
    for (let start = 0; start < text.length; start += size) {
      chunks.push(text.slice(start, start + size));
    }
    assert.deepEqual(await eventsOf(chunks), expected, `pezzi di ${size}`);
  }
});

test("readEvents: CRLF, comments, data on more lines, no name, no space after the colon",
  async () => {
    const text = ': ping\r\n\r\nevent: a\r\ndata: [1,\r\ndata:2]\r\nid: 7\r\n\r\ndata: "x"\n\n';
    assert.deepEqual(await eventsOf([text]), [
      { event: "a", data: [1, 2] },
      { event: "message", data: "x" },
    ]);
  });

test("readEvents: data that are not JSON are undefined; events without data are dropped",
  async () => {
    assert.deepEqual(await eventsOf(["event: text\ndata: {rotto\n\nevent: vuoto\n\n"]), [
      { event: "text", data: undefined },
    ]);
  });

test("readEvents: an event not ended by an empty line (a cut stream) is dropped", async () => {
  const text = 'event: text\ndata: {"delta": "a"}\n\nevent: done\ndata: {}\n';
  assert.deepEqual(await eventsOf([text]), [{ event: "text", data: { delta: "a" } }]);
});

// An SSE text from [event, data] pairs; data in JSON unless already a string.
const sse = (...events) => events.map(([event, data]) => {
  const text = typeof data === "string" ? data : JSON.stringify(data);
  return `event: ${event}\ndata: ${text}\n\n`;
}).join("");

// A fetch whose answer has the body `chunks` (texts) as a stream of bytes; `fail` ends the body
// with a network error after the chunks instead of closing it. Records the calls.
function streamFetch(chunks, { status = 200, fail = false } = {}) {
  const calls = [];
  const encoder = new TextEncoder();
  const fetch = async (url, init) => {
    calls.push({ url, ...init });
    let next = 0;
    const body = new ReadableStream({
      // one chunk per read (an error discards the chunks still queued)
      pull(controller) {
        if (next < chunks.length) {
          controller.enqueue(encoder.encode(chunks[next++]));
        } else if (fail) {
          controller.error(new TypeError("network error"));
        } else {
          controller.close();
        }
      },
    });
    const ok = status >= 200 && status < 300;
    return { ok, status, body, text: async () => chunks.join("") };
  };
  return { fetch, calls };
}

const QUESTION = { id: 1, role: "user", content: "Quanto fa 17 * 23?" };
const ANSWER = { id: 2, role: "assistant", content: "391" };
const DONE = { question: QUESTION, answer: ANSWER };
const TOOL_START = { id: "c1", name: "calculate", args: { expression: "17 * 23" } };
const TOOL_END = { ...TOOL_START, result: 391, ok: true };

// sendMessageStream on a body made of `chunks`: {result (the promise), received, calls}.
function streamWith(chunks, options = {}) {
  const { fetch, calls } = streamFetch(chunks, options);
  const received = [];
  const client = new BackendClient("http://backend:8001", { fetch });
  const result = client.sendMessageStream(3, "Quanto fa 17 * 23?", (event) => received.push(event));
  return { result, received, calls };
}

test("sendMessageStream: POST /chats/{id}/messages/stream, events in order, done", async () => {
  const text = sse(
    ["question", QUESTION], ["tool_start", TOOL_START], ["tool_end", TOOL_END],
    ["text", { delta: "17 * 23 " }], ["reset", { reason: "review", detail: "manca" }],
    ["text", { delta: "fa 391." }], ["done", DONE],
  );
  const { result, received, calls } = streamWith([text.slice(0, 50), text.slice(50)]);
  assert.deepEqual(await result, DONE);
  assert.deepEqual(received.map((event) => event.event), [
    "question", "tool_start", "tool_end", "text", "reset", "text",
  ]);
  assert.deepEqual(received[1], { event: "tool_start", data: TOOL_START });
  assert.deepEqual(received[4], { event: "reset", data: { reason: "review", detail: "manca" } });
  assert.equal(calls[0].url, "http://backend:8001/chats/3/messages/stream");
  assert.equal(calls[0].method, "POST");
  assert.equal(calls[0].body, json({ content: "Quanto fa 17 * 23?" }));
  assert.deepEqual(calls[0].headers, { "Content-Type": "application/json" });
  assert.ok(calls[0].signal instanceof AbortSignal);
});

test("sendMessageStream: comments and unknown events are ignored", async () => {
  const text = ": ping\n\n" + sse(["altro", { x: 1 }], ["done", DONE]);
  const { result, received } = streamWith([text]);
  assert.deepEqual(await result, DONE);
  assert.deepEqual(received, []);
});

test("sendMessageStream: done ends the reading, the rest of the stream is not read", async () => {
  const { result, received } = streamWith([sse(["done", DONE], ["text", { delta: "dopo" }])]);
  assert.deepEqual(await result, DONE);
  assert.deepEqual(received, []);
});

test("sendMessageStream: done before the body ends releases the body", async () => {
  // a body that never closes by itself: only the client can stop it
  let cancelled = false;
  const encoder = new TextEncoder();
  const fetch = async () => ({
    ok: true,
    status: 200,
    body: new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(sse(["done", DONE])));
      },
      cancel() {
        cancelled = true;
      },
    }),
  });
  const client = new BackendClient("http://b", { fetch });
  assert.deepEqual(await client.sendMessageStream(3, "x", () => {}), DONE);
  assert.equal(cancelled, true);
});

test("sendMessageStream: error event → BackendError(200, error, detail)", async () => {
  const text = sse(
    ["question", QUESTION], ["text", { delta: "Ini" }],
    ["error", { error: "agent_error", detail: "l'agente ha risposto con un errore" }],
  );
  const { result, received } = streamWith([text]);
  await assert.rejects(
    result, expectError(200, "agent_error", "l'agente ha risposto con un errore"),
  );
  assert.equal(received.length, 2); // the events before the error were passed on
});

const INTERRUPTED = [
  ["closed without done", sse(["question", QUESTION], ["text", { delta: "a" }])],
  ["empty body", ""],
  ["data not JSON", "event: text\ndata: {rotto\n\n"],
  ["data not an object", sse(["text", [1, 2]])],
  ["done without the answer", sse(["done", { question: QUESTION }])],
  ["error without a code", sse(["error", { detail: "x" }])],
];

for (const [name, text] of INTERRUPTED) {
  test(`sendMessageStream: ${name} → stream_interrupted`, async () => {
    const { result } = streamWith([text]);
    await assert.rejects(result, (error) => {
      assert.ok(error instanceof BackendError);
      assert.deepEqual([error.status, error.code], [200, "stream_interrupted"]);
      assert.ok(error.detail);
      return true;
    });
  });
}

test("sendMessageStream: body cut by the network → stream_interrupted", async () => {
  const { result, received } = streamWith([sse(["question", QUESTION])], { fail: true });
  await assert.rejects(
    result, (error) => error.status === 200 && error.code === "stream_interrupted",
  );
  assert.equal(received.length, 1);
});

test("sendMessageStream: error answer before the stream, with the body of the back-end",
  async () => {
    const body = json({ error: "agent_unavailable", detail: "agente non raggiungibile" });
    const { result, received } = streamWith([body], { status: 503 });
    await assert.rejects(
      result, expectError(503, "agent_unavailable", "agente non raggiungibile"),
    );
    assert.deepEqual(received, []);
  });

test("sendMessageStream: fetch that fails → status 0, code network", async () => {
  const fetch = async () => {
    throw new TypeError("Failed to fetch");
  };
  const client = new BackendClient("http://b", { fetch });
  await assert.rejects(
    client.sendMessageStream(3, "x", () => {}), expectError(0, "network", null),
  );
});

test("sendMessageStream: stream not finished within sendTimeoutMs → timeout", async () => {
  let signal;
  const encoder = new TextEncoder();
  const fetch = async (url, init) => {
    signal = init.signal;
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(sse(["question", QUESTION])));
        init.signal.addEventListener(
          "abort", () => controller.error(new DOMException("aborted", "AbortError")),
        );
      },
    });
    return { ok: true, status: 200, body };
  };
  const received = [];
  const client = new BackendClient("http://b", { fetch, timeoutMs: 2_000, sendTimeoutMs: 30 });
  await assert.rejects(
    client.sendMessageStream(3, "x", (event) => received.push(event)),
    expectError(0, "timeout", null),
  );
  assert.equal(signal.aborted, true);
  assert.equal(received.length, 1); // the events before the time were passed on
});

test("sendMessageStream: an error of onEvent reaches the caller as it is", async () => {
  const failure = new RangeError("errore della pagina");
  const { fetch } = streamFetch([sse(["question", QUESTION], ["done", DONE])]);
  const client = new BackendClient("http://b", { fetch });
  const failing = () => {
    throw failure;
  };
  await assert.rejects(client.sendMessageStream(3, "x", failing), (error) => error === failure);
});
