-- Cast safely, but also validate syntax before trusting the cast: decimal casts
-- can round excess precision, so a successful cast alone is not sufficient.
CREATE TABLE classified AS
WITH typed AS (
    SELECT *,
        try_cast(order_date AS DATE) AS date_value,
        try_cast(quantity AS DECIMAL(38,0)) AS quantity_value,
        try_cast(unit_price AS DECIMAL(18,2)) AS price_value,
        try_cast(discount_pct AS DECIMAL(18,2)) AS discount_value
    FROM ranked WHERE duplicate_rank = 1
)
SELECT *, list_filter([
    CASE WHEN coalesce(order_id, '') = '' THEN 'order_id_required' END,
    CASE WHEN coalesce(customer_id, '') = '' THEN 'customer_id_required' END,
    CASE WHEN NOT coalesce(regexp_full_match(order_date, '[0-9]{4}-[0-9]{2}-[0-9]{2}')
        AND date_value BETWEEN DATE '0001-01-01' AND DATE '9999-12-31', false) THEN 'order_date_invalid' END,
    CASE WHEN coalesce(product_name, '') = '' THEN 'product_name_required' END,
    CASE WHEN NOT coalesce(regexp_full_match(quantity, '[+]?[0-9]+(\.0+)?')
        AND quantity_value BETWEEN 1 AND 1000000, false) THEN 'quantity_invalid' END,
    CASE WHEN NOT coalesce(regexp_full_match(unit_price, '[+-]?[0-9]+(\.[0-9]{1,2}0*)?')
        AND price_value BETWEEN 0 AND 999999999.99, false) THEN 'unit_price_invalid' END,
    CASE WHEN NOT coalesce(regexp_full_match(discount_pct, '[+-]?[0-9]+(\.[0-9]{1,2}0*)?')
        AND discount_value BETWEEN 0 AND 100, false) THEN 'discount_pct_invalid' END,
    CASE WHEN coalesce(country, '') = '' THEN 'country_required' END,
    CASE WHEN NOT coalesce(order_status IN ('new', 'paid', 'shipped', 'completed', 'cancelled'), false)
        THEN 'order_status_invalid' END
], reason -> reason IS NOT NULL) AS reasons
FROM typed;

CREATE VIEW rejected AS
SELECT r.*, array_to_string(c.reasons, ';') AS rejection_reasons
FROM classified c JOIN raw r USING (source_record_number)
WHERE len(c.reasons) > 0;
