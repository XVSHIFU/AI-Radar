#!/usr/bin/env bash
# Executed separately by the official entrypoint only on a new data volume.
set -euo pipefail
for item in owner api ingest; do
  value="$(cat "/run/secrets/db_${item}_password")"
  [[ "$value" =~ ^[A-Za-z0-9_-]{43,128}$ ]] || exit 1
  export "RADAR_INIT_${item^^}_PASSWORD=$value"
done
unset value
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
\getenv owner_password RADAR_INIT_OWNER_PASSWORD
\getenv api_password RADAR_INIT_API_PASSWORD
\getenv ingest_password RADAR_INIT_INGEST_PASSWORD
CREATE EXTENSION IF NOT EXISTS vector;
CREATE ROLE radar_owner LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'owner_password';
CREATE ROLE radar_api LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'api_password';
CREATE ROLE radar_ingest LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'ingest_password';
REVOKE ALL ON DATABASE ai_radar FROM PUBLIC;
GRANT CONNECT ON DATABASE ai_radar TO radar_owner, radar_api, radar_ingest;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO radar_owner;
GRANT USAGE ON SCHEMA public TO radar_api, radar_ingest;
ALTER DEFAULT PRIVILEGES FOR ROLE radar_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO radar_api, radar_ingest;
ALTER DEFAULT PRIVILEGES FOR ROLE radar_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO radar_api, radar_ingest;
SQL
unset RADAR_INIT_OWNER_PASSWORD RADAR_INIT_API_PASSWORD RADAR_INIT_INGEST_PASSWORD
