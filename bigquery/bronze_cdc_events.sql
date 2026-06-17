-- Creates the append-only Bronze landing table for raw Debezium CDC events.
-- Run this after setting the GCP project with:
--   bq config set project_id YOUR_GCP_PROJECT_ID

CREATE SCHEMA IF NOT EXISTS `bronze`
OPTIONS(location = 'US');

CREATE TABLE IF NOT EXISTS `bronze.cdc_events`
(
  source_table STRING NOT NULL,
  op STRING NOT NULL,
  event_ts TIMESTAMP,
  kafka_topic STRING NOT NULL,
  kafka_partition INT64 NOT NULL,
  kafka_offset INT64 NOT NULL,
  before_json JSON,
  after_json JSON,
  raw_event_json JSON NOT NULL,
  ingested_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(ingested_at)
CLUSTER BY source_table, op
OPTIONS (
  description = 'Append-only Bronze landing table for raw Debezium CDC events from Kafka.'
);
