// State of the page, events and DOM. Talks only to the back-end, through BackendClient.
// The open chat is in the address of the page (#/chats/<id>): reloading finds it again.

import { BackendClient, BackendError } from "./api.js";
import {
  TEXTS, chatSubtitle, errorMessage, formatDate, questionSaved, toolDetail, toolsSummary,
  visibleMessages,
} from "./texts.js";

const backendUrl = (window.APP_CONFIG && window.APP_CONFIG.backendUrl) || "";
const client = new BackendClient(backendUrl);

const state = {
  chats: [], // ChatInfo of the back-end, most recent first
  listLoading: false,
  openId: null, // id in the address of the page
  openChat: null, // ChatDetail of the open chat, once read
  openLoading: false,
  pending: new Map(), // chat id → {text, started}: questions waiting for their answer
  drafts: new Map(), // chat id → text written and not sent, while another chat is open
};

const element = (id) => document.getElementById(id);

// --- errors ---

function showError(error) {
  element("error-text").textContent = errorMessage(error, backendUrl);
  element("error").hidden = false;
}

function clearError() {
  element("error").hidden = true;
  element("error-text").textContent = "";
}

const isMissingChat = (error) => error instanceof BackendError && error.code === "chat_not_found";

// --- rendering (texts always as textContent, never as HTML) ---

function renderList() {
  const list = element("chat-list");
  list.replaceChildren();
  for (const chat of state.chats) {
    const item = document.createElement("li");

    const open = document.createElement("button");
    open.type = "button";
    open.className = "chat-open";
    open.dataset.chatId = String(chat.id);
    if (chat.id === state.openId) {
      open.setAttribute("aria-current", "true");
    }
    const name = document.createElement("span");
    name.className = "chat-name";
    name.textContent = chat.title;
    const date = document.createElement("span");
    date.className = "chat-date";
    date.textContent = chatSubtitle(chat);
    open.append(name, date);
    open.addEventListener("click", () => selectChat(chat.id));

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "chat-delete";
    remove.textContent = "Elimina";
    remove.setAttribute("aria-label", TEXTS.deleteLabel(chat.title));
    remove.addEventListener("click", () => deleteChat(chat));

    item.append(open, remove);
    list.append(item);
  }
  let status = "";
  if (state.listLoading) {
    status = TEXTS.loading;
  } else if (state.chats.length === 0) {
    status = TEXTS.noChats;
  }
  element("chats-status").textContent = status;
}

function messageItem(message, pending = false) {
  const item = document.createElement("li");
  item.className = `message ${message.role}${pending ? " pending" : ""}`;
  const text = document.createElement("p");
  text.className = "message-text";
  text.textContent = message.content;
  item.append(text);
  if (message.created_at) {
    const time = document.createElement("time");
    time.className = "message-time";
    time.dateTime = message.created_at;
    time.textContent = formatDate(message.created_at);
    item.append(time);
  }
  const tools = message.tools_used || [];
  if (tools.length > 0) {
    const details = document.createElement("details");
    details.className = "tools";
    const summary = document.createElement("summary");
    summary.textContent = toolsSummary(tools);
    details.append(summary);
    for (const tool of tools) {
      const detail = document.createElement("pre");
      detail.textContent = toolDetail(tool);
      details.append(detail);
    }
    item.append(details);
  }
  return item;
}

const secondsSince = (started) => Math.floor((Date.now() - started) / 1000);

function renderMessages(messages, pending) {
  const list = element("messages");
  list.replaceChildren(...messages.map((message) => messageItem(message)));
  if (pending) {
    list.append(messageItem({ role: "user", content: pending.text }, true));
    const waiting = document.createElement("li");
    waiting.id = "waiting";
    waiting.className = "waiting";
    waiting.setAttribute("role", "status");
    waiting.textContent = TEXTS.waiting(secondsSince(pending.started));
    list.append(waiting);
  }
  if (list.lastElementChild) {
    list.lastElementChild.scrollIntoView({ block: "nearest" });
  }
}

function renderView() {
  const chat = state.openChat;
  const pending = chat ? state.pending.get(chat.id) : undefined;
  const messages = chat ? visibleMessages(chat.messages, pending ? pending.text : null) : [];
  element("chat-title").textContent = chat ? chat.title : "";
  let status = "";
  if (state.openId === null) {
    status = TEXTS.noSelection;
  } else if (state.openLoading) {
    status = TEXTS.loading;
  } else if (chat !== null && messages.length === 0 && !pending) {
    status = TEXTS.noMessages;
  }
  element("chat-status").textContent = status;
  renderMessages(messages, pending);
  // one question at a time per chat: only the chat that is waiting cannot send
  element("composer").hidden = chat === null;
  element("message-input").disabled = Boolean(pending);
  element("send").disabled = Boolean(pending);
}

function render() {
  renderList();
  renderView();
}

// --- address of the page ---

function idFromAddress() {
  const match = /^#\/chats\/(\d+)$/.exec(window.location.hash);
  return match ? Number(match[1]) : null;
}

function clearAddress() {
  // replaceState does not fire "hashchange": the caller updates the state itself
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
}

// The text written in the field belongs to the open chat: it is kept when another one opens.
function switchDraft(id) {
  const input = element("message-input");
  if (state.openId !== null) {
    state.drafts.set(state.openId, input.value);
  }
  input.value = state.drafts.get(id) ?? "";
}

function selectChat(id) {
  clearError();
  if (id === idFromAddress()) {
    openFromAddress();
  } else {
    window.location.hash = `#/chats/${id}`; // "hashchange" opens it
  }
}

// --- operations ---

async function loadChats() {
  state.listLoading = true;
  renderList();
  try {
    state.chats = await client.listChats();
    // the first question gives the chat its title: the open chat takes it from the list
    const info = state.chats.find((chat) => chat.id === state.openId);
    if (info && state.openChat !== null && state.openChat.id === info.id) {
      state.openChat.title = info.title;
      element("chat-title").textContent = info.title; // the messages are not drawn again
    }
  } catch (error) {
    showError(error);
  } finally {
    state.listLoading = false;
    renderList();
  }
}

// Reads the open chat `id` from the back-end; the view keeps what it shows until the answer.
async function readOpenChat(id) {
  try {
    const chat = await client.getChat(id);
    if (state.openId !== id) {
      return; // the user opened another chat meanwhile
    }
    state.openChat = chat;
  } catch (error) {
    if (state.openId !== id) {
      return;
    }
    showError(error);
    if (isMissingChat(error)) {
      clearAddress();
      state.openId = null;
      state.openChat = null;
      loadChats();
    }
  }
  state.openLoading = false;
  render();
  if (state.openChat !== null && !state.pending.has(id)) {
    element("message-input").focus();
  }
}

function openFromAddress() {
  const id = idFromAddress();
  if (id !== state.openId) {
    switchDraft(id);
  }
  state.openId = id;
  state.openChat = null;
  state.openLoading = id !== null;
  render();
  if (id !== null) {
    readOpenChat(id);
  }
}

async function createChat() {
  clearError();
  const button = element("new-chat");
  button.disabled = true;
  try {
    const chat = await client.createChat();
    state.chats = [chat, ...state.chats.filter((other) => other.id !== chat.id)];
    renderList();
    selectChat(chat.id);
  } catch (error) {
    showError(error);
  } finally {
    button.disabled = false;
  }
}

async function deleteChat(chat) {
  clearError();
  if (!window.confirm(TEXTS.confirmDelete(chat.title))) {
    return;
  }
  try {
    await client.deleteChat(chat.id);
  } catch (error) {
    showError(error);
    if (!isMissingChat(error)) {
      return;
    }
    loadChats(); // already deleted elsewhere: the list is read again
  }
  state.chats = state.chats.filter((other) => other.id !== chat.id);
  state.drafts.delete(chat.id);
  if (state.openId === chat.id) {
    clearAddress();
    state.openId = null;
    state.openChat = null;
    state.openLoading = false;
  }
  render();
}

// --- sending a question ---

let waitingTimer = null;

// Every second: the seconds of the open chat's waiting line; stops when nothing waits.
function updateWaiting() {
  const pending = state.pending.get(state.openId);
  const line = element("waiting");
  if (pending && line) {
    line.textContent = TEXTS.waiting(secondsSince(pending.started));
  }
  if (state.pending.size === 0) {
    clearInterval(waitingTimer);
    waitingTimer = null;
  }
}

// The text of a question that was not saved goes back to the field of its chat, unless the user
// has meanwhile written something else there.
function restoreText(id, text) {
  const input = element("message-input");
  if (state.openId === id) {
    if (input.value.trim() === "") {
      input.value = text;
    }
  } else if (!(state.drafts.get(id) || "").trim()) {
    state.drafts.set(id, text);
  }
}

async function sendMessage(event) {
  event.preventDefault();
  const id = state.openId;
  const input = element("message-input");
  const text = input.value.trim();
  if (id === null || state.openChat === null || text === "" || state.pending.has(id)) {
    return;
  }
  clearError();
  input.value = "";
  state.pending.set(id, { text, started: Date.now() });
  if (waitingTimer === null) {
    waitingTimer = setInterval(updateWaiting, 1000);
  }
  renderView();
  try {
    const { question, answer } = await client.sendMessage(id, text);
    state.pending.delete(id);
    if (state.openId === id && state.openChat !== null) {
      const saved = new Set([question.id, answer.id]); // the question may be there already
      const earlier = state.openChat.messages.filter((message) => !saved.has(message.id));
      state.openChat.messages = [...earlier, question, answer];
      renderView();
      input.focus();
    }
  } catch (error) {
    state.pending.delete(id);
    if (!questionSaved(error)) {
      restoreText(id, text);
    }
    if (state.openId === id) {
      showError(error);
      renderView();
      readOpenChat(id); // shows the question if the back-end saved it
    }
  }
  loadChats(); // title and date of the last message
}

function sendOnEnter(event) {
  // Enter sends, Shift+Enter starts a new line; not while composing an accented letter
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    element("composer").requestSubmit();
  }
}

// --- start ---

element("new-chat").addEventListener("click", createChat);
element("composer").addEventListener("submit", sendMessage);
element("message-input").addEventListener("keydown", sendOnEnter);
element("error-close").addEventListener("click", clearError);
window.addEventListener("hashchange", openFromAddress);

render();
loadChats();
openFromAddress();
