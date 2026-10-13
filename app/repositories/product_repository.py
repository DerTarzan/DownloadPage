from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.document import Document
from app.models.product import Product


class ProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, product_id: int) -> Product | None:
        return self.db.get(Product, product_id)

    def list(self, *, category_id: int | None = None, active: bool | None = None) -> list[Product]:
        stmt = select(Product).order_by(Product.category_id, Product.sort_order, Product.id)
        if category_id is not None:
            stmt = stmt.where(Product.category_id == category_id)
        if active is not None:
            stmt = stmt.where(Product.active.is_(active))
        return list(self.db.scalars(stmt))

    def list_active_in_category(self, category_id: int) -> list[Product]:
        return self.list(category_id=category_id, active=True)

    def get_public(self, category_slug: str, product_slug: str) -> tuple[Category, Product] | None:
        row = self.db.execute(
            select(Category, Product)
            .join(Product, Product.category_id == Category.id)
            .where(
                Category.slug == category_slug,
                Product.slug == product_slug,
                Category.active.is_(True),
                Product.active.is_(True),
            )
        ).first()
        return (row[0], row[1]) if row else None

    def slug_exists(self, category_id: int, slug: str, exclude_id: int | None = None) -> bool:
        stmt = select(func.count()).select_from(Product).where(Product.category_id == category_id, Product.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(Product.id != exclude_id)
        return self.db.scalar(stmt) > 0

    def next_sort_order(self, category_id: int) -> int:
        return (
            self.db.scalar(select(func.max(Product.sort_order)).where(Product.category_id == category_id)) or 0
        ) + 1

    def document_count(self, product_id: int) -> int:
        return self.db.scalar(select(func.count()).select_from(Document).where(Document.product_id == product_id))

    def add(self, product: Product) -> Product:
        self.db.add(product)
        self.db.flush()
        return product

    def delete(self, product: Product) -> None:
        self.db.delete(product)
        self.db.flush()
