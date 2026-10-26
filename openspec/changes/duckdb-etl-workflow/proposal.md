# Proposal

## Why

The repository demonstrates a distributed CDC pipeline but has no small, offline batch exercise for learning SQL-based ETL and reviewing its results visually. A standalone CSV workflow will provide an approachable DuckDB exercise and a polished, verifiable demonstration of data cleaning and run status without operating the streaming stack.

## What Changes

- Add an isolated `csv_etl/` mini-project using embedded DuckDB and readable SQL files, with Python limited to orchestration, logging, and HTML rendering; do not use pandas.
- Include a synthetic e-commerce order-line CSV with 60 data rows and exactly 10 input columns, deliberately containing fixable values, duplicates, and invalid records.
- Validate input structure, normalize values, remove exact normalized duplicates, reject invalid rows with reasons, and derive gross and net amounts.
- Produce deterministic cleaned CSV data, a rejected-row CSV, and a post-run, self-contained offline HTML dashboard with actual metrics, stage outcomes, quality issues, previews, and category sales summaries.
- Document local setup, execution, failure behavior, and tests without starting Docker services or requiring cloud credentials.
- Preserve all existing ingestion and transformation behavior. Live progress, a web server, upload UI, scheduling, persistent databases, and CDC integration are out of scope.

## Capabilities

### New Capabilities

- `csv-etl`: A local, repeatable DuckDB SQL workflow for validating, transforming, classifying, and exporting order-line CSV data.
- `etl-run-report`: A self-contained offline HTML report that accurately communicates a completed ETL attempt, including failures and data-quality warnings.

### Modified Capabilities

None. There are no existing OpenSpec capability specifications, and the CDC pipeline's requirements are unchanged.

## Impact

- Proposed additions: `csv_etl/` Python runner, SQL stages, fixture, report template, tests, standalone dependency file, and usage documentation.
- Limited integration edits during implementation: a root README link and `.gitignore` entries for generated mini-project outputs. Clarify the standalone, non-service exercise exception to the Docker runtime guideline in `AGENTS.md`.
- DuckDB is the only proposed new third-party Python dependency; use the standard library for the CLI, reporting support, and tests. Keep it separate from `consumer/requirements.txt` and the Airflow image.
- No changes to `docker-compose.yml`, Kafka topics, Debezium, BigQuery tables, Dataform models, Airflow DAGs, credentials, or existing source tables.
- Based on the reviewed CSV Studio HTML planning artifact and the subsequently confirmed offline-report preference. The planning artifact's illustrative metrics are not fixture expectations; the delivered report must compute its own values and work without its CDN dependencies or Lavish.
