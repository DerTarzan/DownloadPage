from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.product import Product


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(String(512))  # relativ zum Storage-Root
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0", index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    # passive_deletes="all": das Löschen steuern die Services (inkl. Dateien), nie die ORM-Kaskade
    products: Mapped[list["Product"]] = relationship(
        back_populates="category", passive_deletes="all", order_by="Product.sort_order, Product.id"
    )

    @property
    def image_url(self) -> str | None:
        return f"/media/{self.image_path}" if self.image_path else None
