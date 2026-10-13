import logging
import re
import threading
import time
from collections import defaultdict
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
    """Einfache Brute-Force-Bremse pro (IP, Benutzername). In-Memory, pro Prozess.
    Bei mehreren Workern/Servern später durch Redis o. ä. ersetzen."""

    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._fails: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _prune(self, key: str) -> list[float]:
        cutoff = time.monotonic() - self.window
        self._fails[key] = [t for t in self._fails[key] if t > cutoff]
        return self._fails[key]

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key)) >= self.max_attempts

    def register_failure(self, key: str) -> None:
        with self._lock:
            self._prune(key).append(time.monotonic())

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._fails.clear()
            else:
                self._fails.pop(key, None)


_s = get_settings()
login_throttle = LoginThrottle(_s.login_max_attempts, _s.login_lockout_seconds)


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
        key = f"{client_ip}|{norm}"
        if login_throttle.is_blocked(key):
            audit.warning("Login gesperrt (zu viele Versuche) user=%r ip=%s", norm[:64], client_ip)
            raise TooManyRequestsError()

        user = self.users.get_by_username(norm)
        ok = verify_password(user.password_hash if user else DUMMY_HASH, password)
        if not user or not ok or not user.is_active:
            login_throttle.register_failure(key)
            audit.warning("Login fehlgeschlagen user=%r ip=%s", norm[:64], client_ip)
            raise UnauthorizedError("Ungültige Anmeldedaten")

        login_throttle.reset(key)
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
