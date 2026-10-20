from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatContext(BaseModel):
    """Produkt, auf das sich „dieses Produkt“ bezieht (zuletzt gezeigter Treffer bzw. aktuelle Seite). Wird serverseitig geprüft."""

    category_slug: str = Field(max_length=100, pattern=r"^[a-z0-9-]+$")
    product_slug: str = Field(max_length=100, pattern=r"^[a-z0-9-]+$")


class ChatRequest(BaseModel):
    # Obergrenze hier fest; die konfigurierte (kleinere) Grenze CHAT_MAX_MESSAGE_LENGTH prüft der Router
    message: str = Field(max_length=2000)
    lang: Literal["de", "en"] = "de"
    context: ChatContext | None = None

    @field_validator("message")
    @classmethod
    def _strip(cls, v: str) -> str:
        return " ".join(v.split())


class ChatDocument(BaseModel):
    title: str
    url: str
    version: str
    file_size: int
    matched: bool = False


class ChatProduct(BaseModel):
    name: str
    url: str
    description: str | None = None
    image_url: str | None = None
    category_name: str
    category_url: str
    category_path: list[str]
    documents: list[ChatDocument] = []


class ChatCategory(BaseModel):
    name: str
    url: str
    product_count: int


ChatKind = Literal["greeting", "clarify", "found", "multiple", "category", "documents", "none"]


class ChatResponse(BaseModel):
    reply: str
    kind: ChatKind
    lang: Literal["de", "en"]
    results: list[ChatProduct] = []
    similar: list[ChatProduct] = []
    categories: list[ChatCategory] = []
