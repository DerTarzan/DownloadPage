from sqlalchemy import select

from app.models.user import User
from tests.conftest import ADMIN_PASSWORD, ADMIN_USER


def test_admin_login_success(anon, admin_user):
    r = anon.post("/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["username"] == ADMIN_USER and body["csrf_token"]
    assert "password" not in str(body).lower()
    set_cookie = r.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie


def test_password_is_hashed_with_argon2(db, admin_user):
    stored = db.scalar(select(User.password_hash).where(User.username == ADMIN_USER))
    assert stored.startswith("$argon2") and ADMIN_PASSWORD not in stored


def test_wrong_password(anon, admin_user):
    r = anon.post("/auth/login", json={"username": ADMIN_USER, "password": "falsch"})
    assert r.status_code == 401
    assert "set-cookie" not in r.headers


def test_unknown_user_gets_same_error(anon, admin_user):
    a = anon.post("/auth/login", json={"username": "nobody", "password": "x"})
    b = anon.post("/auth/login", json={"username": ADMIN_USER, "password": "x"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_login_throttle(anon, admin_user):
    for _ in range(5):
        assert anon.post("/auth/login", json={"username": ADMIN_USER, "password": "falsch"}).status_code == 401
    assert anon.post("/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD}).status_code == 429


def test_me_requires_authentication(anon):
    assert anon.get("/auth/me").status_code == 401


def test_me_when_logged_in(admin):
    r = admin.get("/auth/me")
    assert r.status_code == 200 and r.json()["user"]["is_admin"] is True


def test_logout_invalidates_session(admin):
    assert admin.post("/auth/logout").status_code == 204
    assert admin.get("/auth/me").status_code == 401


def test_admin_endpoints_without_authentication(anon):
    for method, url in [
        ("GET", "/api/admin/categories"),
        ("POST", "/api/admin/categories"),
        ("GET", "/api/admin/products"),
        ("GET", "/api/admin/documents"),
        ("GET", "/api/admin/settings"),
        ("PUT", "/api/admin/settings"),
        ("DELETE", "/api/admin/documents/1"),
    ]:
        assert anon.request(method, url, json={}).status_code == 401, (method, url)


def test_csrf_token_required_for_writes(admin):
    del admin.headers["X-CSRF-Token"]
    assert admin.get("/api/admin/categories").status_code == 200  # lesen ohne Token ok
    r = admin.post("/api/admin/categories", json={"name": "X"})
    assert r.status_code == 403
    r = admin.post("/api/admin/categories", json={"name": "X"}, headers={"X-CSRF-Token": "falsch"})
    assert r.status_code == 403


def test_inactive_user_cannot_login_or_use_session(anon, admin, db, admin_user):
    user = db.get(User, admin_user.id)
    user.is_active = False
    db.commit()
    assert admin.get("/api/admin/categories").status_code == 401
    assert anon.post("/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD}).status_code == 401


def test_non_admin_is_forbidden(anon, db, admin_user):
    user = db.get(User, admin_user.id)
    user.is_admin = False
    db.commit()
    r = anon.post("/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    anon.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    assert anon.get("/api/admin/categories").status_code == 403


def test_validation_error_does_not_echo_input(anon):
    r = anon.post("/auth/login", json={"username": "x"})
    assert r.status_code == 422 and "input" not in r.text


def test_admin_html_pages_redirect_when_logged_out(anon):
    r = anon.get("/admin", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/admin/login"
    assert anon.get("/admin/login", headers={"accept": "text/html"}).status_code == 200
