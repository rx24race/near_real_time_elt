import logging
import os
import signal
import time


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("python-bq-consumer")

running = True


def handle_shutdown(signum, frame):
    global running
    logger.info("Received shutdown signal %s; stopping consumer skeleton.", signum)
    running = False


def main():
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    project_id = os.getenv("GCP_PROJECT_ID", "your-gcp-project-id")
    bronze_dataset = os.getenv("BIGQUERY_BRONZE_DATASET", "bronze")

    logger.info(
        "Consumer skeleton started. bootstrap_servers=%s project_id=%s bronze_dataset=%s",
        bootstrap_servers,
        project_id,
        bronze_dataset,
    )

    # Story 5 will replace this heartbeat loop with Kafka polling and BigQuery inserts.
    while running:
        logger.info("Consumer skeleton heartbeat.")
        time.sleep(30)

    logger.info("Consumer skeleton stopped.")


if __name__ == "__main__":
    main()
