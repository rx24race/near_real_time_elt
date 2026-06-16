-- Deterministic seed data for local demos and tests.

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
VALUES
    (1, 'Ava', 'Chen', 'ava.chen@example.com', 'Taipei', 'gold', '2026-01-05 09:00:00+00', '2026-01-05 09:00:00+00'),
    (2, 'Noah', 'Patel', 'noah.patel@example.com', 'Seattle', 'standard', '2026-01-06 10:30:00+00', '2026-01-06 10:30:00+00'),
    (3, 'Mia', 'Garcia', 'mia.garcia@example.com', 'Austin', 'silver', '2026-01-07 14:45:00+00', '2026-01-07 14:45:00+00')
ON CONFLICT (customer_id) DO UPDATE SET
    first_name = EXCLUDED.first_name,
    last_name = EXCLUDED.last_name,
    email = EXCLUDED.email,
    city = EXCLUDED.city,
    membership_tier = EXCLUDED.membership_tier,
    updated_at = EXCLUDED.updated_at;

INSERT INTO products (
    product_id,
    product_name,
    category,
    unit_price,
    created_at,
    updated_at
)
VALUES
    (1, 'Everyday Backpack', 'bags', 79.99, '2026-01-05 09:00:00+00', '2026-01-05 09:00:00+00'),
    (2, 'Insulated Travel Mug', 'drinkware', 24.50, '2026-01-05 09:10:00+00', '2026-01-05 09:10:00+00'),
    (3, 'Noise-Canceling Headphones', 'electronics', 149.00, '2026-01-05 09:20:00+00', '2026-01-05 09:20:00+00')
ON CONFLICT (product_id) DO UPDATE SET
    product_name = EXCLUDED.product_name,
    category = EXCLUDED.category,
    unit_price = EXCLUDED.unit_price,
    updated_at = EXCLUDED.updated_at;

INSERT INTO orders (
    order_id,
    customer_id,
    order_status,
    order_total,
    created_at,
    updated_at
)
VALUES
    (1, 1, 'paid', 104.49, '2026-01-08 11:00:00+00', '2026-01-08 11:05:00+00'),
    (2, 2, 'paid', 149.00, '2026-01-09 12:00:00+00', '2026-01-09 12:03:00+00')
ON CONFLICT (order_id) DO UPDATE SET
    customer_id = EXCLUDED.customer_id,
    order_status = EXCLUDED.order_status,
    order_total = EXCLUDED.order_total,
    updated_at = EXCLUDED.updated_at;

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
    (1, 1, 1, 1, 79.99, '2026-01-08 11:00:00+00', '2026-01-08 11:00:00+00'),
    (2, 1, 2, 1, 24.50, '2026-01-08 11:00:00+00', '2026-01-08 11:00:00+00'),
    (3, 2, 3, 1, 149.00, '2026-01-09 12:00:00+00', '2026-01-09 12:00:00+00')
ON CONFLICT (order_item_id) DO UPDATE SET
    order_id = EXCLUDED.order_id,
    product_id = EXCLUDED.product_id,
    quantity = EXCLUDED.quantity,
    unit_price = EXCLUDED.unit_price,
    updated_at = EXCLUDED.updated_at;

INSERT INTO payments (
    payment_id,
    order_id,
    payment_method,
    payment_status,
    amount,
    created_at,
    updated_at
)
VALUES
    (1, 1, 'credit_card', 'captured', 104.49, '2026-01-08 11:05:00+00', '2026-01-08 11:05:00+00'),
    (2, 2, 'paypal', 'captured', 149.00, '2026-01-09 12:03:00+00', '2026-01-09 12:03:00+00')
ON CONFLICT (payment_id) DO UPDATE SET
    order_id = EXCLUDED.order_id,
    payment_method = EXCLUDED.payment_method,
    payment_status = EXCLUDED.payment_status,
    amount = EXCLUDED.amount,
    updated_at = EXCLUDED.updated_at;
