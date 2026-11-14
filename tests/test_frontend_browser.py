"""The real page in the browser installed on the computer (Edge, or Chrome with
BROWSER_CHANNEL=chrome), driven by Playwright without a window.

The back-end is the real app on SQLite in memory, with CORS for the front-end; both services run
with uvicorn on free ports in threads of this process. Marker `browser`: pytest -m browser.
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

from backend.api import create_app as create_backend_app
from backend.db import Base, create_db_engine, init_db
from backend.store import AgentState, ChatStore
from frontend.app import create_app as create_frontend_app
from frontend.config import FrontendConfig

pytestmark = pytest.mark.browser

NO_CHATS = 'Nessuna chat. Premi "Nuova chat" per iniziare.'
NO_SELECTION = "Seleziona una chat o creane una nuova."
NO_MESSAGES = "Nessun messaggio: scrivi la prima domanda."


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


class NoAgent:
    """The chat operations of this step never call the agent."""

    def chat(self, *args, **kwargs):
        raise AssertionError("l'agente non deve essere chiamato")


@pytest.fixture(scope="module")
def engine():
    engine = create_db_engine("sqlite://")
    init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def services(engine) -> Iterator[tuple[str, str]]:
    """(front-end URL, back-end URL), the back-end accepting the page of the front-end."""
    backend_port, frontend_port = free_port(), free_port()
    frontend_origin = f"http://127.0.0.1:{frontend_port}"
    backend_app = create_backend_app(
        store=ChatStore(engine), agent=NoAgent(), cors_origins=(frontend_origin,)
    )
    with ServerThread(backend_app, backend_port) as backend:
        frontend_app = create_frontend_app(FrontendConfig(backend_url=backend.url))
        with ServerThread(frontend_app, frontend_port) as frontend:
            yield frontend.url, backend.url


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
