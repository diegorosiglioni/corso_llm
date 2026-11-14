// State of the page, events and DOM. Talks only to the back-end, through BackendClient.
// The open chat is in the address of the page (#/chats/<id>): reloading finds it again.

import { BackendClient, BackendError } from "./api.js";
import { TEXTS, chatSubtitle, errorMessage } from "./texts.js";

const backendUrl = (window.APP_CONFIG && window.APP_CONFIG.backendUrl) || "";
const client = new BackendClient(backendUrl);

const state = {
  chats: [], // ChatInfo of the back-end, most recent first
  listLoading: false,
  openId: null, // id in the address of the page
  openChat: null, // ChatDetail of the open chat, once read
  openLoading: false,
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

function renderView() {
  const chat = state.openChat;
  element("chat-title").textContent = chat ? chat.title : "";
  let status = "";
  if (state.openId === null) {
    status = TEXTS.noSelection;
  } else if (state.openLoading) {
    status = TEXTS.loading;
  } else if (chat !== null && chat.messages.length === 0) {
    status = TEXTS.noMessages;
  }
  element("chat-status").textContent = status;
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
  } catch (error) {
    showError(error);
  } finally {
    state.listLoading = false;
    renderList();
  }
}

async function openFromAddress() {
  const id = idFromAddress();
  state.openId = id;
  state.openChat = null;
  state.openLoading = id !== null;
  render();
  if (id === null) {
    return;
  }
  try {
    const chat = await client.getChat(id);
    if (idFromAddress() !== id) {
      return; // the user opened another chat meanwhile
    }
    state.openChat = chat;
  } catch (error) {
    if (idFromAddress() !== id) {
      return;
    }
    showError(error);
    if (isMissingChat(error)) {
      clearAddress();
      state.openId = null;
      loadChats();
    }
  }
  state.openLoading = false;
  render();
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
  if (state.openId === chat.id) {
    clearAddress();
    state.openId = null;
    state.openChat = null;
    state.openLoading = false;
  }
  render();
}

// --- start ---

element("new-chat").addEventListener("click", createChat);
element("error-close").addEventListener("click", clearError);
window.addEventListener("hashchange", openFromAddress);

render();
loadChats();
openFromAddress();
