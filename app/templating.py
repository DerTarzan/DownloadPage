from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

from app.core.config import get_settings
from app.i18n import LANGUAGE_NAMES, SUPPORTED, resolve_lang, translate

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["site_name"] = get_settings().app_name
templates.env.globals["docs_enabled"] = get_settings().docs_enabled
templates.env.globals["chat_enabled"] = get_settings().chat_enabled
templates.env.globals["chat_max_length"] = get_settings().chat_max_message_length
templates.env.globals["languages"] = [(code, LANGUAGE_NAMES[code]) for code in SUPPORTED]


@pass_context
def _lang(ctx) -> str:
    """Sprache der aktuellen Anfrage ('de' oder 'en') – für <html lang> und Vergleiche in Templates."""
    return resolve_lang(ctx["request"])


@pass_context
def _t(ctx, key: str, **params: object) -> str:
    """Übersetzter Seitentext: {{ t('index_heading') }}."""
    return translate(resolve_lang(ctx["request"]), key, **params)


templates.env.globals["lang"] = _lang
templates.env.globals["t"] = _t


def wants_html(request: Request) -> bool:
    """Browser (Accept beginnt mit text/html) bekommen HTML, alle anderen JSON."""
    first = request.headers.get("accept", "").split(",")[0].split(";")[0].strip().lower()
    return first == "text/html"
