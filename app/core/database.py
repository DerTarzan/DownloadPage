"""SQLAlchemy-2-Engine, Session-Factory und Declarative Base."""
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
_is_sqlite = _settings.database_url.startswith("sqlite")

engine: Engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

if _is_sqlite:  # nur für lokale Tests ohne Postgres

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover
        dbapi_conn.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
