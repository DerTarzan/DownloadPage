from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.category import PublicCategory
from app.schemas.document import PublicDocument


class ProductCreate(BaseModel):
    category_id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=100)
    description: str | None = None
    sort_order: int | None = Field(default=None, ge=0, le=1_000_000)
    active: bool = True


class ProductUpdate(BaseModel):
    category_id: int | None = Field(default=None, ge=1, description="Verschiebt das Produkt in eine andere Kategorie")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=100)
    description: str | None = None
    sort_order: int | None = Field(default=None, ge=0, le=1_000_000)
    active: bool | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category_id: int
    name: str
    slug: str
    description: str | None
    image_url: str | None
    sort_order: int
    active: bool
    created_at: datetime
    updated_at: datetime


class ProductReorderRequest(BaseModel):
    category_id: int = Field(ge=1)
    ids: list[int] = Field(min_length=1)


class PublicProduct(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    slug: str
    description: str | None
    image_url: str | None


class PublicCategoryList(BaseModel):
    categories: list[PublicCategory]


class PublicCategoryDetail(BaseModel):
    category: PublicCategory
    products: list[PublicProduct]


class PublicProductDetail(BaseModel):
    category: PublicCategory
    product: PublicProduct
    documents: list[PublicDocument]
