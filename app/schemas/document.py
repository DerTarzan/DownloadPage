from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    version: str | None = Field(default=None, min_length=1, max_length=32)
    active: bool | None = None
    product_id: int | None = Field(default=None, ge=1, description="Dokument einem anderen Produkt zuordnen")


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    title: str
    description: str | None
    original_filename: str
    mime_type: str
    file_size: int
    checksum_sha256: str | None
    version: str
    active: bool
    uploaded_by: int | None
    download_url: str
    created_at: datetime
    updated_at: datetime


class PublicDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str | None
    original_filename: str
    mime_type: str
    file_size: int
    version: str
    download_url: str
