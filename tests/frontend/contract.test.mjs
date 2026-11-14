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
  ChatMessageInfo: ["id", "role", "content", "tools_used", "created_at"],
  SendMessageRequest: ["content"],
  SendMessageResponse: ["question", "answer"],
  ErrorBody: ["error", "detail"],
};

// Operation of the contract → schema of its successful answer that the page reads.
const ANSWERS = [
  ["get", "/chats", "200", "ChatInfo", true],
  ["post", "/chats", "201", "ChatInfo", false],
  ["get", "/chats/{chat_id}", "200", "ChatDetail", false],
  ["post", "/chats/{chat_id}/messages", "201", "SendMessageResponse", false],
];

// The requests the client makes, recorded with a fake fetch.
async function clientRequests() {
  const calls = [];
  const done = 'event: done\ndata: {"question": {}, "answer": {}}\n\n';
  const fetch = async (url, init) => {
    calls.push({ method: init.method.toLowerCase(), path: new URL(url).pathname });
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(done));
        controller.close();
      },
    });
    return { ok: true, status: 200, text: async () => "{}", body };
  };
  const client = new BackendClient("http://backend", { fetch });
  await client.listChats();
  await client.createChat();
  await client.getChat(7);
  await client.deleteChat(7);
  await client.sendMessage(7, "ciao");
  await client.sendMessageStream(7, "ciao", () => {});
  return calls;
}

const template = (path) => path.replace(/\/\d+(?=\/|$)/g, "/{chat_id}");

test("every request of the client is an operation of the contract", async () => {
  const calls = await clientRequests();
  assert.equal(calls.length, 6);
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
    ["post", "/chats/{chat_id}/messages", "400"],
    ["post", "/chats/{chat_id}/messages", "404"],
    ["post", "/chats/{chat_id}/messages", "502"],
    ["post", "/chats/{chat_id}/messages", "503"],
    ["post", "/chats/{chat_id}/messages", "504"],
  ];
  for (const [method, path, status] of errors) {
    const content = contract.paths[path][method].responses[status].content["application/json"];
    const where = `${method} ${path} ${status}`;
    assert.equal(content.schema.$ref, "#/components/schemas/ErrorBody", where);
  }
});

test("the question is sent as the body SendMessageRequest", () => {
  for (const path of ["/chats/{chat_id}/messages", "/chats/{chat_id}/messages/stream"]) {
    const body = contract.paths[path].post.requestBody;
    assert.equal(
      body.content["application/json"].schema.$ref, "#/components/schemas/SendMessageRequest",
      path,
    );
  }
});

test("the stream answers text/event-stream, its errors before the stream use ErrorBody", () => {
  const operation = contract.paths["/chats/{chat_id}/messages/stream"].post;
  assert.ok(operation.responses["200"].content["text/event-stream"]);
  for (const status of ["400", "404", "502", "503", "504"]) {
    const content = operation.responses[status].content["application/json"];
    assert.equal(content.schema.$ref, "#/components/schemas/ErrorBody", status);
  }
  // the events the page reads are described in the contract
  for (const event of ["question", "text", "reset", "tool_start", "tool_end", "done", "error"]) {
    assert.ok(operation.description.includes(`\`${event}\``), `evento ${event} non descritto`);
  }
});

test("the messages of a chat and of the answer to a question are ChatMessageInfo", () => {
  const { schemas } = contract.components;
  const message = "#/components/schemas/ChatMessageInfo";
  assert.equal(schemas.ChatDetail.properties.messages.items.$ref, message);
  assert.equal(schemas.SendMessageResponse.properties.question.$ref, message);
  assert.equal(schemas.SendMessageResponse.properties.answer.$ref, message);
});
