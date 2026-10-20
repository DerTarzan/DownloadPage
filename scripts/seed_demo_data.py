"""Insert 50 demo categories, products, images, and PDFs into the configured database."""

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

DATA_DIR = ROOT / "scripts" / "data"
PDF_SOURCE = DATA_DIR / "Bellavita (Drive Medical).pdf"

IMAGE_SOURCES = {
    "rampe.png": DATA_DIR / "Med_aire_Flex_Wave.png",
    "rollstuhl.png": DATA_DIR / "Med_aire_Flex_Wave.png",
    "treppenlift.png": DATA_DIR / "Med_aire_Flex_Wave.png",
}

ITEMS = [
    # Mobilität
    ("Mobilität", None, "Mobilität allgemein", "rollstuhl.png"),
    ("Mobilität", "Rollstühle", "Leichtgewichtrollstuhl", "rollstuhl.png"),
    ("Mobilität", "Rollstühle", "Standardrollstuhl faltbar", "rollstuhl.png"),
    ("Mobilität", "Rollstühle", "Aktivrollstuhl", "rollstuhl.png"),
    ("Mobilität", "Rollstühle", "Elektrorollstuhl kompakt", "rollstuhl.png"),
    ("Mobilität", "Rollatoren", "Premium-Rollator", "rollstuhl.png"),
    ("Mobilität", "Rollatoren", "Leichtgewichtrollator", "rollstuhl.png"),
    ("Mobilität", "Rollatoren", "Indoor-Rollator", "rollstuhl.png"),
    ("Mobilität", "Rollatoren", "Outdoor-Rollator", "rollstuhl.png"),
    ("Mobilität", "Gehhilfen", "Unterarmgehstützen", "rollstuhl.png"),
    ("Mobilität", "Gehhilfen", "Gehstock höhenverstellbar", "rollstuhl.png"),
    ("Mobilität", "Gehhilfen", "Vierfußgehhilfe", "rollstuhl.png"),
    ("Mobilität", "Gehhilfen", "Gehbock faltbar", "rollstuhl.png"),
    ("Mobilität", "Elektromobile", "Elektromobil City", "treppenlift.png"),
    ("Mobilität", "Elektromobile", "Elektromobil mit Dach", "treppenlift.png"),
    ("Mobilität", "Elektromobile", "Elektromobil kompakt", "treppenlift.png"),
    ("Mobilität", "Rollstuhlzubehör", "Rollstuhlkissen ergonomisch", "rollstuhl.png"),
    ("Mobilität", "Rollstuhlzubehör", "Rollstuhlrampe faltbar", "rampe.png"),
    ("Mobilität", "Rollstuhlzubehör", "Rollstuhl-Beinstütze", "rollstuhl.png"),
    ("Mobilität", "Rollstuhlzubehör", "Rollstuhl-Schiebehilfe", "rollstuhl.png"),

    # Treppen- und Zugangshilfen
    ("Treppen- und Zugangshilfen", None, "Zugangshilfen allgemein", "rampe.png"),
    ("Treppen- und Zugangshilfen", "Treppenlifte", "Sitzlift Komfort", "treppenlift.png"),
    ("Treppen- und Zugangshilfen", "Treppenlifte", "Kurventreppenlift", "treppenlift.png"),
    ("Treppen- und Zugangshilfen", "Treppenlifte", "Plattformlift", "treppenlift.png"),
    ("Treppen- und Zugangshilfen", "Treppenlifte", "Außentreppenlift", "treppenlift.png"),
    ("Treppen- und Zugangshilfen", "Treppenraupen", "Treppenraupe transportabel", "treppenlift.png"),
    ("Treppen- und Zugangshilfen", "Treppenraupen", "Treppenraupe mit Sitz", "treppenlift.png"),
    ("Treppen- und Zugangshilfen", "Rampen", "Mobile Schwellenrampe", "rampe.png"),
    ("Treppen- und Zugangshilfen", "Rampen", "Aluminium-Kofferrampe", "rampe.png"),
    ("Treppen- und Zugangshilfen", "Rampen", "Teleskoprampe", "rampe.png"),
    ("Treppen- und Zugangshilfen", "Rampen", "Türschwellenrampe flexibel", "rampe.png"),
    ("Treppen- und Zugangshilfen", "Rampen", "Modulare Rampenanlage", "rampe.png"),

    # Pflegebetten und Schlafzimmer
    ("Pflegebetten und Schlafzimmer", None, "Schlafzimmerhilfen allgemein", "rollstuhl.png"),
    ("Pflegebetten und Schlafzimmer", "Pflegebetten", "Elektrisches Pflegebett", "rollstuhl.png"),
    ("Pflegebetten und Schlafzimmer", "Pflegebetten", "Niedrigbett", "rollstuhl.png"),
    ("Pflegebetten und Schlafzimmer", "Pflegebetten", "Seitenlagerungsbett", "rollstuhl.png"),
    ("Pflegebetten und Schlafzimmer", "Pflegebetten", "Komfortpflegebett", "rollstuhl.png"),
    ("Pflegebetten und Schlafzimmer", "Matratzen", "Pflegematratze Komfort", "rollstuhl.png"),
    ("Pflegebetten und Schlafzimmer", "Matratzen", "Wechseldruckmatratze", "rollstuhl.png"),
    ("Pflegebetten und Schlafzimmer", "Matratzen", "Schaumstoffmatratze", "rollstuhl.png"),
    ("Pflegebetten und Schlafzimmer", "Bettzubehör", "Bettgalgen mit Triangelgriff", "rollstuhl.png"),
    ("Pflegebetten und Schlafzimmer", "Bettzubehör", "Bettleiter Aufrichthilfe", "rollstuhl.png"),
    ("Pflegebetten und Schlafzimmer", "Bettzubehör", "Bettseitengitter", "rollstuhl.png"),
    ("Pflegebetten und Schlafzimmer", "Lagerungshilfen", "Positionierungskissen-Set", "rollstuhl.png"),
    ("Pflegebetten und Schlafzimmer", "Lagerungshilfen", "Lagerungsrolle weich", "rollstuhl.png"),
    ("Pflegebetten und Schlafzimmer", "Lagerungshilfen", "Fersenfreilagerungskissen", "rollstuhl.png"),

    # Heben und Transfer
    ("Heben und Transfer", None, "Transferhilfen allgemein", "rollstuhl.png"),
    ("Heben und Transfer", "Patientenlifter", "Aktivlifter kompakt", "rollstuhl.png"),
    ("Heben und Transfer", "Patientenlifter", "Passivlifter elektrisch", "rollstuhl.png"),
    ("Heben und Transfer", "Patientenlifter", "Mobiler Patientenlifter", "rollstuhl.png"),
    ("Heben und Transfer", "Deckenlifter", "Deckenlifter Schienensystem", "treppenlift.png"),
    ("Heben und Transfer", "Deckenlifter", "Deckenlifter mit Wendefunktion", "treppenlift.png"),
    ("Heben und Transfer", "Transferhilfen", "Rutschbrett Komfort", "rampe.png"),
    ("Heben und Transfer", "Transferhilfen", "Drehscheibe für Transfers", "rampe.png"),
    ("Heben und Transfer", "Transferhilfen", "Gleitmatte für Pflege", "rollstuhl.png"),
    ("Heben und Transfer", "Aufstehhilfen", "Aufstehsessel elektrisch", "treppenlift.png"),
    ("Heben und Transfer", "Aufstehhilfen", "Mobiler Aufstehhilfegriff", "rollstuhl.png"),
    ("Heben und Transfer", "Aufstehhilfen", "Aufstehstütze für Bett", "rollstuhl.png"),

    # Bad und WC
    ("Bad und WC", None, "Bad- und WC-Hilfen allgemein", "rampe.png"),
    ("Bad und WC", "Duschstühle", "Duschstuhl mit Armlehnen", "rampe.png"),
    ("Bad und WC", "Duschstühle", "Duschhocker höhenverstellbar", "rampe.png"),
    ("Bad und WC", "Duschstühle", "Duschstuhl mit Rückenlehne", "rampe.png"),
    ("Bad und WC", "Badewannenhilfen", "Badewannensitz drehbar", "rampe.png"),
    ("Bad und WC", "Badewannenhilfen", "Badewannenlifter kompakt", "rampe.png"),
    ("Bad und WC", "Badewannenhilfen", "Einstiegshilfe Badewanne", "rampe.png"),
    ("Bad und WC", "Haltegriffe", "Wandhaltegriff Edelstahl", "rampe.png"),
    ("Bad und WC", "Haltegriffe", "Stützklappgriff WC", "rampe.png"),
    ("Bad und WC", "Haltegriffe", "Saughaltegriff mobil", "rampe.png"),
    ("Bad und WC", "Toilettenhilfen", "Toilettenstützgestell", "rampe.png"),
    ("Bad und WC", "Toilettenhilfen", "Toilettensitzerhöhung", "rampe.png"),
    ("Bad und WC", "Toilettenstühle", "Toilettenstuhl fahrbar", "rollstuhl.png"),
    ("Bad und WC", "Toilettenstühle", "Toilettenstuhl mit Armlehnen", "rollstuhl.png"),
    ("Bad und WC", "Duschsysteme", "Handbrause mit langem Schlauch", "rampe.png"),
    ("Bad und WC", "Duschsysteme", "Thermostat-Duschsystem", "rampe.png"),

    # Sitzen und Wohnen
    ("Sitzen und Wohnen", None, "Wohnhilfen allgemein", "rollstuhl.png"),
    ("Sitzen und Wohnen", "Pflegesessel", "Aufstehsessel elektrisch", "treppenlift.png"),
    ("Sitzen und Wohnen", "Pflegesessel", "Ruhe- und Pflegesessel", "treppenlift.png"),
    ("Sitzen und Wohnen", "Sitzhilfen", "Drehkissen für Transfers", "rampe.png"),
    ("Sitzen und Wohnen", "Sitzhilfen", "Sitzkissen druckentlastend", "rollstuhl.png"),
    ("Sitzen und Wohnen", "Sitzhilfen", "Keilkissen ergonomisch", "rollstuhl.png"),
    ("Sitzen und Wohnen", "Möbel", "Pflegenachttisch höhenverstellbar", "rollstuhl.png"),
    ("Sitzen und Wohnen", "Möbel", "Beistellwagen mit Ablagen", "rollstuhl.png"),
    ("Sitzen und Wohnen", "Möbel", "Pflegewagen kompakt", "rollstuhl.png"),

    # Inkontinenz und Pflegebedarf
    ("Inkontinenz und Pflegebedarf", None, "Pflegebedarf allgemein", "rollstuhl.png"),
    ("Inkontinenz und Pflegebedarf", "Inkontinenzversorgung", "Bettschutzeinlage waschbar", "rollstuhl.png"),
    ("Inkontinenz und Pflegebedarf", "Inkontinenzversorgung", "Inkontinenzunterlage saugfähig", "rollstuhl.png"),
    ("Inkontinenz und Pflegebedarf", "Inkontinenzversorgung", "Fixierhose für Pflege", "rollstuhl.png"),
    ("Inkontinenz und Pflegebedarf", "Pflegehilfsmittel", "Pflegehandschuhe Einweg", "rollstuhl.png"),
    ("Inkontinenz und Pflegebedarf", "Pflegehilfsmittel", "Waschschüssel für Pflege", "rollstuhl.png"),
    ("Inkontinenz und Pflegebedarf", "Pflegehilfsmittel", "Pflegewagen kompakt", "rollstuhl.png"),
    ("Inkontinenz und Pflegebedarf", "Hygiene", "Waschhandschuhe weich", "rollstuhl.png"),
    ("Inkontinenz und Pflegebedarf", "Hygiene", "Hautschutz- und Pflege-Set", "rollstuhl.png"),

    # Therapie und Druckentlastung
    ("Therapie und Druckentlastung", None, "Therapieprodukte allgemein", "rollstuhl.png"),
    ("Therapie und Druckentlastung", "Antidekubitus", "Sitzkissen druckentlastend", "rollstuhl.png"),
    ("Therapie und Druckentlastung", "Antidekubitus", "Dekubitusmatratze", "rollstuhl.png"),
    ("Therapie und Druckentlastung", "Antidekubitus", "Fersenentlastungssystem", "rollstuhl.png"),
    ("Therapie und Druckentlastung", "Therapiegeräte", "Wärmekissen elektrisch", "rollstuhl.png"),
    ("Therapie und Druckentlastung", "Therapiegeräte", "Bewegungstrainer kompakt", "rollstuhl.png"),
    ("Therapie und Druckentlastung", "Therapiegeräte", "Pedaltrainer für Arme und Beine", "rollstuhl.png"),
    ("Therapie und Druckentlastung", "Lagerungshilfen", "Lagerungsrolle weich", "rollstuhl.png"),

    # Orthopädie
    ("Orthopädie", None, "Orthopädie allgemein", "rollstuhl.png"),
    ("Orthopädie", "Orthesen", "Handgelenkorthese stabil", "rollstuhl.png"),
    ("Orthopädie", "Orthesen", "Sprunggelenkorthese", "rollstuhl.png"),
    ("Orthopädie", "Orthesen", "Rückenorthese stützend", "rollstuhl.png"),
    ("Orthopädie", "Bandagen", "Kniebandage elastisch", "rollstuhl.png"),
    ("Orthopädie", "Bandagen", "Handgelenkbandage", "rollstuhl.png"),
    ("Orthopädie", "Bandagen", "Sprunggelenkbandage", "rollstuhl.png"),
    ("Orthopädie", "Kompressionsversorgung", "Anziehhilfe für Kompressionsstrümpfe", "rampe.png"),
    ("Orthopädie", "Kompressionsversorgung", "Strumpfanzieher gleitfähig", "rampe.png"),
    ("Orthopädie", "Einlagen", "Alltagseinlage anatomisch", "rollstuhl.png"),
    ("Orthopädie", "Schuhe", "Komfortschuh Klettverschluss", "rollstuhl.png"),
    ("Orthopädie", "Schuhe", "Verbandschuh weit zu öffnen", "rollstuhl.png"),

    # Alltagshilfen
    ("Alltagshilfen", None, "Alltagshilfen allgemein", "rollstuhl.png"),
    ("Alltagshilfen", "Greifhilfen", "Greifzange mit Magnet", "rampe.png"),
    ("Alltagshilfen", "Greifhilfen", "Greifhilfe mit langem Griff", "rampe.png"),
    ("Alltagshilfen", "Anziehhilfen", "Strumpfanzieher gleitfähig", "rampe.png"),
    ("Alltagshilfen", "Anziehhilfen", "Knöpfhilfe für Kleidung", "rampe.png"),
    ("Alltagshilfen", "Ess- und Trinkhilfen", "Trinkbecher mit Nasenausschnitt", "rollstuhl.png"),
    ("Alltagshilfen", "Ess- und Trinkhilfen", "Besteck mit verdicktem Griff", "rollstuhl.png"),
    ("Alltagshilfen", "Ess- und Trinkhilfen", "Rutschfeste Essunterlage", "rollstuhl.png"),
    ("Alltagshilfen", "Haushaltshilfen", "Öffnungshilfe für Schraubgläser", "rollstuhl.png"),
    ("Alltagshilfen", "Haushaltshilfen", "Greifhilfe für den Haushalt", "rampe.png"),

    # Diagnose und Gesundheit
    ("Diagnose und Gesundheit", None, "Gesundheitsprodukte allgemein", "rollstuhl.png"),
    ("Diagnose und Gesundheit", "Vitalmessgeräte", "Blutdruckmessgerät digital", "rollstuhl.png"),
    ("Diagnose und Gesundheit", "Vitalmessgeräte", "Pulsoximeter", "rollstuhl.png"),
    ("Diagnose und Gesundheit", "Vitalmessgeräte", "Fieberthermometer digital", "rollstuhl.png"),
    ("Diagnose und Gesundheit", "Medikamentenorganisation", "Tablettenbox Wochenplan", "rollstuhl.png"),
    ("Diagnose und Gesundheit", "Medikamentenorganisation", "Tablettenteiler", "rollstuhl.png"),

    # Sicherheit und Kommunikation
    ("Sicherheit und Kommunikation", None, "Sicherheitsprodukte allgemein", "rollstuhl.png"),
    ("Sicherheit und Kommunikation", "Hausnotruf", "Hausnotruf-Armband", "rollstuhl.png"),
    ("Sicherheit und Kommunikation", "Hausnotruf", "Hausnotruf-Sender für Zuhause", "rollstuhl.png"),
    ("Sicherheit und Kommunikation", "Orientierungshilfen", "Bewegungsmelder Nachtlicht", "treppenlift.png"),
    ("Sicherheit und Kommunikation", "Orientierungshilfen", "Nachtlicht mit Sensor", "treppenlift.png"),
    ("Sicherheit und Kommunikation", "Kommunikationshilfen", "Bildtelefon mit Großtasten", "rollstuhl.png"),
    ("Sicherheit und Kommunikation", "Kommunikationshilfen", "Telefon mit Fototasten", "rollstuhl.png"),
    ("Sicherheit und Kommunikation", "Umfeldsteuerung", "Funk-Schaltsystem", "treppenlift.png"),
    ("Sicherheit und Kommunikation", "Umfeldsteuerung", "Sprachgesteuerte Steckdose", "treppenlift.png"),
]


def file_metadata(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()

    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)

    return path.stat().st_size, digest.hexdigest()


def inspect_assets() -> tuple[int, int, str]:
    from app.services.file_service import sniff_image_type

    settings = get_settings()
    data_dir = DATA_DIR.resolve(strict=True)

    # Validate all image sources.
    for source in dict.fromkeys(IMAGE_SOURCES.values()):
        resolved = source.resolve(strict=True)

        if not resolved.is_relative_to(data_dir):
            raise ValueError(
                f"Bild liegt außerhalb von scripts/data: {source.name}"
            )

        if resolved.suffix.lower() != ".png":
            raise ValueError(
                f"Bilddatei muss die Endung .png haben: {source.name}"
            )

        with resolved.open("rb") as image_file:
            mime_type = sniff_image_type(image_file.read(16))

        if mime_type != "image/png":
            raise ValueError(
                f"Ungültiges oder nicht unterstütztes Bildformat: {source.name}"
            )

        image_size, _ = file_metadata(resolved)

        if image_size > settings.max_image_bytes:
            raise ValueError(
                f"Bild überschreitet MAX_IMAGE_SIZE_MB: {source.name}"
            )

    # Validate the PDF source.
    pdf = PDF_SOURCE.resolve(strict=True)

    if not pdf.is_relative_to(data_dir):
        raise ValueError("Die PDF-Datei liegt außerhalb von scripts/data.")

    with pdf.open("rb") as pdf_file:
        pdf_header = pdf_file.read(1024)

    if b"%PDF-" not in pdf_header:
        raise ValueError(
            f"{PDF_SOURCE.name} ist keine gültige PDF-Datei."
        )

    pdf_size, pdf_checksum = file_metadata(pdf)

    if pdf_size > settings.max_pdf_bytes:
        raise ValueError(
            f"{PDF_SOURCE.name} überschreitet MAX_PDF_SIZE_MB."
        )

    image_size = next(iter(IMAGE_SOURCES.values())).stat().st_size

    return image_size, pdf_size, pdf_checksum


def copy_exclusive(source: Path, destination: Path) -> None:
    """Copy a file without overwriting an existing destination."""
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        with source.open("rb") as input_file:
            with destination.open("xb") as output_file:
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
    """Remove only files created by this seed run."""
    for path in reversed(paths):
        path.unlink(missing_ok=True)

        try:
            path.parent.rmdir()
        except OSError:
            pass


def seed(dry_run: bool = False) -> int:
    settings = get_settings()
    storage_root = settings.storage_dir.resolve()

    image_size, pdf_size, pdf_checksum = inspect_assets()

    if dry_run:
        print(
            f"Vorschau: {len(ITEMS)} Kategorien, "
            f"{len(ITEMS)} Produkte und {len(ITEMS)} PDFs. "
            "Die Bilder und PDFs werden aus scripts/data kopiert."
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
            db.scalars(
                select(Category).where(
                    Category.slug.like(f"{SEED_CATEGORY_PREFIX}%")
                )
            )
        )

        existing_products = list(
            db.scalars(
                select(Product).where(
                    Product.slug.like(f"{SEED_PRODUCT_PREFIX}%")
                )
            )
        )

        existing_documents = list(
            db.scalars(
                select(Document).where(
                    Document.storage_path.like(
                        "documents/demo-produkt-%"
                    )
                )
            )
        )

        counts = (
            len(existing_categories),
            len(existing_products),
            len(existing_documents),
        )
        expected = (len(ITEMS), len(ITEMS), len(ITEMS))

        if counts == expected:
            print(
                "Demo-Daten sind bereits vollständig vorhanden; "
                "es wurde nichts geändert."
            )
            return 0

        if any(counts):
            raise RuntimeError(
                "Unvollständige Demo-Daten gefunden "
                f"(Kategorien/Produkte/PDFs: {counts}). "
                "Bitte den Zustand manuell prüfen. "
                "Das Skript löscht oder überschreibt keine Daten."
            )

        category_specs = []
        product_specs = []
        image_copies: list[tuple[Path, Path]] = []
        pdf_copies: list[tuple[Path, Path]] = []

        for index, (
            category_name,
            product_name,
            image_filename,
        ) in enumerate(ITEMS, start=1):

            category_slug = (
                f"{SEED_CATEGORY_PREFIX}{index:02d}-"
                f"{slugify(category_name)}"
            )
            product_slug = (
                f"{SEED_PRODUCT_PREFIX}{index:02d}-"
                f"{slugify(product_name)}"
            )

            category_image = f"images/demo-kategorie-{index:02d}.png"
            product_image = f"images/demo-produkt-{index:02d}.png"

            pdf_path = (
                f"documents/demo-produkt-{index:02d}/"
                "Gebrauchsanweisung.pdf"
            )

            category_specs.append(
                (
                    category_name,
                    category_slug,
                    image_filename,
                    category_image,
                )
            )

            product_specs.append(
                (
                    product_name,
                    product_slug,
                    image_filename,
                    product_image,
                    pdf_path,
                )
            )

            source_image = IMAGE_SOURCES[image_filename]

            image_copies.extend(
                [
                    (
                        source_image,
                        image_dir / Path(category_image).name,
                    ),
                    (
                        source_image,
                        image_dir / Path(product_image).name,
                    ),
                ]
            )

            pdf_copies.append(
                (
                    PDF_SOURCE,
                    document_dir
                    / f"demo-produkt-{index:02d}"
                    / "Gebrauchsanweisung.pdf",
                )
            )

        target_paths = [
            target for _, target in image_copies + pdf_copies
        ]

        collisions = [path for path in target_paths if path.exists()]

        if collisions:
            raise FileExistsError(
                "Demo-Dateien sind bereits im Storage vorhanden, "
                "aber nicht vollständig in der Datenbank registriert. "
                f"Erste betroffene Datei: {collisions[0]}"
            )

        created_files: list[Path] = []

        try:
            # Copy all assets before writing database records.
            for source, target in image_copies + pdf_copies:
                copy_exclusive(source, target)
                created_files.append(target)

            categories = [
                Category(
                    name=name,
                    slug=slug,
                    description=(
                        "Beispieldaten zum Testen der Produktplattform."
                    ),
                    image_path=image_path,
                    sort_order=index,
                    active=True,
                )
                for index, (name, slug, _, image_path)
                in enumerate(category_specs, start=1)
            ]

            db.add_all(categories)
            db.flush()

            products = [
                Product(
                    category_id=categories[index - 1].id,
                    name=name,
                    slug=slug,
                    description=(
                        "Beispielprodukt zum Testen der Produktplattform."
                    ),
                    image_path=image_path,
                    sort_order=1,
                    active=True,
                )
                for index, (name, slug, _, image_path, _)
                in enumerate(product_specs, start=1)
            ]

            db.add_all(products)
            db.flush()

            documents = [
                Document(
                    product_id=products[index - 1].id,
                    title=(
                        f"Gebrauchsanweisung – "
                        f"{products[index - 1].name}"
                    ),
                    description=(
                        f"Demo-PDF aus der Datei {PDF_SOURCE.name}."
                    ),
                    original_filename=PDF_SOURCE.name,
                    storage_path=pdf_path,
                    mime_type="application/pdf",
                    file_size=pdf_size,
                    checksum_sha256=pdf_checksum,
                    version="1.0",
                    active=True,
                )
                for index, (_, _, _, _, pdf_path)
                in enumerate(product_specs, start=1)
            ]

            db.add_all(documents)
            db.commit()

        except Exception:
            db.rollback()
            remove_created_files(created_files)
            raise

    print(
        f"Demo-Daten angelegt: {len(ITEMS)} Kategorien, "
        f"{len(ITEMS)} Produkte und {len(ITEMS)} PDFs "
        f"(Bild: {image_size:,} Bytes, PDF: {pdf_size:,} Bytes)."
    )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "50 Demo-Kategorien, Produkte, Bilder und PDFs anlegen."
        )
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prüfen, was angelegt würde, ohne Änderungen.",
    )

    args = parser.parse_args()

    try:
        get_settings()
        return seed(dry_run=args.dry_run)

    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            env_path = ROOT / ".env"

            print(
                f"Konfiguration unvollständig. Bitte {env_path} "
                "anlegen/ergänzen und mindestens DATABASE_URL sowie "
                "einen SECRET_KEY mit 32 oder mehr Zeichen setzen. "
                "Die Vorlage liegt in .env.example.",
                file=sys.stderr,
            )
            return 1

        print(
            f"Fehler beim Anlegen der Demo-Daten: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())