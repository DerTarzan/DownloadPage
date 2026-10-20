"""Zentrale Konfiguration (aus Umgebungsvariablen bzw. .env)."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Dokumentenplattform"
    environment: str = "production"  # development | production | test
    docs_enabled: bool = True  # /docs und /redoc

    database_url: str
    secret_key: str = Field(min_length=32)

    # Nur für den initialen Admin (CLI / seed-admin). Nach dem ersten Start entfernbar.
    admin_username: str | None = None
    admin_password: str | None = None

    storage_dir: Path = Path("storage")
    max_pdf_size_mb: int = Field(default=50, ge=1)
    max_image_size_mb: int = Field(default=5, ge=1)
    max_request_body_kb: int = Field(default=1024, ge=1)  # alle Requests außer Datei-Uploads (JSON, Login, ...)

    session_ttl_hours: int = Field(default=12, ge=1)
    cookie_secure: bool = True  # lokal über http: COOKIE_SECURE=false
    login_max_attempts: int = Field(default=5, ge=1)
    login_lockout_seconds: int = Field(default=300, ge=1)
    login_max_attempts_per_ip: int = Field(default=20, ge=1)  # Fehlversuche je IP über alle Benutzernamen
    login_max_concurrent_hashes: int = Field(default=4, ge=1)  # gleichzeitige Argon2-Prüfungen (je ~64 MiB RAM)

    # Chatbot (lokale Produktsuche, keine externen Dienste)
    chat_enabled: bool = True
    chat_max_message_length: int = Field(default=300, ge=20, le=2000)
    chat_max_results: int = Field(default=5, ge=1, le=20)
    chat_rate_limit_per_minute: int = Field(default=20, ge=1)  # Anfragen je IP und Minute

    log_level: str = "INFO"

    def production_warnings(self) -> list[str]:
        """Unsichere Einstellungen, die in ENVIRONMENT=production nicht gewollt sein sollten.
        Nur Warnungen (kein Abbruch), damit bestehende Installationen weiterlaufen."""
        if self.environment.lower() != "production":
            return []
        warnings = []
        if not self.cookie_secure:
            warnings.append(
                "COOKIE_SECURE=false: das Session-Cookie wird ohne Secure-Flag gesendet. Hinter HTTPS auf true setzen."
            )
        if self.docs_enabled:
            warnings.append(
                "DOCS_ENABLED=true: /docs, /redoc und /openapi.json sind öffentlich erreichbar. In Produktion auf false setzen."
            )
        return warnings

    @property
    def max_pdf_bytes(self) -> int:
        return self.max_pdf_size_mb * 1024 * 1024

    @property
    def max_image_bytes(self) -> int:
        return self.max_image_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
