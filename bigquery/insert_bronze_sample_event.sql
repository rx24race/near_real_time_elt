-- Optional smoke test for Story 4.
-- Replace the project id before running, or run through bq with a configured default project.

INSERT INTO `bronze.cdc_events`
(
  source_table,
  op,
  event_ts,
  kafka_topic,
  kafka_partition,
  kafka_offset,
  before_json,
  after_json,
  raw_event_json,
  ingested_at
)
VALUES
(
  'customers',
  'c',
  CURRENT_TIMESTAMP(),
  'postgres.customers',
  0,
  0,
  NULL,
  JSON '{"customer_id": 9999, "email": "bronze_smoke_test@example.com"}',
  JSON '{"op": "c", "after": {"customer_id": 9999, "email": "bronze_smoke_test@example.com"}}',
  CURRENT_TIMESTAMP()
);
