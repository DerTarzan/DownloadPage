import logging
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ConflictError, TooManyRequestsError, UnauthorizedError, UnprocessableError
from app.core.security import (
    DUMMY_HASH,
    generate_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    verify_password,
)
from app.models.mixins import utcnow
from app.models.user import User
from app.models.user_session import UserSession
from app.repositories.user_repository import UserRepository
from app.services.base import commit_or_conflict

audit = logging.getLogger("app.audit")

MIN_PASSWORD_LENGTH = 12
USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,64}$")


class LoginThrottle:
    """Brute-Force-Bremse. In-Memory, pro Prozess (bei mehreren Workern/Servern durch Redis o. ä. ersetzen).

    Zwei Zähler im selben Zeitfenster:
    - pro (IP, Benutzername): begrenzt Raten gegen ein bestimmtes Konto
    - pro IP über alle Benutzernamen: verhindert, dass wechselnde Benutzernamen die Bremse umgehen, und
      begrenzt damit auch die Zahl teurer Argon2-Prüfungen pro Quelle
    Der Speicher ist begrenzt (MAX_KEYS); lesende Abfragen legen keine Einträge an."""

    MAX_KEYS = 10_000

    def __init__(self, max_attempts: int, window_seconds: int, max_attempts_per_ip: int | None = None):
        self.max_attempts = max_attempts
        self.max_attempts_per_ip = max_attempts_per_ip or max_attempts * 4
        self.window = window_seconds
        self._fails: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _user_key(ip: str, username: str) -> str:
        return f"u|{ip}|{username}"

    @staticmethod
    def _ip_key(ip: str) -> str:
        return f"i|{ip}"

    def _recent(self, key: str) -> list[float]:
        """Aktuelle Fehlversuche; entfernt abgelaufene Einträge (und leere Schlüssel). Legt nie etwas an."""
        times = self._fails.get(key)
        if not times:
            return []
        cutoff = time.monotonic() - self.window
        fresh = [t for t in times if t > cutoff]
        if fresh:
            self._fails[key] = fresh
        else:
            del self._fails[key]
        return fresh

    def is_blocked(self, ip: str, username: str) -> bool:
        with self._lock:
            return (
                len(self._recent(self._user_key(ip, username))) >= self.max_attempts
                or len(self._recent(self._ip_key(ip))) >= self.max_attempts_per_ip
            )

    def register_failure(self, ip: str, username: str) -> None:
        with self._lock:
            if len(self._fails) + 2 > self.MAX_KEYS:  # unten kommen bis zu 2 neue Schlüssel dazu
                for key in list(self._fails):  # erst abgelaufene Einträge entfernen
                    self._recent(key)
                while len(self._fails) + 2 > self.MAX_KEYS:  # sonst den ältesten verdrängen
                    del self._fails[next(iter(self._fails))]
            now = time.monotonic()
            for key in (self._user_key(ip, username), self._ip_key(ip)):
                self._fails.setdefault(key, []).append(now)

    def clear_user(self, ip: str, username: str) -> None:
        """Nach erfolgreichem Login: nur den Zähler dieses Kontos zurücksetzen (der IP-Zähler läuft weiter)."""
        with self._lock:
            self._fails.pop(self._user_key(ip, username), None)

    def reset(self) -> None:
        with self._lock:
            self._fails.clear()


# Argon2 braucht pro Prüfung ~64 MiB RAM: gleichzeitige Prüfungen begrenzen (Schutz vor Speichererschöpfung)
HASH_SLOT_TIMEOUT_SECONDS = 5.0

_s = get_settings()
login_throttle = LoginThrottle(_s.login_max_attempts, _s.login_lockout_seconds, _s.login_max_attempts_per_ip)
_hash_slots = threading.BoundedSemaphore(_s.login_max_concurrent_hashes)


@contextmanager
def _hash_slot():
    if not _hash_slots.acquire(timeout=HASH_SLOT_TIMEOUT_SECONDS):
        raise TooManyRequestsError("Server ausgelastet, bitte gleich erneut versuchen")
    try:
        yield
    finally:
        _hash_slots.release()


def _loggable_username(norm: str) -> str:
    """Nur Benutzernamen im erlaubten Format ins Log: Wer sein Passwort ins Benutzername-Feld tippt, soll es dort nicht finden."""
    return norm if USERNAME_RE.match(norm) else "<ungültig>"


@dataclass
class AuthContext:
    user: User
    session: UserSession


@dataclass
class LoginResult:
    user: User
    token: str
    csrf_token: str


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def normalize_username(username: str) -> str:
    return username.strip().lower()


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.settings = get_settings()

    def login(self, username: str, password: str, client_ip: str | None) -> LoginResult:
        norm = normalize_username(username)
        ip = client_ip or "unknown"
        if login_throttle.is_blocked(ip, norm):
            audit.warning("Login gesperrt (zu viele Versuche) user=%r ip=%s", _loggable_username(norm), client_ip)
            raise TooManyRequestsError()

        user = self.users.get_by_username(norm)
        with _hash_slot():
            ok = verify_password(user.password_hash if user else DUMMY_HASH, password)
        if not user or not ok or not user.is_active:
            login_throttle.register_failure(ip, norm)
            audit.warning("Login fehlgeschlagen user=%r ip=%s", _loggable_username(norm), client_ip)
            raise UnauthorizedError("Ungültige Anmeldedaten")

        login_throttle.clear_user(ip, norm)
        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        now = utcnow()
        user.last_login = now
        token, csrf = generate_token(), generate_token()
        self.users.delete_expired_sessions(now)
        self.users.add_session(
            UserSession(
                user_id=user.id,
                token_hash=hash_token(token),
                csrf_token=csrf,
                ip_address=(client_ip or "")[:45] or None,
                expires_at=now + timedelta(hours=self.settings.session_ttl_hours),
            )
        )
        self.db.commit()
        audit.info("Login erfolgreich user=%s ip=%s", user.username, client_ip)
        return LoginResult(user=user, token=token, csrf_token=csrf)

    def validate_session(self, token: str) -> AuthContext | None:
        session = self.users.get_session_by_hash(hash_token(token))
        if session is None:
            return None
        if _aware(session.expires_at) <= utcnow():
            self.users.delete_session(session)
            self.db.commit()
            return None
        user = self.users.get(session.user_id)
        if user is None or not user.is_active:
            return None
        return AuthContext(user=user, session=session)

    def logout(self, session: UserSession) -> None:
        self.users.delete_session(session)
        self.db.commit()

    # --- Benutzerverwaltung (CLI) ---
    def create_admin(self, username: str, password: str) -> User:
        norm = normalize_username(username)
        if not USERNAME_RE.match(norm):
            raise UnprocessableError("Benutzername: 3-64 Zeichen aus a-z, 0-9, '.', '_' oder '-'")
        self._check_password(password)
        if self.users.get_by_username(norm):
            raise ConflictError("Benutzername ist bereits vergeben")
        user = self.users.add(User(username=norm, password_hash=hash_password(password), is_admin=True, is_active=True))
        commit_or_conflict(self.db)
        audit.info("Admin angelegt user=%s", norm)
        return user

    def set_password(self, username: str, password: str) -> None:
        self._check_password(password)
        user = self.users.get_by_username(normalize_username(username))
        if not user:
            raise UnprocessableError("Benutzer nicht gefunden")
        user.password_hash = hash_password(password)
        # alle bestehenden Sessions des Benutzers ungültig machen
        from sqlalchemy import delete

        self.db.execute(delete(UserSession).where(UserSession.user_id == user.id))
        self.db.commit()
        audit.info("Passwort geändert user=%s", user.username)

    def admin_exists(self) -> bool:
        return self.users.admin_exists()

    @staticmethod
    def _check_password(password: str) -> None:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise UnprocessableError(f"Passwort muss mindestens {MIN_PASSWORD_LENGTH} Zeichen lang sein")
