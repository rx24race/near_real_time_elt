-- Fixed-point cents keep division exact: DuckDB's / operator returns floating
-- point even for DECIMAL operands. HUGEINT has room for the bounded products.
-- Adding half a denominator before integer division implements half-up rounding
-- for our nonnegative amounts, including the 0.05 at 10% boundary (0.045 -> 0.05).
CREATE TABLE accepted AS
WITH cents AS (
    SELECT *,
        cast(quantity_value AS HUGEINT) * cast(price_value * 100 AS HUGEINT) AS gross_cents,
        cast(discount_value * 100 AS HUGEINT) AS discount_basis_points
    FROM classified WHERE len(reasons) = 0
), amounts AS (
    SELECT *, (gross_cents * (10000 - discount_basis_points) + 5000) // 10000 AS net_cents
    FROM cents
)
SELECT source_record_number, order_id, customer_id, date_value AS order_date,
    product_name, category, cast(quantity_value AS BIGINT) AS quantity,
    price_value AS unit_price, discount_value AS discount_pct, country, order_status,
    cast(cast(gross_cents AS DECIMAL(18,0)) * 0.01 AS DECIMAL(18,2)) AS gross_amount,
    cast(cast(net_cents AS DECIMAL(18,0)) * 0.01 AS DECIMAL(18,2)) AS net_amount
FROM amounts
ORDER BY source_record_number;

CREATE VIEW category_totals AS
SELECT category, sum(net_amount) AS net_amount
FROM accepted GROUP BY category ORDER BY category;

CREATE VIEW accepted_preview AS
SELECT * FROM accepted ORDER BY source_record_number LIMIT 10;
