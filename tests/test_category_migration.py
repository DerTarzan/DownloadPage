import sqlite3
from types import SimpleNamespace

from alembic import command
from alembic.config import Config

from app.core import config as app_config


def test_category_parent_migration_preserves_existing_categories(monkeypatch, tmp_path):
    database_path = tmp_path / "legacy.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setattr(app_config, "get_settings", lambda: SimpleNamespace(database_url=database_url))

    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "0001_initial")

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO categories (name, slug) VALUES (?, ?)",
            ("Rollstühle", "rollstuehle"),
        )
        connection.commit()

    command.upgrade(cfg, "head")

    with sqlite3.connect(database_path) as connection:
        category = connection.execute("SELECT name, slug, parent_id FROM categories").fetchone()

    assert category == ("Rollstühle", "rollstuehle", None)
