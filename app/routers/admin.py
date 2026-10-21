"""Admin: Einstellungen (Wartungsmodus) per API + HTML-Seiten der Verwaltungsoberfläche."""
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.dependencies import AdminDep, OptionalAdminDep, SettingServiceDep, require_admin
from app.schemas.common import ADMIN_ERRORS
from app.schemas.setting import ChatbotOut, ChatbotUpdate, SiteSettingsOut, SiteSettingsUpdate
from app.templating import templates

audit = logging.getLogger("app.audit")

# ---- API ----
settings_router = APIRouter(
    prefix="/api/admin/settings",
    tags=["admin: settings"],
    dependencies=[Depends(require_admin)],
    responses=ADMIN_ERRORS,
)


@settings_router.get("", response_model=SiteSettingsOut, summary="Website-Einstellungen lesen")
def get_site_settings(svc: SettingServiceDep):
    return svc.get()


@settings_router.put("", response_model=SiteSettingsOut, summary="Wartungsmodus / Nachricht ändern")
def update_site_settings(data: SiteSettingsUpdate, svc: SettingServiceDep, admin: AdminDep):
    result = svc.update(data)
    audit.info("Einstellungen geändert maintenance_mode=%s von=%s", result.maintenance_mode, admin.username)
    return result


# ---- Chatbot an-/ausschalten ----
chatbot_router = APIRouter(
    prefix="/api/admin/chatbot",
    tags=["admin: chatbot"],
    dependencies=[Depends(require_admin)],
    responses=ADMIN_ERRORS,
)


def _chatbot_state(svc) -> ChatbotOut:
    enabled, available = svc.is_chat_enabled(), get_settings().chat_enabled
    return ChatbotOut(enabled=enabled, available=available, active=enabled and available)


@chatbot_router.get("", response_model=ChatbotOut, summary="Chatbot-Status lesen")
def get_chatbot(svc: SettingServiceDep):
    return _chatbot_state(svc)


@chatbot_router.put("", response_model=ChatbotOut, summary="Chatbot aktivieren oder deaktivieren")
def update_chatbot(data: ChatbotUpdate, svc: SettingServiceDep, admin: AdminDep):
    svc.set_chat_enabled(data.enabled)
    audit.info("Chatbot %s von=%s", "aktiviert" if data.enabled else "deaktiviert", admin.username)
    return _chatbot_state(svc)


# ---- HTML-Seiten der Verwaltung (nicht in der OpenAPI-Doku) ----
pages_router = APIRouter(prefix="/admin", include_in_schema=False)


@pages_router.get("/login")
def login_page(request: Request, admin: OptionalAdminDep):
    if admin:
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(request, "login.html", {})


def _admin_page(request: Request, admin, template: str, nav: str):
    """Gemeinsame Auslieferung der Admin-Seiten; `nav` markiert den aktiven Menüpunkt."""
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    return templates.TemplateResponse(request, template, {"admin": admin, "nav": nav})


@pages_router.get("")
def dashboard(request: Request, admin: OptionalAdminDep):
    return _admin_page(request, admin, "admin_dashboard.html", "overview")


@pages_router.get("/catalog")
def catalog_page(request: Request, admin: OptionalAdminDep):
    return _admin_page(request, admin, "admin_catalog.html", "catalog")


@pages_router.get("/documents")
def documents_page(request: Request, admin: OptionalAdminDep):
    return _admin_page(request, admin, "admin_documents.html", "documents")


@pages_router.get("/upload")
def upload_page(request: Request, admin: OptionalAdminDep):
    return _admin_page(request, admin, "admin_upload.html", "upload")


@pages_router.get("/logs")
def logs_page(request: Request, admin: OptionalAdminDep):
    return _admin_page(request, admin, "admin_logs.html", "logs")


@pages_router.get("/settings")
def settings_page(request: Request, admin: OptionalAdminDep):
    return _admin_page(request, admin, "admin_settings.html", "settings")
