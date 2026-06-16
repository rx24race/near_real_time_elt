-- Demo: update a customer's membership tier for SCD Type 2 demonstrations later.

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
    'standard',
    now(),
    now()
)
ON CONFLICT (customer_id) DO NOTHING;

UPDATE customers
SET
    membership_tier = 'gold',
    updated_at = now()
WHERE customer_id = 1001;
