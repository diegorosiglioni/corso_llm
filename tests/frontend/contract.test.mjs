// Every request of the client and every field the page reads exist in the contract,
// frontend/backend-openapi.json (OpenAPI of the back-end, CA-82).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { BackendClient } from "../../frontend/static/api.js";

const contract = JSON.parse(
  readFileSync(new URL("../../frontend/backend-openapi.json", import.meta.url), "utf-8"),
);

// The fields of the answers that app.js and texts.js read, by schema of the contract.
// Update this list together with the page.
const FIELDS_READ = {
  ChatInfo: ["id", "title", "last_message_at"],
  ChatDetail: ["id", "title", "messages"],
  ErrorBody: ["error", "detail"],
};

// Operation of the contract → schema of its successful answer that the page reads.
const ANSWERS = [
  ["get", "/chats", "200", "ChatInfo", true],
  ["post", "/chats", "201", "ChatInfo", false],
  ["get", "/chats/{chat_id}", "200", "ChatDetail", false],
];

// The requests the client makes, recorded with a fake fetch.
async function clientRequests() {
  const calls = [];
  const fetch = async (url, init) => {
    calls.push({ method: init.method.toLowerCase(), path: new URL(url).pathname });
    return { ok: true, status: 200, text: async () => "{}" };
  };
  const client = new BackendClient("http://backend", { fetch });
  await client.listChats();
  await client.createChat();
  await client.getChat(7);
  await client.deleteChat(7);
  return calls;
}

const template = (path) => path.replace(/\/\d+(?=\/|$)/g, "/{chat_id}");

test("every request of the client is an operation of the contract", async () => {
  const calls = await clientRequests();
  assert.equal(calls.length, 4);
  for (const { method, path } of calls) {
    const operations = contract.paths[template(path)];
    assert.ok(operations, `percorso ${path} assente dal contratto`);
    assert.ok(operations[method], `${method.toUpperCase()} ${path} assente dal contratto`);
  }
});

test("delete answers 204 without a body", () => {
  assert.ok(contract.paths["/chats/{chat_id}"].delete.responses["204"]);
});

test("every field read by the page is in its schema", () => {
  for (const [schema, fields] of Object.entries(FIELDS_READ)) {
    const properties = contract.components.schemas[schema]?.properties;
    assert.ok(properties, `schema ${schema} assente dal contratto`);
    for (const field of fields) {
      assert.ok(properties[field], `campo ${schema}.${field} assente dal contratto`);
    }
  }
});

test("the answers read by the page have the expected schema", () => {
  for (const [method, path, status, schema, isList] of ANSWERS) {
    const content = contract.paths[path][method].responses[status].content["application/json"];
    const reference = isList ? content.schema.items.$ref : content.schema.$ref;
    assert.equal(reference, `#/components/schemas/${schema}`, `${method} ${path}`);
  }
});

test("the error answers of the chat operations use ErrorBody", () => {
  const errors = [
    ["get", "/chats/{chat_id}", "404"],
    ["delete", "/chats/{chat_id}", "404"],
    ["get", "/chats", "503"],
    ["post", "/chats", "503"],
  ];
  for (const [method, path, status] of errors) {
    const content = contract.paths[path][method].responses[status].content["application/json"];
    const where = `${method} ${path} ${status}`;
    assert.equal(content.schema.$ref, "#/components/schemas/ErrorBody", where);
  }
});
