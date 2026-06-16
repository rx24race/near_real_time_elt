-- Demo: create and delete a disposable product to produce a CDC delete event.

INSERT INTO products (
    product_id,
    product_name,
    category,
    unit_price,
    created_at,
    updated_at
)
VALUES (
    9001,
    'Demo Product To Delete',
    'demo',
    1.00,
    now(),
    now()
)
ON CONFLICT (product_id) DO UPDATE SET
    product_name = EXCLUDED.product_name,
    category = EXCLUDED.category,
    unit_price = EXCLUDED.unit_price,
    updated_at = now();

DELETE FROM products
WHERE product_id = 9001;
