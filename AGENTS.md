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

* All infrastructure runs locally via Docker except:

  * BigQuery
  * Dataform

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

* Gold implements SCD Type 2 on customer dimensions.

## Coding Guidelines

* Keep implementations simple and interview-friendly.
* Prefer readability over optimization.
* Add comments explaining major decisions.
* Include logging and error handling.
* Make all components idempotent.
* Avoid unnecessary dependencies.
* Avoid introducing additional containers unless justified.

## Deliverables

* Working Docker Compose setup
* Reproducible local environment
* README suitable for interview demonstrations
* Demo scripts showing CDC end-to-end
