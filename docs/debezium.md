# Debezium CDC Setup

The PostgreSQL connector captures changes from the e-commerce source tables and writes them to Kafka.

## Captured Tables

- `public.customers`
- `public.products`
- `public.orders`
- `public.order_items`
- `public.payments`

## Kafka Topics

The connector uses Debezium's default PostgreSQL topic prefix and a routing transform so topics match the project plan:

- `postgres.customers`
- `postgres.products`
- `postgres.orders`
- `postgres.order_items`
- `postgres.payments`

## Register Connector

From Git Bash or WSL:

```bash
./scripts/register_debezium_connector.sh
```

From PowerShell:

```powershell
.\scripts\register_debezium_connector.ps1
```

The script uses `PUT`, so it is safe to rerun when the config changes.

## Verify Status

```bash
curl http://localhost:8083/connectors/postgres-cdc-connector/status
```

PowerShell:

```powershell
Invoke-RestMethod http://localhost:8083/connectors/postgres-cdc-connector/status | ConvertTo-Json -Depth 20
```

## Verify Kafka Messages

List topics:

```bash
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --list
```

Consume a few customer CDC events:

```bash
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic postgres.customers --from-beginning --max-messages 5
```

Run a demo SQL script to generate new events:

```bash
docker compose exec postgres psql -U postgres -d ecommerce -v ON_ERROR_STOP=1 -f /opt/project/scripts/update_customer_city.sql
```
