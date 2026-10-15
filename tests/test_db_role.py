"""Regressionstests SEC-004: Laufzeit-Rolle ohne Superuser-Rechte, getrennte Migration.

Die statischen Tests laufen immer. Die Rechte-Tests brauchen ein echtes PostgreSQL (TEST_DATABASE_URL mit einem
Superuser, z. B. in der CI) und `psql` im PATH; sonst werden sie übersprungen.
"""
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "docker" / "postgres" / "01-app-role.sh"
APP_PASSWORD = "pw-mit-'Anfuehrung\"-und-$pecial"  # Sonderzeichen: Quoting muss stimmen


# ---------------------------------------------------------------- statische Prüfungen
def _compose() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def test_migrations_run_in_a_separate_service_with_owner_credentials():
    migrate = _compose()["services"]["migrate"]
    assert migrate["entrypoint"] == ["alembic", "upgrade", "head"]
    assert "${POSTGRES_USER}" in migrate["environment"]["DATABASE_URL"]
    assert migrate["restart"] == "no"


def test_app_waits_for_migration_and_uses_runtime_role():
    app = _compose()["services"]["app"]
    assert app["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
    assert app["environment"]["RUN_MIGRATIONS"] == "false"
    url = app["environment"]["DATABASE_URL"]
    assert "${APP_DB_USER:-${POSTGRES_USER}}" in url and "${APP_DB_PASSWORD:-${POSTGRES_PASSWORD}}" in url


def test_owner_credentials_are_not_passed_into_the_app_environment():
    env = _compose()["services"]["app"]["environment"]
    assert env["POSTGRES_USER"] == "" and env["POSTGRES_PASSWORD"] == ""  # überschreibt env_file: .env


def test_db_service_mounts_the_role_script():
    db = _compose()["services"]["db"]
    assert any("01-app-role.sh:/docker-entrypoint-initdb.d/01-app-role.sh" in v for v in db["volumes"])
    assert "APP_DB_USER" in db["environment"] and "APP_DB_PASSWORD" in db["environment"]
    assert "ports" not in db  # Datenbank bleibt unveröffentlicht


def test_entrypoint_can_skip_migrations():
    text_ = (ROOT / "docker-entrypoint.sh").read_text(encoding="utf-8")
    assert 'RUN_MIGRATIONS:-true' in text_ and "alembic upgrade head" in text_
    # Das Bit im Git-Index ist 644; das Image setzt es selbst.
    assert "chmod +x /app/docker-entrypoint.sh" in (ROOT / "Dockerfile").read_text(encoding="utf-8")


def test_role_script_is_safe_to_source():
    """Das Postgres-Image führt .sh-Dateien ohne Ausführungsrecht per source aus: kein exit/exec/set auf oberster Ebene."""
    for number, line in enumerate(SCRIPT.read_text(encoding="utf-8").splitlines(), start=1):
        assert not re.match(r"(exit|exec|set)\b", line), f"Zeile {number}: {line}"
    assert os.access(SCRIPT, os.X_OK)


@pytest.mark.parametrize("template", [".env.example", ".env.local.example"])
def test_templates_define_runtime_role(template):
    values = dict(
        line.split("=", 1) for line in (ROOT / template).read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.startswith("#")
    )
    assert values["APP_DB_USER"] and values["APP_DB_USER"] != values["POSTGRES_USER"]
    assert values["APP_DB_PASSWORD"] == ""  # wird von generate_env.py erzeugt, kein Standardpasswort


def test_generate_env_creates_distinct_runtime_password():
    import importlib.util

    spec = importlib.util.spec_from_file_location("generate_env", ROOT / "scripts" / "generate_env.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    values = gen.generate_values("admin")
    assert len(values["APP_DB_PASSWORD"]) >= 32 and values["APP_DB_PASSWORD"] != values["POSTGRES_PASSWORD"]
    assert re.fullmatch(r"[0-9a-f]+", values["APP_DB_PASSWORD"])  # URL-sicher


# ---------------------------------------------------------------- Rechte-Tests gegen echtes PostgreSQL
_PG_URL = os.environ.get("TEST_DATABASE_URL", "")
needs_postgres = pytest.mark.skipif(
    not _PG_URL.startswith("postgresql") or shutil.which("psql") is None,
    reason="braucht TEST_DATABASE_URL=postgresql+psycopg://<superuser>... und psql im PATH",
)


def _run_script(url, db, role, password, *, check=True):
    env = {**os.environ, "POSTGRES_USER": url.username, "POSTGRES_DB": db, "APP_DB_USER": role, "APP_DB_PASSWORD": password}
    env["PGHOST"] = url.query.get("host") or url.host or ""
    if url.port:
        env["PGPORT"] = str(url.port)
    if url.password:
        env["PGPASSWORD"] = url.password
    return subprocess.run(["sh", str(SCRIPT)], env=env, capture_output=True, text=True, check=check)


def _migrate_as_owner(url, db):
    owner_url = url.set(drivername="postgresql+psycopg", database=db).render_as_string(hide_password=False)
    env = {**os.environ, "DATABASE_URL": owner_url}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True, capture_output=True)


@pytest.fixture
def scratch():
    """Frische Datenbank + Rollenname; räumt danach alles weg (die Test-DB der Suite bleibt unberührt)."""
    url = make_url(_PG_URL).set(drivername="postgresql+psycopg")
    db, role = f"sec004_{uuid.uuid4().hex[:8]}", f"app_{uuid.uuid4().hex[:8]}"
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db}"'))
    yield url, db, role
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)'))
        conn.execute(text(f'DROP ROLE IF EXISTS "{role}"'))
    admin.dispose()


def _app_engine(url, db, role, password=APP_PASSWORD):
    return create_engine(url.set(database=db, username=role, password=password), isolation_level="AUTOCOMMIT")


def _denied(engine, statement):
    with engine.connect() as conn:
        with pytest.raises(DBAPIError) as excinfo:
            conn.execute(text(statement))
    return str(excinfo.value)


def _assert_runtime_role_is_limited(url, db, role):
    engine = _app_engine(url, db, role)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT current_setting('is_superuser')")).scalar() == "off"
        # normale Arbeit: lesen, schreiben, ändern, löschen (inkl. Sequenzen für automatische IDs)
        conn.execute(text("INSERT INTO users (username, password_hash) VALUES ('u1', 'h')"))
        conn.execute(text("INSERT INTO users (username, password_hash) VALUES ('u2', 'h')"))
        assert conn.execute(text("SELECT count(*) FROM users")).scalar() == 2
        conn.execute(text("UPDATE settings SET value = 'true' WHERE key = 'maintenance_mode'"))
        conn.execute(text("DELETE FROM users WHERE username = 'u1'"))
    # alles, was ein kompromittierter App-Prozess missbrauchen könnte, ist verboten
    for statement in (
        "CREATE TABLE evil (id int)",
        "DROP TABLE users",
        "ALTER TABLE users ADD COLUMN evil int",
        "TRUNCATE users",
        "CREATE ROLE evil LOGIN",
        "CREATE SCHEMA evil",
        "SELECT * FROM pg_authid",
        "COPY users TO PROGRAM 'id'",
        "COPY users FROM '/etc/passwd'",
        "CREATE DATABASE evil",
        "ALTER ROLE postgres PASSWORD 'x'",
    ):
        assert re.search(r"permission denied|must be (superuser|owner)|only roles", _denied(engine, statement), re.I), statement
    engine.dispose()


@needs_postgres
def test_fresh_install_order_script_first_then_migration(scratch):
    """Neues Volume: Init-Skript läuft VOR den Migrationen; Default-Privilegien decken die Tabellen der Migration ab."""
    url, db, role = scratch
    _run_script(url, db, role, APP_PASSWORD)
    _migrate_as_owner(url, db)
    _assert_runtime_role_is_limited(url, db, role)


@needs_postgres
def test_existing_install_order_migration_first_then_script(scratch):
    """Bestehende Datenbank: Tabellen existieren schon, das Skript vergibt die Rechte nachträglich."""
    url, db, role = scratch
    _migrate_as_owner(url, db)
    _run_script(url, db, role, APP_PASSWORD)
    _assert_runtime_role_is_limited(url, db, role)


def _role_hash(url, role):
    admin = create_engine(url)
    with admin.connect() as conn:
        value = conn.execute(text("SELECT rolpassword FROM pg_authid WHERE rolname = :r"), {"r": role}).scalar()
    admin.dispose()
    return value


@needs_postgres
def test_script_is_idempotent_and_updates_password(scratch):
    """Zweiter Lauf: kein Fehler, Passwort wird nachgezogen (SCRAM-Hash ändert sich).

    Ein echter Login-Test mit falschem Passwort ist hier nicht möglich, weil der Test-Server per Socket `trust` nutzt.
    """
    url, db, role = scratch
    _migrate_as_owner(url, db)
    _run_script(url, db, role, APP_PASSWORD)
    first = _role_hash(url, role)
    _run_script(url, db, role, "neues-passwort-123")
    second = _role_hash(url, role)
    assert first.startswith("SCRAM-SHA-256$") and second.startswith("SCRAM-SHA-256$") and first != second
    with _app_engine(url, db, role, "neues-passwort-123").connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM settings")).scalar() >= 1


@needs_postgres
def test_script_without_credentials_creates_nothing(scratch):
    url, db, role = scratch
    result = _run_script(url, db, role, "")
    assert result.returncode == 0 and "nicht gesetzt" in result.stdout
    admin = create_engine(url)
    with admin.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM pg_roles WHERE rolname = :r"), {"r": role}).scalar() == 0
    admin.dispose()


@needs_postgres
def test_runtime_role_is_harmless_in_other_databases(scratch):
    """Das Skript berührt nur die App-Datenbank. In anderen DBs (template1/postgres) gilt das Postgres-Standardverhalten:
    CONNECT für PUBLIC, aber kein Schreiben im Schema public (PG >= 15)."""
    url, db, role = scratch
    _run_script(url, db, role, APP_PASSWORD)
    for other in ("template1", "postgres"):
        engine = _app_engine(url, other, role)
        assert re.search(r"permission denied", _denied(engine, "CREATE TABLE evil (id int)"), re.I), other
        engine.dispose()
