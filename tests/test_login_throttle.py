"""Regressionstests SEC-002 (Proxy-IP, Login-Bremse) und SEC-005 (Speicher, Argon2-Parallelität), SEC-014 (Log)."""
import logging
import re
import threading
import time
from pathlib import Path

import uvicorn
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.config import get_settings
from app.main import app
from app.services import auth_service
from app.services.auth_service import LoginThrottle
from tests.conftest import ADMIN_PASSWORD, ADMIN_USER

ROOT = Path(__file__).resolve().parent.parent


def _login(client, user=ADMIN_USER, password="falsch", **headers):
    return client.post("/auth/login", json={"username": user, "password": password}, headers=headers)


# ---- LoginThrottle (Einheit) ----
def test_reading_does_not_create_entries():
    throttle = LoginThrottle(5, 300)
    for i in range(200):
        assert throttle.is_blocked("1.2.3.4", f"user{i}") is False
    assert throttle._fails == {}


def test_user_counter_blocks_only_that_account():
    throttle = LoginThrottle(3, 300, max_attempts_per_ip=100)
    for _ in range(3):
        throttle.register_failure("1.2.3.4", "admin")
    assert throttle.is_blocked("1.2.3.4", "admin") is True
    assert throttle.is_blocked("1.2.3.4", "anderer") is False
    assert throttle.is_blocked("5.6.7.8", "admin") is False


def test_ip_counter_blocks_username_rotation():
    throttle = LoginThrottle(5, 300, max_attempts_per_ip=10)
    for i in range(10):
        throttle.register_failure("1.2.3.4", f"user{i}")  # jedes Mal ein anderer Benutzername
    assert throttle.is_blocked("1.2.3.4", "frischer-name") is True
    assert throttle.is_blocked("5.6.7.8", "frischer-name") is False


def test_entries_expire_and_are_removed():
    throttle = LoginThrottle(2, 0.05)
    throttle.register_failure("1.2.3.4", "admin")
    throttle.register_failure("1.2.3.4", "admin")
    assert throttle.is_blocked("1.2.3.4", "admin") is True
    time.sleep(0.1)
    assert throttle.is_blocked("1.2.3.4", "admin") is False
    assert throttle._fails == {}  # abgelaufene Schlüssel werden entfernt, nicht nur geleert


def test_memory_is_bounded():
    throttle = LoginThrottle(5, 300)
    throttle.MAX_KEYS = 100
    for i in range(5000):
        throttle.register_failure(f"10.0.{i // 250}.{i % 250}", f"user{i}")
    assert len(throttle._fails) <= 100


def test_success_clears_only_the_user_counter():
    throttle = LoginThrottle(5, 300, max_attempts_per_ip=100)
    throttle.register_failure("1.2.3.4", "admin")
    throttle.clear_user("1.2.3.4", "admin")
    assert ("u|1.2.3.4|admin") not in throttle._fails and "i|1.2.3.4" in throttle._fails


# ---- Login-Endpunkt ----
def test_username_rotation_hits_ip_limit_through_the_endpoint(anon, admin_user):
    limit = get_settings().login_max_attempts_per_ip
    for i in range(limit):
        assert _login(anon, user=f"nobody{i}").status_code == 401
    # IP gesperrt: selbst das richtige Passwort wird nicht mehr geprüft
    assert _login(anon, password=ADMIN_PASSWORD).status_code == 429


def test_successful_login_resets_user_counter(anon, admin_user):
    for _ in range(get_settings().login_max_attempts - 1):
        assert _login(anon).status_code == 401
    assert _login(anon, password=ADMIN_PASSWORD).status_code == 200
    for _ in range(get_settings().login_max_attempts - 1):  # Zähler wieder bei 0: nochmal bis kurz vor die Sperre
        assert _login(anon).status_code == 401


def test_hash_slots_limit_concurrent_argon2_work(anon, admin_user, monkeypatch):
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(auth_service, "_hash_slots", slots)
    monkeypatch.setattr(auth_service, "HASH_SLOT_TIMEOUT_SECONDS", 0.05)
    assert slots.acquire(blocking=False)  # der einzige Platz ist belegt
    r = _login(anon, password=ADMIN_PASSWORD)
    assert r.status_code == 429 and "ausgelastet" in r.json()["detail"]
    slots.release()
    assert _login(anon, password=ADMIN_PASSWORD).status_code == 200
    assert slots.acquire(blocking=False)  # nach dem Login wurde der Platz wieder freigegeben
    slots.release()


def test_failed_login_releases_hash_slot(anon, admin_user, monkeypatch):
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(auth_service, "_hash_slots", slots)
    for _ in range(3):
        assert _login(anon).status_code == 401
    assert slots.acquire(blocking=False)


# ---- SEC-014: Log ----
def test_invalid_username_format_is_not_logged(anon, caplog):
    secret = "Mein Passwort 123!"
    with caplog.at_level(logging.WARNING, logger="app.audit"):
        assert _login(anon, user=secret).status_code == 401
        assert _login(anon, user="nobody").status_code == 401
    assert "Mein Passwort" not in caplog.text and "<ungültig>" in caplog.text
    assert "nobody" in caplog.text  # Benutzernamen im erlaubten Format bleiben für die Auswertung sichtbar


# ---- Proxy-Header: Verhalten mit uvicorns ProxyHeadersMiddleware (so läuft die App im Container) ----
def test_real_client_ip_is_used_from_trusted_proxy(admin_user):
    client = TestClient(ProxyHeadersMiddleware(app, trusted_hosts="10.0.0.1"), client=("10.0.0.1", 5000))
    for _ in range(get_settings().login_max_attempts):
        assert _login(client, **{"X-Forwarded-For": "198.51.100.7"}).status_code == 401
    assert _login(client, password=ADMIN_PASSWORD, **{"X-Forwarded-For": "198.51.100.7"}).status_code == 429
    # ein anderer Besucher hinter demselben Proxy ist NICHT mitgesperrt (Admin kann sich einloggen)
    assert _login(client, password=ADMIN_PASSWORD, **{"X-Forwarded-For": "198.51.100.8"}).status_code == 200


def test_x_forwarded_for_is_ignored_from_untrusted_peer(admin_user):
    client = TestClient(ProxyHeadersMiddleware(app, trusted_hosts="10.0.0.1"), client=("192.0.2.5", 5000))
    for i in range(get_settings().login_max_attempts):  # Angreifer wechselt bei jedem Versuch die "IP"
        assert _login(client, **{"X-Forwarded-For": f"203.0.113.{i}"}).status_code == 401
    assert _login(client, password=ADMIN_PASSWORD, **{"X-Forwarded-For": "203.0.113.99"}).status_code == 429


def test_uvicorn_reads_forwarded_allow_ips_from_environment(monkeypatch):
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "172.18.0.5")
    assert uvicorn.Config("app.main:app").forwarded_allow_ips == "172.18.0.5"


def test_proxy_trust_is_not_wildcard_by_default(monkeypatch):
    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)
    assert "*" not in str(uvicorn.Config("app.main:app").forwarded_allow_ips)
    for name in ("Dockerfile", "docker-compose.yml", ".env.example", ".env.local.example"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert re.search(r"forwarded[-_]allow[-_]ips[=\s'\"]+\*", text, re.IGNORECASE) is None, name
