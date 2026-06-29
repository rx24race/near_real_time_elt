# Airflow Orchestration

Airflow runs locally in Docker and orchestrates BigQuery transformations only.

It does not start Debezium, Kafka, or the Python streaming consumer. Those services run continuously outside Airflow so CDC ingestion stays independent from batch transformation orchestration.

## DAG

The DAG is `dataform_bronze_to_gold` and is configured for manual runs only.

```text
bronze_ready -> run_dataform_silver -> run_dataform_gold -> run_dq_checks -> notify
```

- `bronze_ready` checks that `bronze.cdc_events` has data.
- `run_dataform_silver` runs Dataform models tagged `silver`.
- `run_dataform_gold` runs Dataform models tagged `gold` with dependencies.
- `run_dq_checks` records that Dataform assertions already enforced data quality during the Silver and Gold runs.
- `notify` writes a success message to the Airflow task log and sends a success email when email settings are configured.

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

## Email Notifications

The DAG sends:

- a success email from the terminal `notify` task
- a failure email from the DAG-level failure callback after retries are exhausted

Email is disabled by default. To enable it, set the recipient and SMTP settings in `.env`, then restart Airflow:

```text
AIRFLOW_ALERT_EMAIL_TO=you@example.com
AIRFLOW_SMTP_HOST=smtp.gmail.com
AIRFLOW_SMTP_PORT=587
AIRFLOW_SMTP_USER=you@example.com
AIRFLOW_SMTP_PASSWORD=your-app-password
AIRFLOW_SMTP_MAIL_FROM=you@example.com
AIRFLOW_SMTP_STARTTLS=True
AIRFLOW_SMTP_SSL=False
```

For Gmail, use an app password instead of your normal account password. If `AIRFLOW_ALERT_EMAIL_TO` is empty, the DAG skips email and logs that notifications are disabled.

## Manual Runs

Trigger the full DAG from the CLI when you want to refresh Silver and Gold:

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
