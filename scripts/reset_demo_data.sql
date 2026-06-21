-- Demo helper: remove rows created by the Story 12 walkthrough.
-- Run this before a fresh demo if customer 1001/order 2001 already exists.

DELETE FROM payments
WHERE payment_id = 4001;

DELETE FROM order_items
WHERE order_item_id IN (3001, 3002);

DELETE FROM orders
WHERE order_id = 2001;

DELETE FROM customers
WHERE customer_id = 1001;

DELETE FROM products
WHERE product_id = 9001;
