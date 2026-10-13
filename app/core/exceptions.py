"""Fachliche Exceptions; werden zentral in saubere HTTP-Antworten übersetzt."""


class AppError(Exception):
    status_code = 500
    default_detail = "Interner Serverfehler"

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class BadRequestError(AppError):
    status_code = 400
    default_detail = "Ungültige Anfrage"


class UnauthorizedError(AppError):
    status_code = 401
    default_detail = "Nicht authentifiziert"


class ForbiddenError(AppError):
    status_code = 403
    default_detail = "Keine Berechtigung"


class NotFoundError(AppError):
    status_code = 404
    default_detail = "Nicht gefunden"


class ConflictError(AppError):
    status_code = 409
    default_detail = "Konflikt"


class PayloadTooLargeError(AppError):
    status_code = 413
    default_detail = "Datei ist zu groß"


class UnsupportedFileTypeError(AppError):
    status_code = 415
    default_detail = "Dateityp nicht erlaubt"


class UnprocessableError(AppError):
    status_code = 422
    default_detail = "Nicht verarbeitbar"


class TooManyRequestsError(AppError):
    status_code = 429
    default_detail = "Zu viele Versuche, bitte später erneut versuchen"


class MaintenanceError(AppError):
    status_code = 503
    default_detail = "Die Website befindet sich im Wartungsmodus"
