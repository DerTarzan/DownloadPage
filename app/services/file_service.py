"""Datei-Storage (lokal). Später ersetzbar durch S3/MinIO mit gleicher Schnittstelle.

Sicherheit:
- interne Dateinamen sind UUIDs, nie der Name des Benutzers
- Pfade werden nur aus relativen, in der DB gespeicherten Werten gebildet und gegen den Storage-Root geprüft
- Typprüfung per Endung, deklariertem Content-Type UND Magic Bytes
- Größenlimit wird beim Streamen erzwungen (kein vollständiges Laden in den RAM)
"""
import hashlib
import logging
import os
import re
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.exceptions import BadRequestError, PayloadTooLargeError, UnsupportedFileTypeError

logger = logging.getLogger("app.files")

CHUNK_SIZE = 1024 * 1024
ALLOWED_TOP_DIRS = {"images", "documents"}
PDF_CONTENT_TYPES = {"application/pdf"}
IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}
IMAGE_EXTENSIONS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
IMAGE_SUFFIX_BY_MIME = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


class InvalidStoragePathError(ValueError):
    pass


@dataclass(frozen=True)
class StoredFile:
    relative_path: str
    size: int
    sha256: str
    mime_type: str
    original_filename: str


def sanitize_filename(raw: str | None, default: str = "datei") -> str:
    """Nur der Basisname, ohne Pfadanteile/Steuerzeichen/Sonderzeichen (für Anzeige & Download-Namen)."""
    name = (raw or "").replace("\\", "/").split("/")[-1]
    name = unicodedata.normalize("NFKC", name)
    name = "".join(ch for ch in name if ch.isprintable())
    name = re.sub(r"[^\w.\- ()]", "_", name).strip(" .")
    name = re.sub(r"\.{2,}", ".", name)
    if not name:
        return default
    if len(name) > 150:
        root, ext = os.path.splitext(name)
        name = root[: 150 - len(ext)] + ext
    return name


def sniff_image_type(head: bytes) -> str | None:
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def _declared_type(upload: UploadFile) -> str:
    return (upload.content_type or "").split(";")[0].strip().lower()


class FileService:
    def __init__(self, root: Path, max_pdf_bytes: int, max_image_bytes: int):
        self.root = Path(root).resolve()
        self.max_pdf_bytes = max_pdf_bytes
        self.max_image_bytes = max_image_bytes
        for sub in ALLOWED_TOP_DIRS:
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    # ---- Pfade ----
    def resolve(self, relative_path: str) -> Path:
        if not relative_path or "\x00" in relative_path or "\\" in relative_path or relative_path.startswith("/"):
            raise InvalidStoragePathError("ungültiger Pfad")
        parts = relative_path.split("/")  # bewusst kein PurePosixPath: es würde "./" still wegnormalisieren
        if len(parts) < 2 or parts[0] not in ALLOWED_TOP_DIRS or any(p in ("..", ".", "") for p in parts):
            raise InvalidStoragePathError("ungültiger Pfad")
        candidate = (self.root / relative_path).resolve()
        if not candidate.is_relative_to(self.root):
            raise InvalidStoragePathError("Pfad außerhalb des Storage")
        return candidate

    def exists(self, relative_path: str) -> bool:
        try:
            return self.resolve(relative_path).is_file()
        except InvalidStoragePathError:
            return False

    # ---- Speichern ----
    def save_document(self, upload: UploadFile) -> StoredFile:
        filename = sanitize_filename(upload.filename)
        if Path(filename).suffix.lower() != ".pdf":
            raise UnsupportedFileTypeError("Nur PDF-Dateien (.pdf) sind erlaubt")
        if _declared_type(upload) not in PDF_CONTENT_TYPES:
            raise UnsupportedFileTypeError("Content-Type muss application/pdf sein")

        def check_head(head: bytes) -> None:
            if b"%PDF-" not in head[:1024]:
                raise UnsupportedFileTypeError("Die Datei ist kein gültiges PDF")

        rel = f"documents/{uuid.uuid4().hex}/{uuid.uuid4().hex}.pdf"
        size, sha = self._stream_to_disk(upload, self.resolve(rel), self.max_pdf_bytes, check_head)
        return StoredFile(rel, size, sha, "application/pdf", filename)

    def save_image(self, upload: UploadFile) -> StoredFile:
        filename = sanitize_filename(upload.filename)
        ext = Path(filename).suffix.lower()
        if ext not in IMAGE_EXTENSIONS:
            raise UnsupportedFileTypeError("Erlaubt sind nur PNG, JPEG und WebP")
        if _declared_type(upload) not in IMAGE_CONTENT_TYPES:
            raise UnsupportedFileTypeError("Content-Type muss image/png, image/jpeg oder image/webp sein")
        detected: list[str] = []

        def check_head(head: bytes) -> None:
            mime = sniff_image_type(head)
            if mime is None or mime != IMAGE_EXTENSIONS[ext]:
                raise UnsupportedFileTypeError("Dateiinhalt passt nicht zum Bildtyp")
            detected.append(mime)

        rel = f"images/{uuid.uuid4().hex}{IMAGE_SUFFIX_BY_MIME[IMAGE_EXTENSIONS[ext]]}"
        size, sha = self._stream_to_disk(upload, self.resolve(rel), self.max_image_bytes, check_head)
        return StoredFile(rel, size, sha, detected[0], filename)

    def _stream_to_disk(
        self, upload: UploadFile, dest: Path, max_bytes: int, check_head: Callable[[bytes], None]
    ) -> tuple[int, str]:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".part")
        sha = hashlib.sha256()
        size = 0
        try:
            with open(tmp, "xb") as out:
                while chunk := upload.file.read(CHUNK_SIZE):
                    if size == 0:
                        check_head(chunk[:1024])
                    size += len(chunk)
                    if size > max_bytes:
                        raise PayloadTooLargeError(f"Datei ist zu groß (maximal {max_bytes // (1024 * 1024)} MB)")
                    sha.update(chunk)
                    out.write(chunk)
            if size == 0:
                raise BadRequestError("Die Datei ist leer")
            os.replace(tmp, dest)
        except BaseException:
            tmp.unlink(missing_ok=True)
            self._rmdir_if_document_dir(dest)
            raise
        return size, sha.hexdigest()

    # ---- Löschen ----
    def delete(self, relative_path: str | None) -> None:
        """Best effort: Fehler werden geloggt, nie an den Benutzer durchgereicht."""
        if not relative_path:
            return
        try:
            path = self.resolve(relative_path)
        except InvalidStoragePathError:
            logger.error("Löschen verweigert, ungültiger Pfad in der Datenbank: %r", relative_path)
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Datei konnte nicht gelöscht werden: %s", relative_path)
            return
        self._rmdir_if_document_dir(path)

    def _rmdir_if_document_dir(self, path: Path) -> None:
        if path.parent.parent == self.root / "documents":
            try:
                path.parent.rmdir()
            except OSError:
                pass


@lru_cache
def get_file_service() -> FileService:
    s = get_settings()
    return FileService(s.storage_dir, s.max_pdf_bytes, s.max_image_bytes)
