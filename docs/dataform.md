# Dataform Setup

Story 6 initializes the Dataform project used for BigQuery transformations.

Dataform is external to Docker in this project. The local repository stores the project source, while execution happens through Dataform/BigQuery.

## Project Layout

```text
dataform/
  workflow_settings.yaml
  includes/
    datasets.js
  definitions/
    bronze/
      cdc_events.sqlx
    silver/
      customers.sqlx
      products.sqlx
      orders.sqlx
      order_items.sqlx
      payments.sqlx
    gold/
      dim_customer.sqlx
      dim_date.sqlx
      dim_product.sqlx
      fact_order.sqlx
      fact_order_item.sqlx
      fact_payment.sqlx
    assertions/
      bronze_cdc_events_required_fields.sqlx
      silver_*_unique.sqlx
      gold_dim_customer_one_current.sqlx
      gold_fact_*_valid.sqlx
```

## Dataset Configuration

Datasets are configured in `dataform/workflow_settings.yaml`:

```yaml
vars:
  bronzeDataset: bronze
  silverDataset: silver
  goldDataset: gold
```

The Bronze table is declared in Dataform as an external input:

```text
bronze.cdc_events
```

Story 7 adds Silver current-state tables. Story 8 adds Gold dimensions. Story 9 adds Gold facts.

## Local Compile

From the repository root:

```bash
npm run dataform:compile
```

The root `package.json` uses `npx` to run the Dataform CLI against the `dataform/` folder. This keeps `dataform/` as pure Dataform source, which avoids local `node_modules` files being interpreted as project files.

Compilation validates the Dataform project structure and SQLX syntax. It does not run transformations in BigQuery.

## Run Silver

Create a local Dataform credentials wrapper at `dataform/.df-credentials.json`. This file is ignored by Git. It should contain your billing project, BigQuery location, and the service account JSON as a string.

Then run:

```bash
npm run dataform:run:silver
```

This creates or replaces:

```text
silver.customers
silver.products
silver.orders
silver.order_items
silver.payments
```

Each Silver table reads `bronze.cdc_events`, parses the Debezium JSON payload, deduplicates by source primary key, filters out deletes, and keeps the latest current-state row.

## Run Gold Dimensions

```bash
npm run dataform:run:gold
```

This creates or replaces:

```text
gold.dim_customer
gold.dim_date
gold.dim_product
gold.fact_order
gold.fact_order_item
gold.fact_payment
```

`gold.dim_customer` is an SCD Type 2 dimension built from Bronze customer CDC history. It tracks changes to:

- `email`
- `city`
- `membership_tier`

`gold.dim_product` is a current-state product dimension built from `silver.products`.

`gold.dim_date` is a reusable calendar dimension.

Gold facts use stable surrogate keys from the Gold dimensions and source transaction keys from Silver:

- `gold.fact_order` joins `gold.dim_customer` and `gold.dim_date`
- `gold.fact_order_item` joins `gold.dim_customer`, `gold.dim_product`, and `gold.dim_date`
- `gold.fact_payment` joins `gold.dim_customer` and `gold.dim_date`

The fact models are full-refresh and idempotent. Rerunning the command recreates the same facts from Silver and Gold dimensions rather than appending duplicates.

## Cloud Dataform Setup

1. Create a Dataform repository in the same GCP project used by BigQuery.
2. Connect the repository to this Git project.
3. Set the repository root or workspace path to:

   ```text
   dataform
   ```

4. Confirm `workflow_settings.yaml` uses the correct project and location:

   ```yaml
   defaultProject: near-real-time-elt
   defaultLocation: US
   ```

5. Grant Dataform's service account permissions to read Bronze and create Silver/Gold objects.

Recommended roles for this demo project:

- `BigQuery Data Editor`
- `BigQuery Job User`

## Current Actions

Stories 6 through 9 include:

- A declaration for `bronze.cdc_events`
- An assertion that checks required Bronze fields are not null
- Silver current-state tables for all five source tables
- Duplicate-key assertions for each Silver table
- Gold dimensions for date, customer, and product
- SCD Type 2 history for `gold.dim_customer`
- An assertion that checks exactly one current customer dimension row per customer
- Gold facts for orders, order items, and payments
- Fact assertions for unique grain, non-null surrogate keys, and non-negative measures
- Shared dataset constants in `includes/datasets.js`

The Silver models intentionally keep business logic light. They normalize types and current state only; dimensional modeling belongs in Gold.
