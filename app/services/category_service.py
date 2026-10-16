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
        return self.repo.list(active_only=True, roots_only=True)

    def list_public_children(self, category: Category) -> list[Category]:
        return self.repo.list(active_only=True, parent_id=category.id)

    def path(self, category: Category) -> list[Category]:
        return self.repo.path(category)

    def get(self, category_id: int) -> Category:
        category = self.repo.get(category_id)
        if category is None:
            raise NotFoundError("Kategorie nicht gefunden")
        return category

    def get_public_by_slug(self, slug: str) -> Category:
        category = self.repo.get_by_slug(slug)
        if category is None or not all(item.active for item in self.repo.path(category)):
            raise NotFoundError("Kategorie nicht gefunden")
        return category

    def _validate_parent(self, category_id: int | None, parent_id: int | None) -> None:
        current_id = parent_id
        seen: set[int] = set()
        while current_id is not None:
            if current_id == category_id:
                raise UnprocessableError(
                    "Eine Kategorie kann nicht sich selbst oder einen Nachfahren als Elternkategorie haben"
                )
            if current_id in seen:
                raise UnprocessableError("Die ausgewählte Elternkategorie enthält bereits einen Kategorie-Zyklus")
            seen.add(current_id)
            current = self.repo.get(current_id)
            if current is None:
                raise UnprocessableError("Die angegebene übergeordnete Kategorie existiert nicht")
            current_id = current.parent_id

    # --- Schreiben ---
    def _explicit_slug(self, raw: str, exclude_id: int | None = None) -> str:
        slug = slugify(raw)
        if not slug:
            raise UnprocessableError("Slug enthält keine gültigen Zeichen")
        if slug in RESERVED_SLUGS or self.repo.slug_exists(slug, exclude_id):
            raise ConflictError(f"Slug '{slug}' ist bereits vergeben")
        return slug

    def create(self, data: CategoryCreate) -> Category:
        self._validate_parent(None, data.parent_id)
        if data.slug:
            slug = self._explicit_slug(data.slug)
        else:
            slug = unique_slug(slugify(data.name), lambda s: s in RESERVED_SLUGS or self.repo.slug_exists(s), "kategorie")
        category = Category(
            name=data.name.strip(),
            slug=slug,
            parent_id=data.parent_id,
            description=data.description,
            sort_order=data.sort_order if data.sort_order is not None else self.repo.next_sort_order(data.parent_id),
            active=data.active,
        )
        self.repo.add(category)
        commit_or_conflict(self.db, "Slug ist bereits vergeben")
        return category

    def update(self, category_id: int, data: CategoryUpdate) -> Category:
        category = self.get(category_id)
        values = data.model_dump(exclude_unset=True)
        if "parent_id" in values and values["parent_id"] != category.parent_id:
            self._validate_parent(category.id, values["parent_id"])
            category.parent_id = values["parent_id"]
            if values.get("sort_order") is None:
                category.sort_order = self.repo.next_sort_order(category.parent_id)
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
        """Standard: 409, solange Unterkategorien oder Produkte existieren.
        Mit cascade=true wird der gesamte Unterbaum samt zugehörigen Dateien gelöscht."""
        category = self.get(category_id)
        all_categories = self.repo.list()
        children_by_parent: dict[int, list[Category]] = {}
        for item in all_categories:
            if item.parent_id is not None:
                children_by_parent.setdefault(item.parent_id, []).append(item)
        subtree = []
        pending = [category]
        seen: set[int] = set()
        while pending:
            current = pending.pop()
            if current.id in seen:
                raise UnprocessableError("Die Kategorienstruktur enthält einen Zyklus")
            seen.add(current.id)
            subtree.append(current)
            pending.extend(children_by_parent.get(current.id, []))

        products = [p for item in subtree for p in self.products.list(category_id=item.id)]
        if (len(subtree) > 1 or products) and not cascade:
            raise ConflictError(
                f"Kategorie enthält {len(subtree) - 1} Unterkategorie(n) und {len(products)} Produkt(e). "
                "Erst verschieben/löschen oder cascade=true verwenden."
            )
        files_to_delete: list[str | None] = [item.image_path for item in subtree]
        for item in subtree:
            for document in self.documents.list_for_category(item.id):
                files_to_delete.append(document.storage_path)
                self.documents.delete(document)
        for product in products:
            files_to_delete.append(product.image_path)
            self.products.delete(product)
        for item in reversed(subtree):
            self.repo.delete(item)
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
