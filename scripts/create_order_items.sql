-- Demo: create order line items.

\i /opt/project/scripts/create_order.sql

INSERT INTO order_items (
    order_item_id,
    order_id,
    product_id,
    quantity,
    unit_price,
    created_at,
    updated_at
)
VALUES
    (3001, 2001, 1, 1, 79.99, now(), now()),
    (3002, 2001, 2, 1, 24.50, now(), now())
ON CONFLICT (order_item_id) DO UPDATE SET
    order_id = EXCLUDED.order_id,
    product_id = EXCLUDED.product_id,
    quantity = EXCLUDED.quantity,
    unit_price = EXCLUDED.unit_price,
    updated_at = now();
