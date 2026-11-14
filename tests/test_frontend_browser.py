"""The real page in the browser installed on the computer (Edge, or Chrome with
BROWSER_CHANNEL=chrome), driven by Playwright without a window.

The back-end is the real app on SQLite in memory, with CORS for the front-end, and a fake agent
the tests control (its stream of events too); both services run with uvicorn on free ports in
threads of this process.
Marker `browser`: pytest -m browser.
"""

import os
import re
import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn
from playwright.sync_api import Browser, Page, expect, sync_playwright

from assistant.api_client import AgentError
from backend.api import create_app as create_backend_app
from backend.db import Base, create_db_engine, init_db
from backend.store import AgentState, ChatStore
from frontend.app import create_app as create_frontend_app
from frontend.config import FrontendConfig

pytestmark = pytest.mark.browser

NO_CHATS = 'Nessuna chat. Premi "Nuova chat" per iniziare.'
NO_SELECTION = "Seleziona una chat o creane una nuova."
NO_MESSAGES = "Nessun messaggio: scrivi la prima domanda."
TIME = re.compile(r"^\d{2}:\d{2}$")
WAITING = re.compile(r"^L'assistente sta rispondendo… \(\d+ s\)$")
CALCULATE = {"name": "calculate", "args": {"expression": "17 * 23"}, "result": 391, "ok": True}
FAILED = {
    "name": "convert_units", "args": {"value": 1, "from_unit": "m", "to_unit": "kg"},
    "result": {"error": "unità incompatibili"}, "ok": False,
}


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class ServerThread:
    """An ASGI app served by uvicorn in a thread, on 127.0.0.1:`port`."""

    def __init__(self, app, port: int):
        self.url = f"http://127.0.0.1:{port}"
        config = uvicorn.Config(
            app, host="127.0.0.1", port=port, log_config=None, access_log=False
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def __enter__(self) -> "ServerThread":
        self._thread.start()
        deadline = time.monotonic() + 10
        while not self._server.started:
            if time.monotonic() > deadline or not self._thread.is_alive():
                raise RuntimeError(f"server su {self.url} non avviato")
            time.sleep(0.05)
        return self

    def __exit__(self, *exc) -> None:
        self._server.should_exit = True
        self._thread.join(10)


Event = tuple[str, dict]


class FakeAgent:
    """The agent behind the back-end, with the `chat_stream` method of AgentClient (the page
    sends with the streaming).

    `error`, when set, is raised before the stream (an agent that cannot be reached or refuses
    the request: a JSON answer of the back-end). Otherwise the stream waits for `gate` when it is
    an Event (a slow agent), then gives `events` — pairs (name, data), or Events to wait for
    before going on — by default tool_start and tool_end of every tool and the reply in two
    pieces; then raises `stream_error` when set (an error during the turn: an "error" event of
    the back-end) or ends with done: `reply` with `tools`. `calls` records the messages received.
    """

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.reply = "17 * 23 fa 391."
        self.tools: list[dict] = [CALCULATE]
        self.error: Exception | None = None
        self.stream_error: Exception | None = None
        self.gate: threading.Event | None = None
        self.events: list[Event | threading.Event] | None = None
        self.calls: list[str] = []

    def waits(self) -> list[threading.Event]:
        """The Events the stream may wait for: set at the end of every test."""
        return [item for item in [self.gate, *(self.events or [])]
                if isinstance(item, threading.Event)]

    def default_events(self) -> list[Event]:
        events: list[Event] = []
        for number, tool in enumerate(self.tools):
            call = {"id": f"call-{number}", "name": tool["name"], "args": tool["args"]}
            events += [("tool_start", call), ("tool_end", {**call, **tool})]
        half = len(self.reply) // 2
        return [*events, ("text", {"delta": self.reply[:half]}),
                ("text", {"delta": self.reply[half:]})]

    def chat_stream(self, history, summary, *, message=None, prompt=None):
        self.calls.append(message)
        if self.error is not None:
            raise self.error
        return self._stream(history, summary, message)

    def _stream(self, history, summary, message):
        if self.gate is not None:
            self.gate.wait(30)
        for item in self.default_events() if self.events is None else self.events:
            if isinstance(item, threading.Event):
                item.wait(30)
            else:
                yield item
        if self.stream_error is not None:
            raise self.stream_error
        turn = [{"role": "user", "content": message}, {"role": "assistant", "content": self.reply}]
        yield "done", {
            "reply": self.reply, "tools_used": self.tools,
            "history": [*history, *turn], "summary": summary,
        }


@pytest.fixture(scope="module")
def engine():
    engine = create_db_engine("sqlite://")
    init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def module_agent() -> FakeAgent:
    return FakeAgent()


@pytest.fixture(autouse=True)
def agent(module_agent) -> Iterator[FakeAgent]:
    """The fake agent, reset for every test; a waiting answer is let go at the end."""
    module_agent.reset()
    yield module_agent
    for wait in module_agent.waits():
        wait.set()


class Services:
    """Back-end on the chat archive and front-end of its page, served on free ports."""

    def __init__(self, engine, agent: FakeAgent):
        frontend_port = free_port()
        backend_app = create_backend_app(
            store=ChatStore(engine), agent=agent,
            cors_origins=(f"http://127.0.0.1:{frontend_port}",),
        )
        self.backend = ServerThread(backend_app, free_port())
        frontend_app = create_frontend_app(FrontendConfig(backend_url=self.backend.url))
        self.frontend = ServerThread(frontend_app, frontend_port)

    def __enter__(self) -> "Services":
        self.backend.__enter__()
        self.frontend.__enter__()
        return self

    def __exit__(self, *exc) -> None:
        self.frontend.__exit__(*exc)
        self.backend.__exit__(*exc)


@pytest.fixture(scope="module")
def services(engine, module_agent) -> Iterator[tuple[str, str]]:
    """(front-end URL, back-end URL), the back-end accepting the page of the front-end."""
    with Services(engine, module_agent) as running:
        yield running.frontend.url, running.backend.url


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    channel = os.environ.get("BROWSER_CHANNEL", "msedge")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=channel, headless=True)
        yield browser
        browser.close()


@pytest.fixture
def store(engine) -> ChatStore:
    """An empty archive for every test."""
    Base.metadata.drop_all(engine)
    init_db(engine)
    return ChatStore(engine)


@pytest.fixture
def page(browser) -> Iterator[Page]:
    """A new page; at the end no uncaught JavaScript error may have happened."""
    context = browser.new_context(locale="it-IT")
    page = context.new_page()
    page.set_default_timeout(10_000)
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    yield page
    context.close()
    assert errors == [], f"errori JavaScript nella pagina: {errors}"


def open_page(page: Page, url: str) -> None:
    page.goto(url)
    expect(page.locator("#chats-status")).not_to_have_text("Caricamento…")


def chat_buttons(page: Page):
    return page.locator("#chat-list .chat-open")


def chat_button(page: Page, title: str):
    """The button that opens the chat `title` in the list."""
    return chat_buttons(page).filter(has=page.locator(".chat-name", has_text=title))


def delete_button(page: Page, title: str):
    return page.get_by_role("button", name=f"Elimina la chat {title}", exact=True)


def messages(page: Page):
    """The messages shown in the open chat, the question waiting for its answer included."""
    return page.locator("#messages .message")


def field(page: Page):
    return page.locator("#message-input")


def send_button(page: Page):
    return page.get_by_role("button", name="Invia", exact=True)


def send(page: Page, text: str) -> None:
    field(page).fill(text)
    field(page).press("Enter")


# --- list ---

def test_empty_list(page, services, store):  # CA-84
    frontend_url, _ = services
    open_page(page, frontend_url)
    expect(page).to_have_title("Assistente del laboratorio")
    expect(page.locator("#chats-status")).to_have_text(NO_CHATS)
    expect(page.locator("#chat-status")).to_have_text(NO_SELECTION)
    expect(chat_buttons(page)).to_have_count(0)
    expect(page.locator("#error")).to_be_hidden()


def test_list_most_recent_first_with_dates(page, services, store):  # CA-84
    old = store.create_chat("Conversioni")
    store.add_question(old.id, "Quanti km sono 10 miglia?")
    store.add_answer(old.id, "Circa 16,09 km.", [], AgentState([], ""))
    store.create_chat("Vuota")
    frontend_url, _ = services
    open_page(page, frontend_url)
    expect(chat_buttons(page).locator(".chat-name")).to_have_text(["Vuota", "Conversioni"])
    dates = chat_buttons(page).locator(".chat-date")
    expect(dates.nth(0)).to_have_text("nessun messaggio")
    expect(dates.nth(1)).to_have_text(re.compile(r"^\d{2}:\d{2}$"))
    expect(page.locator("#chats-status")).to_have_text("")


# --- creation and selection ---

def test_new_chat_appears_on_top_and_opens(page, services, store):  # CA-84
    store.create_chat("Esistente")
    frontend_url, _ = services
    open_page(page, frontend_url)
    page.get_by_role("button", name="Nuova chat").click()
    expect(chat_buttons(page)).to_have_count(2)
    first = chat_buttons(page).first
    expect(first.locator(".chat-name")).to_have_text("Nuova chat")
    expect(first.locator(".chat-date")).to_have_text("nessun messaggio")
    expect(first).to_have_attribute("aria-current", "true")
    [created] = [chat for chat in store.list_chats() if chat.title is None]
    expect(page).to_have_url(f"{frontend_url}/#/chats/{created.id}")
    expect(page.locator("#chat-title")).to_have_text("Nuova chat")
    expect(page.locator("#chat-status")).to_have_text(NO_MESSAGES)
    assert len(store.list_chats()) == 2


def test_selecting_a_chat_opens_it(page, services, store):  # CA-84
    alpha = store.create_chat("Alfa")
    store.create_chat("Beta")
    frontend_url, _ = services
    open_page(page, frontend_url)
    chat_button(page, "Alfa").click()
    expect(page).to_have_url(f"{frontend_url}/#/chats/{alpha.id}")
    expect(page.locator("#chat-title")).to_have_text("Alfa")
    expect(page.locator("#chat-list .chat-open[aria-current='true']")).to_have_count(1)
    current = page.locator("#chat-list .chat-open[aria-current='true'] .chat-name")
    expect(current).to_have_text("Alfa")
    chat_button(page, "Beta").click()
    expect(page.locator("#chat-title")).to_have_text("Beta")
    expect(current).to_have_text("Beta")


def test_reload_keeps_the_open_chat(page, services, store):  # CA-84
    chat = store.create_chat("Da ritrovare")
    frontend_url, _ = services
    open_page(page, f"{frontend_url}/#/chats/{chat.id}")
    expect(page.locator("#chat-title")).to_have_text("Da ritrovare")
    page.reload()
    expect(page.locator("#chat-title")).to_have_text("Da ritrovare")
    expect(page.locator("#chat-list .chat-open[aria-current='true'] .chat-name")).to_have_text(
        "Da ritrovare"
    )


def test_missing_chat_in_the_address(page, services, store):  # CA-84
    store.create_chat("Presente")
    frontend_url, _ = services
    open_page(page, f"{frontend_url}/#/chats/999")
    expect(page.locator("#error-text")).to_have_text("Questa chat non esiste più.")
    expect(page.locator("#chat-status")).to_have_text(NO_SELECTION)
    expect(page).to_have_url(f"{frontend_url}/")
    expect(chat_buttons(page)).to_have_count(1)


# --- deletion ---

def test_delete_after_confirming(page, services, store):  # CA-84
    keep = store.create_chat("Da tenere")
    gone = store.create_chat("Da eliminare")
    frontend_url, _ = services
    open_page(page, f"{frontend_url}/#/chats/{gone.id}")
    expect(page.locator("#chat-title")).to_have_text("Da eliminare")
    dialogs = []

    def accept(dialog):
        dialogs.append((dialog.type, dialog.message))
        dialog.accept()

    page.once("dialog", accept)
    delete_button(page, "Da eliminare").click()
    expect(chat_buttons(page)).to_have_count(1)
    assert dialogs == [
        ("confirm", 'Eliminare la chat "Da eliminare"? Anche i suoi messaggi saranno cancellati.')
    ]
    expect(page.locator("#chat-status")).to_have_text(NO_SELECTION)
    expect(page.locator("#chat-title")).to_have_text("")
    expect(page).to_have_url(f"{frontend_url}/")
    assert [chat.id for chat in store.list_chats()] == [keep.id]


def test_delete_of_another_chat_keeps_the_open_one(page, services, store):  # CA-84
    open_chat = store.create_chat("Aperta")
    store.create_chat("Altra")
    frontend_url, _ = services
    open_page(page, f"{frontend_url}/#/chats/{open_chat.id}")
    page.once("dialog", lambda dialog: dialog.accept())
    delete_button(page, "Altra").click()
    expect(chat_buttons(page)).to_have_count(1)
    expect(page.locator("#chat-title")).to_have_text("Aperta")
    expect(page).to_have_url(f"{frontend_url}/#/chats/{open_chat.id}")


def test_delete_cancelled(page, services, store):  # CA-84
    store.create_chat("Resta")
    frontend_url, _ = services
    open_page(page, frontend_url)
    page.once("dialog", lambda dialog: dialog.dismiss())
    delete_button(page, "Resta").click()
    expect(chat_buttons(page)).to_have_count(1)
    assert [chat.title for chat in store.list_chats()] == ["Resta"]


def test_delete_of_a_chat_already_deleted(page, services, store):  # CA-84
    chat = store.create_chat("Già eliminata")
    frontend_url, _ = services
    open_page(page, frontend_url)
    store.delete_chat(chat.id)  # deleted from another page meanwhile
    page.once("dialog", lambda dialog: dialog.accept())
    delete_button(page, "Già eliminata").click()
    expect(page.locator("#error-text")).to_have_text("Questa chat non esiste più.")
    expect(chat_buttons(page)).to_have_count(0)
    expect(page.locator("#chats-status")).to_have_text(NO_CHATS)


# --- errors and texts ---

def test_backend_switched_off(page, browser):  # CA-85 (list and creation)
    closed = f"http://127.0.0.1:{free_port()}"
    app = create_frontend_app(FrontendConfig(backend_url=closed))
    with ServerThread(app, free_port()) as frontend:
        open_page(page, frontend.url)
        message = f"Il back-end non risponde ({closed}). Controlla che sia avviato e riprova."
        expect(page.locator("#error-text")).to_have_text(message)
        expect(page.locator("#error")).to_have_attribute("role", "alert")
        page.get_by_role("button", name="Chiudi").click()
        expect(page.locator("#error")).to_be_hidden()
        page.get_by_role("button", name="Nuova chat").click()  # the page is still usable
        expect(page.locator("#error-text")).to_have_text(message)
        expect(page.get_by_role("button", name="Nuova chat")).to_be_enabled()


def test_html_in_a_title_is_shown_as_text(page, services, store):  # CA-85
    title = '<img src=x onerror="window.injected=1"><b>grassetto</b>'
    chat = store.create_chat(title)
    frontend_url, _ = services
    open_page(page, f"{frontend_url}/#/chats/{chat.id}")
    expect(page.locator("#chat-title")).to_have_text(title)
    expect(chat_buttons(page).locator(".chat-name")).to_have_text(title)
    assert page.locator("#chat-list b, #chat-list img, #chat-title b, #chat-title img").count() == 0
    assert page.evaluate("window.injected") is None


# --- messages and sending (CA-85) ---

def test_messages_in_order_with_time_and_tools(page, services, store):  # CA-85
    chat = store.create_chat("Calcoli")
    store.add_question(chat.id, "Quanto fa 17 * 23?")
    store.add_answer(chat.id, "Fa 391.", [CALCULATE, FAILED], AgentState([], ""))
    frontend_url, _ = services
    open_page(page, f"{frontend_url}/#/chats/{chat.id}")
    expect(messages(page).locator(".message-text")).to_have_text(["Quanto fa 17 * 23?", "Fa 391."])
    expect(messages(page).nth(0)).to_have_class("message user")
    expect(messages(page).nth(1)).to_have_class("message assistant")
    expect(messages(page).locator(".message-time")).to_have_text([TIME, TIME])
    expect(messages(page).nth(0).locator("details")).to_have_count(0)
    expect(page.locator("#chat-status")).to_have_text("")
    expect(field(page)).to_be_focused()  # the field is ready for the next question
    tools = messages(page).nth(1).locator("details.tools")
    expect(tools.locator("summary")).to_have_text(
        "Strumenti usati: calculate, convert_units (errore)"
    )
    expect(tools.locator("pre").first).to_be_hidden()
    tools.locator("summary").click()
    assert tools.locator("pre").all_inner_texts() == [
        'calculate\nargomenti: {"expression":"17 * 23"}\nrisultato: 391',
        'convert_units (errore)\nargomenti: {"value":1,"from_unit":"m","to_unit":"kg"}\n'
        'risultato: {"error":"unità incompatibili"}',
    ]


def test_send_with_waiting_state_and_tools(page, services, store, agent):  # CA-85
    chat = store.create_chat()
    agent.gate = threading.Event()
    frontend_url, _ = services
    open_page(page, f"{frontend_url}/#/chats/{chat.id}")
    expect(page.locator("#chat-status")).to_have_text(NO_MESSAGES)
    expect(field(page)).to_have_attribute("placeholder", "Scrivi una domanda…")
    send(page, "  Quanto fa 17 * 23?  ")
    pending = page.locator("#messages .message.pending")
    expect(pending).to_have_text("Quanto fa 17 * 23?")
    expect(pending).to_have_class("message user pending")
    waiting = page.locator("#waiting")
    expect(waiting).to_have_text(WAITING)
    expect(waiting).to_have_text(re.compile(r"\((?:[1-9]\d*) s\)$"))  # the seconds go on
    expect(field(page)).to_be_disabled()
    expect(send_button(page)).to_be_disabled()
    expect(page.locator("#chat-status")).to_have_text("")
    agent.gate.set()
    expect(pending).to_have_count(0)
    expect(waiting).to_have_count(0)
    expect(messages(page).locator(".message-text")).to_have_text(
        ["Quanto fa 17 * 23?", "17 * 23 fa 391."]
    )
    expect(messages(page).nth(1).locator("summary")).to_have_text("Strumenti usati: calculate")
    expect(field(page)).to_be_enabled()
    expect(field(page)).to_have_value("")
    expect(field(page)).to_be_focused()
    # the first question gives the title, the list shows it with the date of the answer
    expect(page.locator("#chat-title")).to_have_text("Quanto fa 17 * 23?")
    expect(chat_buttons(page).first.locator(".chat-name")).to_have_text("Quanto fa 17 * 23?")
    expect(chat_buttons(page).first.locator(".chat-date")).to_have_text(TIME)
    assert agent.calls == ["Quanto fa 17 * 23?"]
    _, saved = store.get_chat(chat.id)
    assert [(message.role, message.content) for message in saved] == [
        ("user", "Quanto fa 17 * 23?"), ("assistant", "17 * 23 fa 391."),
    ]


def test_empty_text_not_sent_and_shift_enter_new_line(page, services, store, agent):  # CA-85
    chat = store.create_chat("Righe")
    frontend_url, _ = services
    open_page(page, f"{frontend_url}/#/chats/{chat.id}")
    send(page, "   ")
    send_button(page).click()
    expect(messages(page)).to_have_count(0)
    field(page).fill("")
    field(page).press_sequentially("prima riga")
    field(page).press("Shift+Enter")
    field(page).press_sequentially("seconda riga")
    expect(field(page)).to_have_value("prima riga\nseconda riga")
    send_button(page).click()
    expect(messages(page).locator(".message-text")).to_have_count(2)
    assert messages(page).locator(".message-text").first.inner_text() == "prima riga\nseconda riga"
    assert agent.calls == ["prima riga\nseconda riga"]  # the empty texts sent nothing


def test_other_chats_usable_while_waiting(page, services, store, agent):  # CA-85, RF-73
    first = store.create_chat("Prima")
    agent.gate = threading.Event()
    frontend_url, _ = services
    open_page(page, f"{frontend_url}/#/chats/{first.id}")
    send(page, "Domanda lenta")
    expect(page.locator("#waiting")).to_be_visible()
    page.get_by_role("button", name="Nuova chat").click()
    expect(page.locator("#chat-title")).to_have_text("Nuova chat")
    expect(page.locator("#waiting")).to_have_count(0)
    expect(field(page)).to_be_enabled()  # only the chat that waits cannot send
    field(page).fill("bozza della nuova chat")
    chat_button(page, "Prima").click()
    expect(page.locator("#waiting")).to_be_visible()
    expect(messages(page)).to_have_count(1)  # the question already saved is not shown twice
    expect(field(page)).to_be_disabled()
    chat_button(page, "Nuova chat").click()
    expect(field(page)).to_have_value("bozza della nuova chat")
    # the answer arrives while another chat is open: only the list changes
    agent.gate.set()
    expect(chat_button(page, "Prima").locator(".chat-date")).to_have_text(TIME)
    expect(page.locator("#chat-title")).to_have_text("Nuova chat")
    expect(messages(page)).to_have_count(0)
    expect(page.locator("#chat-status")).to_have_text(NO_MESSAGES)
    chat_button(page, "Prima").click()
    expect(messages(page).locator(".message-text")).to_have_text(
        ["Domanda lenta", "17 * 23 fa 391."]
    )
    expect(field(page)).to_be_enabled()


def test_agent_switched_off(page, services, store, agent):  # CA-85, RF-74
    chat = store.create_chat("Spento")
    agent.error = AgentError("agent_unreachable", "agente non raggiungibile")
    frontend_url, _ = services
    open_page(page, f"{frontend_url}/#/chats/{chat.id}")
    send(page, "Ci sei?")
    expect(page.locator("#error-text")).to_have_text(
        "L'assistente non è raggiungibile in questo momento. La domanda è salvata nella chat: "
        "riprova più tardi."
    )
    expect(messages(page).locator(".message-text")).to_have_text(["Ci sei?"])  # saved question
    expect(messages(page)).to_have_class(["message user"])
    expect(page.locator("#waiting")).to_have_count(0)
    expect(field(page)).to_be_enabled()
    expect(field(page)).to_have_value("")  # saved: the text does not come back
    expect(chat_button(page, "Spento").locator(".chat-date")).to_have_text(TIME)
    page.get_by_role("button", name="Nuova chat").click()  # the page is still usable
    expect(chat_buttons(page)).to_have_count(2)
    expect(page.locator("#chat-title")).to_have_text("Nuova chat")
    expect(page.locator("#error")).to_be_hidden()


def test_agent_error_with_the_detail(page, services, store, agent):  # CA-85, RF-74
    chat = store.create_chat("Errore")
    agent.error = AgentError("model_unavailable", "LM Studio non risponde")
    frontend_url, _ = services
    open_page(page, f"{frontend_url}/#/chats/{chat.id}")
    send(page, "Che ore sono?")
    expect(page.locator("#error-text")).to_have_text(
        "L'assistente ha risposto con un errore: l'agente ha risposto con un errore "
        "(model_unavailable): LM Studio non risponde. La domanda è salvata nella chat: riprova."
    )
    expect(messages(page).locator(".message-text")).to_have_text(["Che ore sono?"])
    expect(field(page)).to_be_enabled()


def test_chat_deleted_before_sending(page, services, store, agent):  # CA-85, RF-74
    chat = store.create_chat("Sparita")
    frontend_url, _ = services
    open_page(page, f"{frontend_url}/#/chats/{chat.id}")
    expect(page.locator("#chat-title")).to_have_text("Sparita")
    store.delete_chat(chat.id)  # deleted from another page meanwhile
    send(page, "Ci sei?")
    expect(page.locator("#error-text")).to_have_text("Questa chat non esiste più.")
    expect(page.locator("#chat-status")).to_have_text(NO_SELECTION)
    expect(page.locator("#composer")).to_be_hidden()
    expect(chat_buttons(page)).to_have_count(0)
    assert agent.calls == []


def test_backend_switched_off_while_sending(page, engine, store, agent):  # CA-85, RF-74
    chat = store.create_chat("Senza back-end")
    running = Services(engine, agent).__enter__()
    try:
        open_page(page, f"{running.frontend.url}/#/chats/{chat.id}")
        expect(page.locator("#chat-title")).to_have_text("Senza back-end")
    finally:
        running.backend.__exit__(None, None, None)
    try:
        send(page, "Mi senti?")
        backend_url = running.backend.url
        expect(page.locator("#error-text")).to_have_text(
            f"Il back-end non risponde ({backend_url}). Controlla che sia avviato e riprova."
        )
        expect(page.locator("#waiting")).to_have_count(0)
        expect(field(page)).to_be_enabled()
        expect(field(page)).to_have_value("Mi senti?")  # not saved: the text comes back
        page.get_by_role("button", name="Chiudi").click()
        expect(page.locator("#error")).to_be_hidden()
    finally:
        running.frontend.__exit__(None, None, None)
    assert agent.calls == []


def test_html_in_messages_is_shown_as_text(page, services, store, agent):  # CA-85
    question = '<script>window.injected=1</script><b>domanda</b>'
    agent.reply = '<img src=x onerror="window.injected=2"><b>risposta</b>'
    agent.tools = [{
        "name": "<b>strumento</b>", "args": {"x": "<i>a</i>"},
        "result": '<img src=x onerror="window.injected=3">', "ok": True,
    }]
    chat = store.create_chat("HTML")
    frontend_url, _ = services
    open_page(page, f"{frontend_url}/#/chats/{chat.id}")
    send(page, question)
    expect(messages(page).locator(".message-text")).to_have_text([question, agent.reply])
    summary = messages(page).nth(1).locator("summary")
    expect(summary).to_have_text("Strumenti usati: <b>strumento</b>")
    summary.click()
    expect(messages(page).nth(1).locator("pre")).to_contain_text("<i>a</i>")
    assert page.locator("#messages b, #messages i, #messages img, #messages script").count() == 0
    assert page.evaluate("window.injected") is None


# --- the answer arriving with the streaming (CA-100) ---

DRAFT_LABEL = "Bozza: la risposta può ancora cambiare"
CALL = {"id": "call-1", "name": "calculate", "args": {"expression": "17 * 23"}}
CALCULATE_DETAIL = 'calculate\nargomenti: {"expression":"17 * 23"}\nrisultato: 391'


def draft(page: Page):
    return page.locator("#draft")


def test_text_arrives_in_pieces_with_the_tool(page, services, store, agent):  # CA-100
    chat = store.create_chat("Streaming")
    tool_ran, text_started = threading.Event(), threading.Event()
    agent.events = [
        ("tool_start", CALL), tool_ran, ("tool_end", {**CALL, "result": 391, "ok": True}),
        ("text", {"delta": "17 * 23 "}), text_started, ("text", {"delta": "fa 391."}),
    ]
    frontend_url, _ = services
    open_page(page, f"{frontend_url}/#/chats/{chat.id}")
    send(page, "Quanto fa 17 * 23?")
    # the tool is shown while the agent waits for it, under the waiting line
    expect(draft(page)).to_have_class("message assistant draft")
    expect(draft(page).locator(".draft-label")).to_have_text(DRAFT_LABEL)
    expect(draft(page).locator(".draft-tools li")).to_have_text(["Uso lo strumento calculate…"])
    expect(draft(page).locator(".draft-text")).to_have_count(0)
    expect(page.locator("#waiting")).to_have_text(WAITING)
    expect(page.locator("#messages > li")).to_have_count(3)  # question, waiting line, draft
    expect(field(page)).to_be_disabled()
    tool_ran.set()
    # the first piece of text before the end of the turn, the tool with its result
    expect(draft(page).locator(".draft-text")).to_have_text("17 * 23 ")
    assert draft(page).locator(".draft-tools li").all_inner_texts() == [CALCULATE_DETAIL]
    expect(page.locator("#waiting")).to_be_visible()
    # the draft is not a message: only the question has a message text
    expect(page.locator("#messages .message-text")).to_have_text(["Quanto fa 17 * 23?"])
    # another chat meanwhile, then back: the answer arriving is still there
    page.get_by_role("button", name="Nuova chat").click()
    expect(page.locator("#chat-title")).to_have_text("Nuova chat")
    expect(draft(page)).to_have_count(0)
    expect(field(page)).to_be_enabled()
    chat_button(page, "Streaming").click()
    expect(draft(page).locator(".draft-text")).to_have_text("17 * 23 ")
    # the question saved is not shown twice
    expect(page.locator("#messages .message.user")).to_have_count(1)
    text_started.set()
    # done: the saved messages in place of the question waiting and of the draft
    expect(draft(page)).to_have_count(0)
    expect(page.locator("#waiting")).to_have_count(0)
    expect(messages(page).locator(".message-text")).to_have_text(
        ["Quanto fa 17 * 23?", "17 * 23 fa 391."]
    )
    expect(messages(page)).to_have_class(["message user", "message assistant"])
    expect(messages(page).nth(1).locator("summary")).to_have_text("Strumenti usati: calculate")
    expect(field(page)).to_be_enabled()
    _, saved = store.get_chat(chat.id)
    assert [(m.role, m.content) for m in saved] == [
        ("user", "Quanto fa 17 * 23?"), ("assistant", "17 * 23 fa 391."),
    ]


def test_resets_for_tools_and_for_the_reviewer(page, services, store, agent):  # CA-100
    chat = store.create_chat("Revisore")
    first_draft, rewritten = threading.Event(), threading.Event()
    agent.events = [
        ("text", {"delta": "Ci penso"}), ("reset", {"reason": "tools", "detail": ""}),
        ("tool_start", CALL), ("tool_end", {**CALL, "result": 391, "ok": True}),
        ("text", {"delta": "Il calcolo è fatto."}), first_draft,
        ("reset", {"reason": "review", "detail": "La risposta non dà il risultato."}),
        ("text", {"delta": "17 * 23 fa 391."}), rewritten,
    ]
    frontend_url, _ = services
    open_page(page, f"{frontend_url}/#/chats/{chat.id}")
    send(page, "Quanto fa 17 * 23?")
    # reset for the tools: the text before the call is gone, without a notice
    expect(draft(page).locator(".draft-text")).to_have_text("Il calcolo è fatto.")
    expect(draft(page).locator(".draft-notice")).to_have_count(0)
    first_draft.set()
    # reset of the reviewer: the draft is written again, with the reason
    expect(draft(page).locator(".draft-notice")).to_have_text(
        "Il revisore ha chiesto di riscrivere la risposta: La risposta non dà il risultato."
    )
    expect(draft(page).locator(".draft-text")).to_have_text("17 * 23 fa 391.")
    assert draft(page).locator(".draft-tools li").all_inner_texts() == [CALCULATE_DETAIL]
    rewritten.set()
    expect(draft(page)).to_have_count(0)
    expect(messages(page).locator(".message-text")).to_have_text(
        ["Quanto fa 17 * 23?", "17 * 23 fa 391."]
    )


def test_error_during_the_stream(page, services, store, agent):  # CA-100, RF-84
    chat = store.create_chat("Interrotta")
    agent.events = [("text", {"delta": "Sto calcol"})]
    agent.stream_error = AgentError("model_unavailable", "LM Studio non risponde")
    frontend_url, _ = services
    open_page(page, f"{frontend_url}/#/chats/{chat.id}")
    send(page, "Quanto fa 17 * 23?")
    expect(page.locator("#error-text")).to_have_text(
        "L'assistente ha risposto con un errore: l'agente ha risposto con un errore "
        "(model_unavailable): LM Studio non risponde. La domanda è salvata nella chat: riprova."
    )
    expect(draft(page)).to_have_count(0)
    expect(page.locator("#waiting")).to_have_count(0)
    expect(messages(page).locator(".message-text")).to_have_text(["Quanto fa 17 * 23?"])
    expect(messages(page)).to_have_class(["message user"])
    expect(field(page)).to_be_enabled()
    expect(field(page)).to_have_value("")  # saved: the text does not come back
    _, saved = store.get_chat(chat.id)
    assert [(m.role, m.content) for m in saved] == [("user", "Quanto fa 17 * 23?")]
    page.get_by_role("button", name="Nuova chat").click()  # the page is still usable
    expect(page.locator("#chat-title")).to_have_text("Nuova chat")


def test_unexpected_error_of_the_backend_during_the_stream(page, services, store, agent):
    # CA-100: an exception that is not of the agent becomes "error" internal_error
    chat = store.create_chat("Guasto")
    agent.stream_error = RuntimeError("guasto imprevisto")
    frontend_url, _ = services
    open_page(page, f"{frontend_url}/#/chats/{chat.id}")
    send(page, "Ci sei?")
    expect(page.locator("#error-text")).to_have_text(
        "Errore del back-end durante la risposta: errore interno del back-end; dettagli nel log."
    )
    expect(messages(page).locator(".message-text")).to_have_text(["Ci sei?"])
    expect(field(page)).to_have_value("")
