"""Erzeugt eine .env mit zufälligen Secrets (überschreibt nichts Vorhandenes).

    python scripts/generate_env.py [--local] [--admin-username NAME]

Ohne --local wird die Produktions-Vorlage (.env.example) verwendet, mit --local die Vorlage für die
lokale Entwicklung über http (.env.local.example).
Das generierte Admin-Passwort wird EINMAL auf der Konsole ausgegeben und steht danach nur in der .env.
"""
import argparse
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PRODUCTION = ".env.example"
TEMPLATE_LOCAL = ".env.local.example"


def render(template: str, values: dict[str, str]) -> str:
    """Setzt die Werte in die Vorlage ein; alle anderen Zeilen bleiben unverändert."""
    lines = []
    for line in template.splitlines():
        key, sep, _ = line.partition("=")
        lines.append(f"{key}={values[key]}" if sep and key in values else line)
    return "\n".join(lines) + "\n"


def generate_values(admin_username: str) -> dict[str, str]:
    return {
        "SECRET_KEY": secrets.token_urlsafe(48),
        "POSTGRES_PASSWORD": secrets.token_hex(24),  # nur [0-9a-f]: URL-sicher
        "ADMIN_USERNAME": admin_username,
        "ADMIN_PASSWORD": secrets.token_urlsafe(18),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-username", default="admin")
    parser.add_argument("--local", action="store_true", help="Vorlage für lokale Entwicklung über http verwenden")
    args = parser.parse_args()

    target = ROOT / ".env"
    if target.exists():
        print(".env existiert bereits – nichts geändert.", file=sys.stderr)
        return 1

    template = (ROOT / (TEMPLATE_LOCAL if args.local else TEMPLATE_PRODUCTION)).read_text(encoding="utf-8")
    values = generate_values(args.admin_username)
    content = render(template, values)
    # Datei von Anfang an nur für den Besitzer lesbar anlegen (kein Zeitfenster mit Standardrechten)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write(content)
    print(f".env geschrieben ({'lokal' if args.local else 'Produktion'}).")
    print(f"Admin-Benutzer: {args.admin_username}\nAdmin-Passwort: {values['ADMIN_PASSWORD']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
