from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["site_name"] = get_settings().app_name
templates.env.globals["docs_enabled"] = get_settings().docs_enabled
templates.env.globals["chat_enabled"] = get_settings().chat_enabled
templates.env.globals["chat_max_length"] = get_settings().chat_max_message_length


def wants_html(request: Request) -> bool:
    """Browser (Accept beginnt mit text/html) bekommen HTML, alle anderen JSON."""
    first = request.headers.get("accept", "").split(",")[0].split(";")[0].strip().lower()
    return first == "text/html"
