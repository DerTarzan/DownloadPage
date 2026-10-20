import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine
from app.core.errors import register_exception_handlers
from app.core.logging_config import setup_logging
from app.core.request_guard import RequestGuardMiddleware
from app.routers import admin, auth, categories, chat, documents, products, public

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    logger.info("Server startet (environment=%s, storage=%s)", s.environment, s.storage_dir)
    for warning in s.production_warnings():
        logger.warning("Unsichere Produktionskonfiguration – %s", warning)
    yield
    logger.info("Server wird beendet")


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Öffentliche Produkt-/Dokumentenplattform – Backend. Admin-API unter /api/admin (Cookie-Session + X-CSRF-Token).",
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    register_exception_handlers(app)
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
    # VOR security_headers registrieren (= weiter innen): auch Abweisungen bekommen die Sicherheits-Header
    app.add_middleware(RequestGuardMiddleware)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        path = request.url.path
        if path.startswith("/media/"):
            response.headers.setdefault("Content-Security-Policy", "default-src 'none'")
        if path.startswith(("/admin", "/auth", "/api")):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.get("/health", tags=["system"], summary="Liveness + DB-Check")
    def health():
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}

    # Reihenfolge wichtig: spezifische Router zuerst, public (Catch-all) zuletzt
    app.include_router(auth.router)
    app.include_router(admin.pages_router)
    app.include_router(admin.settings_router)
    app.include_router(categories.router)
    app.include_router(products.router)
    app.include_router(documents.router)
    app.include_router(chat.router)
    app.include_router(public.router)
    return app


app = create_app()
