// BackendClient with a fake fetch: methods, paths, bodies, 204, errors, network, timeout (CA-83).
import assert from "node:assert/strict";
import { test } from "node:test";

import { BackendClient, BackendError } from "../../frontend/static/api.js";

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
