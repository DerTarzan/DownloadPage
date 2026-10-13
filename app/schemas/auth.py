from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    is_admin: bool
    is_active: bool
    last_login: datetime | None


class SessionInfo(BaseModel):
    user: UserOut
    csrf_token: str = Field(description="Muss bei schreibenden Requests als Header X-CSRF-Token gesendet werden")
