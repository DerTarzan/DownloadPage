from sqlalchemy import text

from app.core.database import engine
from app.core.slugs import slugify, unique_slug


def test_database_connection():
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1


def test_health_endpoint(anon):
    r = anon.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_slugify_handles_umlauts_and_symbols():
    assert slugify("Elektrischer Rollstuhl Modell 5000") == "elektrischer-rollstuhl-modell-5000"
    assert slugify("Rollstühle") == "rollstuehle"
    assert slugify("Größe & Maß!") == "groesse-mass"
    assert slugify("  --  ") == ""


def test_unique_slug_strategy():
    taken = {"produkt", "produkt-2"}
    assert unique_slug("produkt", lambda s: s in taken) == "produkt-3"
    assert unique_slug("", lambda s: False, "kategorie") == "kategorie"
