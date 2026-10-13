from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError


def commit_or_conflict(db: Session, message: str = "Konflikt: Eintrag existiert bereits oder wird noch verwendet") -> None:
    """Fängt Race Conditions auf DB-Constraints (z. B. Slug-Unique) sauber als 409 ab."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(message) from exc
