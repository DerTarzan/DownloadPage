"""Erzeugt eine .env mit zufälligen Secrets (überschreibt nichts Vorhandenes).

    python scripts/generate_env.py [--admin-username NAME]

Das generierte Admin-Passwort wird EINMAL auf der Konsole ausgegeben und steht danach nur in der .env.
"""
import argparse
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-username", default="admin")
    args = parser.parse_args()

    target = ROOT / ".env"
    if target.exists():
        print(".env existiert bereits – nichts geändert.", file=sys.stderr)
        return 1

    admin_password = secrets.token_urlsafe(18)
    values = {
        "SECRET_KEY": secrets.token_urlsafe(48),
        "POSTGRES_PASSWORD": secrets.token_hex(24),  # nur [0-9a-f]: URL-sicher
        "ADMIN_USERNAME": args.admin_username,
        "ADMIN_PASSWORD": admin_password,
    }
    lines = []
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        key, sep, _ = line.partition("=")
        lines.append(f"{key}={values[key]}" if sep and key in values else line)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    target.chmod(0o600)
    print(f".env geschrieben.\nAdmin-Benutzer: {args.admin_username}\nAdmin-Passwort: {admin_password}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
