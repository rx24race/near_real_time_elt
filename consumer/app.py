import json
import logging
import os
import signal
import time
from datetime import datetime, timezone
from typing import Any

from google.cloud import bigquery
from kafka import KafkaConsumer
from kafka.errors import KafkaError, NoBrokersAvailable


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("python-bq-consumer")

running = True

DEFAULT_TOPICS = [
    "postgres.customers",
    "postgres.products",
    "postgres.orders",
    "postgres.order_items",
    "postgres.payments",
]


def handle_shutdown(signum, frame):
    """Mark the consumer loop for graceful shutdown when the container stops."""
    global running
    logger.info("event=shutdown_signal signal=%s", signum)
    running = False


def env_int(name: str, default: int) -> int:
    """Read an integer environment variable with a safe fallback."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning("event=invalid_int_env name=%s value=%s default=%s", name, value, default)
        return default


def env_float(name: str, default: float) -> float:
    """Read a float environment variable with a safe fallback."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        logger.warning("event=invalid_float_env name=%s value=%s default=%s", name, value, default)
        return default


def utc_now() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def timestamp_ms_to_iso(timestamp_ms: Any) -> str | None:
    """Convert a Debezium millisecond timestamp into an ISO-8601 string."""
    if timestamp_ms is None:
        return None
    try:
        return datetime.fromtimestamp(int(timestamp_ms) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        logger.warning("event=invalid_event_timestamp timestamp_ms=%s", timestamp_ms)
        return None


def decode_json_message(raw_value: bytes | None) -> dict[str, Any] | None:
    """Decode a Kafka message value from UTF-8 JSON into a Python dictionary."""
    if raw_value is None:
        return None
    try:
        return json.loads(raw_value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.error("event=invalid_json_message error=%s", exc)
        return None


def source_table_from_event(event: dict[str, Any], topic: str) -> str:
    """Resolve the source table from Debezium metadata, falling back to the topic name."""
    source = event.get("source") or {}
    if source.get("table"):
        return source["table"]
    return topic.rsplit(".", 1)[-1]


def to_bigquery_json(value: Any) -> str | None:
    """Serialize a Python value as stable JSON for storage in BigQuery."""
    if value is None:
        return None
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def debezium_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Return the Debezium payload whether the event is wrapped or already flattened."""
    payload = event.get("payload")
    if isinstance(payload, dict):
        return payload
    return event


def build_bronze_row(message) -> dict[str, Any] | None:
    """Transform one Kafka CDC message into the append-only Bronze table shape."""
    event = decode_json_message(message.value)
    if event is None:
        return None

    # Debezium emits source metadata and before/after records in the envelope.
    # Bronze keeps those fields raw so Silver can handle all business parsing later.
    payload = debezium_payload(event)
    source = payload.get("source") or {}
    event_ts = timestamp_ms_to_iso(payload.get("ts_ms") or source.get("ts_ms"))

    return {
        "source_table": source_table_from_event(payload, message.topic),
        "op": payload.get("op", "unknown"),
        "event_ts": event_ts,
        "kafka_topic": message.topic,
        "kafka_partition": message.partition,
        "kafka_offset": message.offset,
        "before_json": to_bigquery_json(payload.get("before")),
        "after_json": to_bigquery_json(payload.get("after")),
        "raw_event_json": to_bigquery_json(event),
        "ingested_at": utc_now(),
    }


class BigQueryBronzeWriter:
    def __init__(
        self,
        project_id: str,
        dataset: str,
        table: str,
        max_retries: int,
        retry_backoff_seconds: float,
    ):
        """Create a BigQuery writer for the configured Bronze table."""
        self.client = bigquery.Client(project=project_id)
        self.table_id = f"{project_id}.{dataset}.{table}"
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    def insert_rows(self, rows: list[dict[str, Any]]) -> None:
        """Insert a batch of Bronze rows into BigQuery with retries."""
        if not rows:
            return

        # Kafka coordinates make deterministic insert ids. BigQuery uses them
        # for best-effort de-duplication if the consumer retries a batch.
        row_ids = [
            f"{row['kafka_topic']}:{row['kafka_partition']}:{row['kafka_offset']}"
            for row in rows
        ]

        for attempt in range(1, self.max_retries + 1):
            errors = self.client.insert_rows_json(
                self.table_id,
                rows,
                row_ids=row_ids,
            )
            if not errors:
                logger.info(
                    "event=bigquery_insert_success table=%s row_count=%s",
                    self.table_id,
                    len(rows),
                )
                return

            logger.error(
                "event=bigquery_insert_error table=%s attempt=%s max_retries=%s errors=%s",
                self.table_id,
                attempt,
                self.max_retries,
                errors,
            )
            if attempt < self.max_retries:
                time.sleep(self.retry_backoff_seconds * attempt)

        raise RuntimeError(f"BigQuery insert failed after {self.max_retries} attempts")


def create_consumer(topics: list[str]) -> KafkaConsumer:
    """Create a Kafka consumer subscribed to the configured Debezium topics."""
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    group_id = os.getenv("KAFKA_CONSUMER_GROUP", "cdc-bq-bronze-loader")
    auto_offset_reset = os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest")

    logger.info(
        "event=kafka_consumer_start bootstrap_servers=%s group_id=%s topics=%s auto_offset_reset=%s",
        bootstrap_servers,
        group_id,
        ",".join(topics),
        auto_offset_reset,
    )

    return KafkaConsumer(
        *topics,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        auto_offset_reset=auto_offset_reset,
        # Commit offsets only after BigQuery accepts the rows to avoid losing
        # CDC events during a transient warehouse or network failure.
        enable_auto_commit=False,
        value_deserializer=None,
        consumer_timeout_ms=1000,
    )


def validate_config(project_id: str, dataset: str, table: str) -> None:
    """Fail fast when required BigQuery configuration is missing or placeholder."""
    if not project_id or project_id == "your-gcp-project-id":
        raise ValueError("Set GCP_PROJECT_ID to your real GCP project id.")
    if not dataset:
        raise ValueError("BIGQUERY_BRONZE_DATASET cannot be empty.")
    if not table:
        raise ValueError("BIGQUERY_BRONZE_TABLE cannot be empty.")


def configure_google_credentials() -> None:
    """Ensure Google client libraries can find the mounted service account key."""
    configured_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    default_path = "/opt/app/credentials/service_account.json"

    if configured_path and os.path.exists(configured_path):
        return

    if os.path.exists(default_path):
        # The Docker Compose mount uses this default path; setting the env var
        # here makes local container startup less fragile.
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = default_path
        logger.warning(
            "event=credentials_path_fallback configured_path=%s fallback_path=%s",
            configured_path,
            default_path,
        )


def main():
    """Run the CDC consumer loop from Kafka polling through BigQuery offset commits."""
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    topics = [
        topic.strip()
        for topic in os.getenv("KAFKA_TOPICS", ",".join(DEFAULT_TOPICS)).split(",")
        if topic.strip()
    ]
    project_id = os.getenv("GCP_PROJECT_ID", "your-gcp-project-id")
    dataset = os.getenv("BIGQUERY_BRONZE_DATASET", "bronze")
    table = os.getenv("BIGQUERY_BRONZE_TABLE", "cdc_events")
    poll_timeout_ms = env_int("KAFKA_POLL_TIMEOUT_MS", 5000)
    max_poll_records = env_int("KAFKA_MAX_POLL_RECORDS", 100)
    max_retries = env_int("BIGQUERY_MAX_RETRIES", 3)
    retry_backoff_seconds = env_float("BIGQUERY_RETRY_BACKOFF_SECONDS", 5.0)

    validate_config(project_id, dataset, table)
    configure_google_credentials()

    writer = BigQueryBronzeWriter(
        project_id=project_id,
        dataset=dataset,
        table=table,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
    )

    consumer = None
    while running and consumer is None:
        try:
            consumer = create_consumer(topics)
        except NoBrokersAvailable as exc:
            logger.error("event=kafka_unavailable error=%s retry_seconds=10", exc)
            time.sleep(10)

    if consumer is None:
        return

    logger.info("event=consumer_ready target_table=%s.%s.%s", project_id, dataset, table)

    try:
        while running:
            records = consumer.poll(timeout_ms=poll_timeout_ms, max_records=max_poll_records)
            rows = []
            polled_count = 0

            for partition, messages in records.items():
                for message in messages:
                    polled_count += 1
                    row = build_bronze_row(message)
                    if row is None:
                        logger.warning(
                            "event=message_skipped topic=%s partition=%s offset=%s",
                            message.topic,
                            message.partition,
                            message.offset,
                        )
                        continue
                    rows.append(row)

            if polled_count == 0:
                logger.info("event=consumer_heartbeat topics=%s", ",".join(topics))
                continue

            if rows:
                writer.insert_rows(rows)
            # Offsets are committed after the BigQuery write. This gives the
            # consumer at-least-once delivery with BigQuery de-duplication.
            consumer.commit()
            logger.info(
                "event=kafka_offsets_committed polled_count=%s inserted_count=%s",
                polled_count,
                len(rows),
            )

    except KafkaError as exc:
        logger.exception("event=kafka_error error=%s", exc)
        raise
    finally:
        logger.info("event=consumer_stopping")
        consumer.close()
        logger.info("event=consumer_stopped")


if __name__ == "__main__":
    main()
