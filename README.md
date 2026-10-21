# Dokumenten-/Produktplattform – Backend

FastAPI · PostgreSQL · SQLAlchemy 2 · Alembic · Argon2 · Docker.
Struktur: **Startseite → Kategorie → optionale Unterkategorien beliebiger Tiefe → Produkt → Dokument (PDF)**, alles dynamisch aus DB/Storage.
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
| http://localhost:8000/admin/login | Admin-Login |
| http://localhost:8000/admin | Verwaltung: Übersicht · `/admin/catalog` Kategorien & Produkte · `/admin/documents` Dokumente · `/admin/upload` PDF hochladen · `/admin/logs` Live-Logs · `/admin/settings` Einstellungen (Wartungsmodus, Chatbot an/aus) |
| http://localhost:8000/docs | OpenAPI/Swagger (nur mit `DOCS_ENABLED=true`, im Produktionsprofil aus) |

Compose enthält keinen Reverse Proxy und stellt die App standardmäßig nur lokal unter `http://localhost:8000` bereit
(`APP_BIND=127.0.0.1`). Für Produktion muss ein externer Reverse Proxy HTTPS bereitstellen und an den App-Port
weiterleiten; DNS und TLS-Zertifikate werden außerhalb dieses Compose-Setups konfiguriert. Das Produktionsprofil setzt
`COOKIE_SECURE=true`, der Admin-Login funktioniert dann nur über HTTPS. Lokal setzt das Profil `--local`
`COOKIE_SECURE=false`.

In der Verwaltung (Kategorien & Produkte) können Kategorie- und Produktbilder beim Anlegen hochgeladen sowie später ersetzt oder entfernt werden.
Erlaubte Bildformate sind PNG, JPEG und WebP; die maximale Dateigröße wird über `MAX_IMAGE_SIZE_MB` festgelegt.

Beim Start migriert zuerst der einmalige Service `migrate` (`alembic upgrade head`, mit den Zugangsdaten des
Datenbank-Besitzers). Danach läuft in der App `docker-entrypoint.sh`: `python -m app.cli seed-admin` → Server.
Daten liegen in den Volumes `postgres_data` (DB) und `document_storage` (Bilder/PDFs) und überleben `docker compose down`
(nur `down -v` löscht sie).

Kategorien können in der Verwaltung verschachtelt und zwischen Elternkategorien verschoben werden. Bestehende Kategorien
bleiben nach Migration `0002_category_parent` Hauptkategorien. Löschen ohne `cascade=true` wird abgewiesen, solange direkte
Produkte oder Unterkategorien vorhanden sind; eine bestätigte Kaskade entfernt den gesamten Unterbaum mitsamt Produkten,
Dokumenten und zugehörigen Dateien.

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

Nach `alembic upgrade head` kannst du die Beispieldaten mit dem PNG und der PDF aus `scripts/data/` einfügen:

```powershell
python scripts/seed_demo_data.py --dry-run
python scripts/seed_demo_data.py
```

Das Skript legt 50 Beispielkategorien mit jeweils einem Produkt, Bild und PDF an. Es verwendet `Med_aire_Flex_Wave.png` und `Bellavita (Drive Medical).pdf` für alle Einträge, kopiert sie in die verwalteten `storage/images/`- und `storage/documents/`-Ordner, überschreibt keine Dateien und löscht keine bestehenden Daten.

## Tests

Die Tests leeren alle Tabellen und benutzen deshalb **nie** `DATABASE_URL`, sondern `TEST_DATABASE_URL`
(ohne Angabe: temporäre SQLite-Datei). Migrationen werden per Alembic angewendet.

```bash
TEST_DATABASE_URL=postgresql+psycopg://user:pw@localhost:5432/docplatform_test pytest      # empfohlen: echtes Postgres
pytest                                                                                     # schnell, SQLite
# im Container:
INSTALL_DEV=true docker compose build app && docker compose run --rm --no-deps app pytest   # nutzt SQLite im Container
```

## Chatbot (lokale Produktsuche)

Auf allen öffentlichen Seiten erscheint unten rechts ein rundes Chat-Icon. Besucher stellen dort Fragen in natürlicher Sprache
(„Ich suche den Rollator STF 300“, „Welche Rollatoren gibt es?“, „Bedienungsanleitung für den STF 300“) und bekommen eine
kurze Antwort samt Karten mit Links auf die **tatsächlichen** Produkt-, Kategorie- und Dokumentseiten. Der Chat ist rein lokal:
**kein Cloud-KI-Dienst, kein API-Schlüssel, keine GPU, kein Modell, kein zusätzlicher Container, keine Migration.**
Er erscheint nicht im Admin-Bereich, auf der Login- und der Wartungsseite.

**Integration:** `app/templates/base.html` bindet `_chat.html` ein (Block `chat`); `static/js/chat.js` baut das Widget auf,
`static/css/chat.css` nutzt die Farbvariablen aus `base.css` (Hell-/Dunkelmodus, `prefers-reduced-motion`, Mobil). Escape schließt,
Tastaturbedienung und ARIA (`role="dialog"`, `role="log"`) sind umgesetzt. Der Verlauf und die Sprache bleiben nur in der
Browser-Sitzung (`sessionStorage`); der Server speichert und loggt keine Chatnachrichten.

**Endpunkt:** `POST /api/chat` mit `{"message": "...", "lang": "de"|"en", "context": {"category_slug", "product_slug"}}` (Kontext optional,
wird serverseitig gegen den öffentlichen Katalog geprüft). Antwort: `reply`, `kind` (`found`, `multiple`, `category`, `documents`,
`clarify`, `greeting`, `none`), `results` (Produktkarten mit Dokumenten), `categories`, `similar`.

```
app/routers/chat.py              Endpunkt, Wartungsmodus, Rate-Limit, Längenprüfung
app/services/chat/service.py     Ablauf, Antwortgenerator, Karten und Links
app/services/chat/search.py      Katalogmodell (nur öffentlich Sichtbares) und Relevanzbewertung
app/services/chat/text.py        Normalisierung, Tippfehler-Toleranz (Damerau-Levenshtein)
app/services/chat/vocabulary.py  Füllwörter und Dokument-Stichwörter (DE+EN)
app/services/chat/i18n.py        Antworttexte DE/EN       (UI-Texte: static/js/chat.js)
app/services/chat/llm.py         optionaler Hook für ein lokales Sprachmodell
app/repositories/chat_repository.py  drei schlanke Lese-Abfragen
```

**Suchalgorithmus:** Der Katalog (aktive Kategorien mit aktiver Eltern-Kette, aktive Produkte, aktive Dokumente) wird je Anfrage mit drei
parametrisierten Abfragen gelesen und im Speicher bewertet. Das funktioniert identisch auf PostgreSQL und SQLite und braucht keine
Zusatzsoftware; für Kataloge im Bereich von einigen tausend Produkten ist das schnell genug. Die Frage wird gefaltet (Kleinschreibung,
ä→ae, ß→ss, Akzente weg), in Wörter zerlegt (`STF300` = `STF-300` = `STF 300`) und von Füllwörtern und Dokument-Stichwörtern
befreit. Je Suchwort zählt der beste Treffer mit Gewicht: Produktname 1,0 · Kategorie 0,7 · Beschreibung 0,6 · Dokumenttitel/-dateiname 0,6.
Ähnlichkeit: exakt, gleicher Wortstamm (Plural), Präfix, Teilwort, Tippfehler (1 Fehler ab 4, 2 ab 8 Buchstaben, Vertauschungen eingeschlossen).
**Zahlen müssen exakt passen** (`STF 3000` findet `STF 300` nicht, schlägt ihn aber als ähnlich vor); Zahlen zählen doppelt, fehlende Zahlen
werten stark ab. Boni für „alle Wörter im Namen“ und „Name exakt“. Treffer unter der Mindestrelevanz oder unter 60 % des besten fallen weg;
es werden höchstens `CHAT_MAX_RESULTS` gezeigt. Ein eindeutig bester Treffer wird als einzelner Treffer gezeigt, sonst als Liste. Passt eine Kategorie
(„Welche Rollatoren gibt es?“), wird sie samt Produkten ihres gesamten Unterbaums gezeigt. Ohne Treffer gibt es ähnliche Produkte, sonst die
Hauptkategorien. Ohne verwertbare Wörter fragt der Bot nach; „… zu diesem Produkt“ bezieht sich auf das zuletzt gezeigte Produkt bzw. die aktuelle Produktseite.
Die Produkttabelle hat **keine Artikelnummer**; Modellbezeichnungen wie „STF 300“ werden deshalb aus dem Produktnamen (und Dokumenttiteln) gefunden.

**Sprache:** Deutsch ist Standard, Umschaltung per Auswahl im Chatfenster. Bot-Antworten kommen in der gewählten Sprache; die Suche ist sprachunabhängig
(Füllwörter und Dokument-Stichwörter gibt es in beiden Sprachen), englische Fragen finden also deutsche Produktnamen. Produktnamen, Titel und Dateinamen werden nie übersetzt.
Die Sprache (Deutsch/Englisch) wählen Besucher seitenweit über das Lesezeichen im Footer (Cookie `lang`, Texte in `app/i18n.py`); der Chat übernimmt sie von der Seite. Die Chat-Texte liegen in `chat.js` (UI) und `services/chat/i18n.py` (Antworten). Tests stellen sicher, dass alle Sprachen dieselben Schlüssel haben.

**Chatbot an-/ausschalten:** In der Verwaltung unter *Einstellungen → Chatbot* (`GET/PUT /api/admin/chatbot`). Deaktiviert verschwindet der Chat-Button auf allen öffentlichen Seiten und `/api/chat` antwortet mit 404. `CHAT_ENABLED=false` in der `.env` sperrt den Chatbot weiterhin serverseitig und hat Vorrang vor dem Schalter.

**Sicherheit:** Nur lesend, nur öffentlich Sichtbares (inaktive Produkte/Dokumente/Kategorien oder deren Unterbäume tauchen nicht auf), keine Dateisystempfade
(Dokument-Links nutzen die vorhandene Produkt-Download-Route), parametrisierte Abfragen, Pydantic-Validierung, Nachrichtenlänge (`CHAT_MAX_MESSAGE_LENGTH`),
Body-Limit 8 KB, Rate-Limit je IP (`CHAT_RATE_LIMIT_PER_MINUTE`, pro Prozess; hinter einem Proxy `FORWARDED_ALLOW_IPS` setzen, sonst teilen sich alle Besucher eine IP),
Wartungsmodus gilt auch für den Chat. Nutzertext wird nie als HTML eingefügt (`textContent`), Links nur als relative Pfade. Nachrichten sind reine Suchtexte
und lösen keine Aktionen aus. Der Chat macht keine ausgehenden Anfragen.

**Konfiguration** (alle optional, siehe `.env.example`): `CHAT_ENABLED` (true), `CHAT_MAX_MESSAGE_LENGTH` (300), `CHAT_MAX_RESULTS` (5), `CHAT_RATE_LIMIT_PER_MINUTE` (20).
Docker Compose: nichts anpassen; `docker compose up -d --build` genügt (keine neuen Dienste, Ports, Abhängigkeiten oder Migrationen). Zum Abschalten `CHAT_ENABLED=false` und neu starten.

**Optional: lokales Sprachmodell (z. B. Ollama).** `app/services/chat/llm.py` definiert `TermExtractor.extract_terms(message, lang) -> str | None`.
Eine eigene Implementierung (z. B. Aufruf eines lokalen Ollama-Servers) wird mit `set_term_extractor(...)` registriert, etwa beim App-Start. Das Modell darf nur Suchbegriffe
aus der Frage ableiten; die Treffer kommen weiterhin ausschließlich aus der Datenbank. Fehler des Modells fallen automatisch auf die Standardlogik zurück.
Mitgeliefert ist nur die Schnittstelle, keine Modell-Anbindung und keine neue Abhängigkeit.

**Einschränkungen:** Die Bewertung ist regelbasiert (kein semantisches Verständnis; Synonyme wie „Gehhilfe“ ↔ „Rollator“ werden nur gefunden, wenn sie in Namen, Beschreibung,
Kategorie oder Dokumenttiteln vorkommen). Der Katalog wird je Anfrage neu gelesen (kein Cache); bei sehr großen Katalogen wäre ein kurzer Cache oder eine
Datenbank-Volltextsuche der nächste Schritt. Das Rate-Limit gilt je Prozess. Die Dokument-Links stammen aus den Datenbank-Metadaten; fehlt eine Datei im Storage, liefert der Download wie auf der Produktseite 404.

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
  services/          auth, category, product, document, setting, file, chat/ (Produktsuche)
  routers/           public, auth, admin (Settings + HTML), categories, products, documents, chat
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

## Live-Logs (Verwaltung → Live-Logs)

Zeigt in Echtzeit, was auf der Website passiert: Zugriffe, Änderungen im Admin (Audit), Chat-Anfragen, Fehler. Neue Einträge erscheinen binnen Sekundenbruchteilen
(Server-Sent Events: `GET /api/admin/logs/stream`, Rückblick: `GET /api/admin/logs`; nur für angemeldete Admins). Filter nach Stufe, Quelle und Text, Pausieren, Anzeige leeren.

* Die Einträge liegen nur im Arbeitsspeicher (letzte 2000, Ringpuffer) und sind nach einem Neustart weg. Die vollständigen Logs stehen weiter in `docker compose logs app`.
* Der Puffer gilt pro Prozess; die App läuft mit einem uvicorn-Worker. Bei mehreren Workern sähe jede Ansicht nur die Einträge ihres Workers.
* Chat-Anfragen erscheinen nur als Metadaten (Sprache, Antwortart, Trefferzahl), der Nachrichtentext wird nie geloggt. Healthchecks und die Log-Ansicht selbst werden ausgeblendet.
* Was angezeigt wird, richtet sich nach `LOG_LEVEL` (Standard `INFO`).
* Der Stream endet nach 5 Minuten von selbst; der Browser verbindet sich automatisch neu und prüft dabei die Anmeldung erneut.
* Hinter Caddy ist normalerweise nichts einzustellen (`text/event-stream` wird sofort durchgereicht). Bleibt die Anzeige auf „Verbinde …“ hängen, im `reverse_proxy`-Block `flush_interval -1` ergänzen.

## Betriebshinweise

* Der Port der App sollte nicht direkt öffentlich erreichbar sein (`APP_BIND=127.0.0.1`, Standard). Wenn ein externer
  Reverse Proxy `X-Forwarded-*`-Header sendet, `FORWARDED_ALLOW_IPS` in `.env` auf dessen konkrete Quell-IP(s) setzen;
  **niemals `FORWARDED_ALLOW_IPS=*` setzen.**
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
