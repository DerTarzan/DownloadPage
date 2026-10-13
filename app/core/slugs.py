"""Slug-Erzeugung. Strategie: automatisch erzeugte Slugs werden eindeutig gemacht
(name, name-2, name-3 ...); explizit angegebene, bereits belegte Slugs -> 409."""
import re
import unicodedata
from collections.abc import Callable

MAX_SLUG_LENGTH = 100

# Erste URL-Segmente, die von der Anwendung selbst belegt sind.
RESERVED_SLUGS = frozenset(
    {"admin", "api", "auth", "documents", "media", "health", "docs", "redoc", "static", "login", "logout"}
)

_GERMAN = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "ae", "Ö": "oe", "Ü": "ue", "ẞ": "ss"}


def slugify(text: str, max_length: int = MAX_SLUG_LENGTH) -> str:
    for src, dst in _GERMAN.items():
        text = text.replace(src, dst)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:max_length].strip("-")


def unique_slug(base: str, exists: Callable[[str], bool], fallback: str = "item") -> str:
    base = base or fallback
    candidate, counter = base, 2
    while exists(candidate):
        suffix = f"-{counter}"
        candidate = f"{base[: MAX_SLUG_LENGTH - len(suffix)]}{suffix}"
        counter += 1
    return candidate
