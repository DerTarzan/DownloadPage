from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.product import Product


class CategoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, category_id: int) -> Category | None:
        return self.db.get(Category, category_id)

    def get_by_slug(self, slug: str) -> Category | None:
        return self.db.scalar(select(Category).where(Category.slug == slug))

    def list(self, *, active_only: bool = False) -> list[Category]:
        stmt = select(Category).order_by(Category.sort_order, Category.id)
        if active_only:
            stmt = stmt.where(Category.active.is_(True))
        return list(self.db.scalars(stmt))

    def slug_exists(self, slug: str, exclude_id: int | None = None) -> bool:
        stmt = select(func.count()).select_from(Category).where(Category.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(Category.id != exclude_id)
        return self.db.scalar(stmt) > 0

    def next_sort_order(self) -> int:
        return (self.db.scalar(select(func.max(Category.sort_order))) or 0) + 1

    def product_count(self, category_id: int) -> int:
        return self.db.scalar(select(func.count()).select_from(Product).where(Product.category_id == category_id))

    def add(self, category: Category) -> Category:
        self.db.add(category)
        self.db.flush()
        return category

    def delete(self, category: Category) -> None:
        self.db.delete(category)
        self.db.flush()
