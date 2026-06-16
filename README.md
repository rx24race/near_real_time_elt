# CDC-to-BigQuery Lakehouse Data Engineering Project

An interview-ready near real-time data engineering project for an e-commerce domain.

## Architecture

```text
PostgreSQL -> Debezium -> Kafka -> Python Consumer -> BigQuery Bronze
                                                   -> Dataform Silver/Gold
                                                   -> Airflow orchestration
```

Local Docker services:

- `postgres`
- `kafka`
- `kafka-connect`
- `python-bq-consumer`
- `airflow`

BigQuery and Dataform remain external managed services.

## Repository Structure

```text
postgres/     PostgreSQL schema, seed data, and demo SQL scripts
debezium/     Debezium connector configuration
consumer/     Python Kafka-to-BigQuery consumer
airflow/      Airflow DAGs and local runtime folders
dataform/     Dataform project files
scripts/      Local setup and demo helper scripts
docs/         Interview notes, diagrams, and troubleshooting
```

## Quick Start

1. Copy the example environment file.

   ```bash
   cp .env.example .env
   ```

2. Start the local stack.

   ```bash
   docker compose up -d
   ```

3. Check container status.

   ```bash
   docker compose ps
   ```

Airflow is available at `http://localhost:8080` with the default credentials in `.env.example`.

## Current Status

Story 1 creates the project skeleton and Docker Compose foundation. Later stories add the PostgreSQL schema, Debezium connector registration, BigQuery Bronze table, Dataform transformations, and Airflow DAGs.
