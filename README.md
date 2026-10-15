# Dokumenten-/Produktplattform – Backend

FastAPI · PostgreSQL · SQLAlchemy 2 · Alembic · Argon2 · Docker.
Struktur: **Startseite → Kategorie → Produkt → Dokument (PDF)**, alles dynamisch aus DB/Storage.
Das Frontend verwendet Jinja-Vorlagen und separate CSS-Dateien für gemeinsame sowie seitenspezifische Styles.

## Schnellstart mit Docker

```bash
# 1. .env mit zufälligen Secrets erzeugen (gibt das Admin-Passwort EINMAL aus)
python scripts/generate_env.py --admin-username admin           # Produktionsprofil (COOKIE_SECURE=true, Docs aus)
python scripts/generate_env.py --admin-username admin --local   # lokal über http (COOKIE_SECURE=false, Docs an)
#    ohne Python: .env.example (Produktion) bzw. .env.local.example (lokal) nach .env kopieren und
#    SECRET_KEY, POSTGRES_PASSWORD, ADMIN_USERNAME, ADMIN_PASSWORD selbst setzen

# 2. starten (baut das Image, wendet Migrationen an, legt den ersten Admin an)
docker compose up -d --build

# 3. prüfen
curl http://localhost:8000/health        # {"status":"ok"}
```

| URL | Zweck |
|---|---|
| http://localhost:8000/ | Startseite (Kategorien) |
| http://localhost:8000/admin/login | Admin-Login (Testseite) |
| http://localhost:8000/docs | OpenAPI/Swagger (nur mit `DOCS_ENABLED=true`, im Produktionsprofil aus) |

Der App-Port ist standardmäßig nur an `127.0.0.1` gebunden (`APP_BIND` in der `.env`). Für den Zugriff von außen gehört ein
Reverse Proxy mit TLS davor; `APP_BIND=0.0.0.0` nur bewusst setzen. Das Produktionsprofil setzt `COOKIE_SECURE=true`,
der Admin-Login funktioniert dann nur über HTTPS (lokal stattdessen das Profil `--local` verwenden).

Im Admin-Dashboard können Kategorie- und Produktbilder beim Anlegen hochgeladen sowie später ersetzt oder entfernt werden.
Erlaubte Bildformate sind PNG, JPEG und WebP; die maximale Dateigröße wird über `MAX_IMAGE_SIZE_MB` festgelegt.

Beim Start migriert zuerst der einmalige Service `migrate` (`alembic upgrade head`, mit den Zugangsdaten des
Datenbank-Besitzers). Danach läuft in der App `docker-entrypoint.sh`: `python -m app.cli seed-admin` → Server.
Daten liegen in den Volumes `postgres_data` (DB) und `document_storage` (Bilder/PDFs) und überleben `docker compose down`
(nur `down -v` löscht sie).

### Datenbank-Rolle der App (Least Privilege)

Die App verbindet sich nicht als Superuser, sondern als Rolle `APP_DB_USER` (nur `SELECT/INSERT/UPDATE/DELETE` auf die
Tabellen, kein DDL, kein `CREATE ROLE`). Angelegt wird sie beim ersten Start eines neuen DB-Volumes durch
`docker/postgres/01-app-role.sh`; `generate_env.py` erzeugt `APP_DB_PASSWORD` zufällig. Die Superuser-Zugangsdaten
(`POSTGRES_USER`/`POSTGRES_PASSWORD`) kennt nur der Service `migrate`, sie werden nicht in die Umgebung der App durchgereicht.

**Bestehende Installation auf die Laufzeit-Rolle umstellen** (die Init-Skripte laufen nur bei einem neuen Volume):

```bash
# 1. in der .env ergänzen:  APP_DB_USER=docplatform_app   APP_DB_PASSWORD=<zufälliger Wert, nur a-z0-9>
# 2. db neu erstellen (Daten bleiben im Volume) und die Rolle anlegen (idempotent):
docker compose up -d db
docker compose exec db sh /docker-entrypoint-initdb.d/01-app-role.sh
# 3. Migration und App neu starten:
docker compose up -d --build
```

Ohne `APP_DB_USER`/`APP_DB_PASSWORD` in der `.env` ändert sich nichts: die App nutzt dann wie bisher den Besitzer.
Beide Werte setzen oder beide weglassen. Wird nur einer gesetzt, schlägt die Anmeldung an der Datenbank fehl.

## Ersten Admin anlegen

* **Automatisch:** `ADMIN_USERNAME`/`ADMIN_PASSWORD` in der `.env` (Passwort ≥ 12 Zeichen). `seed-admin` legt den Admin nur an,
  wenn noch keiner existiert. Danach `ADMIN_PASSWORD` aus der `.env` entfernen.
* **Manuell (Passwort per Prompt, nirgends gespeichert):**
  ```bash
  docker compose exec app python -m app.cli create-admin --username admin
  docker compose exec app python -m app.cli reset-password admin   # Passwort neu setzen, beendet alle Sessions
  ```

Es gibt kein Default-Passwort im Code.

## Lokal ohne Docker

### PostgreSQL auf einem neuen Windows-PC einrichten

1. PostgreSQL für Windows über [postgresql.org/download/windows](https://www.postgresql.org/download/windows/) installieren. Das während der Installation gesetzte Passwort für den Datenbankbenutzer `postgres` merken; `psql` muss mitinstalliert werden.
2. In PowerShell mit PostgreSQL verbinden:
   ```powershell
   psql -U postgres -h localhost -d postgres
   ```
3. In der `psql`-Eingabe einen Anwendungsbenutzer und eine leere Datenbank anlegen. `<PASSWORT>` durch ein eigenes, starkes Passwort aus Buchstaben und Zahlen ersetzen:
   ```sql
   CREATE ROLE docplatform WITH LOGIN PASSWORD '<PASSWORT>';
   CREATE DATABASE docplatform OWNER docplatform;
   \q
   ```
4. Im Projekt die `.env.local.example` nach `.env` kopieren und `SECRET_KEY` sowie `DATABASE_URL` setzen. Für `SECRET_KEY` einen zufälligen Wert mit mindestens 32 Zeichen verwenden. Das Passwort in `DATABASE_URL` muss genau dem bei `CREATE ROLE` gesetzten Passwort entsprechen:
   ```powershell
   Copy-Item .env.local.example .env
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
   Den ausgegebenen Wert als `SECRET_KEY` in `.env` eintragen.
   ```dotenv
   SECRET_KEY=<zufälliger Wert mit mindestens 32 Zeichen>
   DATABASE_URL=postgresql+psycopg://docplatform:<PASSWORT>@localhost:5432/docplatform
   STORAGE_DIR=storage
   COOKIE_SECURE=false
   ```
   Ein Passwort nur aus Buchstaben und Zahlen vermeidet URL-Encoding-Probleme. `.env` enthält Geheimnisse und darf nicht veröffentlicht oder eingecheckt werden.

Die folgenden Befehle installieren die Python-Abhängigkeiten, wenden das Schema an, legen den ersten Admin interaktiv an und starten den lokalen Server:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m app.cli create-admin --username admin
uvicorn app.main:app --reload
```

Unter Windows PowerShell die venv-Aktivierung stattdessen so ausführen; danach die übrigen Befehle wie oben:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

### Beispieldaten einfügen

Nach `alembic upgrade head` kannst du die vorhandenen Bilder und die `Gebrauchsanweisung.pdf` aus `storage/` in die Datenbank einfügen:

```powershell
python scripts/seed_demo_data.py --dry-run
python scripts/seed_demo_data.py
```

Das Skript legt 50 Beispielkategorien mit jeweils einem Produkt, Bild und PDF an. Es kopiert die vorhandenen Dateien in die verwalteten `storage/images/`- und `storage/documents/`-Ordner, überschreibt keine Dateien und löscht keine bestehenden Daten. Die PDFs sind Kopien derselben vorhandenen Gebrauchsanweisung.

## Tests

Die Tests leeren alle Tabellen und benutzen deshalb **nie** `DATABASE_URL`, sondern `TEST_DATABASE_URL`
(ohne Angabe: temporäre SQLite-Datei). Migrationen werden per Alembic angewendet.

```bash
TEST_DATABASE_URL=postgresql+psycopg://user:pw@localhost:5432/docplatform_test pytest      # empfohlen: echtes Postgres
pytest                                                                                     # schnell, SQLite
# im Container:
INSTALL_DEV=true docker compose build app && docker compose run --rm --no-deps app pytest   # nutzt SQLite im Container
```

## Architektur

```
Router (HTTP, Validierung)  →  Service (Fachlogik, Transaktionen)  →  Repository (SQL)  →  SQLAlchemy  →  PostgreSQL
                                   └→ FileService (Storage, Upload-Prüfung)
```

```
app/
  main.py            App-Factory, Middleware, Router-Reihenfolge
  dependencies.py    DI: Session, Services, Auth/CSRF, Wartungsmodus
  core/              config, database, security (Argon2/Token), slugs, exceptions, errors, logging
  models/            User, UserSession, Category, Product, Document, Setting
  schemas/           Pydantic Request-/Response-Modelle
  repositories/      Datenbankzugriff (select/insert/delete)
  services/          auth, category, product, document, setting, file
  routers/           public, auth, admin (Settings + HTML), categories, products, documents
  templates/         minimale Testseiten
migrations/          Alembic (0001 = komplettes Schema + Default-Settings)
storage/             images/ und documents/ (Volume)
```

### Wichtige Entscheidungen

* **Auth:** Server-seitige Session in der DB; Cookie `session_token` (HttpOnly, SameSite=Lax, Secure per `COOKIE_SECURE`).
  Der Token liegt nur als HMAC (mit `SECRET_KEY`) in der DB. **CSRF:** schreibende Requests brauchen den Header
  `X-CSRF-Token` (Wert aus `/auth/login` bzw. `/auth/me`). Login-Bremse: 5 Fehlversuche je IP+Benutzer → 429 (in-memory, pro Prozess).
* **Passwörter:** Argon2id, Mindestlänge 12; unbekannte Benutzer kosten die gleiche Zeit (kein Enumeration-Timing).
* **Slugs:** Automatisch aus dem Namen (`Rollstühle` → `rollstuehle`); Kollision → `-2`, `-3`.
  Explizit angegebener, belegter Slug → `409`. Kategorie-Slugs sind global eindeutig, Produkt-Slugs je Kategorie.
  Reservierte Namen (`admin`, `api`, `auth`, `documents`, `media`, `health`, `docs`, …) werden nie vergeben.
  Slugs ändern sich nicht automatisch bei Umbenennung (stabile URLs).
* **Löschen:** Kategorie mit Produkten bzw. Produkt mit Dokumenten → `409`, außer `?cascade=true` (löscht Inhalt und Dateien mit).
  Dokument löschen entfernt Zeile und Datei. Dateien werden erst **nach** erfolgreichem Commit gelöscht; schlägt ein Commit nach dem
  Upload fehl, wird die neue Datei wieder entfernt (keine Waisen). FKs sind `RESTRICT`, ORM-Kaskaden sind aus.
* **Uploads:** Endung + Content-Type + Magic Bytes (`%PDF-`, PNG/JPEG/WebP), UUID-Dateinamen, Streaming mit hartem
  Größenlimit (`MAX_PDF_SIZE_MB`, `MAX_IMAGE_SIZE_MB`), Pfade nur aus der DB und gegen den Storage-Root geprüft (inkl. Symlinks).
  SVG wird bewusst nicht akzeptiert (XSS). Falscher Typ → 415, zu groß → 413.
* **Downloads:** `FileResponse` (streamt von Platte), `Content-Disposition: attachment`, nur wenn **Dokument, Produkt und Kategorie** aktiv sind.
  Zwei URLs: `/documents/{id}/download` und `/{kategorie}/{produkt}/dokument/{id}/download`.
* **Wartungsmodus:** Tabelle `settings` (`maintenance_mode`, `maintenance_message`), `GET/PUT /api/admin/settings`.
  Gilt für alle öffentlichen Routen (503 + `Retry-After`), **nicht** für `/auth`, `/admin`, `/api/admin`, `/health`, `/docs`;
  angemeldete Admins sehen die Website weiterhin. Der Admin kann sich nicht aussperren.
* **Content Negotiation:** Browser (`Accept: text/html`) bekommen die Testseiten, alle anderen JSON. Ein späteres SPA-Frontend nutzt dieselben Routen.

### Admin-API (Auszug, vollständig unter `/docs`)

```
POST/GET        /api/admin/categories            PUT /api/admin/categories/reorder
GET/PUT/DELETE  /api/admin/categories/{id}       POST/DELETE /api/admin/categories/{id}/image
POST/GET        /api/admin/products              PUT /api/admin/products/reorder
GET/PUT/DELETE  /api/admin/products/{id}         POST/DELETE /api/admin/products/{id}/image
POST            /api/admin/products/{id}/documents     (multipart: file, title, description, version, active)
GET             /api/admin/documents             GET/PUT/DELETE /api/admin/documents/{id}
PUT             /api/admin/documents/{id}/file   (PDF ersetzen)
GET/PUT         /api/admin/settings
```

Beispiel mit curl:

```bash
curl -c jar -X POST localhost:8000/auth/login -H 'content-type: application/json' -d '{"username":"admin","password":"…"}'
# csrf_token aus der Antwort übernehmen:
curl -b jar -H "X-CSRF-Token: <token>" -F file=@handbuch.pdf -F title=Handbuch localhost:8000/api/admin/products/1/documents
```

## Betriebshinweise

* Hinter einem Reverse Proxy mit HTTPS: `COOKIE_SECURE=true` setzen und in der `.env` `FORWARDED_ALLOW_IPS=<IP des Proxys>`
  eintragen (uvicorn liest die Variable selbst; **niemals `*`**). Nur dann sieht die Login-Bremse die echte Client-IP aus
  `X-Forwarded-For`; ohne den Eintrag zählen alle Besucher als die Proxy-IP, und ein Angreifer könnte den Admin-Login sperren.
  Der Port der App sollte nicht direkt öffentlich erreichbar sein (`APP_BIND=127.0.0.1`, Standard).
* Der Proxy sollte zusätzlich eigene Limits setzen (z. B. Nginx `client_max_body_size`, `limit_req` für `/auth/login`). Die App
  begrenzt Request-Bodys selbst (`MAX_PDF_SIZE_MB`, `MAX_IMAGE_SIZE_MB`, `MAX_REQUEST_BODY_KB`) und weist schreibende
  Admin-Requests ohne gültige Session ab, bevor der Body gelesen wird.
* Login-Bremse: `LOGIN_MAX_ATTEMPTS` je (IP, Benutzer) und `LOGIN_MAX_ATTEMPTS_PER_IP` je IP über alle Benutzernamen innerhalb von
  `LOGIN_LOCKOUT_SECONDS`; gleichzeitige Passwortprüfungen sind über `LOGIN_MAX_CONCURRENT_HASHES` begrenzt.
  Die Bremse ist pro Prozess; bei mehreren Workern/Instanzen später durch Redis o. Ä. ersetzen.
* Backup: Volumes `postgres_data` **und** `document_storage` zusammen sichern (DB enthält nur Metadaten).
* Erweiterungspunkte: `DocumentService` (Versionierung, Download-Logger `app.downloads`), `FileService` (S3/MinIO),
  `Document.version` → später eigene Versions-Tabelle.

## Design

Das Styling liegt in `app/static/css/base.css` sowie den seitenspezifischen CSS-Dateien unter `app/static/css/`.
Die Farbpalette im Conrady-Blau und der automatische Dark Mode werden über die CSS-Variablen am Anfang von
`base.css` gesteuert. Seiten-Templates: `app/templates/`. Der Seitenname kommt aus `APP_NAME` in der `.env`.

## Abhängigkeiten, Lock-Dateien und CI

- `requirements.txt`/`requirements-dev.txt` enthalten die Versionsbereiche, `requirements.lock`/`requirements-dev.lock` die exakten Versionen **mit Hashes**. Das Docker-Image installiert aus den Lock-Dateien (`pip install --require-hashes`).
- Lock-Dateien neu erzeugen (z. B. nach Dependabot-PR oder Änderung der `.txt`-Dateien):
  `uv pip compile requirements.txt --generate-hashes --python-version 3.12 --python-platform linux -o requirements.lock` (entsprechend für `requirements-dev.txt`).
- `.github/workflows/ci.yml`: Tests (SQLite und PostgreSQL), Lock-Aktualität, `pip-audit`, Bandit, Secret-Scan (`.secrets.baseline`), Image-Build und Trivy. `.github/dependabot.yml` hält pip, Docker und Actions aktuell.
