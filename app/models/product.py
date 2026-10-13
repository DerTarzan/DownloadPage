from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.document import Document


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("category_id", "slug", name="uq_products_category_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(String(512))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    category: Mapped["Category"] = relationship(back_populates="products")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="product", passive_deletes="all", order_by="Document.id"
    )

    @property
    def image_url(self) -> str | None:
        return f"/media/{self.image_path}" if self.image_path else None
