#!/bin/bash
# Creates the Zabbix database and user on first postgres start.
# Runs as part of docker-entrypoint-initdb.d — executes once.

set -e

ZABBIX_DB="${ZABBIX_DB_NAME:-zabbix}"
ZABBIX_USER="${ZABBIX_DB_USER:-zabbix}"
ZABBIX_PASS="${ZABBIX_DB_PASSWORD:-zabbix}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
    CREATE USER ${ZABBIX_USER} WITH PASSWORD '${ZABBIX_PASS}';
    CREATE DATABASE ${ZABBIX_DB} OWNER ${ZABBIX_USER} ENCODING 'UTF8';
    GRANT ALL PRIVILEGES ON DATABASE ${ZABBIX_DB} TO ${ZABBIX_USER};
EOSQL

echo "[init-zabbix-db] Zabbix DB and user created."
