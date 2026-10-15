#!/bin/sh
# Wendet Migrationen an (außer RUN_MIGRATIONS=false), legt (einmalig) den initialen Admin an und startet dann den Server.
# Unter Docker Compose migriert der Service "migrate" mit den Besitzer-Zugangsdaten; die App selbst setzt
# RUN_MIGRATIONS=false und braucht dadurch keine DDL-Rechte.
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "[entrypoint] alembic upgrade head"
    alembic upgrade head
else
    echo "[entrypoint] Migrationen übersprungen (RUN_MIGRATIONS=${RUN_MIGRATIONS})"
fi

echo "[entrypoint] seed-admin"
python -m app.cli seed-admin

exec "$@"
