"""Admin: Einstellungen (Wartungsmodus) per API + minimale HTML-Testseiten."""
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.dependencies import AdminDep, OptionalAdminDep, SettingServiceDep, require_admin
from app.schemas.common import ADMIN_ERRORS
from app.schemas.setting import SiteSettingsOut, SiteSettingsUpdate
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


# ---- HTML-Testseiten (nicht in der OpenAPI-Doku) ----
pages_router = APIRouter(prefix="/admin", include_in_schema=False)


@pages_router.get("/login")
def login_page(request: Request, admin: OptionalAdminDep):
    if admin:
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(request, "login.html", {})


@pages_router.get("")
def dashboard(request: Request, admin: OptionalAdminDep):
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    return templates.TemplateResponse(request, "admin_dashboard.html", {"admin": admin})


@pages_router.get("/upload")
def upload_page(request: Request, admin: OptionalAdminDep):
    if not admin:
        return RedirectResponse("/admin/login", status_code=303)
    return templates.TemplateResponse(request, "admin_upload.html", {"admin": admin})
