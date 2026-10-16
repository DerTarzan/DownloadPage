import logging
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, UnprocessableError
from app.models.document import Document
from app.repositories.category_repository import CategoryRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.document import DocumentUpdate
from app.services.base import commit_or_conflict
from app.services.file_service import FileService, InvalidStoragePathError

logger = logging.getLogger("app.documents")
downloads = logging.getLogger("app.downloads")  # Erweiterungspunkt: später DB-Logging / Statistik


class DocumentService:
    def __init__(self, db: Session, files: FileService):
        self.db = db
        self.files = files
        self.repo = DocumentRepository(db)
        self.products = ProductRepository(db)
        self.categories = CategoryRepository(db)

    # --- Lesen ---
    def list_admin(self, product_id: int | None = None, active: bool | None = None) -> list[Document]:
        return self.repo.list(product_id=product_id, active=active)

    def list_public(self, product_id: int) -> list[Document]:
        return self.repo.list_active_for_product(product_id)

    def get(self, document_id: int) -> Document:
        document = self.repo.get(document_id)
        if document is None:
            raise NotFoundError("Dokument nicht gefunden")
        return document

    def get_public_download(
        self, document_id: int, category_slug: str | None = None, product_slug: str | None = None
    ) -> tuple[Document, Path]:
        """Liefert Dokument + Dateipfad, nur wenn Dokument, Produkt und Kategorie aktiv sind."""
        found = self.repo.get_public(document_id)
        if found is None:
            raise NotFoundError("Dokument nicht gefunden")
        document, product, category = found
        if not all(item.active for item in self.categories.path(category)):
            raise NotFoundError("Dokument nicht gefunden")
        if (category_slug and category.slug != category_slug) or (product_slug and product.slug != product_slug):
            raise NotFoundError("Dokument nicht gefunden")
        try:
            path = self.files.resolve(document.storage_path)
        except InvalidStoragePathError:
            logger.error("Ungültiger storage_path bei Dokument %s", document.id)
            raise NotFoundError("Dokument nicht gefunden")
        if not path.is_file():
            logger.error("Datei fehlt im Storage: Dokument %s (%s)", document.id, document.storage_path)
            raise NotFoundError("Dokument nicht gefunden")
        downloads.info("Download document_id=%s product_id=%s", document.id, document.product_id)
        return document, path

    # --- Schreiben ---
    def create(
        self,
        product_id: int,
        upload: UploadFile,
        *,
        title: str | None,
        description: str | None,
        version: str,
        active: bool,
        uploaded_by: int | None,
    ) -> Document:
        if self.products.get(product_id) is None:
            raise NotFoundError("Produkt nicht gefunden")
        stored = self.files.save_document(upload)
        document = Document(
            product_id=product_id,
            title=(title or "").strip() or Path(stored.original_filename).stem[:200],
            description=description,
            original_filename=stored.original_filename,
            storage_path=stored.relative_path,
            mime_type=stored.mime_type,
            file_size=stored.size,
            checksum_sha256=stored.sha256,
            version=version,
            active=active,
            uploaded_by=uploaded_by,
        )
        try:
            self.repo.add(document)
            commit_or_conflict(self.db)
        except Exception:
            self.db.rollback()
            self.files.delete(stored.relative_path)  # keine verwaisten Dateien
            raise
        return document

    def replace_file(self, document_id: int, upload: UploadFile, version: str | None = None) -> Document:
        document = self.get(document_id)
        stored = self.files.save_document(upload)
        old_path = document.storage_path
        document.original_filename = stored.original_filename
        document.storage_path = stored.relative_path
        document.mime_type = stored.mime_type
        document.file_size = stored.size
        document.checksum_sha256 = stored.sha256
        if version:
            document.version = version
        try:
            commit_or_conflict(self.db)
        except Exception:
            self.db.rollback()
            self.files.delete(stored.relative_path)
            raise
        self.files.delete(old_path)
        return document

    def update(self, document_id: int, data: DocumentUpdate) -> Document:
        document = self.get(document_id)
        values = data.model_dump(exclude_unset=True)
        if values.get("product_id") is not None and values["product_id"] != document.product_id:
            if self.products.get(values["product_id"]) is None:
                raise UnprocessableError("Das angegebene Produkt existiert nicht")
            document.product_id = values["product_id"]
        if values.get("title") is not None:
            document.title = values["title"].strip()
        if "description" in values:
            document.description = values["description"]
        if values.get("version") is not None:
            document.version = values["version"].strip()
        if values.get("active") is not None:
            document.active = values["active"]
        commit_or_conflict(self.db)
        return document

    def delete(self, document_id: int) -> None:
        document = self.get(document_id)
        path = document.storage_path
        self.repo.delete(document)
        commit_or_conflict(self.db)
        self.files.delete(path)  # erst nach erfolgreichem Commit
