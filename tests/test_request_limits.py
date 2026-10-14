"""Regressionstests SEC-001: kein Body-Lesen vor der Authentifizierung, Body-Größenlimits."""
import asyncio

import pytest

from app.core.config import get_settings
from app.core.request_guard import MULTIPART_OVERHEAD, RequestGuardMiddleware, body_limit
from tests.conftest import PDF_BYTES, upload_pdf

MB = 1024 * 1024
UPLOAD_URL = "/api/admin/products/1/documents"


def _call(method: str, path: str, headers: list[tuple[bytes, bytes]]):
    """Ruft die Middleware direkt auf einem ASGI-Level auf; liefert (gesendete Nachrichten, receive-Aufrufe, inner erreicht)."""
    state = {"receive": 0, "inner": False}
    sent: list[dict] = []

    async def inner(scope, receive, send):
        state["inner"] = True

    async def receive():
        state["receive"] += 1
        return {"type": "http.request", "body": b"x" * 1024, "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": method, "path": path, "query_string": b"", "headers": headers}
    asyncio.run(RequestGuardMiddleware(inner)(scope, receive, send))
    return sent, state


def test_body_is_not_read_for_anonymous_admin_write():
    sent, state = _call("POST", UPLOAD_URL, [(b"content-length", b"1048576")])
    assert sent[0]["status"] == 401
    assert state["receive"] == 0 and state["inner"] is False  # Body nie angefasst, App nie erreicht


def test_body_is_not_read_for_invalid_session_cookie():
    sent, state = _call("POST", UPLOAD_URL, [(b"cookie", b"session_token=gefaelscht")])
    assert sent[0]["status"] == 401
    assert state["receive"] == 0 and state["inner"] is False


def test_oversize_content_length_is_rejected_without_reading_body():
    limit = body_limit("POST", "/auth/login", get_settings())
    sent, state = _call("POST", "/auth/login", [(b"content-length", str(limit + 1).encode())])
    assert sent[0]["status"] == 413
    assert state["receive"] == 0 and state["inner"] is False


def test_invalid_content_length_is_rejected():
    sent, state = _call("POST", "/auth/login", [(b"content-length", b"abc")])
    assert sent[0]["status"] == 400 and state["inner"] is False


def test_public_get_and_safe_methods_pass_through():
    sent, state = _call("GET", "/", [])
    assert state["inner"] is True
    sent, state = _call("GET", "/api/admin/categories", [])  # GET hat keinen Body; Auth prüft die Dependency
    assert state["inner"] is True


def test_limits_per_endpoint_type():
    s = get_settings()
    assert body_limit("POST", UPLOAD_URL, s) == s.max_pdf_bytes + MULTIPART_OVERHEAD
    assert body_limit("PUT", "/api/admin/documents/3/file", s) == s.max_pdf_bytes + MULTIPART_OVERHEAD
    assert body_limit("POST", "/api/admin/categories/2/image", s) == s.max_image_bytes + MULTIPART_OVERHEAD
    assert body_limit("POST", "/api/admin/products/2/image", s) == s.max_image_bytes + MULTIPART_OVERHEAD
    assert body_limit("POST", "/api/admin/categories", s) == s.max_request_body_kb * 1024
    assert body_limit("POST", "/auth/login", s) == s.max_request_body_kb * 1024
    # Datei-Limits gelten nur für die Upload-Pfade, nicht für beliebige /api/admin-Pfade
    assert body_limit("POST", "/api/admin/products/x/documents", s) == s.max_request_body_kb * 1024


# ---- Ende-zu-Ende über die echte App ----
def test_anonymous_large_upload_is_rejected_with_401(anon, product):
    r = anon.post(
        f"/api/admin/products/{product['id'] if isinstance(product, dict) else 1}/documents",
        files={"file": ("a.pdf", b"%PDF-" + b"0" * (3 * MB), "application/pdf")},
    )
    assert r.status_code == 401 and "Traceback" not in r.text
    assert r.headers["x-content-type-options"] == "nosniff"  # Abweisung bekommt die Sicherheits-Header
    assert r.headers["cache-control"] == "no-store"


def test_authenticated_upload_over_hard_limit_gets_413_from_guard(admin, product):
    big = b"%PDF-" + b"0" * (3 * MB)  # Test-Limit: 1 MB Datei + 1 MB Overhead
    r = upload_pdf(admin, product["id"], content=big)
    assert r.status_code == 413 and r.json()["detail"] == "Anfrage ist zu groß"


def test_streamed_body_without_content_length_is_limited(admin, product):
    boundary = "testboundary"

    def chunks():  # Generator => "Transfer-Encoding: chunked", kein Content-Length-Header
        yield (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="a.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n%PDF-"
        ).encode()
        for _ in range(3):
            yield b"0" * MB
        yield f"\r\n--{boundary}--\r\n".encode()

    r = admin.post(
        f"/api/admin/products/{product['id']}/documents",
        content=chunks(),
        headers={"content-type": f"multipart/form-data; boundary={boundary}"},
    )
    assert r.status_code == 413 and r.json()["detail"] == "Anfrage ist zu groß"


def test_large_json_body_is_limited(admin):
    r = admin.post("/api/admin/categories", json={"name": "X", "description": "a" * (2 * MB)})
    assert r.status_code == 413


def test_login_body_is_limited(anon):
    r = anon.post("/auth/login", json={"username": "a", "password": "b" * (2 * MB)})
    assert r.status_code == 413


def test_upload_between_service_limit_and_hard_limit_still_gets_service_413(admin, product):
    r = upload_pdf(admin, product["id"], content=b"%PDF-1.4\n" + b"0" * (MB + 10))
    assert r.status_code == 413 and r.json()["detail"] != "Anfrage ist zu groß"  # kommt vom FileService


def test_normal_uploads_still_work(admin, product):
    assert upload_pdf(admin, product["id"], content=PDF_BYTES).status_code == 201


def test_session_cookie_name_matches_dependencies():
    from app import dependencies
    from app.core import request_guard

    assert request_guard.SESSION_COOKIE == dependencies.SESSION_COOKIE


@pytest.mark.parametrize("method,url", [("PUT", "/api/admin/documents/1/file"), ("POST", "/api/admin/categories/1/image")])
def test_other_upload_endpoints_reject_anonymous_before_body(anon, method, url):
    r = anon.request(method, url, files={"file": ("a.png", b"0" * (3 * MB), "image/png")})
    assert r.status_code == 401
