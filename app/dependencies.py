"""FastAPI-Dependencies: DB-Session, Services, Authentifizierung, Wartungsmodus."""
from typing import Annotated

from fastapi import Depends, Path, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, MaintenanceError, UnauthorizedError
from app.core.security import constant_time_equals
from app.models.user import User
from app.services.auth_service import AuthContext, AuthService
from app.services.category_service import CategoryService
from app.services.document_service import DocumentService
from app.services.file_service import FileService, get_file_service
from app.services.product_service import ProductService
from app.services.setting_service import SettingService

SESSION_COOKIE = "session_token"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

IdPath = Annotated[int, Path(ge=1, le=2_147_483_647)]

DbDep = Annotated[Session, Depends(get_db)]
FileServiceDep = Annotated[FileService, Depends(get_file_service)]


def get_auth_service(db: DbDep) -> AuthService:
    return AuthService(db)


def get_category_service(db: DbDep, files: FileServiceDep) -> CategoryService:
    return CategoryService(db, files)


def get_product_service(db: DbDep, files: FileServiceDep) -> ProductService:
    return ProductService(db, files)


def get_document_service(db: DbDep, files: FileServiceDep) -> DocumentService:
    return DocumentService(db, files)


def get_setting_service(db: DbDep) -> SettingService:
    return SettingService(db)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
CategoryServiceDep = Annotated[CategoryService, Depends(get_category_service)]
ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
SettingServiceDep = Annotated[SettingService, Depends(get_setting_service)]


# ---------------- Authentifizierung ----------------
def get_session_context(request: Request, auth: AuthServiceDep) -> AuthContext | None:
    token = request.cookies.get(SESSION_COOKIE)
    return auth.validate_session(token) if token else None


def require_user(ctx: Annotated[AuthContext | None, Depends(get_session_context)]) -> AuthContext:
    if ctx is None:
        raise UnauthorizedError()
    return ctx


def require_user_csrf(request: Request, ctx: Annotated[AuthContext, Depends(require_user)]) -> AuthContext:
    """Schreibende Requests mit Cookie-Session brauchen den CSRF-Token im Header."""
    if request.method not in SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not sent or not constant_time_equals(sent, ctx.session.csrf_token):
            raise ForbiddenError("CSRF-Token fehlt oder ist ungültig")
    return ctx


def require_admin(ctx: Annotated[AuthContext, Depends(require_user_csrf)]) -> User:
    if not ctx.user.is_admin:
        raise ForbiddenError("Administratorrechte erforderlich")
    return ctx.user


def optional_admin(ctx: Annotated[AuthContext | None, Depends(get_session_context)]) -> User | None:
    return ctx.user if ctx and ctx.user.is_admin else None


AdminDep = Annotated[User, Depends(require_admin)]
OptionalAdminDep = Annotated[User | None, Depends(optional_admin)]


# ---------------- Wartungsmodus ----------------
def ensure_site_available(admin: OptionalAdminDep, settings: SettingServiceDep) -> None:
    """Auf allen öffentlichen Routen: im Wartungsmodus nur für angemeldete Admins erreichbar.
    /auth, /admin und /api/admin hängen bewusst NICHT daran -> Admin kann sich nie aussperren."""
    if admin is None and settings.is_maintenance():
        raise MaintenanceError(settings.maintenance_message())
