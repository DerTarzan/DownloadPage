from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.product import Product


class Document(TimestampMixin, Base):
    """Metadaten eines Dokuments; die Datei selbst liegt im Storage (nie als BLOB in der DB).

    Erweiterbarkeit: Für echte Versionierung kann später eine Tabelle `document_versions`
    (document_id, version, storage_path, ...) ergänzt werden; `version` bleibt dann die aktuelle Version.
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(512), unique=True)  # relativ zum Storage-Root
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(32), default="1.0", server_default="1.0")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    product: Mapped["Product"] = relationship(back_populates="documents")

    @property
    def download_url(self) -> str:
        return f"/documents/{self.id}/download"
