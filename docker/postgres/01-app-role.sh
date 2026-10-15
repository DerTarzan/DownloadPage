#!/bin/sh
# Legt die Laufzeit-Rolle der Anwendung an (SEC-004): kein Superuser, kein DDL, nur Lese-/Schreibrechte auf Tabellen.
#
# - Läuft automatisch beim ERSTEN Start eines neuen Datenbank-Volumes (docker-entrypoint-initdb.d).
# - Für eine bestehende Datenbank von Hand (idempotent, kann beliebig oft laufen):
#       docker compose exec db sh /docker-entrypoint-initdb.d/01-app-role.sh
# - Ohne APP_DB_USER/APP_DB_PASSWORD passiert nichts (die App nutzt dann weiter den Besitzer = Superuser).
#
# Bewusst ohne "exit"/"exec"/"set" auf oberster Ebene: das Image führt .sh-Dateien ohne Ausführungsrecht per
# "source" aus, ein exit würde dann die gesamte Initialisierung beenden.

app_role_init() {
    if [ -z "${APP_DB_USER:-}" ] || [ -z "${APP_DB_PASSWORD:-}" ]; then
        echo "[app-role] APP_DB_USER/APP_DB_PASSWORD nicht gesetzt - keine Laufzeit-Rolle angelegt."
        return 0
    fi
    if [ "${APP_DB_USER}" = "${POSTGRES_USER}" ]; then
        echo "[app-role] APP_DB_USER entspricht dem Besitzer (POSTGRES_USER) - übersprungen."
        return 0
    fi
    echo "[app-role] richte Rolle '${APP_DB_USER}' ein"
    # Werte kommen per \getenv in psql (nicht über die Kommandozeile) und werden mit %I/%L bzw. :"..." korrekt quotiert.
    psql -v ON_ERROR_STOP=1 --no-psqlrc --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'EOSQL'
\getenv app_user APP_DB_USER
\getenv app_password APP_DB_PASSWORD
\getenv owner POSTGRES_USER
\getenv db POSTGRES_DB

-- Rolle anlegen bzw. Passwort/Eigenschaften nachziehen (idempotent)
SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
              :'app_user', :'app_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'app_user')
\gexec
SELECT format('ALTER ROLE %I NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
              :'app_user', :'app_password')
WHERE EXISTS (SELECT FROM pg_roles WHERE rolname = :'app_user')
\gexec

-- Verbinden nur für Besitzer und App-Rolle; Schema public nur lesen/benutzen, nie Objekte anlegen
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', :'db')
\gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'db', :'app_user')
\gexec
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO :"app_user";

-- Bereits vorhandene Tabellen/Sequenzen (bestehende Installation) ...
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"app_user";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO :"app_user";
-- ... und alle künftig vom Besitzer (Migrationen) angelegten
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"app_user";
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO :"app_user";
EOSQL
}

app_role_init
