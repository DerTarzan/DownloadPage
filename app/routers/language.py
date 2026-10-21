"""Sprachwahl der öffentlichen Seiten (Lesezeichen im Footer).

Bewusst OHNE ensure_site_available: Die Sprache lässt sich auch auf der Wartungsseite umstellen.
Funktioniert ohne JavaScript (Formular-POST + Redirect). Gespeichert wird nur ein Cookie mit dem Sprachcode."""
from typing import Annotated

from fastapi import APIRouter, Form
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.i18n import LANG_COOKIE, LANG_COOKIE_MAX_AGE, SUPPORTED, normalize_lang, safe_next_path

router = APIRouter(prefix="/api", tags=["language"])


@router.post(
    "/language",
    status_code=303,
    include_in_schema=False,
    summary="Seitensprache setzen (Cookie) und zurück zur vorherigen Seite",
)
def set_language(lang: Annotated[str, Form(max_length=5)], next: Annotated[str, Form(max_length=2000)] = "/"):
    response = RedirectResponse(safe_next_path(next), status_code=303)
    if lang in SUPPORTED:
        response.set_cookie(
            LANG_COOKIE,
            normalize_lang(lang),
            max_age=LANG_COOKIE_MAX_AGE,
            path="/",
            secure=get_settings().cookie_secure,
            httponly=True,
            samesite="lax",
        )
    return response
