"""Regressionstests SEC-003: sichere Produktionsvorlage, Start-Warnungen, Port-Bindung."""
import importlib.util
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app

ROOT = Path(__file__).resolve().parent.parent


def _parse_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def _load_generate_env():
    spec = importlib.util.spec_from_file_location("generate_env", ROOT / "scripts" / "generate_env.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_production_template_is_secure_by_default():
    env = _parse_env(ROOT / ".env.example")
    assert env["ENVIRONMENT"] == "production"
    assert env["COOKIE_SECURE"] == "true"
    assert env["DOCS_ENABLED"] == "false"
    assert env["APP_BIND"] == "127.0.0.1"
    # keine bekannten Schwachpasswörter in der Vorlage: Geheimnisse sind leer und müssen erzeugt werden
    for key in ("SECRET_KEY", "ADMIN_PASSWORD", "POSTGRES_PASSWORD"):
        assert env[key] == "", key


def test_local_template_is_explicitly_development():
    env = _parse_env(ROOT / ".env.local.example")
    assert env["ENVIRONMENT"] == "development"
    assert env["COOKIE_SECURE"] == "false"  # nur lokal über http
    for key in ("SECRET_KEY", "ADMIN_PASSWORD", "POSTGRES_PASSWORD"):
        assert env[key] == "", key


@pytest.mark.parametrize("template", [".env.example", ".env.local.example"])
def test_generate_env_fills_secrets_and_keeps_other_values(template, tmp_path):
    gen = _load_generate_env()
    values = gen.generate_values("chef")
    result = gen.render((ROOT / template).read_text(encoding="utf-8"), values)
    out = tmp_path / ".env"
    out.write_text(result, encoding="utf-8")
    env = _parse_env(out)
    assert len(env["SECRET_KEY"]) >= 32 and env["POSTGRES_PASSWORD"] and len(env["ADMIN_PASSWORD"]) >= 12
    assert env["ADMIN_USERNAME"] == "chef"
    original = _parse_env(ROOT / template)
    assert env["COOKIE_SECURE"] == original["COOKIE_SECURE"]  # Sicherheitswerte der Vorlage bleiben erhalten
    assert env["DOCS_ENABLED"] == original["DOCS_ENABLED"]


def test_generated_admin_password_meets_policy():
    from app.services.auth_service import MIN_PASSWORD_LENGTH

    gen = _load_generate_env()
    assert len(gen.generate_values("admin")["ADMIN_PASSWORD"]) >= MIN_PASSWORD_LENGTH


def test_compose_binds_app_port_to_localhost_by_default():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert '"${APP_BIND:-127.0.0.1}:${APP_PORT:-8000}:8000"' in compose
    assert '- "${APP_PORT:-8000}:8000"' not in compose


def test_compose_does_not_include_a_reverse_proxy():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "caddy" not in compose.lower()
    assert "proxy:" not in compose
    assert '"80:80"' not in compose and '"443:443"' not in compose
    assert '"${APP_BIND:-127.0.0.1}:${APP_PORT:-8000}:8000"' in compose


def _settings(**overrides) -> Settings:
    base = dict(database_url="sqlite://", secret_key="x" * 40, environment="production", cookie_secure=True, docs_enabled=False)
    return Settings(_env_file=None, **{**base, **overrides})


def test_no_warnings_for_secure_production_config():
    assert _settings().production_warnings() == []


def test_warnings_for_insecure_production_config():
    warnings = _settings(cookie_secure=False, docs_enabled=True).production_warnings()
    assert len(warnings) == 2
    assert any("COOKIE_SECURE" in w for w in warnings) and any("DOCS_ENABLED" in w for w in warnings)


def test_no_warnings_outside_production():
    assert _settings(environment="development", cookie_secure=False, docs_enabled=True).production_warnings() == []
    assert _settings(environment="test", cookie_secure=False, docs_enabled=True).production_warnings() == []


def test_startup_logs_warning_for_insecure_production(monkeypatch, caplog):
    insecure = _settings(cookie_secure=False, docs_enabled=True)
    monkeypatch.setattr("app.main.get_settings", lambda: insecure)
    with caplog.at_level(logging.WARNING, logger="app"):
        with TestClient(app):  # löst den lifespan (Start) aus
            pass
    assert "Unsichere Produktionskonfiguration" in caplog.text
