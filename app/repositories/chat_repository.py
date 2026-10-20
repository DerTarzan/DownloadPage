from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.document import Document
from app.models.product import Product


class ChatRepository:
    """Nur lesend; liefert schlanke Zeilen (keine Dateipfade) für die Chat-Suche."""

    def __init__(self, db: Session):
        self.db = db

    def categories(self):
        return self.db.execute(
            select(Category.id, Category.parent_id, Category.name, Category.slug, Category.description, Category.active)
            .order_by(Category.sort_order, Category.id)
        ).all()

    def active_products(self):
        return self.db.execute(
            select(Product.id, Product.category_id, Product.name, Product.slug, Product.description, Product.image_path)
            .where(Product.active.is_(True))
            .order_by(Product.category_id, Product.sort_order, Product.id)
        ).all()

    def active_documents(self):
        return self.db.execute(
            select(Document.id, Document.product_id, Document.title, Document.original_filename, Document.version, Document.file_size)
            .where(Document.active.is_(True))
            .order_by(Document.product_id, Document.id)
        ).all()
