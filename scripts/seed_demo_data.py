"""Fills the configured database with 50 demo categories, products, images, and PDFs."""
import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings

SEED_CATEGORY_PREFIX = "demo-kategorie-"
SEED_PRODUCT_PREFIX = "demo-produkt-"
PDF_SOURCE = ROOT / "storage" / "Gebrauchsanweisung.pdf"
IMAGE_SOURCES = {
    "rampe.jpg": ROOT / "storage" / "rampe.jpg",
    "rollstuhl.jpg": ROOT / "storage" / "rollstuhl.jpg",
    "treppenlift.jpg": ROOT / "storage" / "treppenlift.jpg",
}

ITEMS = [
    ("Mobilität", "Leichtgewichtrollstuhl", "rollstuhl.jpg"),
    ("Rollatoren", "Premium-Rollator", "rollstuhl.jpg"),
    ("Treppenlifte", "Sitzlift Komfort", "treppenlift.jpg"),
    ("Rampen", "Mobile Schwellenrampe", "rampe.jpg"),
    ("Pflegebetten", "Elektrisches Pflegebett", "rollstuhl.jpg"),
    ("Badehilfen", "Duschhocker höhenverstellbar", "rampe.jpg"),
    ("Toilettenhilfen", "Toilettenstützgestell", "rampe.jpg"),
    ("Patientenlifter", "Aktivlifter kompakt", "rollstuhl.jpg"),
    ("Gehhilfen", "Unterarmgehstützen", "rollstuhl.jpg"),
    ("Elektromobile", "Elektromobil City", "treppenlift.jpg"),
    ("Scooter-Zubehör", "Gepäckbox für Scooter", "treppenlift.jpg"),
    ("Rollstuhlzubehör", "Rollstuhlkissen ergonomisch", "rollstuhl.jpg"),
    ("Transferhilfen", "Rutschbrett Komfort", "rampe.jpg"),
    ("Lagerungshilfen", "Positionierungskissen-Set", "rollstuhl.jpg"),
    ("Antidekubitus", "Sitzkissen druckentlastend", "rollstuhl.jpg"),
    ("Duschstühle", "Duschstuhl mit Armlehnen", "rampe.jpg"),
    ("Badewannenhilfen", "Badewannensitz drehbar", "rampe.jpg"),
    ("Haltegriffe", "Wandhaltegriff Edelstahl", "rampe.jpg"),
    ("Aufstehhilfen", "Aufstehsessel elektrisch", "treppenlift.jpg"),
    ("Gehböcke", "Gehbock faltbar", "rollstuhl.jpg"),
    ("Unterarmgehstützen", "Komfortstütze anatomisch", "rollstuhl.jpg"),
    ("Pflegehilfsmittel", "Pflegewagen kompakt", "rollstuhl.jpg"),
    ("Lagerungsrollen", "Lagerungsrolle weich", "rollstuhl.jpg"),
    ("Inkontinenzversorgung", "Bettschutzeinlage waschbar", "rollstuhl.jpg"),
    ("Medikamentenorganisation", "Tablettenbox Wochenplan", "rollstuhl.jpg"),
    ("Vitalmessgeräte", "Blutdruckmessgerät digital", "rollstuhl.jpg"),
    ("Therapiegeräte", "Wärmekissen elektrisch", "rollstuhl.jpg"),
    ("Kompressionsversorgung", "Anziehhilfe für Kompressionsstrümpfe", "rampe.jpg"),
    ("Orthesen", "Handgelenkorthese stabil", "rollstuhl.jpg"),
    ("Bandagen", "Kniebandage elastisch", "rollstuhl.jpg"),
    ("Einlagen", "Alltagseinlage anatomisch", "rollstuhl.jpg"),
    ("Schuhe", "Komfortschuh Klettverschluss", "rollstuhl.jpg"),
    ("Sitzhilfen", "Drehkissen für Transfers", "rampe.jpg"),
    ("Bettzubehör", "Bettgalgen mit Triangelgriff", "rollstuhl.jpg"),
    ("Matratzen", "Pflegematratze Komfort", "rollstuhl.jpg"),
    ("Aufstehhilfen fürs Bett", "Bettleiter Aufrichthilfe", "rollstuhl.jpg"),
    ("Türschwellenhilfen", "Türschwellenrampe flexibel", "rampe.jpg"),
    ("Treppenraupen", "Treppenraupe transportabel", "treppenlift.jpg"),
    ("Deckenlifter", "Deckenlifter Schienensystem", "treppenlift.jpg"),
    ("Badewannenlifter", "Badewannenlifter kompakt", "rampe.jpg"),
    ("Duschsysteme", "Handbrause mit langem Schlauch", "rampe.jpg"),
    ("Toilettenstühle", "Toilettenstuhl fahrbar", "rollstuhl.jpg"),
    ("Ess- und Trinkhilfen", "Trinkbecher mit Nasenausschnitt", "rollstuhl.jpg"),
    ("Greifhilfen", "Greifzange mit Magnet", "rampe.jpg"),
    ("Anziehhilfen", "Strumpfanzieher gleitfähig", "rampe.jpg"),
    ("Kommunikationshilfen", "Bildtelefon mit Großtasten", "rollstuhl.jpg"),
    ("Orientierungshilfen", "Bewegungsmelder Nachtlicht", "treppenlift.jpg"),
    ("Sicherheitsprodukte", "Hausnotruf-Armband", "rollstuhl.jpg"),
    ("Pflegewagen", "Beistellwagen mit Ablagen", "rollstuhl.jpg"),
    ("Umfeldsteuerung", "Funk-Schaltsystem", "treppenlift.jpg"),
]


def inspect_assets(source_root: Path) -> tuple[int, str]:
    from app.services.file_service import sniff_image_type

    settings = get_settings()
    for filename, source in IMAGE_SOURCES.items():
        resolved = source.resolve(strict=True)
        if not resolved.is_relative_to(source_root):
            raise ValueError(f"Bild liegt außerhalb des Storage-Verzeichnisses: {filename}")
        with resolved.open("rb") as image_file:
            mime_type = sniff_image_type(image_file.read(16))
        expected_type = "image/jpeg" if resolved.suffix.lower() in {".jpg", ".jpeg"} else None
        if mime_type != expected_type or mime_type is None:
            raise ValueError(f"Bilddatei hat ein ungültiges oder nicht unterstütztes Format: {filename}")
        size, _ = file_metadata(resolved)
        if size > settings.max_image_bytes:
            raise ValueError(f"Bild überschreitet MAX_IMAGE_SIZE_MB: {filename}")

    pdf = PDF_SOURCE.resolve(strict=True)
    with pdf.open("rb") as pdf_file:
        pdf_header = pdf_file.read(1024)
    if not pdf.is_relative_to(source_root) or b"%PDF-" not in pdf_header:
        raise ValueError("Gebrauchsanweisung.pdf fehlt oder ist keine gültige PDF-Datei.")
    pdf_size, pdf_checksum = file_metadata(pdf)
    if pdf_size > settings.max_pdf_bytes:
        raise ValueError("Gebrauchsanweisung.pdf überschreitet MAX_PDF_SIZE_MB.")
    return pdf_size, pdf_checksum


def file_metadata(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return path.stat().st_size, digest.hexdigest()


def copy_exclusive(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with source.open("rb") as input_file, destination.open("xb") as output_file:
            while chunk := input_file.read(1024 * 1024):
                output_file.write(chunk)
    except BaseException:
        destination.unlink(missing_ok=True)
        try:
            destination.parent.rmdir()
        except OSError:
            pass
        raise


def remove_created_files(paths: list[Path]) -> None:
    for path in reversed(paths):
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass


def seed(dry_run: bool = False) -> int:
    settings = get_settings()
    storage_root = settings.storage_dir.resolve()
    pdf_size, pdf_checksum = inspect_assets((ROOT / "storage").resolve())
    if dry_run:
        print(
            f"Vorschau: {len(ITEMS)} Kategorien, {len(ITEMS)} Produkte und "
            f"{len(ITEMS)} PDFs; Bilder und PDFs werden aus storage kopiert."
        )
        return 0

    from sqlalchemy import select

    from app.core.database import SessionLocal
    from app.core.slugs import slugify
    from app.models.category import Category
    from app.models.document import Document
    from app.models.product import Product

    image_dir = storage_root / "images"
    document_dir = storage_root / "documents"

    with SessionLocal() as db:
        existing_categories = list(
            db.scalars(select(Category).where(Category.slug.like(f"{SEED_CATEGORY_PREFIX}%")))
        )
        existing_products = list(
            db.scalars(select(Product).where(Product.slug.like(f"{SEED_PRODUCT_PREFIX}%")))
        )
        existing_documents = list(
            db.scalars(select(Document).where(Document.storage_path.like("documents/demo-produkt-%")))
        )
        counts = (len(existing_categories), len(existing_products), len(existing_documents))
        expected = (len(ITEMS), len(ITEMS), len(ITEMS))
        if counts == expected:
            print("Demo-Daten sind bereits vollständig vorhanden; es wurde nichts geändert.")
            return 0
        if any(counts):
            raise RuntimeError(
                "Unvollständige Demo-Daten gefunden "
                f"(Kategorien/Produkte/PDFs: {counts}). Bitte den Zustand manuell prüfen; "
                "das Skript löscht oder überschreibt keine Daten."
            )

        category_specs = []
        product_specs = []
        image_copies: list[tuple[Path, Path]] = []
        pdf_copies: list[tuple[Path, Path]] = []
        for index, (category_name, product_name, image_filename) in enumerate(ITEMS, start=1):
            category_slug = f"{SEED_CATEGORY_PREFIX}{index:02d}-{slugify(category_name)}"
            product_slug = f"{SEED_PRODUCT_PREFIX}{index:02d}-{slugify(product_name)}"
            category_image = f"images/demo-kategorie-{index:02d}{Path(image_filename).suffix.lower()}"
            product_image = f"images/demo-produkt-{index:02d}{Path(image_filename).suffix.lower()}"
            pdf_path = f"documents/demo-produkt-{index:02d}/Gebrauchsanweisung.pdf"
            category_specs.append((category_name, category_slug, image_filename, category_image))
            product_specs.append((product_name, product_slug, image_filename, product_image, pdf_path))
            image_copies.extend(
                [
                    (IMAGE_SOURCES[image_filename], image_dir / Path(category_image).name),
                    (IMAGE_SOURCES[image_filename], image_dir / Path(product_image).name),
                ]
            )
            pdf_copies.append((PDF_SOURCE, document_dir / f"demo-produkt-{index:02d}" / "Gebrauchsanweisung.pdf"))

        target_paths = [target for _, target in image_copies + pdf_copies]
        collisions = [path for path in target_paths if path.exists()]
        if collisions:
            raise FileExistsError(
                "Demo-Dateien sind bereits im Storage vorhanden, aber nicht vollständig in der Datenbank "
                f"registriert; erste betroffene Datei: {collisions[0]}"
            )

        created_files: list[Path] = []
        try:
            for source, target in image_copies + pdf_copies:
                copy_exclusive(source, target)
                created_files.append(target)

            categories = [
                Category(
                    name=name,
                    slug=slug,
                    description="Beispieldaten zum Testen der Produktplattform.",
                    image_path=image_path,
                    sort_order=index,
                    active=True,
                )
                for index, (name, slug, _, image_path) in enumerate(category_specs, start=1)
            ]
            db.add_all(categories)
            db.flush()

            products = [
                Product(
                    category_id=categories[index - 1].id,
                    name=name,
                    slug=slug,
                    description="Beispielprodukt zum Testen der Produktplattform.",
                    image_path=image_path,
                    sort_order=1,
                    active=True,
                )
                for index, (name, slug, _, image_path, _) in enumerate(product_specs, start=1)
            ]
            db.add_all(products)
            db.flush()

            db.add_all(
                [
                    Document(
                        product_id=products[index - 1].id,
                        title=f"Gebrauchsanweisung – {products[index - 1].name}",
                        description="Demo-PDF aus der vorhandenen Datei Gebrauchsanweisung.pdf.",
                        original_filename=PDF_SOURCE.name,
                        storage_path=pdf_path,
                        mime_type="application/pdf",
                        file_size=pdf_size,
                        checksum_sha256=pdf_checksum,
                        version="1.0",
                        active=True,
                    )
                    for index, (_, _, _, _, pdf_path) in enumerate(product_specs, start=1)
                ]
            )
            db.commit()
        except Exception:
            db.rollback()
            remove_created_files(created_files)
            raise

    print(f"Demo-Daten angelegt: {len(ITEMS)} Kategorien, {len(ITEMS)} Produkte und {len(ITEMS)} PDFs.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="50 Demo-Kategorien, Produkte, Bilder und PDFs anlegen.")
    parser.add_argument("--dry-run", action="store_true", help="Prüfen, was angelegt würde, ohne Änderungen.")
    args = parser.parse_args()
    try:
        get_settings()
        return seed(dry_run=args.dry_run)
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            env_path = ROOT / ".env"
            print(
                f"Konfiguration unvollständig. Bitte {env_path} anlegen/ergänzen und mindestens "
                "DATABASE_URL sowie einen SECRET_KEY mit 32 oder mehr Zeichen setzen. "
                "Die Vorlage liegt in .env.example.",
                file=sys.stderr,
            )
            return 1
        print(f"Fehler beim Anlegen der Demo-Daten: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
