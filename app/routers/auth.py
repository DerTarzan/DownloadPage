from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.core.config import get_settings
from app.dependencies import SESSION_COOKIE, AuthServiceDep, require_user, require_user_csrf
from app.schemas.auth import LoginRequest, SessionInfo
from app.schemas.common import ERR_401, ERR_403, ErrorResponse
from app.services.auth_service import AuthContext

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=SessionInfo,
    summary="Anmelden",
    responses={**ERR_401, 429: {"model": ErrorResponse, "description": "Zu viele Versuche"}},
)
def login(data: LoginRequest, request: Request, response: Response, auth: AuthServiceDep):
    settings = get_settings()
    client_ip = request.client.host if request.client else None
    result = auth.login(data.username, data.password, client_ip)
    response.set_cookie(
        SESSION_COOKIE,
        result.token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return SessionInfo(user=result.user, csrf_token=result.csrf_token)  # type: ignore[arg-type]


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Abmelden",
    responses={**ERR_401, **ERR_403},
)
def logout(ctx: Annotated[AuthContext, Depends(require_user_csrf)], auth: AuthServiceDep):
    auth.logout(ctx.session)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/me", response_model=SessionInfo, summary="Aktueller Benutzer", responses=ERR_401)
def me(ctx: Annotated[AuthContext, Depends(require_user)]):
    return SessionInfo(user=ctx.user, csrf_token=ctx.session.csrf_token)  # type: ignore[arg-type]
