-- Preserve raw separately so rejected exports can show original values.
-- Unicode separators plus ASCII/control whitespace; do not trim only plain spaces.
CREATE MACRO clean_text(value) AS regexp_replace(
    value, '^[\s\p{Z}\x{0085}\x{000B}]+|[\s\p{Z}\x{0085}\x{000B}]+$', '', 'g'
);

CREATE TABLE normalized AS
WITH cleaned AS (
    SELECT source_record_number,
        clean_text(order_id) AS order_id,
        clean_text(customer_id) AS customer_id,
        clean_text(order_date) AS order_date,
        clean_text(product_name) AS product_name,
        coalesce(nullif(lower(clean_text(category)), ''), 'Unknown') AS category,
        clean_text(quantity) AS quantity,
        clean_text(unit_price) AS unit_price,
        clean_text(discount_pct) AS discount_pct,
        upper(clean_text(country)) AS country,
        lower(clean_text(order_status)) AS order_status
    FROM raw
)
SELECT c.*,
    (c.order_id, c.customer_id, c.order_date, c.product_name, c.category,
     c.quantity, c.unit_price, c.discount_pct, c.country, c.order_status)
    IS DISTINCT FROM
    (r.order_id, r.customer_id, r.order_date, r.product_name, r.category,
     r.quantity, r.unit_price, r.discount_pct, r.country, r.order_status) AS corrected
FROM cleaned c JOIN raw r USING (source_record_number);

-- An order can contain several lines. Only all-field text equality is a duplicate.
-- Rank before validation so a duplicate invalid record is counted exactly once.
CREATE TABLE ranked AS
SELECT *, row_number() OVER (
    PARTITION BY order_id, customer_id, order_date, product_name, category,
                 quantity, unit_price, discount_pct, country, order_status
    ORDER BY source_record_number
) AS duplicate_rank
FROM normalized;
