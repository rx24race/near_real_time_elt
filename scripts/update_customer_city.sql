-- Demo: update a customer's city to produce a CDC update event.

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
ON CONFLICT (customer_id) DO NOTHING;

UPDATE customers
SET
    city = 'New York',
    updated_at = now()
WHERE customer_id = 1001;
