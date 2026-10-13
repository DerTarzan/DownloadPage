"""Test-Setup.

WICHTIG: Tests leeren alle Tabellen. Sie verwenden deshalb NIE die DATABASE_URL der Entwicklung,
sondern TEST_DATABASE_URL (z. B. postgresql+psycopg://user:pw@localhost:5432/docs_test) oder – ohne
Angabe – eine temporäre SQLite-Datei. Die Migrationen werden per Alembic angewendet.
"""
import os
import shutil
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="docplatform-tests-"))
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_TMP / 'test.db'}"
os.environ["SECRET_KEY"] = "test-secret-key-test-secret-key-test-secret-key"
os.environ["STORAGE_DIR"] = str(_TMP / "storage")
os.environ["COOKIE_SECURE"] = "false"
os.environ["ENVIRONMENT"] = "test"
os.environ["MAX_PDF_SIZE_MB"] = "1"
os.environ["MAX_IMAGE_SIZE_MB"] = "1"
os.environ["ADMIN_USERNAME"] = ""
os.environ["ADMIN_PASSWORD"] = ""
os.environ["LOG_LEVEL"] = "WARNING"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ADMIN_USER = "testadmin"
ADMIN_PASSWORD = "correct-horse-battery"

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.auth_service import AuthService, login_throttle  # noqa: E402
from app.services.file_service import get_file_service  # noqa: E402

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture(scope="session", autouse=True)
def _migrated_database():
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    yield
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture(autouse=True)
def _clean_state():
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    storage = get_file_service().root
    for sub in ("images", "documents"):
        shutil.rmtree(storage / sub, ignore_errors=True)
        (storage / sub).mkdir(parents=True, exist_ok=True)
    login_throttle.reset()
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def admin_user(db):
    return AuthService(db).create_admin(ADMIN_USER, ADMIN_PASSWORD)


@pytest.fixture
def anon():
    return TestClient(app)


@pytest.fixture
def admin(admin_user):
    """Angemeldeter Admin-Client (Cookie + CSRF-Header)."""
    client = TestClient(app)
    r = client.post("/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    client.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    return client


@pytest.fixture
def storage_root() -> Path:
    return get_file_service().root


def make_category(client, name="Rollstühle", **extra):
    r = client.post("/api/admin/categories", json={"name": name, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def make_product(client, category_id, name="Produkt A", **extra):
    r = client.post("/api/admin/products", json={"category_id": category_id, "name": name, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def upload_pdf(client, product_id, content=PDF_BYTES, filename="manual.pdf", content_type="application/pdf", **data):
    return client.post(
        f"/api/admin/products/{product_id}/documents",
        files={"file": (filename, content, content_type)},
        data=data,
    )


@pytest.fixture
def product(admin):
    cat = make_category(admin)
    return make_product(admin, cat["id"])


@pytest.fixture
def document(admin, product):
    r = upload_pdf(admin, product["id"], title="Bedienungsanleitung")
    assert r.status_code == 201, r.text
    return r.json()
