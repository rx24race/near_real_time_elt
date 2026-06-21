# Demo Scenarios

Story 12 demonstrates the full CDC pipeline with small e-commerce changes.

The demo path is:

```text
PostgreSQL change
  -> Debezium captures CDC
  -> Kafka receives a topic event
  -> Python consumer appends to BigQuery Bronze
  -> Airflow runs Dataform
  -> Silver reflects current source state
  -> Gold reflects dimensional analytics state
```

## Prerequisites

Start the local services:

```bash
docker compose up -d
```

Register or refresh the Debezium connector:

```bash
./scripts/register_debezium_connector.sh
```

Confirm the consumer is running:

```bash
docker compose logs -f python-bq-consumer
```

Healthy ingestion logs include:

```text
event=bigquery_insert_success
event=kafka_offsets_committed
```

## Optional Reset

For a repeatable source-system demo, remove prior demo rows before starting:

```bash
docker exec cdc_postgres psql -U postgres -d ecommerce -v ON_ERROR_STOP=1 -f //opt/project/scripts/reset_demo_data.sql
```

The double slash before `opt` is intentional for Git Bash on Windows. It prevents Git Bash from rewriting the container path into a Windows path like `C:/Program Files/Git/opt/...`.

This only affects the demo IDs:

- customer `1001`
- order `2001`
- order items `3001`, `3002`
- payment `4001`
- disposable product `9001`

This reset changes PostgreSQL only. It does not delete historical Bronze CDC events from BigQuery. Because Bronze is append-only, repeated demos can produce additional historical SCD2 rows in `gold.dim_customer`. That is expected; for a completely clean warehouse demo, reset Kafka/Debezium offsets and truncate or recreate the BigQuery Bronze table before replaying from the initial snapshot.

## Scenario 1: Insert A New Customer

Run:

```bash
docker exec cdc_postgres psql -U postgres -d ecommerce -v ON_ERROR_STOP=1 -f //opt/project/scripts/insert_new_customer.sql
```

Expected CDC:

- Debezium writes a customer create/update event to `postgres.customers`.
- The Python consumer appends a `customers` row to `bronze.cdc_events`.
- After Airflow/Dataform runs, `silver.customers` contains customer `1001`.
- `gold.dim_customer` contains a current SCD2 row for customer `1001`.

## Scenario 2: Update Customer City

Run:

```bash
docker exec cdc_postgres psql -U postgres -d ecommerce -v ON_ERROR_STOP=1 -f //opt/project/scripts/update_customer_city.sql
```

Expected CDC:

- Debezium emits an update event with `before` and `after` customer images.
- Bronze stores the raw update event.
- Silver shows customer `1001` with city `New York`.
- Gold creates a new SCD2 customer version because `city` is a tracked attribute.

Expected Gold result:

```text
customer_id=1001
old row: city=Chicago, is_current=false
new row: city=New York, is_current=true
```

If you have run the demo before, `gold.dim_customer` may show additional older versions for customer `1001`. The key check is that exactly one row is current and it reflects the latest customer values.

## Scenario 3: Update Membership Tier

Run:

```bash
docker exec cdc_postgres psql -U postgres -d ecommerce -v ON_ERROR_STOP=1 -f //opt/project/scripts/update_customer_tier.sql
```

Expected CDC:

- Debezium emits another customer update event.
- Silver shows customer `1001` with membership tier `gold`.
- Gold creates another SCD2 version because `membership_tier` is tracked.

Expected Gold result:

```text
customer_id=1001
old current row expires
new row: membership_tier=gold, is_current=true
```

## Scenario 4: Create An Order And Line Items

Run:

```bash
docker exec cdc_postgres psql -U postgres -d ecommerce -v ON_ERROR_STOP=1 -f //opt/project/scripts/create_order_items.sql
```

Expected CDC:

- Debezium emits events for `orders` and `order_items`.
- Bronze receives raw events for both source tables.
- Silver shows order `2001` and order items `3001`, `3002`.
- Gold `fact_order` has one row for order `2001`.
- Gold `fact_order_item` has two rows for order items `3001`, `3002`.
- Gold facts reference `dim_customer`, `dim_product`, and `dim_date` surrogate keys.

## Scenario 5: Capture Payment

Run:

```bash
docker exec cdc_postgres psql -U postgres -d ecommerce -v ON_ERROR_STOP=1 -f //opt/project/scripts/create_payment.sql
```

Expected CDC:

- Debezium emits an `orders` update changing order `2001` to `paid`.
- Debezium emits a `payments` event for payment `4001`.
- Silver shows order `2001` as `paid` and payment `4001` as `captured`.
- Gold `fact_payment` has one row for payment `4001`.

## Scenario 6: Delete A Record

Run:

```bash
docker exec cdc_postgres psql -U postgres -d ecommerce -v ON_ERROR_STOP=1 -f //opt/project/scripts/delete_record.sql
```

Expected CDC:

- Debezium emits a product insert/update event for product `9001`.
- Debezium emits a delete event for product `9001`.
- Bronze keeps both raw events because Bronze is append-only.
- Silver filters out the deleted product from current state.
- Gold `dim_product` does not keep product `9001` as an active product dimension row.

## Run Transformations

Airflow is configured for manual runs in this local demo:

```bash
docker compose exec airflow airflow dags trigger dataform_bronze_to_gold
```

For a synchronous local demo:

```bash
docker compose exec airflow airflow dags test dataform_bronze_to_gold 2026-06-21
```

## Verify In BigQuery

Recent Bronze events:

```bash
bq --project_id near-real-time-elt query --use_legacy_sql=false \
  "SELECT source_table, op, kafka_topic, kafka_partition, kafka_offset, ingested_at
   FROM bronze.cdc_events
   ORDER BY ingested_at DESC
   LIMIT 20"
```

Customer current state:

```bash
bq --project_id near-real-time-elt query --use_legacy_sql=false \
  "SELECT customer_id, first_name, last_name, city, membership_tier
   FROM silver.customers
   WHERE customer_id = 1001"
```

Customer SCD2 history:

```bash
bq --project_id near-real-time-elt query --use_legacy_sql=false \
  "SELECT customer_id, city, membership_tier, effective_start_at, effective_end_at, is_current
   FROM gold.dim_customer
   WHERE customer_id = 1001
   ORDER BY effective_start_at"
```

Order facts:

```bash
bq --project_id near-real-time-elt query --use_legacy_sql=false \
  "SELECT order_id, customer_id, order_status, order_total, customer_sk
   FROM gold.fact_order
   WHERE order_id = 2001"
```

Payment facts:

```bash
bq --project_id near-real-time-elt query --use_legacy_sql=false \
  "SELECT payment_id, order_id, payment_status, amount, customer_sk
   FROM gold.fact_payment
   WHERE payment_id = 4001"
```

## Interview Talking Points

- Bronze is append-only and preserves raw CDC events for replay and debugging.
- Silver is current-state and deduplicates CDC events by source primary key.
- Gold is analytics-ready and uses dimensional modeling.
- Customer updates create SCD Type 2 history in `gold.dim_customer`.
- Airflow schedules transformations only; streaming ingestion stays independent.
- Dataform assertions fail transformation tasks when data quality rules are violated.
