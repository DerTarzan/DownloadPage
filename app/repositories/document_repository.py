from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.document import Document
from app.models.product import Product


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, document_id: int) -> Document | None:
        return self.db.get(Document, document_id)

    def list(self, *, product_id: int | None = None, active: bool | None = None) -> list[Document]:
        stmt = select(Document).order_by(Document.product_id, Document.id)
        if product_id is not None:
            stmt = stmt.where(Document.product_id == product_id)
        if active is not None:
            stmt = stmt.where(Document.active.is_(active))
        return list(self.db.scalars(stmt))

    def list_active_for_product(self, product_id: int) -> list[Document]:
        return self.list(product_id=product_id, active=True)

    def list_for_category(self, category_id: int) -> list[Document]:
        return list(
            self.db.scalars(
                select(Document).join(Product, Product.id == Document.product_id).where(Product.category_id == category_id)
            )
        )

    def get_public(self, document_id: int) -> tuple[Document, Product, Category] | None:
        """Nur wenn Dokument, Produkt UND Kategorie aktiv sind."""
        row = self.db.execute(
            select(Document, Product, Category)
            .join(Product, Product.id == Document.product_id)
            .join(Category, Category.id == Product.category_id)
            .where(
                Document.id == document_id,
                Document.active.is_(True),
                Product.active.is_(True),
                Category.active.is_(True),
            )
        ).first()
        return (row[0], row[1], row[2]) if row else None

    def add(self, document: Document) -> Document:
        self.db.add(document)
        self.db.flush()
        return document

    def delete(self, document: Document) -> None:
        self.db.delete(document)
        self.db.flush()
