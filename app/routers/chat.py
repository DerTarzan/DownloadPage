"""Öffentlicher Chat-Endpunkt: reine Lese-Suche auf den öffentlichen Katalogdaten, ohne Speicherung der Nachrichten."""
import logging

from fastapi import APIRouter, Depends, Request

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, TooManyRequestsError, UnprocessableError
from app.core.rate_limit import RateLimiter
from app.dependencies import DbDep, ensure_site_available
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.common import ErrorResponse
from app.services.chat.service import ChatService
from app.services.setting_service import SettingService

log = logging.getLogger("app.chat")

router = APIRouter(prefix="/api", tags=["chat"], dependencies=[Depends(ensure_site_available)])

_s = get_settings()
chat_limiter = RateLimiter(_s.chat_rate_limit_per_minute, 60.0)


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Produktsuche in natürlicher Sprache",
    responses={
        404: {"model": ErrorResponse, "description": "Chat deaktiviert"},
        422: {"model": ErrorResponse, "description": "Ungültige Nachricht"},
        429: {"model": ErrorResponse, "description": "Zu viele Anfragen"},
    },
)
def chat(data: ChatRequest, request: Request, db: DbDep) -> ChatResponse:
    settings = get_settings()
    if not settings.chat_enabled or not SettingService(db).is_chat_enabled():
        raise NotFoundError()
    ip = request.client.host if request.client else "unknown"
    if not chat_limiter.allow(ip):
        raise TooManyRequestsError("Zu viele Anfragen, bitte einen Moment warten")
    if not data.message:
        raise UnprocessableError("Nachricht darf nicht leer sein")
    if len(data.message) > settings.chat_max_message_length:
        raise UnprocessableError(f"Nachricht ist zu lang (maximal {settings.chat_max_message_length} Zeichen)")
    result = ChatService(db, settings.chat_max_results).reply(data.message, data.lang, data.context)
    # Für die Live-Logs im Admin-Bereich: nur Metadaten, NIE der Nachrichtentext
    log.info("Anfrage lang=%s antwort=%s treffer=%d", result.lang, result.kind, len(result.results))
    return result
