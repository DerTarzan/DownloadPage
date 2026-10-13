"""Passwort-Hashing (Argon2id) und Token-Hilfen."""
import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

_hasher = PasswordHasher()
# Dummy-Hash: Login für unbekannte Benutzer kostet gleich viel Zeit (kein User-Enumeration-Timing).
DUMMY_HASH = _hasher.hash(secrets.token_hex(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Session-Tokens liegen nur als HMAC in der DB (DB-Leak => keine gültigen Sessions)."""
    return hmac.new(get_settings().secret_key.encode(), token.encode(), hashlib.sha256).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
