-- These views depend only on classification, so even an all-invalid run can
-- report truthful counts without pretending transformation completed.
CREATE VIEW totals AS SELECT
    (SELECT count(*) FROM raw) AS rows_read,
    (SELECT count(*) FROM classified WHERE len(reasons) = 0) AS rows_accepted,
    (SELECT count(*) FROM rejected) AS rows_rejected,
    (SELECT count(*) FROM ranked WHERE duplicate_rank > 1) AS duplicates_removed,
    (SELECT count(*) FROM normalized WHERE corrected) AS corrected_records;

CREATE VIEW issue_counts AS
SELECT reason, count(*) AS row_count
FROM (SELECT unnest(reasons) AS reason FROM classified)
GROUP BY reason ORDER BY reason;

CREATE VIEW rejected_preview AS
SELECT * FROM rejected ORDER BY source_record_number LIMIT 10;
