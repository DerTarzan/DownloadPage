import logging

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, UnprocessableError
from app.core.slugs import slugify, unique_slug
from app.models.category import Category
from app.models.product import Product
from app.repositories.category_repository import CategoryRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.base import commit_or_conflict
from app.services.file_service import FileService

logger = logging.getLogger("app.products")


class ProductService:
    def __init__(self, db: Session, files: FileService):
        self.db = db
        self.files = files
        self.repo = ProductRepository(db)
        self.categories = CategoryRepository(db)
        self.documents = DocumentRepository(db)

    # --- Lesen ---
    def list_admin(self, category_id: int | None = None, active: bool | None = None) -> list[Product]:
        return self.repo.list(category_id=category_id, active=active)

    def list_public(self, category: Category) -> list[Product]:
        return self.repo.list_active_in_category(category.id)

    def get(self, product_id: int) -> Product:
        product = self.repo.get(product_id)
        if product is None:
            raise NotFoundError("Produkt nicht gefunden")
        return product

    def get_public(self, category_slug: str, product_slug: str) -> tuple[Category, Product]:
        found = self.repo.get_public(category_slug, product_slug)
        if found is None:
            raise NotFoundError("Produkt nicht gefunden")
        return found

    # --- Schreiben ---
    def _require_category(self, category_id: int) -> Category:
        category = self.categories.get(category_id)
        if category is None:
            raise UnprocessableError("Die angegebene Kategorie existiert nicht")
        return category

    def _explicit_slug(self, category_id: int, raw: str, exclude_id: int | None = None) -> str:
        slug = slugify(raw)
        if not slug:
            raise UnprocessableError("Slug enthält keine gültigen Zeichen")
        if self.repo.slug_exists(category_id, slug, exclude_id):
            raise ConflictError(f"Slug '{slug}' ist in dieser Kategorie bereits vergeben")
        return slug

    def create(self, data: ProductCreate) -> Product:
        self._require_category(data.category_id)
        if data.slug:
            slug = self._explicit_slug(data.category_id, data.slug)
        else:
            slug = unique_slug(slugify(data.name), lambda s: self.repo.slug_exists(data.category_id, s), "produkt")
        product = Product(
            category_id=data.category_id,
            name=data.name.strip(),
            slug=slug,
            description=data.description,
            sort_order=data.sort_order if data.sort_order is not None else self.repo.next_sort_order(data.category_id),
            active=data.active,
        )
        self.repo.add(product)
        commit_or_conflict(self.db, "Slug ist in dieser Kategorie bereits vergeben")
        return product

    def update(self, product_id: int, data: ProductUpdate) -> Product:
        product = self.get(product_id)
        values = data.model_dump(exclude_unset=True)
        target_category = product.category_id
        if values.get("category_id") is not None and values["category_id"] != product.category_id:
            target_category = self._require_category(values["category_id"]).id
        new_slug = product.slug
        if values.get("slug"):
            new_slug = self._explicit_slug(target_category, values["slug"], exclude_id=product.id)
        elif target_category != product.category_id and self.repo.slug_exists(target_category, product.slug):
            raise ConflictError("Slug existiert bereits in der Ziel-Kategorie; bitte zusätzlich einen neuen Slug angeben")
        if target_category != product.category_id:
            product.sort_order = self.repo.next_sort_order(target_category)
        product.category_id = target_category
        product.slug = new_slug
        if values.get("name") is not None:
            product.name = values["name"].strip()
        if "description" in values:
            product.description = values["description"]
        if values.get("sort_order") is not None:
            product.sort_order = values["sort_order"]
        if values.get("active") is not None:
            product.active = values["active"]
        commit_or_conflict(self.db, "Slug ist in dieser Kategorie bereits vergeben")
        return product

    def reorder(self, category_id: int, ids: list[int]) -> list[Product]:
        self._require_category(category_id)
        products = {p.id: p for p in self.repo.list(category_id=category_id)}
        if len(set(ids)) != len(ids) or set(ids) != set(products):
            raise UnprocessableError("ids muss genau alle Produkt-IDs dieser Kategorie genau einmal enthalten")
        for position, product_id in enumerate(ids, start=1):
            products[product_id].sort_order = position
        commit_or_conflict(self.db)
        return self.repo.list(category_id=category_id)

    def delete(self, product_id: int, cascade: bool = False) -> None:
        product = self.get(product_id)
        documents = self.documents.list(product_id=product.id)
        if documents and not cascade:
            raise ConflictError(
                f"Produkt enthält noch {len(documents)} Dokument(e). Erst löschen oder cascade=true verwenden."
            )
        files_to_delete: list[str | None] = [product.image_path]
        for document in documents:
            files_to_delete.append(document.storage_path)
            self.documents.delete(document)
        self.repo.delete(product)
        commit_or_conflict(self.db)
        for path in files_to_delete:
            self.files.delete(path)

    # --- Bild ---
    def set_image(self, product_id: int, upload: UploadFile) -> Product:
        product = self.get(product_id)
        stored = self.files.save_image(upload)
        old = product.image_path
        product.image_path = stored.relative_path
        try:
            commit_or_conflict(self.db)
        except Exception:
            self.files.delete(stored.relative_path)
            raise
        self.files.delete(old)
        return product

    def remove_image(self, product_id: int) -> None:
        product = self.get(product_id)
        old = product.image_path
        product.image_path = None
        commit_or_conflict(self.db)
        self.files.delete(old)
