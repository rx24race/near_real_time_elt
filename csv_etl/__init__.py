"""Standalone, SQL-first CSV ETL exercise; independent of the CDC services."""

HEADERS = (
    "order_id", "customer_id", "order_date", "product_name", "category",
    "quantity", "unit_price", "discount_pct", "country", "order_status",
)
