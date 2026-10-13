#!/bin/sh
# Wendet Migrationen an, legt (einmalig) den initialen Admin an und startet dann den Server.
set -e

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

echo "[entrypoint] seed-admin"
python -m app.cli seed-admin

exec "$@"
