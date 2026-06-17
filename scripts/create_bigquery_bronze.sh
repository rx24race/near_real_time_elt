#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-}"
DATASET="${BIGQUERY_BRONZE_DATASET:-bronze}"
LOCATION="${BIGQUERY_LOCATION:-US}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-id|-ProjectId)
      PROJECT_ID="${2:-}"
      shift 2
      ;;
    --project-id=*|-ProjectId=*)
      PROJECT_ID="${1#*=}"
      shift
      ;;
    --dataset)
      DATASET="${2:-}"
      shift 2
      ;;
    --dataset=*)
      DATASET="${1#*=}"
      shift
      ;;
    --location)
      LOCATION="${2:-}"
      shift 2
      ;;
    --location=*)
      LOCATION="${1#*=}"
      shift
      ;;
    *)
      if [[ -z "${PROJECT_ID}" ]]; then
        PROJECT_ID="$1"
      else
        echo "Unknown argument: $1" >&2
        exit 1
      fi
      shift
      ;;
  esac
done

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "your-gcp-project-id" ]]; then
  echo "Set GCP_PROJECT_ID or pass --project-id your-real-gcp-project-id." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DDL_PATH="${SCRIPT_DIR}/../bigquery/bronze_cdc_events.sql"

if [[ ! -f "${DDL_PATH}" ]]; then
  echo "Could not find BigQuery DDL file at ${DDL_PATH}." >&2
  exit 1
fi

DDL="$(sed \
  -e "s/\`bronze\`/\`${DATASET}\`/g" \
  -e "s/\`bronze.cdc_events\`/\`${PROJECT_ID}.${DATASET}.cdc_events\`/g" \
  -e "s/location = 'US'/location = '${LOCATION}'/g" \
  "${DDL_PATH}")"
TMP_SQL="$(mktemp)"
trap 'rm -f "${TMP_SQL}"' EXIT
printf "%s\n" "${DDL}" > "${TMP_SQL}"

echo "Creating BigQuery Bronze dataset and table..."
echo "Project : ${PROJECT_ID}"
echo "Dataset : ${DATASET}"
echo "Location: ${LOCATION}"

bq --location "${LOCATION}" --project_id "${PROJECT_ID}" query --use_legacy_sql=false < "${TMP_SQL}"

echo "Bronze table is ready: ${PROJECT_ID}.${DATASET}.cdc_events"
