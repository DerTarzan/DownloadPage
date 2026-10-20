"""Optionale Erweiterung: lokales Sprachmodell (z. B. Ollama).

Die Basisfunktion braucht KEIN Modell. Ein Modell darf nur die Suchbegriffe aus einer Frage extrahieren; die Treffer
kommen weiterhin ausschließlich aus der Datenbank, das Modell kann also keine Produkte oder Dokumente erfinden.
Zum Aktivieren eine Implementierung von `TermExtractor` schreiben und mit `set_term_extractor()` registrieren (siehe README).
"""
from typing import Protocol


class TermExtractor(Protocol):
    def extract_terms(self, message: str, lang: str) -> str | None:
        """Suchbegriffe (Produktname/Modell/Kategorie) aus der Frage, oder None, um die Standardlogik zu nutzen."""


_extractor: TermExtractor | None = None


def set_term_extractor(extractor: TermExtractor | None) -> None:
    global _extractor
    _extractor = extractor


def get_term_extractor() -> TermExtractor | None:
    return _extractor
