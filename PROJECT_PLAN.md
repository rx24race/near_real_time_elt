# PROJECT_PLAN.md

## Project Name

CDC-to-BigQuery Lakehouse Data Engineering Project

---

# Project Goal

Build an interview-ready end-to-end near real-time data engineering project that demonstrates modern data engineering concepts and best practices.

The project should showcase:

* Change Data Capture (CDC)
* Event streaming with Kafka
* Debezium
* BigQuery Bronze/Silver/Gold architecture
* Dataform transformations
* Airflow orchestration
* SCD Type 2 dimensional modeling
* Idempotency and deduplication
* Dockerized local development

---

# Architecture

```text
PostgreSQL
    ↓ CDC
Debezium
    ↓
Kafka
    ↓
Custom Python Consumer
    ↓
BigQuery Bronze
    ↓
Airflow
    ↓
Dataform
    ↓
BigQuery Silver
    ↓
Dataform
    ↓
BigQuery Gold
```

---

# Scope

## Local Infrastructure

Everything should run locally via Docker except:

* BigQuery
* Dataform

## Docker Services

Required containers:

* postgres
* kafka
* kafka-connect
* python-bq-consumer
* airflow

Optional:

* kafka-ui

Use Kafka KRaft mode if possible.

Avoid introducing unnecessary containers.

---

# Business Domain

Use an e-commerce domain.

Source OLTP tables:

* customers
* products
* orders
* order_items
* payments

---

# Story 1: Project Skeleton

## Goal

Set up repository structure and Docker Compose.

## Tasks

Create folders:

```text
postgres/
debezium/
consumer/
airflow/
dataform/
scripts/
docs/
```

Create:

* docker-compose.yml
* .env.example
* README.md

Add Docker services:

* postgres
* kafka
* kafka-connect
* python-bq-consumer
* airflow

Verify:

```bash
docker compose up -d
```

## Acceptance Criteria

* All containers start successfully.
* Repository structure is complete.

---

# Story 2: PostgreSQL Source Database

## Goal

Create the OLTP source system.

## Tasks

Create PostgreSQL initialization scripts.

Create tables:

### customers

Fields:

* customer_id
* first_name
* last_name
* email
* city
* membership_tier
* created_at
* updated_at

### products

Fields:

* product_id
* product_name
* category
* unit_price
* created_at
* updated_at

### orders

Fields:

* order_id
* customer_id
* order_status
* order_total
* created_at
* updated_at

### order_items

Fields:

* order_item_id
* order_id
* product_id
* quantity
* unit_price
* created_at
* updated_at

### payments

Fields:

* payment_id
* order_id
* payment_method
* payment_status
* amount
* created_at
* updated_at

Add:

* primary keys
* foreign keys
* sample seed data

Create demo SQL scripts for:

* insert customer
* update customer city
* update membership tier
* create order
* create order items
* create payment
* delete record

## Acceptance Criteria

* Database initializes automatically.
* Seed data exists.
* Demo scripts execute successfully.

---

# Story 3: Debezium CDC Setup

## Goal

Capture PostgreSQL changes and publish them into Kafka.

## Tasks

Enable PostgreSQL logical replication.

Configure Kafka Connect.

Configure Debezium PostgreSQL connector.

Capture:

* customers
* products
* orders
* order_items
* payments

Expected Kafka topics:

```text
postgres.customers
postgres.products
postgres.orders
postgres.order_items
postgres.payments
```

Create:

```text
scripts/register_debezium_connector.sh
```

Document:

* how to register connector
* how to verify connector status

## Acceptance Criteria

* Inserts generate Kafka events.
* Updates generate Kafka events.
* Deletes generate Kafka events.

---

# Story 4: BigQuery Bronze Setup

## Goal

Create raw append-only landing tables.

## Tasks

Create dataset:

```text
bronze
```

Create table:

```text
bronze.cdc_events
```

Schema:

* source_table STRING
* op STRING
* event_ts TIMESTAMP
* kafka_topic STRING
* kafka_partition INT64
* kafka_offset INT64
* before_json JSON
* after_json JSON
* raw_event_json JSON
* ingested_at TIMESTAMP

Document:

* GCP project setup
* service account authentication
* dataset creation

## Acceptance Criteria

* Bronze table exists.
* Consumer can write to Bronze.

---

# Story 5: Python Kafka Consumer

## Goal

Continuously load CDC events into BigQuery.

## Tasks

Build a Python consumer service.

Subscribe to:

* postgres.customers
* postgres.products
* postgres.orders
* postgres.order_items
* postgres.payments

Parse Debezium envelope.

Extract:

* source_table
* operation type
* event timestamp
* before payload
* after payload
* Kafka topic
* Kafka partition
* Kafka offset
* raw event

Write append-only rows into:

```text
bronze.cdc_events
```

Requirements:

* no transformations
* structured logging
* retry handling
* graceful shutdown
* Dockerfile
* environment variable configuration

## Acceptance Criteria

* CDC events appear in Bronze.
* Consumer survives transient failures.

---

# Story 6: Dataform Project Setup

## Goal

Initialize Dataform.

## Tasks

Create folders:

```text
definitions/bronze/
definitions/silver/
definitions/gold/
definitions/assertions/
includes/
```

Configure datasets:

* bronze
* silver
* gold

Document:

* setup instructions
* deployment instructions

## Acceptance Criteria

* Dataform project compiles successfully.

---

# Story 7: Silver Current-State Models

## Goal

Build cleaned operational tables.

## Tasks

Create:

* silver.customers
* silver.products
* silver.orders
* silver.order_items
* silver.payments

Each model should:

* read Bronze events
* filter by source_table
* parse JSON
* cast datatypes
* deduplicate CDC events
* retain latest state
* handle deletes
* normalize timestamps

Silver represents:

> The latest operational state of source systems.

## Acceptance Criteria

* Silver reflects source state accurately.
* Duplicate CDC events do not create duplicates.

---

# Story 8: Gold Dimensions

## Goal

Build dimensional models.

## Tasks

Create:

* gold.dim_date
* gold.dim_customer
* gold.dim_product

Implement SCD Type 2 for:

```text
gold.dim_customer
```

Optional:

```text
gold.dim_product
```

Track changes for:

* email
* city
* membership_tier

dim_customer columns:

* customer_sk
* customer_id
* first_name
* last_name
* email
* city
* membership_tier
* effective_start_at
* effective_end_at
* is_current
* record_hash

Behavior:

* expire existing row
* insert new row
* preserve history

## Acceptance Criteria

* Customer updates create SCD2 records.
* Exactly one current row exists per customer.

---

# Story 9: Gold Facts

## Goal

Create analytics-ready fact tables.

## Tasks

Create:

* gold.fact_order
* gold.fact_order_item
* gold.fact_payment

Join dimensions:

* dim_customer
* dim_product
* dim_date

Use surrogate keys.

Requirements:

* idempotent loads
* no SCD2 logic
* re-runnable transformations

## Acceptance Criteria

* Facts reference valid dimensions.
* Re-runs do not duplicate facts.

---

# Story 10: Airflow Orchestration

## Goal

Orchestrate warehouse transformations.

## Tasks

Create DAG scheduled every 5 minutes.

Flow:

```text
bronze_ready
    ↓
run_dataform_silver
    ↓
run_dataform_gold
    ↓
run_dq_checks
    ↓
notify
```

Requirements:

* Airflow does NOT orchestrate CDC.
* Configure retries.
* Configure alerts.
* Support manual reruns.

## Acceptance Criteria

* DAG completes successfully.
* Failures are observable.

---

# Story 11: Data Quality Checks

## Goal

Validate Silver and Gold outputs.

## Tasks

Silver checks:

* no duplicate customer_id
* no duplicate product_id
* no duplicate order_id
* required fields not null

Gold checks:

* one current SCD2 row per customer
* surrogate keys not null
* order totals >= 0
* payment amounts >= 0

Integrate checks into Airflow.

## Acceptance Criteria

* Failing checks fail the DAG.

---

# Story 12: Demo Scenarios

## Goal

Demonstrate the pipeline end-to-end.

## Tasks

Create scripts:

* insert_new_customer.sql
* update_customer_city.sql
* update_customer_tier.sql
* create_order.sql
* create_payment.sql
* delete_record.sql

Document expected behavior.

Example:

```text
Update customer city
↓
Debezium captures CDC
↓
Kafka receives event
↓
Consumer writes Bronze
↓
Silver updates current state
↓
Gold creates SCD2 version
```

## Acceptance Criteria

* Demo scripts showcase the full pipeline.

---

# Story 13: Observability

## Goal

Improve debugging and operational visibility.

## Tasks

Document:

* viewing Kafka topics
* consuming Kafka messages
* checking consumer logs
* checking Airflow logs

Add:

* consumer heartbeat logs
* troubleshooting guide

Cover:

* connector failures
* Kafka issues
* BigQuery authentication failures
* Airflow failures

## Acceptance Criteria

* Common failures can be diagnosed quickly.

---

# Story 14: Interview Portfolio README

## Goal

Create a polished artifact suitable for interviews.

## Tasks

Document:

* architecture overview
* CDC rationale
* Debezium rationale
* Kafka rationale
* custom consumer rationale
* Bronze/Silver/Gold rationale
* Dataform rationale
* Airflow rationale
* SCD2 rationale
* idempotency strategy
* deduplication strategy

Include:

* architecture diagram
* setup instructions
* demo walkthrough
* screenshots/placeholders
* lessons learned
* future improvements

## Acceptance Criteria

* README is presentation-ready.
* README can be used to walk interviewers through the project.

---

# Future Enhancements (Out of Scope)

Potential future improvements:

* Schema Registry
* Avro serialization
* Kafka UI
* Great Expectations
* dbt comparison
* BigQuery partitioning and clustering optimization
* CI/CD pipeline
* GitHub Actions
* Infrastructure as Code
* Kubernetes deployment
* Data catalog integration
* Lineage tooling

These should NOT be implemented unless explicitly requested later.
