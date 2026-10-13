"""CLI: python -m app.cli <create-admin|seed-admin|reset-password>

Passwörter kommen nie als Default aus dem Code, sondern aus Prompt (getpass) oder Umgebung."""
import argparse
import getpass
import sys

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.exceptions import AppError
from app.services.auth_service import AuthService


def _prompt_password() -> str:
    pw = getpass.getpass("Passwort (min. 12 Zeichen): ")
    if pw != getpass.getpass("Passwort wiederholen: "):
        print("Passwörter stimmen nicht überein.", file=sys.stderr)
        sys.exit(1)
    return pw


def create_admin(args) -> int:
    settings = get_settings()
    username = args.username or settings.admin_username or input("Benutzername: ").strip()
    password = args.password_from_env and settings.admin_password or _prompt_password()
    with SessionLocal() as db:
        AuthService(db).create_admin(username, password)
    print(f"Admin '{username.lower()}' wurde angelegt.")
    return 0


def seed_admin(_args) -> int:
    """Idempotent (für den Container-Start): legt nur dann einen Admin an, wenn noch keiner existiert
    UND ADMIN_USERNAME/ADMIN_PASSWORD gesetzt sind."""
    settings = get_settings()
    with SessionLocal() as db:
        auth = AuthService(db)
        if auth.admin_exists():
            print("seed-admin: Admin existiert bereits – übersprungen.")
            return 0
        if not (settings.admin_username and settings.admin_password):
            print("seed-admin: ADMIN_USERNAME/ADMIN_PASSWORD nicht gesetzt – übersprungen. Siehe: python -m app.cli create-admin")
            return 0
        auth.create_admin(settings.admin_username, settings.admin_password)
    print(f"seed-admin: Admin '{settings.admin_username.lower()}' angelegt.")
    return 0


def reset_password(args) -> int:
    password = _prompt_password()
    with SessionLocal() as db:
        AuthService(db).set_password(args.username, password)
    print("Passwort geändert; bestehende Sessions wurden beendet.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-admin", help="Admin-Benutzer anlegen (Passwort per Prompt oder --password-from-env)")
    p.add_argument("--username")
    p.add_argument("--password-from-env", action="store_true", help="ADMIN_PASSWORD aus der Umgebung verwenden")
    p.set_defaults(func=create_admin)

    p = sub.add_parser("seed-admin", help="Admin aus ADMIN_USERNAME/ADMIN_PASSWORD anlegen, falls noch keiner existiert")
    p.set_defaults(func=seed_admin)

    p = sub.add_parser("reset-password", help="Passwort eines Benutzers neu setzen")
    p.add_argument("username")
    p.set_defaults(func=reset_password)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except AppError as exc:
        print(f"Fehler: {exc.detail}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
