from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=100, description="Optional; sonst automatisch aus dem Namen")
    description: str | None = None
    sort_order: int | None = Field(default=None, ge=0, le=1_000_000)
    active: bool = True


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=100)
    description: str | None = None
    sort_order: int | None = Field(default=None, ge=0, le=1_000_000)
    active: bool | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    description: str | None
    image_url: str | None
    sort_order: int
    active: bool
    created_at: datetime
    updated_at: datetime


class PublicCategory(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    slug: str
    description: str | None
    image_url: str | None
