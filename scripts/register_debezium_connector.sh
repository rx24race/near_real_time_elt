#!/usr/bin/env bash
set -euo pipefail

CONNECT_URL="${KAFKA_CONNECT_URL:-http://localhost:8083}"
CONNECTOR_NAME="${DEBEZIUM_CONNECTOR_NAME:-postgres-cdc-connector}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${1:-${SCRIPT_DIR}/../debezium/postgres-connector-config.json}"

echo "Registering Debezium connector '${CONNECTOR_NAME}' at ${CONNECT_URL}"

curl --fail --show-error --silent \
  -X PUT \
  -H "Content-Type: application/json" \
  --data @"${CONFIG_FILE}" \
  "${CONNECT_URL}/connectors/${CONNECTOR_NAME}/config"

echo
echo "Connector status:"
curl --fail --show-error --silent \
  "${CONNECT_URL}/connectors/${CONNECTOR_NAME}/status"
echo
