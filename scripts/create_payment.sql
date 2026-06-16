-- Demo: create a payment for the demo order.

\i /opt/project/scripts/create_order_items.sql

UPDATE orders
SET
    order_status = 'paid',
    updated_at = now()
WHERE order_id = 2001;

INSERT INTO payments (
    payment_id,
    order_id,
    payment_method,
    payment_status,
    amount,
    created_at,
    updated_at
)
VALUES (
    4001,
    2001,
    'credit_card',
    'captured',
    104.49,
    now(),
    now()
)
ON CONFLICT (payment_id) DO UPDATE SET
    order_id = EXCLUDED.order_id,
    payment_method = EXCLUDED.payment_method,
    payment_status = EXCLUDED.payment_status,
    amount = EXCLUDED.amount,
    updated_at = now();
