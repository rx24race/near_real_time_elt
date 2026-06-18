# BigQuery Bronze Setup

Story 4 creates the raw append-only landing layer used by the Kafka consumer.

## Resources

```text
Dataset: bronze
Table:   bronze.cdc_events
```

The table stores one row per Debezium CDC message. It intentionally keeps raw JSON payloads so later Silver and Gold transformations can be rerun from the original event history.

## Prerequisites

1. Create or choose a GCP project.
2. Enable the BigQuery API.
3. Install and authenticate the Google Cloud CLI.

   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

4. Create a service account for the consumer.

   Recommended minimum roles for this project:

   - `BigQuery Data Editor`
   - `BigQuery Job User`

5. Download the service account key JSON and place it at:

   ```text
   bigquery/service_account.json
   ```

   Keep this file local. It must not be committed.

## Environment

Copy `.env.example` to `.env` and set:

```text
GCP_PROJECT_ID=your-real-gcp-project-id
BIGQUERY_BRONZE_DATASET=bronze
BIGQUERY_LOCATION=US
GOOGLE_APPLICATION_CREDENTIALS=/opt/app/credentials/service_account.json
```

Use the same `BIGQUERY_LOCATION` for all BigQuery datasets in this project.

## Create Bronze

PowerShell:

```powershell
.\scripts\create_bigquery_bronze.ps1 -ProjectId your-real-gcp-project-id
```

Bash:

```bash
./scripts/create_bigquery_bronze.sh --project-id your-real-gcp-project-id
```

The scripts run the idempotent DDL in `bigquery/bronze_cdc_events.sql`, so they are safe to rerun.

## Verify

```bash
bq show your-real-gcp-project-id:bronze.cdc_events
```

Expected columns:

```text
source_table STRING
op STRING
event_ts TIMESTAMP
kafka_topic STRING
kafka_partition INT64
kafka_offset INT64
before_json JSON
after_json JSON
raw_event_json JSON
ingested_at TIMESTAMP
```

Optional write smoke test:

```bash
bq --project_id your-real-gcp-project-id query --use_legacy_sql=false < bigquery/insert_bronze_sample_event.sql
```

Confirm the sample row:

```bash
bq --project_id your-real-gcp-project-id query --use_legacy_sql=false \
  "SELECT source_table, op, kafka_topic, kafka_offset FROM bronze.cdc_events WHERE kafka_offset = 0"
```

## Consumer Contract

Story 5 will write append-only rows to `bronze.cdc_events`. The expected row grain is:

```text
one Kafka message -> one Bronze row
```

The Kafka topic, partition, and offset are stored with each row so downstream transformations can deduplicate CDC events deterministically.
