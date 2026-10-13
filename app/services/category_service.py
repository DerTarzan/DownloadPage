import logging

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, UnprocessableError
from app.core.slugs import RESERVED_SLUGS, slugify, unique_slug
from app.models.category import Category
from app.repositories.category_repository import CategoryRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services.base import commit_or_conflict
from app.services.file_service import FileService

logger = logging.getLogger("app.categories")


class CategoryService:
    def __init__(self, db: Session, files: FileService):
        self.db = db
        self.files = files
        self.repo = CategoryRepository(db)
        self.products = ProductRepository(db)
        self.documents = DocumentRepository(db)

    # --- Lesen ---
    def list_admin(self) -> list[Category]:
        return self.repo.list()

    def list_public(self) -> list[Category]:
        return self.repo.list(active_only=True)

    def get(self, category_id: int) -> Category:
        category = self.repo.get(category_id)
        if category is None:
            raise NotFoundError("Kategorie nicht gefunden")
        return category

    def get_public_by_slug(self, slug: str) -> Category:
        category = self.repo.get_by_slug(slug)
        if category is None or not category.active:
            raise NotFoundError("Kategorie nicht gefunden")
        return category

    # --- Schreiben ---
    def _explicit_slug(self, raw: str, exclude_id: int | None = None) -> str:
        slug = slugify(raw)
        if not slug:
            raise UnprocessableError("Slug enthält keine gültigen Zeichen")
        if slug in RESERVED_SLUGS or self.repo.slug_exists(slug, exclude_id):
            raise ConflictError(f"Slug '{slug}' ist bereits vergeben")
        return slug

    def create(self, data: CategoryCreate) -> Category:
        if data.slug:
            slug = self._explicit_slug(data.slug)
        else:
            slug = unique_slug(slugify(data.name), lambda s: s in RESERVED_SLUGS or self.repo.slug_exists(s), "kategorie")
        category = Category(
            name=data.name.strip(),
            slug=slug,
            description=data.description,
            sort_order=data.sort_order if data.sort_order is not None else self.repo.next_sort_order(),
            active=data.active,
        )
        self.repo.add(category)
        commit_or_conflict(self.db, "Slug ist bereits vergeben")
        return category

    def update(self, category_id: int, data: CategoryUpdate) -> Category:
        category = self.get(category_id)
        values = data.model_dump(exclude_unset=True)
        if values.get("slug"):
            category.slug = self._explicit_slug(values["slug"], exclude_id=category.id)
        if values.get("name") is not None:
            category.name = values["name"].strip()
        if "description" in values:
            category.description = values["description"]
        if values.get("sort_order") is not None:
            category.sort_order = values["sort_order"]
        if values.get("active") is not None:
            category.active = values["active"]
        commit_or_conflict(self.db, "Slug ist bereits vergeben")
        return category

    def reorder(self, ids: list[int]) -> list[Category]:
        categories = {c.id: c for c in self.repo.list()}
        if len(set(ids)) != len(ids) or set(ids) != set(categories):
            raise UnprocessableError("ids muss genau alle vorhandenen Kategorie-IDs genau einmal enthalten")
        for position, category_id in enumerate(ids, start=1):
            categories[category_id].sort_order = position
        commit_or_conflict(self.db)
        return self.repo.list()

    def delete(self, category_id: int, cascade: bool = False) -> None:
        """Standard: 409, solange Produkte existieren. Mit cascade=true werden Produkte,
        Dokumente und alle zugehörigen Dateien bewusst mitgelöscht."""
        category = self.get(category_id)
        products = self.products.list(category_id=category.id)
        if products and not cascade:
            raise ConflictError(
                f"Kategorie enthält noch {len(products)} Produkt(e). Erst verschieben/löschen oder cascade=true verwenden."
            )
        files_to_delete: list[str | None] = [category.image_path]
        for document in self.documents.list_for_category(category.id):
            files_to_delete.append(document.storage_path)
            self.documents.delete(document)
        for product in products:
            files_to_delete.append(product.image_path)
            self.products.delete(product)
        self.repo.delete(category)
        commit_or_conflict(self.db)
        for path in files_to_delete:  # erst nach erfolgreichem Commit
            self.files.delete(path)

    # --- Bild ---
    def set_image(self, category_id: int, upload: UploadFile) -> Category:
        category = self.get(category_id)
        stored = self.files.save_image(upload)
        old = category.image_path
        category.image_path = stored.relative_path
        try:
            commit_or_conflict(self.db)
        except Exception:
            self.files.delete(stored.relative_path)
            raise
        self.files.delete(old)
        return category

    def remove_image(self, category_id: int) -> None:
        category = self.get(category_id)
        old = category.image_path
        category.image_path = None
        commit_or_conflict(self.db)
        self.files.delete(old)
