from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    detail: str


class ReorderRequest(BaseModel):
    ids: list[int] = Field(min_length=1, description="Alle IDs in der gewünschten Reihenfolge")


# Wiederverwendbare Fehlerantworten für die OpenAPI-Doku
ERR_401 = {401: {"model": ErrorResponse, "description": "Nicht angemeldet"}}
ERR_403 = {403: {"model": ErrorResponse, "description": "Keine Berechtigung / CSRF-Token ungültig"}}
ERR_404 = {404: {"model": ErrorResponse, "description": "Nicht gefunden"}}
ERR_409 = {409: {"model": ErrorResponse, "description": "Konflikt (z. B. Slug bereits vergeben)"}}
ERR_413 = {413: {"model": ErrorResponse, "description": "Datei zu groß"}}
ERR_415 = {415: {"model": ErrorResponse, "description": "Dateityp nicht erlaubt"}}
ADMIN_ERRORS = {**ERR_401, **ERR_403}
