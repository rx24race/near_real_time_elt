# Python Kafka Consumer

Story 5 implements the custom streaming ingestion service:

```text
Kafka Debezium topics -> Python consumer -> BigQuery bronze.cdc_events
```

Airflow does not start or schedule this service. It runs continuously as the `python-bq-consumer` Docker service.

## Topics

The consumer subscribes to:

```text
postgres.customers
postgres.products
postgres.orders
postgres.order_items
postgres.payments
```

Override the list with `KAFKA_TOPICS` if needed.

## BigQuery Credentials

Place the service account key at:

```text
bigquery/service_account.json
```

Docker Compose mounts `bigquery/` into the consumer container as read-only credentials:

```text
/opt/app/credentials/service_account.json
```

The key is ignored by Git via `bigquery/*.json`.

## Run

Build or rebuild the consumer after dependency changes:

```bash
docker compose build python-bq-consumer
docker compose up -d python-bq-consumer
```

Watch logs:

```bash
docker compose logs -f python-bq-consumer
```

Expected healthy messages include:

```text
event=consumer_ready
event=consumer_heartbeat
event=bigquery_insert_success
event=kafka_offsets_committed
```

## Delivery Semantics

The consumer is intentionally simple and interview-friendly:

- Kafka auto-commit is disabled.
- Rows are inserted into BigQuery first.
- Kafka offsets are committed only after BigQuery accepts the batch.
- `kafka_topic`, `kafka_partition`, and `kafka_offset` are stored in Bronze for deterministic downstream deduplication.

This gives at-least-once delivery. If the consumer crashes after a BigQuery insert but before a Kafka commit, the same CDC event can be inserted again. Silver models should deduplicate by topic, partition, and offset.

## Verify Rows

After running a demo SQL script that changes PostgreSQL data, query Bronze:

```bash
bq --project_id near-real-time-elt query --use_legacy_sql=false \
  "SELECT source_table, op, kafka_topic, kafka_partition, kafka_offset, ingested_at
   FROM bronze.cdc_events
   ORDER BY ingested_at DESC
   LIMIT 20"
```

## Common Failures

If the consumer logs `Set GCP_PROJECT_ID`, update `.env`.

If BigQuery authentication fails, confirm `bigquery/service_account.json` exists and that the service account has:

- `BigQuery Data Editor`
- `BigQuery Job User`

If Kafka is unavailable, the consumer logs `event=kafka_unavailable` and retries every 10 seconds.
