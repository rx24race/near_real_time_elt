"""Thin orchestration around readable DuckDB SQL stages."""

import csv
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import duckdb

from csv_etl import HEADERS


PACKAGE = Path(__file__).resolve().parent
CLEANED_HEADERS = HEADERS + ("gross_amount", "net_amount")
REJECTED_HEADERS = ("source_record_number",) + HEADERS + ("rejection_reasons",)
ARTIFACTS = ("cleaned.csv", "rejected.csv", "dashboard.html")
logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    source: str
    run_id: str = field(default_factory=lambda: new_run_id())
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ended_at: str = ""
    duration_seconds: float = 0.0
    status: str = "Failed"
    error: str | None = None
    artifact_dir: Path | None = None
    stages: dict = field(default_factory=lambda: dict.fromkeys(("extract", "validate", "transform", "load"), "not run"))
    metrics: dict = field(default_factory=lambda: {
        "rows_read": None, "rows_accepted": None, "rows_written": 0,
        "rows_rejected": None, "duplicates_removed": None, "corrected_records": None,
    })
    issues: list | None = None
    categories: list | None = None
    accepted_preview: list | None = None
    rejected_preview: list | None = None

    def finish(self, started: float) -> None:
        self.ended_at = datetime.now(timezone.utc).isoformat()
        self.duration_seconds = perf_counter() - started


def connect() -> duckdb.DuckDBPyConnection:
    """One ephemeral database per attempt; sequential reads preserve source order."""
    connection = duckdb.connect(":memory:")
    connection.execute("SET threads = 1")
    connection.execute("SET preserve_insertion_order = true")
    return connection


def preflight(source: Path) -> int:
    """Count logical records, rejecting structural problems before SQL ingestion."""
    with source.open(encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        if tuple(next(reader, ())) != HEADERS:
            raise ValueError("Input headers must exactly match the documented 10 columns and order.")
        count = 0
        for count, row in enumerate(reader, start=1):
            if len(row) != len(HEADERS):
                raise ValueError(f"Source record {count}: expected 10 fields, found {len(row)}.")
    return count


def load_raw(connection: duckdb.DuckDBPyConnection, source: Path) -> int:
    count = preflight(source)
    # Identifiers/types are application-owned; only the path is provided by the user.
    columns = ", ".join(f"'{name}': 'VARCHAR'" for name in HEADERS)
    not_null = ", ".join(f"'{name}'" for name in HEADERS)
    connection.execute(
        "CREATE TABLE raw AS SELECT row_number() OVER () AS source_record_number, * "
        "FROM read_csv(?, header=true, auto_detect=false, all_varchar=true, "
        f"columns={{{columns}}}, delim=',', quote='\"', escape='\"', "
        f"force_not_null=[{not_null}], parallel=false, strict_mode=true, ignore_errors=false)",
        [str(source.resolve())],
    )
    actual = connection.execute("SELECT count(*) FROM raw").fetchone()[0]
    if actual != count:
        raise ValueError(f"CSV parser record-count mismatch: preflight={count}, DuckDB={actual}.")
    return count


def execute_sql(connection: duckdb.DuckDBPyConnection, filename: str) -> None:
    connection.execute((PACKAGE / "sql" / filename).read_text(encoding="utf-8"))


def records(connection: duckdb.DuckDBPyConnection, query: str) -> list[dict]:
    cursor = connection.execute(query)
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def classification_summary(connection: duckdb.DuckDBPyConnection) -> dict:
    metrics = records(connection, "SELECT * FROM totals")[0]
    if metrics["rows_read"] != sum(metrics[key] for key in ("rows_accepted", "rows_rejected", "duplicates_removed")):
        raise ValueError("Row-accounting invariant failed; refusing to export inconsistent results.")
    return {
        "metrics": metrics,
        "issues": records(connection, "SELECT * FROM issue_counts ORDER BY reason"),
        "rejected_preview": records(connection, "SELECT * FROM rejected_preview ORDER BY source_record_number"),
    }


def transformed_summary(connection: duckdb.DuckDBPyConnection) -> dict:
    return {
        "categories": records(connection, "SELECT * FROM category_totals ORDER BY category"),
        "accepted_preview": records(connection, "SELECT * FROM accepted_preview ORDER BY source_record_number"),
    }


def sql_literal(value: str) -> str:
    """Quote a data value, never an identifier, for DuckDB COPY destinations."""
    return "'" + value.replace("'", "''") + "'"


def export_csvs(connection: duckdb.DuckDBPyConnection, directory: Path) -> None:
    for filename, relation, columns in (
        ("cleaned.csv", "accepted", CLEANED_HEADERS),
        ("rejected.csv", "rejected", REJECTED_HEADERS),
    ):
        projection = ", ".join(columns)
        destination = sql_literal(str(directory / filename))
        # Fully ordered, fixed schema and LF newlines make repeated data exports
        # byte-identical. Directory creation/publication belongs to the runner.
        connection.execute(
            f"COPY (SELECT {projection} FROM {relation} ORDER BY source_record_number) "
            f"TO {destination} (FORMAT CSV, HEADER true, FORCE_QUOTE *, "
            "DATEFORMAT '%Y-%m-%d', NEW_LINE '\n')"
        )


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:12]


def check_source_safety(source: Path, paths: list[Path]) -> None:
    for path in paths:
        if source.resolve() == path.resolve() or (
            source.exists() and path.exists() and source.samefile(path)
        ):
            raise ValueError(f"Output would replace source or an alias: {path}")


def prepare_output(source: Path, parent: Path, run_id: str) -> tuple[Path, Path]:
    parent = parent.resolve()
    staging, final = parent / f".{run_id}.tmp", parent / run_id
    check_source_safety(source, [directory / name for directory in (staging, final) for name in ARTIFACTS])
    if final.exists() or final.is_symlink():
        raise FileExistsError(f"Run destination already exists: {final}")
    parent.mkdir(parents=True, exist_ok=True)
    # Never reuse a staging directory: only files in a directory created by this
    # attempt can subsequently be cleaned up.
    staging.mkdir(exist_ok=False)
    return staging, final


def publish(staging: Path, final: Path) -> None:
    if final.exists() or final.is_symlink():
        raise FileExistsError(f"Run destination already exists: {final}")
    staging.rename(final)


def cleanup_staging(staging: Path) -> None:
    """Bounded cleanup, never recursively delete a user-selected directory."""
    for name in ARTIFACTS:
        path = staging / name
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Cannot remove this run's staged file %s: %s", path, exc)
    try:
        staging.rmdir()
    except OSError as exc:
        logger.warning("Staging directory left unpublished at %s: %s", staging, exc)


def verify_exports(directory: Path, metrics: dict) -> None:
    for name, headers, expected in (
        ("cleaned.csv", CLEANED_HEADERS, metrics["rows_accepted"]),
        ("rejected.csv", REJECTED_HEADERS, metrics["rows_rejected"]),
    ):
        with (directory / name).open(encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            if tuple(next(reader, ())) != headers or sum(1 for _ in reader) != expected:
                raise ValueError(f"Staged export does not match classified results: {name}")


def run(source: Path, output_parent: Path, renderer=None) -> RunResult:
    """Publish a complete success, or a report-only handled failure. Never overwrite."""
    if renderer is None:
        from csv_etl.report import render_report
        renderer = render_report
    source, output_parent = Path(source).resolve(), Path(output_parent).resolve()
    result, started = RunResult(source=source.name), perf_counter()
    connection = None
    staging = None
    current = "load"
    logger.info("Run %s source=%s output_parent=%s", result.run_id, source.name, output_parent)
    try:
        staging, final = prepare_output(source, output_parent, result.run_id)
        current = "extract"
        connection = connect()
        result.metrics["rows_read"] = load_raw(connection, source)
        result.stages[current] = "complete"
        logger.info("Run %s extract complete rows=%s", result.run_id, result.metrics["rows_read"])

        current = "validate"
        for filename in ("normalize.sql", "classify.sql", "metrics.sql"):
            execute_sql(connection, filename)
        summary = classification_summary(connection)
        result.metrics.update(summary["metrics"])
        result.issues, result.rejected_preview = summary["issues"], summary["rejected_preview"]
        if result.metrics["rows_accepted"] == 0:
            raise ValueError("No accepted records: input is empty or every retained record is invalid.")
        result.stages[current] = "complete"
        logger.info("Run %s validate complete metrics=%s", result.run_id, result.metrics)

        current = "transform"
        execute_sql(connection, "transform.sql")
        summary = transformed_summary(connection)
        result.categories, result.accepted_preview = summary["categories"], summary["accepted_preview"]
        result.stages[current] = "complete"
        logger.info("Run %s transform complete", result.run_id)

        current = "load"
        export_csvs(connection, staging)
        verify_exports(staging, result.metrics)
        result.status = "Success with warnings" if any(
            result.metrics[key] for key in ("corrected_records", "duplicates_removed", "rows_rejected")
        ) else "Success"
        # These values become visible only if the complete directory is published.
        result.metrics["rows_written"] = result.metrics["rows_accepted"]
        result.stages[current] = "complete"
        result.finish(started)
        (staging / "dashboard.html").write_text(renderer(result), encoding="utf-8")
        publish(staging, final)
        staging = None
        result.artifact_dir = final
        logger.info("Run %s %s; dashboard: %s", result.run_id, result.status, final / "dashboard.html")
    except Exception as exc:
        # Data, SQL, renderer, and filesystem errors are all failed attempts, not
        # a reason to publish a partially successful set of artifacts.
        result.status, result.error = "Failed", str(exc)
        result.stages[current] = "failed"
        result.metrics["rows_written"] = 0
        result.finish(started)
        logger.error("Run %s failed at %s (destination %s): %s", result.run_id, current, output_parent, exc)
        if staging is not None:
            cleanup_staging(staging)
            staging = None
        try:
            staging, final = prepare_output(source, output_parent, result.run_id)
            (staging / "dashboard.html").write_text(renderer(result), encoding="utf-8")
            publish(staging, final)
            staging = None
            result.artifact_dir = final
            logger.info("Run %s failure dashboard: %s", result.run_id, final / "dashboard.html")
        except Exception as report_error:
            logger.error("Run %s: could not publish failure report to %s: %s", result.run_id, output_parent, report_error)
            if staging is not None:
                cleanup_staging(staging)
    finally:
        if connection is not None:
            connection.close()
    return result
