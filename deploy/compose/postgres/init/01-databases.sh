#!/usr/bin/env bash
# Runs once, on first start with an empty data volume.
# Creates one database and one login role per service. Each role owns only its
# own database, and PUBLIC may not connect, so services cannot read each
# other's data even though they share one server locally.
set -euo pipefail

create_service_db() {
  local name="$1" password="$2"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
       -v name="$name" -v password="$password" <<'SQL'
CREATE ROLE :"name" LOGIN PASSWORD :'password';
CREATE DATABASE :"name" OWNER :"name";
REVOKE ALL ON DATABASE :"name" FROM PUBLIC;
SQL
}

create_service_db marketplace "$MARKETPLACE_DB_PASSWORD"
create_service_db checkout    "$CHECKOUT_DB_PASSWORD"
create_service_db inventory   "$INVENTORY_DB_PASSWORD"
create_service_db assistant   "$ASSISTANT_DB_PASSWORD"

# PostGIS is not a trusted extension, so the superuser installs it
# for the one service that needs geo queries.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname marketplace \
     -c "CREATE EXTENSION IF NOT EXISTS postgis;"
