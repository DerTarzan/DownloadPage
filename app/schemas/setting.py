from pydantic import BaseModel, Field


class SiteSettingsOut(BaseModel):
    maintenance_mode: bool
    maintenance_message: str


class SiteSettingsUpdate(BaseModel):
    maintenance_mode: bool | None = None
    maintenance_message: str | None = Field(default=None, max_length=1000)
