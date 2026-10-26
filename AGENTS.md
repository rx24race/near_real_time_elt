# AGENTS.md

## Project Objective

Build an interview-ready end-to-end CDC data engineering project demonstrating:

* PostgreSQL CDC using Debezium
* Kafka streaming
* Custom Python Kafka consumer
* BigQuery Bronze/Silver/Gold architecture
* Dataform transformations
* Airflow orchestration
* SCD Type 2 dimensional modeling

## Architecture Constraints

* Runtime services run locally via Docker; BigQuery is the managed cloud warehouse.
* The optional `csv_etl/` exercise is a standalone local Python command using embedded DuckDB SQL and offline HTML reporting. It is a non-service exception to the Docker guideline; it must remain independent of the CDC services and cloud credentials.
* Dataform CLI runs inside the local Airflow container and submits SQL to BigQuery. The current workflow does not use Cloud Dataform workflow invocations.

* Use an e-commerce domain.

* Use the following source tables:

  * customers
  * products
  * orders
  * order_items
  * payments

* Debezium captures CDC events from PostgreSQL.

* Kafka transports CDC events.

* A custom Python consumer loads append-only CDC events into BigQuery Bronze.

* Airflow orchestrates transformations only.

* Airflow must NOT orchestrate streaming ingestion.

* Dataform transforms:

  * Bronze → Silver
  * Silver → Gold
  * Bronze → Gold for customer SCD Type 2 history, because Silver retains only the latest source state.

* Gold implements SCD Type 2 on customer dimensions.

## Current Implementation

### Continuous Ingestion

* PostgreSQL contains the five e-commerce source tables listed above.
* Debezium runs inside Kafka Connect, takes an initial snapshot, and then captures changes from PostgreSQL's transaction log.
* Kafka transports events through `postgres.customers`, `postgres.products`, `postgres.orders`, `postgres.order_items`, and `postgres.payments`.
* `consumer/app.py` continuously appends events from all five topics to `bronze.cdc_events`.
* Bronze preserves before/after JSON, raw events, operation types, event and ingestion timestamps, and Kafka topic/partition/offset metadata.
* Kafka offsets are committed only after a successful BigQuery batch write. Delivery is at-least-once, with deterministic insert IDs for best-effort BigQuery deduplication; exactly-once delivery is not guaranteed.

### Transformations and Modeling

* Dataform models live in `dataform/definitions/`.
* Silver parses and types raw events, selects the latest event per source primary key, and excludes records whose latest event is a delete.
* Silver and Gold models currently rebuild tables on each run rather than using incremental MERGEs.
* Gold contains `dim_customer`, `dim_product`, `dim_date`, `fact_order`, `fact_order_item`, and `fact_payment`.
* `dim_customer` reconstructs SCD Type 2 history directly from Bronze, tracking changes to `email`, `city`, and `membership_tier`. It exposes `effective_start_at`, `effective_end_at`, and `is_current`; delete events close customer versions.
* Facts resolve customer surrogate keys using the dimension version valid at the order or payment creation timestamp. Missing dimension matches use an `unknown` member.

### Orchestration and Quality

* `airflow/dags/dataform_transformations.py` defines the manually triggered `dataform_bronze_to_gold` DAG; no automatic schedule is configured.
* Task order: `bronze_ready` → `run_dataform_silver` → `run_dataform_gold` → `run_dq_checks` → `notify`.
* `bronze_ready` checks that Bronze contains at least one event; it does not verify freshness or ingestion completeness.
* The Gold Dataform command uses `--include-deps`, so Silver dependencies can run again during the Gold task.
* Dataform assertions enforce data quality during Silver and Gold runs. The separate `run_dq_checks` task currently logs confirmation only; it does not execute additional checks.
* Tasks have two retries with a one-minute retry delay. Success and DAG failure email notifications are optional and require recipient and SMTP configuration.
* Near-real-time freshness applies to Bronze. Silver and Gold refresh only when transformations run.

## Coding Guidelines

* Keep implementations simple and interview-friendly.
* Prefer readability over optimization.
* Add comments explaining major decisions.
* Include logging and error handling.
* Make all components idempotent.
* Preserve replay-safe transformations and explicitly document ingestion delivery guarantees; do not assume best-effort deduplication provides exactly-once delivery.
* Avoid unnecessary dependencies.
* Avoid introducing additional containers unless justified.

## Deliverables

* Working Docker Compose setup
* Reproducible local environment
* README suitable for interview demonstrations
* Demo scripts showing CDC end-to-end
