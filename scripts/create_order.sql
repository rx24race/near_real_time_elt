-- Demo: create or update an order header.

INSERT INTO customers (
    customer_id,
    first_name,
    last_name,
    email,
    city,
    membership_tier,
    created_at,
    updated_at
)
VALUES (
    1001,
    'Jordan',
    'Lee',
    'jordan.lee.demo@example.com',
    'New York',
    'gold',
    now(),
    now()
)
ON CONFLICT (customer_id) DO NOTHING;

INSERT INTO orders (
    order_id,
    customer_id,
    order_status,
    order_total,
    created_at,
    updated_at
)
VALUES (
    2001,
    1001,
    'created',
    104.49,
    now(),
    now()
)
ON CONFLICT (order_id) DO UPDATE SET
    customer_id = EXCLUDED.customer_id,
    order_status = EXCLUDED.order_status,
    order_total = EXCLUDED.order_total,
    updated_at = now();
