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
- `kafka-ui`
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

Kafka UI is available at `http://localhost:8081`.

## PostgreSQL Source Database

The source database initializes with e-commerce OLTP tables and seed data:

- `customers`
- `products`
- `orders`
- `order_items`
- `payments`

For a fresh local environment, the SQL files in `postgres/init/` run automatically when the Postgres volume is created.

If the Postgres container already existed before these files were added, apply them manually:

```bash
docker compose exec postgres psql -U postgres -d ecommerce -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/001_create_source_tables.sql
docker compose exec postgres psql -U postgres -d ecommerce -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/002_seed_source_data.sql
```

Demo SQL scripts are mounted into the Postgres container at `/opt/project/scripts`:

```bash
docker compose exec postgres psql -U postgres -d ecommerce -v ON_ERROR_STOP=1 -f /opt/project/scripts/insert_new_customer.sql
docker compose exec postgres psql -U postgres -d ecommerce -v ON_ERROR_STOP=1 -f /opt/project/scripts/update_customer_city.sql
docker compose exec postgres psql -U postgres -d ecommerce -v ON_ERROR_STOP=1 -f /opt/project/scripts/update_customer_tier.sql
docker compose exec postgres psql -U postgres -d ecommerce -v ON_ERROR_STOP=1 -f /opt/project/scripts/create_order.sql
docker compose exec postgres psql -U postgres -d ecommerce -v ON_ERROR_STOP=1 -f /opt/project/scripts/create_order_items.sql
docker compose exec postgres psql -U postgres -d ecommerce -v ON_ERROR_STOP=1 -f /opt/project/scripts/create_payment.sql
docker compose exec postgres psql -U postgres -d ecommerce -v ON_ERROR_STOP=1 -f /opt/project/scripts/delete_record.sql
```

## Debezium CDC

Register the PostgreSQL Debezium connector after the stack is running:

```bash
./scripts/register_debezium_connector.sh
```

PowerShell users can run:

```powershell
.\scripts\register_debezium_connector.ps1
```

The connector captures `customers`, `products`, `orders`, `order_items`, and `payments`, then writes CDC events to:

- `postgres.customers`
- `postgres.products`
- `postgres.orders`
- `postgres.order_items`
- `postgres.payments`

More details are in `docs/debezium.md`.

## Current Status

Stories 1 through 3 create the Docker Compose foundation, PostgreSQL source database, and Debezium CDC setup. Later stories add the BigQuery Bronze table, Dataform transformations, and Airflow DAGs.
