"""Admin-Bereich: Chatbot an-/ausschalten und Live-Logs (Ringpuffer, Backlog-API, SSE-Stream)."""
import asyncio
import json
import logging

import pytest

from app.core.config import get_settings
from app.core.log_buffer import LogBuffer, LogBufferHandler, install_log_buffer, log_buffer, source_of
from app.routers import admin_logs
from tests.conftest import make_category, make_product

HTML = {"accept": "text/html"}
CHAT = "/api/chat"
CHATBOT = "/api/admin/chatbot"


@pytest.fixture(autouse=True)
def _fresh_buffer():
    install_log_buffer()
    log_buffer.clear()
    app_logger = logging.getLogger("app")
    previous = app_logger.level
    app_logger.setLevel(logging.INFO)  # die Testumgebung läuft mit LOG_LEVEL=WARNING, Produktion mit INFO (Audit-/Chat-Zeilen)
    yield
    app_logger.setLevel(previous)
    log_buffer.clear()


@pytest.fixture
def shop(admin):
    cat = make_category(admin, "Rollatoren")
    make_product(admin, cat["id"], "Rollator STF 300")


# ---------------------------------------------------------------- Chatbot-Schalter
def test_chatbot_is_on_by_default(admin):
    assert admin.get(CHATBOT).json() == {"enabled": True, "available": True, "active": True}


def test_chatbot_can_be_disabled_and_enabled_again(admin, anon, shop):
    assert anon.post(CHAT, json={"message": "Rollator"}).status_code == 200
    assert "chat-root" in anon.get("/", headers=HTML).text

    assert admin.put(CHATBOT, json={"enabled": False}).json() == {"enabled": False, "available": True, "active": False}
    assert anon.post(CHAT, json={"message": "Rollator"}).status_code == 404  # API sperrt sofort
    for url in ("/", "/rollatoren", "/gibt-es-nicht"):
        assert "chat-root" not in anon.get(url, headers=HTML).text, url  # Widget verschwindet auf allen öffentlichen Seiten

    assert admin.put(CHATBOT, json={"enabled": True}).json()["active"] is True
    assert anon.post(CHAT, json={"message": "Rollator"}).status_code == 200
    assert "chat-root" in anon.get("/", headers=HTML).text


def test_server_config_still_overrules_the_switch(admin, anon, monkeypatch):
    monkeypatch.setattr(get_settings(), "chat_enabled", False)
    state = admin.get(CHATBOT).json()
    assert state == {"enabled": True, "available": False, "active": False}
    assert "chat-root" not in anon.get("/", headers=HTML).text
    assert anon.post(CHAT, json={"message": "x"}).status_code == 404


def test_chatbot_endpoints_require_admin_and_csrf(admin, anon):
    assert anon.get(CHATBOT).status_code == 401
    assert anon.put(CHATBOT, json={"enabled": False}).status_code == 401
    del admin.headers["X-CSRF-Token"]
    assert admin.put(CHATBOT, json={"enabled": False}).status_code == 403
    assert "chat-root" in admin.get("/", headers=HTML).text  # nichts wurde geändert


def test_chatbot_validates_payload(admin):
    assert admin.put(CHATBOT, json={}).status_code == 422
    assert admin.put(CHATBOT, json={"enabled": "vielleicht"}).status_code == 422


def test_switch_change_is_written_to_the_audit_log(admin):
    admin.put(CHATBOT, json={"enabled": False})
    messages = [e["message"] for e in log_buffer.since(0) if e["source"] == "audit"]
    assert any("Chatbot deaktiviert" in m for m in messages)


def test_settings_page_contains_the_chatbot_switch(admin):
    page = admin.get("/admin/settings", headers=HTML).text
    assert 'id="cb"' in page and "Chatbot" in page and "/static/js/admin_settings.js" in page


# ---------------------------------------------------------------- Chat-Logzeile ohne Nachrichtentext
def test_chat_logs_metadata_but_never_the_message_text(shop, anon):
    secret = "Geheimer Suchbegriff 4711"# pragma: allowlist secret
    assert anon.post(CHAT, json={"message": secret}).status_code == 200
    entries = [e for e in log_buffer.since(0) if e["source"] == "chat"]
    assert len(entries) == 1 and "lang=de" in entries[0]["message"] and "antwort=" in entries[0]["message"]
    assert "4711" not in json.dumps(log_buffer.since(0))


# ---------------------------------------------------------------- Ringpuffer
def test_buffer_is_a_bounded_ring_with_increasing_ids():
    buf = LogBuffer(max_entries=3)
    for i in range(5):
        buf.append({"message": str(i)})
    assert [e["message"] for e in buf.since(0)] == ["2", "3", "4"]
    assert [e["id"] for e in buf.since(0)] == [3, 4, 5] and buf.last_id() == 5


def test_buffer_since_returns_only_newer_entries_oldest_first():
    buf = LogBuffer()
    for i in range(6):
        buf.append({"message": str(i)})
    assert [e["id"] for e in buf.since(4)] == [5, 6]
    assert [e["id"] for e in buf.since(0, limit=2)] == [5, 6]  # Rückblick = die neuesten
    assert buf.since(6) == [] and buf.since(99) == []


def test_handler_records_level_source_and_exceptions():
    buf = LogBuffer()
    logger = logging.getLogger("app.chat.test")
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    handler = LogBufferHandler(buf)
    logger.addHandler(handler)
    try:
        logger.warning("Hallo %s", "Welt")
        try:
            raise ValueError("kaputt")
        except ValueError:
            logger.exception("Fehler")
    finally:
        logger.removeHandler(handler)
    first, second = buf.since(0)
    assert first["level"] == "WARNING" and first["source"] == "chat" and first["message"] == "Hallo Welt" and "exc" not in first
    assert second["level"] == "ERROR" and "ValueError: kaputt" in second["exc"]


def test_handler_truncates_huge_messages():
    buf = LogBuffer()
    logger = logging.getLogger("app.truncate.test")
    logger.propagate = False
    handler = LogBufferHandler(buf)
    logger.addHandler(handler)
    try:
        logger.error("x" * 50_000)
    finally:
        logger.removeHandler(handler)
    assert len(buf.since(0)[0]["message"]) == 2000


def test_noise_is_not_recorded():
    buf = LogBuffer()
    logger = logging.getLogger("uvicorn.access.test")
    handler = LogBufferHandler(buf)
    record = lambda path: logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d', ("1.2.3.4", "GET", path, "1.1", 200), None)  # noqa: E731
    for path in ("/health", "/api/admin/logs/stream?after=3", "/api/admin/logs"):
        handler.handle(record(path))
    handler.handle(record("/rollatoren"))
    assert [e["message"] for e in buf.since(0)] == ['1.2.3.4 - "GET /rollatoren HTTP/1.1" 200']
    del logger


def test_sources():
    assert source_of("uvicorn.access") == "access" and source_of("app.audit") == "audit" and source_of("app.chat") == "chat"
    assert source_of("uvicorn.error") == "server" and source_of("app.errors") == "app" and source_of("sqlalchemy") == "system"


def test_install_is_idempotent():
    root = logging.getLogger()
    before = sum(isinstance(h, LogBufferHandler) for h in root.handlers)
    install_log_buffer()
    install_log_buffer()
    assert sum(isinstance(h, LogBufferHandler) for h in root.handlers) == before >= 1
    logging.getLogger("app.once").warning("nur einmal")
    assert sum(e["message"] == "nur einmal" for e in log_buffer.since(0)) == 1


# ---------------------------------------------------------------- Backlog-API
def test_logs_api_returns_recent_entries(admin):
    logging.getLogger("app.test").warning("Eintrag A")
    data = admin.get("/api/admin/logs").json()
    assert data["last_id"] >= 1
    assert any(e["message"] == "Eintrag A" and e["level"] == "WARNING" for e in data["entries"])
    last = data["last_id"]
    logging.getLogger("app.test").warning("Eintrag B")
    newer = admin.get(f"/api/admin/logs?after={last}").json()["entries"]
    assert [e["message"] for e in newer] == ["Eintrag B"]


def test_logs_api_validates_parameters(admin):
    assert admin.get("/api/admin/logs?limit=0").status_code == 422
    assert admin.get("/api/admin/logs?limit=5000").status_code == 422
    assert admin.get("/api/admin/logs?after=-1").status_code == 422


@pytest.mark.parametrize("url", ["/api/admin/logs", "/api/admin/logs/stream"])
def test_logs_require_an_admin_session(anon, url):
    assert anon.get(url).status_code == 401
    assert anon.get("/admin/logs", headers=HTML, follow_redirects=False).headers["location"] == "/admin/login"


# ---------------------------------------------------------------- Stream (SSE)
def parse_sse(text: str):
    events = []
    for block in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "data" in fields:
            events.append((fields["id"], fields["event"], json.loads(fields["data"])))
    return events


def test_stream_sends_backlog_as_server_sent_events(admin, monkeypatch):
    monkeypatch.setattr(admin_logs, "STREAM_MAX_SECONDS", 0.3)
    monkeypatch.setattr(admin_logs, "POLL_INTERVAL", 0.05)
    logging.getLogger("app.test").error("Ä Umlaut-Test")
    r = admin.get("/api/admin/logs/stream")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "no-cache" in r.headers["cache-control"] and r.headers["x-accel-buffering"] == "no"
    assert r.text.startswith("retry: 3000")
    events = parse_sse(r.text)
    assert [ev[1] for ev in events] == ["log"] * len(events)
    assert any(ev[2]["message"] == "Ä Umlaut-Test" and ev[0] == str(ev[2]["id"]) for ev in events)  # id = Last-Event-ID


def test_stream_resumes_after_last_event_id(admin, monkeypatch):
    monkeypatch.setattr(admin_logs, "STREAM_MAX_SECONDS", 0.2)
    monkeypatch.setattr(admin_logs, "POLL_INTERVAL", 0.05)
    log = logging.getLogger("app.test")
    log.warning("eins")
    log.warning("zwei")
    seen = log_buffer.last_id()
    log.warning("drei")
    ids = [ev[2]["message"] for ev in parse_sse(admin.get("/api/admin/logs/stream", headers={"Last-Event-ID": str(seen)}).text)]
    assert ids == ["drei"]
    ids = [ev[2]["message"] for ev in parse_sse(admin.get(f"/api/admin/logs/stream?after={seen}").text)]
    assert ids == ["drei"]


def test_stream_delivers_entries_that_arrive_while_connected():
    """Direkter Test des Generators: ein Eintrag, der nach dem Start erscheint, kommt ohne neuen Request an."""
    buf = LogBuffer()
    buf.append({"ts": "t", "level": "INFO", "logger": "x", "source": "app", "message": "alt"})

    async def run():
        got = []

        async def reader():
            async for chunk in admin_logs.event_stream(None, buf.last_id(), buf, max_seconds=1.5):
                got.append(chunk)

        task = asyncio.create_task(reader())
        await asyncio.sleep(0.2)
        buf.append({"ts": "t", "level": "INFO", "logger": "x", "source": "app", "message": "neu"})
        await task
        return got

    chunks = asyncio.run(run())
    joined = "".join(chunks)
    assert "alt" not in joined and '"message": "neu"' in joined and "id: 2\n" in joined


def test_stream_sends_heartbeats_when_idle(monkeypatch):
    monkeypatch.setattr(admin_logs, "HEARTBEAT_SECONDS", 0.1)
    monkeypatch.setattr(admin_logs, "POLL_INTERVAL", 0.05)

    async def run():
        return [c async for c in admin_logs.event_stream(None, 0, LogBuffer(), max_seconds=0.5)]

    assert ": ping\n\n" in asyncio.run(run())


def test_stream_ends_by_itself(monkeypatch):
    async def run():
        return [c async for c in admin_logs.event_stream(None, 0, LogBuffer(), max_seconds=0.15)]

    assert asyncio.run(run())[0] == "retry: 3000\n\n"  # endet, statt ewig zu laufen (Browser verbindet neu)


def test_stream_does_not_hold_a_database_connection(admin, monkeypatch):
    """Die Anmeldeprüfung nutzt die DB nur kurz; während des Streams darf keine Verbindung belegt bleiben."""
    from app.core.database import engine

    monkeypatch.setattr(admin_logs, "STREAM_MAX_SECONDS", 0.2)
    monkeypatch.setattr(admin_logs, "POLL_INTERVAL", 0.05)
    seen = []
    original = admin_logs.event_stream

    async def spy(*args, **kwargs):
        seen.append(engine.pool.checkedout())
        async for chunk in original(*args, **kwargs):
            yield chunk

    monkeypatch.setattr(admin_logs, "event_stream", spy)
    assert admin.get("/api/admin/logs/stream").status_code == 200
    assert seen == [0]


# ---------------------------------------------------------------- Oberfläche
def test_logs_page_and_navigation(admin):
    page = admin.get("/admin/logs", headers=HTML)
    assert page.status_code == 200
    assert "Live-Logs" in page.text and "/static/js/admin_logs.js" in page.text and 'id="log-view"' in page.text
    assert 'href="/admin/logs"' in admin.get("/admin", headers=HTML).text  # Menüpunkt in der Navigation
    assert 'aria-current="page"' in page.text


def test_logs_script_never_inserts_html():
    from pathlib import Path

    for name in ("admin_logs.js", "admin_settings.js"):
        source = (Path(admin_logs.__file__).resolve().parents[1] / "static" / "js" / name).read_text(encoding="utf-8")
        assert "innerHTML" not in source and "outerHTML" not in source and "insertAdjacentHTML" not in source, name
