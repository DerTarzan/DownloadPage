"""Admin: Live-Logs. Liest den Ringpuffer aus app/core/log_buffer.py (nur Administratoren).

  GET /api/admin/logs         letzte Einträge als JSON (Rückblick / Fallback ohne Stream)
  GET /api/admin/logs/stream  Server-Sent Events: neue Einträge erscheinen binnen Sekundenbruchteilen

Der Stream endet nach STREAM_MAX_SECONDS von selbst. Der Browser (EventSource) verbindet sich dann automatisch neu und
sendet per Last-Event-ID, wo er stehengeblieben ist. Bei jeder neuen Verbindung wird die Admin-Session erneut geprüft;
eine abgemeldete Sitzung sieht also höchstens noch wenige Minuten mit.
"""
import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.log_buffer import LogBuffer, log_buffer
from app.dependencies import DbDep, require_admin
from app.schemas.common import ADMIN_ERRORS

router = APIRouter(
    prefix="/api/admin/logs",
    tags=["admin: logs"],
    dependencies=[Depends(require_admin)],
    responses=ADMIN_ERRORS,
)

STREAM_MAX_SECONDS = 300.0  # danach verbindet der Browser automatisch neu (Session wird dabei erneut geprüft)
POLL_INTERVAL = 0.4  # Sekunden; der Puffer liegt im Arbeitsspeicher, Abfragen sind praktisch kostenlos
HEARTBEAT_SECONDS = 15.0  # Kommentarzeile, damit Proxys die Verbindung nicht als untätig beenden
BACKLOG = 200  # so viele Einträge sieht man beim ersten Öffnen sofort
BATCH = 200  # maximal so viele Einträge pro Durchlauf


class LogEntryOut(BaseModel):
    id: int
    ts: str
    level: str
    logger: str
    source: str
    message: str
    exc: str | None = None


class LogListOut(BaseModel):
    entries: list[LogEntryOut]
    last_id: int


@router.get("", response_model=LogListOut, summary="Letzte Log-Einträge (neueste zuletzt)")
def list_logs(
    after: Annotated[int, Query(ge=0, description="Nur Einträge mit größerer id; 0 = die letzten Einträge")] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = BACKLOG,
):
    return {"entries": log_buffer.since(after, limit), "last_id": log_buffer.last_id()}


def sse_event(entry: dict) -> str:
    """Ein Log-Eintrag als SSE-Nachricht. `id` wird vom Browser als Last-Event-ID gemerkt."""
    return f"id: {entry['id']}\nevent: log\ndata: {json.dumps(entry, ensure_ascii=False)}\n\n"


async def event_stream(
    request: Request | None,
    after_id: int,
    buffer: LogBuffer = log_buffer,
    max_seconds: float | None = None,
) -> AsyncIterator[str]:
    deadline = time.monotonic() + (STREAM_MAX_SECONDS if max_seconds is None else max_seconds)
    last_sent = time.monotonic()
    cursor = after_id
    yield "retry: 3000\n\n"  # Wartezeit des Browsers vor dem automatischen Neuverbinden
    while time.monotonic() < deadline:
        if request is not None and await request.is_disconnected():
            return
        entries = buffer.since(cursor, BACKLOG if cursor <= 0 else BATCH)
        for entry in entries:
            cursor = entry["id"]
            yield sse_event(entry)
        now = time.monotonic()
        if entries:
            last_sent = now
            if len(entries) >= BATCH:
                continue  # es kann mehr warten: sofort weiter statt zu schlafen
        elif now - last_sent >= HEARTBEAT_SECONDS:
            last_sent = now
            yield ": ping\n\n"
        await asyncio.sleep(POLL_INTERVAL)


@router.get(
    "/stream",
    summary="Live-Stream der Log-Einträge (Server-Sent Events)",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "Ereignisstrom (event: log)"}},
)
def stream_logs(
    request: Request,
    db: DbDep,
    after: Annotated[int, Query(ge=0)] = 0,
    last_event_id: Annotated[str | None, Header()] = None,
):
    # Die DB-Verbindung wird nur für die Anmeldeprüfung gebraucht. Ohne close() hielte FastAPI sie, bis der Stream endet.
    db.close()
    cursor = after
    if last_event_id and last_event_id.isdigit():
        cursor = max(cursor, int(last_event_id))
    return StreamingResponse(
        event_stream(request, cursor),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # Nginx-Proxys sollen den Stream nicht puffern (Caddy leitet ihn ohnehin sofort durch)
        },
    )
