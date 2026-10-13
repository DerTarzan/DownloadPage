from tests.conftest import ADMIN_PASSWORD, ADMIN_USER, make_category


def test_default_settings(admin):
    r = admin.get("/api/admin/settings")
    assert r.status_code == 200 and r.json()["maintenance_mode"] is False


def test_enable_and_disable_maintenance_mode(admin, anon, document):
    make_category(admin, "Sichtbar")
    assert anon.get("/").status_code == 200

    r = admin.put("/api/admin/settings", json={"maintenance_mode": True, "maintenance_message": "Bin gleich zurück"})
    assert r.status_code == 200 and r.json() == {"maintenance_mode": True, "maintenance_message": "Bin gleich zurück"}

    # Besucher: alle öffentlichen Routen sind gesperrt
    for url in ("/", "/rollstuehle", "/rollstuehle/produkt-a", f"/documents/{document['id']}/download"):
        r = anon.get(url)
        assert r.status_code == 503, url
        assert r.json()["maintenance"] is True and "Bin gleich zurück" in r.json()["detail"]
        assert r.headers["retry-after"]
    html = anon.get("/", headers={"accept": "text/html"})
    assert html.status_code == 503 and "Bin gleich zurück" in html.text
    assert "/admin" not in html.text

    # Admin kommt weiterhin überall hin
    assert admin.get("/").status_code == 200
    assert admin.get(f"/documents/{document['id']}/download").status_code == 200
    assert admin.get("/api/admin/categories").status_code == 200

    r = admin.put("/api/admin/settings", json={"maintenance_mode": False})
    assert r.json()["maintenance_mode"] is False and r.json()["maintenance_message"] == "Bin gleich zurück"
    assert anon.get("/").status_code == 200


def test_admin_cannot_be_locked_out(admin, anon, admin_user):
    admin.put("/api/admin/settings", json={"maintenance_mode": True})
    # Login, Admin-Seiten und Admin-API bleiben auch für neue Sessions erreichbar
    assert anon.get("/admin/login", headers={"accept": "text/html"}).status_code == 200
    r = anon.post("/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    anon.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    assert anon.put("/api/admin/settings", json={"maintenance_mode": False}).status_code == 200
    assert anon.get("/health").status_code == 200


def test_settings_require_admin(anon):
    assert anon.put("/api/admin/settings", json={"maintenance_mode": True}).status_code == 401
