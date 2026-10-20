"""Textnormalisierung und Ähnlichkeitsfunktionen für die Suche (rein, ohne Datenbankzugriff)."""
import re
import unicodedata

_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_LETTER_DIGIT = re.compile(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])")
_SUFFIXES = ("en", "er", "e", "n", "s")  # grobe Plural-/Flexionsendungen (DE/EN), nur für längere Wörter


def fold(text: str) -> str:
    """Kleinschreibung, ä→ae/ö→oe/ü→ue/ß→ss, übrige Akzente entfernt. So passen „Rollstühle“ und „Rollstuehle“ zusammen."""
    text = text.lower().translate(_UMLAUTS)
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def tokenize(text: str) -> list[str]:
    """Wörter und Zahlen; „STF300“ wird zu „stf“, „300“ (Buchstaben-Ziffern-Grenze)."""
    out: list[str] = []
    for chunk in _NON_ALNUM.split(fold(text)):
        out.extend(part for part in _LETTER_DIGIT.split(chunk) if part)
    return out


def compact(text: str) -> str:
    """Nur Buchstaben und Ziffern: „STF-300“, „STF 300“ und „stf300“ ergeben dasselbe."""
    return _NON_ALNUM.sub("", fold(text))


def stem(token: str) -> str:
    if token.isdigit() or len(token) <= 5:
        return token
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 5:
            return token[: -len(suffix)]
    return token


def edit_distance(a: str, b: str, limit: int) -> int:
    """Damerau-Levenshtein (Tippfehler: Einfügen, Löschen, Ersetzen, Vertauschen); bricht über `limit` ab."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev2: list[int] | None = None
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if prev2 is not None and i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        if min(cur) > limit:
            return limit + 1
        prev2, prev = prev, cur
    return prev[-1]


def max_typos(length: int) -> int:
    return 0 if length < 4 else 1 if length < 8 else 2


def token_similarity(query: str, target: str, *, fuzzy: bool = True) -> float:
    """Ähnlichkeit zweier gefalteter Wörter, 0..1. Zahlen müssen exakt übereinstimmen."""
    if query == target:
        return 1.0
    if query.isdigit() or target.isdigit():
        return 0.0
    if stem(query) == stem(target):
        return 0.95
    shorter, longer = sorted((query, target), key=len)
    if len(shorter) >= 4 and longer.startswith(shorter) and len(shorter) >= 0.7 * len(longer):
        return 0.85
    if len(shorter) >= 4 and shorter in longer:
        return 0.6  # Teilwort, z. B. „trainer“ in „bewegungstrainer“
    if fuzzy:
        limit = max_typos(len(query))
        if limit and edit_distance(query, target, limit) <= limit:
            return 0.8 if edit_distance(query, target, limit) == 1 else 0.7
        sq, st = stem(query), stem(target)
        if limit and edit_distance(sq, st, limit) <= limit:
            return 0.7
    return 0.0
