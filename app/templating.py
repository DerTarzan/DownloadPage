from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["site_name"] = get_settings().app_name


def wants_html(request: Request) -> bool:
    """Browser (Accept beginnt mit text/html) bekommen HTML, alle anderen JSON."""
    first = request.headers.get("accept", "").split(",")[0].split(";")[0].strip().lower()
    return first == "text/html"
