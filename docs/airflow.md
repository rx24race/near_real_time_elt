# Airflow Orchestration

Airflow runs locally in Docker and orchestrates BigQuery transformations only.

It does not start Debezium, Kafka, or the Python streaming consumer. Those services run continuously outside Airflow so CDC ingestion stays independent from batch transformation orchestration.

## DAG

The DAG is `dataform_bronze_to_gold` and runs every five minutes.

```text
bronze_ready -> run_dataform_silver -> run_dataform_gold -> run_dq_checks -> notify
```

- `bronze_ready` checks that `bronze.cdc_events` has data.
- `run_dataform_silver` runs Dataform models tagged `silver`.
- `run_dataform_gold` runs Dataform models tagged `gold` with dependencies.
- `run_dq_checks` records that Dataform assertions already enforced data quality during the Silver and Gold runs.
- `notify` writes a success message to the Airflow task log.

## Local UI

Start or rebuild Airflow after DAG or image changes:

```bash
docker compose build airflow
docker compose up -d airflow
```

Open Airflow at:

```text
http://localhost:8080
```

The default local login is controlled by `.env`:

```text
AIRFLOW_USERNAME=admin
AIRFLOW_PASSWORD=admin
```

## Manual Runs

Trigger the full DAG from the CLI:

```bash
docker compose exec airflow airflow dags trigger dataform_bronze_to_gold
```

Run the DAG synchronously for local testing:

```bash
docker compose exec airflow airflow dags test dataform_bronze_to_gold 2026-06-20
```

Check DAG import errors:

```bash
docker compose exec airflow airflow dags list-import-errors
```

## Failure Visibility

The DAG uses two retries with a one-minute delay. A failing Dataform assertion fails the `run_dataform_silver` or `run_dataform_gold` task because `dataform run` exits with a non-zero status. Failures are visible in:

- the Airflow UI task status
- the Airflow UI task logs
- container logs from `docker compose logs -f airflow`

This keeps failures observable during demos without adding external alerting infrastructure.
