from pydantic import BaseModel, Field


class SiteSettingsOut(BaseModel):
    maintenance_mode: bool
    maintenance_message: str


class SiteSettingsUpdate(BaseModel):
    maintenance_mode: bool | None = None
    maintenance_message: str | None = Field(default=None, max_length=1000)


class ChatbotOut(BaseModel):
    enabled: bool = Field(description="Schalter im Admin-Bereich")
    available: bool = Field(description="False, wenn der Chatbot per Server-Konfiguration (CHAT_ENABLED=false) gesperrt ist")
    active: bool = Field(description="Tatsächlich im Einsatz (enabled und available)")


class ChatbotUpdate(BaseModel):
    enabled: bool
