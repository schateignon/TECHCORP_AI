#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=api_password="$API_DB_PASSWORD" --set=mcp_password="$MCP_DB_PASSWORD" \
  --set=etl_password="$ETL_DB_PASSWORD" <<'SQL'
CREATE ROLE tech_api LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'api_password';
CREATE ROLE tech_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'mcp_password';
CREATE ROLE tech_etl LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'etl_password';
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO tech_api, tech_reader, tech_etl;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO tech_reader;
GRANT SELECT, INSERT ON tickets TO tech_api;
GRANT USAGE, SELECT ON SEQUENCE tickets_id_seq TO tech_api;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO tech_etl;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO tech_etl;
ALTER ROLE tech_reader SET default_transaction_read_only = on;
SQL
