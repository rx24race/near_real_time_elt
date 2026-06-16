-- Demo: insert a new customer.

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
    'Chicago',
    'standard',
    now(),
    now()
)
ON CONFLICT (customer_id) DO UPDATE SET
    first_name = EXCLUDED.first_name,
    last_name = EXCLUDED.last_name,
    email = EXCLUDED.email,
    city = EXCLUDED.city,
    membership_tier = EXCLUDED.membership_tier,
    updated_at = now();
