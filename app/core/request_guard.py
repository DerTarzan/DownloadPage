"""Schutz vor Ressourcenerschöpfung durch Request-Bodys (SEC-001).

FastAPI liest bei Formular-/Datei-Endpunkten den kompletten Body, BEVOR die Dependencies (Authentifizierung)
laufen. Diese Middleware sitzt davor und
  1. weist schreibende Anfragen an /api/admin ohne gültige Session ab, ohne den Body zu lesen (401),
  2. begrenzt die Body-Größe: per Content-Length sofort, bei gestreamten Bodys (chunked) beim Lesen (413).
Die Grenzen sind konfigurierbar (MAX_PDF_SIZE_MB, MAX_IMAGE_SIZE_MB, MAX_REQUEST_BODY_KB).
Ein Reverse Proxy sollte zusätzlich ein eigenes Limit setzen (client_max_body_size).
"""
import re

from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.services.auth_service import AuthService

SESSION_COOKIE = "session_token"  # muss zu app.dependencies.SESSION_COOKIE passen (Test stellt das sicher)
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
ADMIN_API_PREFIX = "/api/admin"
MULTIPART_OVERHEAD = 1024 * 1024  # Formularfelder + Multipart-Rahmen neben der eigentlichen Datei

_DOCUMENT_UPLOAD = re.compile(r"^/api/admin/products/\d+/documents$")
_DOCUMENT_REPLACE = re.compile(r"^/api/admin/documents/\d+/file$")
_IMAGE_UPLOAD = re.compile(r"^/api/admin/(categories|products)/\d+/image$")


def body_limit(method: str, path: str, settings: Settings) -> int:
    """Maximale Body-Größe in Bytes für diese Anfrage."""
    if (method == "POST" and _DOCUMENT_UPLOAD.match(path)) or (method == "PUT" and _DOCUMENT_REPLACE.match(path)):
        return settings.max_pdf_bytes + MULTIPART_OVERHEAD
    if method == "POST" and _IMAGE_UPLOAD.match(path):
        return settings.max_image_bytes + MULTIPART_OVERHEAD
    return settings.max_request_body_kb * 1024


def _session_is_valid(token: str) -> bool:
    with SessionLocal() as db:
        return AuthService(db).validate_session(token) is not None


def _reject(status_code: int, detail: str) -> JSONResponse:
    # "Connection: close": der ungelesene Body darf die Verbindung nicht für weitere Anfragen blockieren
    return JSONResponse({"detail": detail}, status_code=status_code, headers={"Connection": "close"})


class RequestGuardMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method, path = scope["method"], scope["path"]
        limit = body_limit(method, path, get_settings())

        # 1. Admin-Schreibzugriffe nur mit gültiger Session, geprüft BEVOR der Body gelesen wird.
        #    (Rolle und CSRF prüfen weiterhin die Dependencies; hier geht es nur um "kein anonymes Body-Lesen".)
        if method not in SAFE_METHODS and path.startswith(ADMIN_API_PREFIX):
            token = Request(scope).cookies.get(SESSION_COOKIE)
            if not token or not await run_in_threadpool(_session_is_valid, token):
                await _reject(401, "Nicht authentifiziert")(scope, receive, send)
                return

        # 2. Angekündigte Größe prüfen (ohne den Body zu lesen)
        declared = Headers(scope=scope).get("content-length")
        if declared is not None:
            try:
                size = int(declared)
            except ValueError:
                await _reject(400, "Ungültiger Content-Length-Header")(scope, receive, send)
                return
            if size > limit:
                await _reject(413, "Anfrage ist zu groß")(scope, receive, send)
                return

        # 3. Gestreamte Bodys (chunked, oder gelogene Content-Length) beim Lesen mitzählen
        received = 0
        rejected = False
        started = False

        async def guarded_receive() -> Message:
            nonlocal received, rejected
            if rejected:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    rejected = True
                    if not started:
                        await _reject(413, "Anfrage ist zu groß")(scope, receive, send)
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal started
            if rejected:
                return  # die App darf nach unserer 413-Antwort (bzw. dem Abbruch) nichts mehr senden
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        await self.app(scope, guarded_receive, guarded_send)
