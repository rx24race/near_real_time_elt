import json
import logging
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.exceptions import AirflowException
from airflow.operators.python import PythonOperator
from airflow.operators.python import get_current_context
from airflow.utils.email import send_email
from google.cloud import bigquery


PROJECT_ID = os.getenv("GCP_PROJECT_ID", "near-real-time-elt")
BIGQUERY_LOCATION = os.getenv("BIGQUERY_LOCATION", "US")
BRONZE_DATASET = os.getenv("BIGQUERY_BRONZE_DATASET", "bronze")
BRONZE_TABLE = os.getenv("BIGQUERY_BRONZE_TABLE", "cdc_events")
DATAFORM_PROJECT_DIR = Path(os.getenv("DATAFORM_PROJECT_DIR", "/opt/project/dataform"))
DATAFORM_CREDENTIALS_PATH = DATAFORM_PROJECT_DIR / ".df-credentials.json"
SERVICE_ACCOUNT_PATH = Path(
    os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/opt/project/bigquery/service_account.json")
)
ALERT_EMAIL_TO = os.getenv("AIRFLOW_ALERT_EMAIL_TO", "")

logger = logging.getLogger(__name__)


default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}


def bigquery_client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT_ID, location=BIGQUERY_LOCATION)


def bronze_ready() -> None:
    table_id = f"`{PROJECT_ID}.{BRONZE_DATASET}.{BRONZE_TABLE}`"
    query = f"SELECT COUNT(*) AS row_count FROM {table_id}"
    rows = list(bigquery_client().query(query))
    row_count = rows[0]["row_count"]

    logger.info("Bronze readiness check row_count=%s table=%s", row_count, table_id)
    if row_count == 0:
        raise AirflowException(f"Bronze table {table_id} has no CDC events yet.")


def ensure_dataform_credentials() -> None:
    if not SERVICE_ACCOUNT_PATH.exists():
        raise AirflowException(f"Missing service account key: {SERVICE_ACCOUNT_PATH}")

    service_account_json = SERVICE_ACCOUNT_PATH.read_text(encoding="utf-8")
    service_account = json.loads(service_account_json)
    credentials = {
        "projectId": service_account.get("project_id", PROJECT_ID),
        "location": BIGQUERY_LOCATION,
        "credentials": service_account_json,
    }

    DATAFORM_CREDENTIALS_PATH.write_text(
        json.dumps(credentials, indent=2),
        encoding="utf-8",
    )
    logger.info("Prepared Dataform credentials wrapper at %s", DATAFORM_CREDENTIALS_PATH)


def run_command(command: list[str], cwd: Path) -> None:
    logger.info("Running command: %s", " ".join(command))
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    logger.info("Command output:\n%s", completed.stdout)
    if completed.returncode != 0:
        raise AirflowException(
            f"Command failed with exit code {completed.returncode}: {' '.join(command)}"
        )


def run_dataform_silver() -> None:
    ensure_dataform_credentials()
    run_command(
        [
            "dataform",
            "run",
            str(DATAFORM_PROJECT_DIR),
            "--tags",
            "silver",
        ],
        cwd=Path("/opt/project"),
    )


def run_dataform_gold() -> None:
    ensure_dataform_credentials()
    run_command(
        [
            "dataform",
            "run",
            str(DATAFORM_PROJECT_DIR),
            "--tags",
            "gold",
            "--include-deps",
        ],
        cwd=Path("/opt/project"),
    )


def run_dq_checks() -> None:
    logger.info(
        "Data quality is enforced by Dataform assertions during run_dataform_silver "
        "and run_dataform_gold. If an assertion returns rows, Dataform exits non-zero "
        "and the corresponding Airflow task fails."
    )


def email_recipients() -> list[str]:
    return [email.strip() for email in ALERT_EMAIL_TO.split(",") if email.strip()]


def send_dag_email(subject: str, html_content: str) -> None:
    recipients = email_recipients()
    if not recipients:
        logger.info("Skipping email notification because AIRFLOW_ALERT_EMAIL_TO is not set.")
        return

    logger.info("Sending DAG email notification to %s", recipients)
    send_email(to=recipients, subject=subject, html_content=html_content)


def notify_failure(context: dict) -> None:
    task_instance = context.get("task_instance")
    dag_run = context.get("dag_run")
    exception = context.get("exception")

    send_dag_email(
        subject=f"[Airflow] FAILED: {context['dag'].dag_id}",
        html_content=f"""
            <h3>Dataform transformation DAG failed</h3>
            <p><strong>DAG:</strong> {context['dag'].dag_id}</p>
            <p><strong>Task:</strong> {task_instance.task_id if task_instance else "unknown"}</p>
            <p><strong>Run:</strong> {dag_run.run_id if dag_run else "unknown"}</p>
            <p><strong>Project:</strong> {PROJECT_ID}</p>
            <p><strong>Location:</strong> {BIGQUERY_LOCATION}</p>
            <p><strong>Error:</strong> {exception}</p>
        """,
    )


def notify() -> None:
    context = get_current_context()
    dag_run = context.get("dag_run")

    logger.info(
        "Dataform transformation DAG completed successfully for project=%s location=%s",
        PROJECT_ID,
        BIGQUERY_LOCATION,
    )
    send_dag_email(
        subject=f"[Airflow] SUCCESS: {context['dag'].dag_id}",
        html_content=f"""
            <h3>Dataform transformation DAG completed successfully</h3>
            <p><strong>DAG:</strong> {context['dag'].dag_id}</p>
            <p><strong>Run:</strong> {dag_run.run_id if dag_run else "unknown"}</p>
            <p><strong>Project:</strong> {PROJECT_ID}</p>
            <p><strong>Location:</strong> {BIGQUERY_LOCATION}</p>
        """,
    )


with DAG(
    dag_id="dataform_bronze_to_gold",
    description="Orchestrates Dataform Bronze to Silver and Gold transformations only.",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule_interval=None,
    catchup=False,
    max_active_runs=1,
    on_failure_callback=notify_failure,
    tags=["cdc", "dataform", "bigquery"],
) as dag:
    bronze_ready_task = PythonOperator(
        task_id="bronze_ready",
        python_callable=bronze_ready,
    )

    run_dataform_silver_task = PythonOperator(
        task_id="run_dataform_silver",
        python_callable=run_dataform_silver,
    )

    run_dataform_gold_task = PythonOperator(
        task_id="run_dataform_gold",
        python_callable=run_dataform_gold,
    )

    run_dq_checks_task = PythonOperator(
        task_id="run_dq_checks",
        python_callable=run_dq_checks,
    )

    notify_task = PythonOperator(
        task_id="notify",
        python_callable=notify,
    )

    bronze_ready_task >> run_dataform_silver_task >> run_dataform_gold_task >> run_dq_checks_task >> notify_task
