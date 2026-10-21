"""Seitenweite Sprachwahl (Deutsch/Englisch) für die öffentlichen Seiten.

Die Sprache steht im Cookie `lang` und wird über das Lesezeichen im Footer gesetzt (POST /api/language).
Ohne Cookie gilt Deutsch. Der Chat übernimmt die Sprache der Seite (<html lang>).
Die Antworttexte des Bots stehen in services/chat/i18n.py, die Chat-Oberfläche in static/js/chat.js.
"""
from fastapi import Request

SUPPORTED = ("de", "en")
DEFAULT_LANG = "de"
LANG_COOKIE = "lang"
LANG_COOKIE_MAX_AGE = 365 * 24 * 3600

# Eigenbezeichnungen: jede Sprache wird in ihrer eigenen Sprache angezeigt
LANGUAGE_NAMES = {"de": "Deutsch", "en": "English"}

TEXTS: dict[str, dict[str, str]] = {
    "de": {
        "skip": "Zum Inhalt springen",
        "nav_main": "Hauptnavigation",
        "nav_home": "Start",
        "breadcrumbs": "Brotkrumen",
        "lang_label": "Sprache",
        "lang_choose": "Sprache auswählen",
        # Startseite
        "index_title": "Start",
        "index_heading": "Produkte & Dokumente",
        "index_more": "Produkte ansehen",
        "index_empty_title": "Noch keine Kategorien",
        "index_empty_text": "Sobald Inhalte veröffentlicht werden, erscheinen sie hier.",
        # Kategorie
        "category_children": "Unterkategorien",
        "category_open": "Kategorie öffnen",
        "category_product_more": "Details & Dokumente",
        "category_empty_title": "Keine Inhalte",
        "category_empty_text": "In dieser Kategorie gibt es noch keine Unterkategorien oder Produkte.",
        # Produkt
        "docs_heading": "Dokumente & Downloads",
        "docs_version": "Version",
        "docs_download": "Herunterladen",
        "docs_download_aria": "{title} herunterladen",
        "docs_empty": "Zu diesem Produkt sind noch keine Dokumente verfügbar.",
        # Fehlerseite
        "error_title": "Fehler {status}",
        "error_not_found": "Seite nicht gefunden",
        "error_generic": "Das hat leider nicht geklappt",
        "error_home": "Zur Startseite",
        # Wartung
        "maintenance_title": "Wartungsarbeiten",
        "maintenance_heading": "Wir sind gleich wieder da",
        # Anmeldung
        "login_title": "Anmelden",
        "login_heading": "Admin-Anmeldung",
        "login_intro": "Melde dich an, um Inhalte zu verwalten.",
        "login_user": "Benutzername",
        "login_password": "Passwort",
        "login_submit": "Anmelden",
        "login_failed": "Anmeldung fehlgeschlagen",
    },
    "en": {
        "skip": "Skip to content",
        "nav_main": "Main navigation",
        "nav_home": "Home",
        "breadcrumbs": "Breadcrumbs",
        "lang_label": "Language",
        "lang_choose": "Choose language",
        "index_title": "Home",
        "index_heading": "Products & documents",
        "index_more": "View products",
        "index_empty_title": "No categories yet",
        "index_empty_text": "Content will appear here as soon as it is published.",
        "category_children": "Subcategories",
        "category_open": "Open category",
        "category_product_more": "Details & documents",
        "category_empty_title": "No content",
        "category_empty_text": "This category has no subcategories or products yet.",
        "docs_heading": "Documents & downloads",
        "docs_version": "Version",
        "docs_download": "Download",
        "docs_download_aria": "Download {title}",
        "docs_empty": "There are no documents available for this product yet.",
        "error_title": "Error {status}",
        "error_not_found": "Page not found",
        "error_generic": "Something went wrong",
        "error_home": "Back to home page",
        "maintenance_title": "Maintenance",
        "maintenance_heading": "We'll be right back",
        "login_title": "Sign in",
        "login_heading": "Admin sign-in",
        "login_intro": "Sign in to manage content.",
        "login_user": "Username",
        "login_password": "Password",
        "login_submit": "Sign in",
        "login_failed": "Sign-in failed",
    },
}

# Standardmeldungen der Fehlerseite (app/core/exceptions.py) in der Zweitsprache.
# Eigene, frei formulierte Texte (z. B. die Wartungsmeldung aus den Einstellungen) bleiben unverändert.
ERROR_DETAILS_EN = {
    "Interner Serverfehler": "Internal server error",
    "Ungültige Anfrage": "Invalid request",
    "Nicht authentifiziert": "Not authenticated",
    "Keine Berechtigung": "Permission denied",
    "Nicht gefunden": "Not found",
    "Kategorie nicht gefunden": "Category not found",
    "Produkt nicht gefunden": "Product not found",
    "Dokument nicht gefunden": "Document not found",
    "Konflikt": "Conflict",
    "Datei ist zu groß": "File is too large",
    "Dateityp nicht erlaubt": "File type not allowed",
    "Nicht verarbeitbar": "Cannot be processed",
    "Zu viele Versuche, bitte später erneut versuchen": "Too many attempts, please try again later",
    "Die Website befindet sich im Wartungsmodus": "The website is currently under maintenance",
    "Anfrage ist zu groß": "Request is too large",
}


def normalize_lang(lang: str | None) -> str:
    return lang if lang in SUPPORTED else DEFAULT_LANG


def resolve_lang(request: Request) -> str:
    """Sprache der aktuellen Anfrage: Cookie, sonst Deutsch."""
    return normalize_lang(request.cookies.get(LANG_COOKIE))


def translate(lang: str, key: str, **params: object) -> str:
    text = TEXTS[normalize_lang(lang)][key]
    return text.format(**params) if params else text


def translate_detail(lang: str, detail: str) -> str:
    """Übersetzt bekannte Standard-Fehlertexte; alles andere bleibt, wie es ist."""
    return ERROR_DETAILS_EN.get(detail, detail) if normalize_lang(lang) == "en" else detail


def safe_next_path(value: str | None) -> str:
    """Rücksprungziel nach dem Sprachwechsel: nur relative Pfade der eigenen Seite (kein Open Redirect)."""
    if (
        value
        and value.startswith("/")
        and not value.startswith("//")
        and "\\" not in value
        and not any(ord(c) < 32 for c in value)
    ):
        return value
    return "/"
