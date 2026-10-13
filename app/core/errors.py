"""Zentrale Fehlerbehandlung: keine Tracebacks nach außen."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError, MaintenanceError
from app.templating import templates, wants_html

logger = logging.getLogger("app.errors")


def _respond(request: Request, status: int, detail: str, headers: dict | None = None, maintenance: bool = False) -> Response:
    if wants_html(request) and not request.url.path.startswith("/api/"):
        template = "maintenance.html" if maintenance else "error.html"
        return templates.TemplateResponse(
            request, template, {"status": status, "detail": detail, "message": detail}, status_code=status, headers=headers
        )
    content: dict = {"detail": detail}
    if maintenance:
        content["maintenance"] = True
    return JSONResponse(content, status_code=status, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        headers = {"Retry-After": "600"} if isinstance(exc, MaintenanceError) else None
        return _respond(request, exc.status_code, exc.detail, headers, maintenance=isinstance(exc, MaintenanceError))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        return _respond(request, exc.status_code, str(exc.detail), dict(exc.headers or {}) or None)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        # bewusst ohne "input": eingegebene Werte (z. B. Passwörter) werden nicht zurückgespiegelt
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse({"detail": errors}, status_code=422)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.exception("Unbehandelter Fehler bei %s %s", request.method, request.url.path)
        return _respond(request, 500, "Interner Serverfehler")
