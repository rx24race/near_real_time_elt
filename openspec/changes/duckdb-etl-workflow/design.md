# Design

## Context

See `proposal.md` for motivation and the two delta specs for behavior contracts. The current project has Docker-based CDC services, a small standalone Python consumer, Dataform SQL models, and service-specific dependencies. There is no shared Python package configuration, CSV exercise, frontend design system, or established automated-test suite to extend.

The reviewed HTML plan is `C:\Users\User\.opencode\plan\csv-etl-exploration.html`. It provides a visual reference, not a runtime dependency or a portable source file to link from repository documentation. Later review confirmed an offline post-run report rather than a live application. The HTML's other defaults become reviewable choices in this design.

Design is warranted because this introduces DuckDB, a new output contract, filesystem publication semantics, and safe rendering of user-controlled CSV content.

## Goals / Non-Goals

**Goals:**
- Keep transformations inspectable as SQL, with thin Python control flow.
- Derive exported data, quality metrics, and dashboard aggregates from the same classified relations.
- Make individual bad values recoverable while making structural and filesystem errors explicit.
- Keep repeatability, record traceability, and source protection simple enough to explain in an interview.

**Non-Goals:**
- No persistent DuckDB database, shared runtime service, Docker image, Airflow integration, or data movement into BigQuery.
- No GUI upload, live progress polling, frontend build pipeline, or online chart dependencies.
- No generic configurable ETL framework, currency conversion, cross-file joins, or incremental processing.
- No concurrent modification of input files, crash-recovery transaction manager, or protection against every spreadsheet application's formula interpretation. The dashboard escapes HTML; CSV exports remain data artifacts to open with appropriate spreadsheet import settings.

## Decisions

### 1. Isolate the exercise and its dependency

Proposed structure:

```text
csv_etl/
  __init__.py
  __main__.py
  pipeline.py
  report.py
  requirements.txt
  README.md
  data/orders.csv
  sql/
    normalize.sql
    classify.sql
    transform.sql
    metrics.sql
  templates/dashboard.html
  tests/
    test_pipeline.py
    test_report.py
    test_cli.py
  output/                 generated, ignored
```

Use Python 3.10+ and a tested, pinned DuckDB release in `csv_etl/requirements.txt`. The implementation selects and records the exact supported release after installation and testing; version selection does not change the behavioral contract. Use standard-library `argparse`, `logging`, `html`, `csv`, `unittest`, and filesystem utilities rather than adding a dataframe, template, or chart library.

Document `python -m csv_etl --input csv_etl/data/orders.csv --output-dir csv_etl/output` from the repository root, with equivalent PowerShell and Bash setup examples. Require `--input`; default `--output-dir` to the mini-project's output directory resolved relative to the package, not the caller's arbitrary working directory. A run logs its identifier, stage outcomes, counts, and final artifact location.

**Alternatives:** extending the Kafka consumer would mix batch and streaming dependencies; adding a container would make a tiny exercise harder to run. This standalone command is an explicit non-service exception to the project's Docker guidance; document that narrowly in `AGENTS.md` during implementation, without altering its CDC constraints.

### 2. Load text first and keep business rules in SQL

Use an in-memory DuckDB connection per attempt. Disable parallel CSV reading and preserve insertion order so a sequential source record number can be attached before any filtering. Load all 10 fields as text with explicit CSV settings, never inferred date or numeric types, and no ignore-errors behavior.

Python performs a strict UTF-8 CSV structural preflight with the standard library: exact header/order, no duplicate headers, consistent record widths, and valid quoting. It counts logical records (quoted newlines are not new records). DuckDB then loads the file and attaches the same 1-based logical record ordinal; assert that its raw count matches preflight. SQL handles value normalization, deduplication, validation, calculations, aggregates, and CSV `COPY` export. Python's CSV parser does not perform business transformations.

Use parameterized file reads and safely supported DuckDB export-path handling. If the selected version requires literal paths for `COPY`, use a dedicated SQL-literal quoting helper and test apostrophes and spaces; never interpolate unescaped paths. Treat identifiers and SQL files as application-owned, not user-provided SQL.

**Alternative:** type inference is shorter but can hide wrong input types or abort on a single bad value before rejection classification.

### 3. Classify every source record exactly once

Relations and responsibilities:

```text
raw text + source record ordinal
              |
              v
normalized text + per-record correction flag
              |
              v
duplicate rank across all 10 normalized text fields
              |
     +--------+--------+
     |                 |
     v                 v
duplicate copies   retained records
                       |
                       v
               typed values + reasons
                       |
                +------+------+
                |             |
                v             v
             accepted      rejected
                |
                v
          derived amounts
```

Normalization trims all fields, lowercases category/status, uppercases country, and fills blank category with `Unknown` (including that exact sentinel capitalization). All other cases remain unchanged. Count corrections across original source records, including copies later removed or rejected; count a record once, not once per changed field. Thus corrected counts overlap outcome categories and are not part of the row-accounting sum.

Duplicate identity uses normalized text before type parsing. Numeric strings `1` and `1.0` are not duplicates unless their normalized text is identical. Retain the earliest occurrence, excluding the ordinal and correction flag from duplicate identity. Repeated order IDs can represent different lines.

Use safe casts, explicit validity checks, and a stable list of all field-level rejection reasons. SQL NULL must never make a predicate accidentally pass: missing required data is explicitly invalid. Preserve original input field values and logical source record number for rejection export and preview. Preview accepted records from the transformed relation without adding an ordinal to the 12-column cleaned CSV.

**Alternative:** deduplicating after validation double-counts duplicate invalid records unless extra rules are added; deduplicating on `order_id` incorrectly drops distinct order lines.

### 4. Fix a small, documented data contract

The defaults below resolve details left open in the HTML mockup and are proposed for review, not inferred from existing source tables:

- Exact input header/order is specified in `csv-etl/spec.md`. Headers are not normalized or guessed.
- Identifiers are nonempty text, preserving leading zeros; product and country are required text. Country is uppercased without inventing an ISO whitelist.
- Dates must match `YYYY-MM-DD` exactly and be valid calendar dates.
- Quantity must be an integral decimal value from 1 through 1,000,000; `1.0` is integral, `1.5` is not.
- Unit price must be from 0 through 999,999,999.99; discount must be from 0 through 100. Both allow at most two nonzero fractional places; trailing zeros beyond that precision are harmless. Blank, non-finite, exponent-form, and currency-decorated numbers are invalid. Use explicit lexical and safe-cast checks so unsupported precision is not silently rounded.
- Status values are `new`, `paid`, `shipped`, `completed`, and `cancelled`. Unsupported or blank statuses are rejected. All accepted statuses contribute to the category summary; this is a transformed order-value metric, not recognized revenue.
- Use fixed-point decimals with sufficient intermediate precision, for example `DECIMAL(18,2)` price/discount and wider intermediate products. The input bounds keep gross/net values within the documented range. Round final amounts half-up to two decimals; export monetary values consistently with two fractional digits.
- Cleaned output retains the 10 input columns in order, normalized and typed/formatted, followed by `gross_amount` and `net_amount`. Export dates as ISO dates and integral quantities as integers.
- `rejected.csv` always exists on a successful/warning run, even with headers only. Its columns are `source_record_number`, the 10 original fields in source order, and `rejection_reasons`. Join stable reason codes in a deterministic order and explain them in documentation/report labels.

**Alternatives:** accepting arbitrary schemas would need configuration machinery; silently defaulting discounts or repairing invalid dates would conceal errors in an exercise intended to expose data-quality decisions.

### 5. Use one run result for metrics and presentation

Query a compact result containing stage outcomes, known counts, corrected count, issue counts, category totals, and up to 10 accepted/rejected previews. Python adds identifier, timestamps, elapsed duration, destination, and errors. Use `None` for unavailable metrics rather than treating failure as an empty input.

Stage boundaries:
- Extract: preflight and raw load.
- Validate: normalization, duplicate classification, casting, and rejection reasons.
- Transform: accepted amount calculations and summary queries.
- Load: CSV export, report generation, and output publication.

Stage states are complete, failed, or not run. A run with zero accepted records fails after classification; transform and load are not successful simply because a failure report can be written. Distinguish accepted count from published written count: a failed export can have accepted records but zero written records. An unavailable count is not a known zero.

Use exit code 0 for `Success` and `Success with warnings`; code 1 for execution/data failures and the standard argument-parser nonzero code for invalid CLI usage. CLI usage errors occur before a run is created and need not generate a report.

**Alternative:** independently re-reading exported CSVs to build the report risks inconsistent business rules and duplicate processing.

### 6. Publish complete, uniquely identified artifacts

Treat `--output-dir` as a parent, not a fixed set of filenames to overwrite. Generate a safe run ID from UTC time plus a UUID suffix; create a private staging directory beneath the same parent. Exports are ordered by source ordinal, with fixed newline, quoting, column, date, and number formats so cleaned bytes are repeatable across supported platforms.

For a successful or warning attempt:
1. Resolve paths and reject any resolved source/artifact collision; never delete or overwrite source data.
2. Generate both CSVs and the report in staging.
3. Verify the row invariant and staged artifacts before publication.
4. Rename staging to its unique final run directory on the same filesystem. Only then log published paths and successful completion.

On handled errors, do not publish staged cleaned CSVs. Remove only this attempt's known staged files and try to publish a report-only failed-run directory, with written count zero and accurate available metrics. If writing or renaming is impossible, log the failure and return nonzero without asserting a report exists. Existing published directories are never replaced. There is no mutable `latest` report or pointer in this version, eliminating a common stale-success ambiguity.

Use bounded cleanup of files created by this run, not broad recursive deletion. A hard process crash can leave an unpublished staging directory; recovery automation is out of scope and the dot-prefixed staging directory is not a completed result. Same-filesystem directory rename gives local publication semantics, not a distributed transaction guarantee.

**Alternative:** overwriting `cleaned.csv` and `dashboard.html` independently in a shared directory can expose mismatched attempts or stale successes after a failure.

### 7. Translate the mockup into a genuinely offline dashboard

Keep the mockup's dark surface, warm gold accent, prominent status, metric cards, stage summary, sales-by-category bars, and quality notes. Implement its runtime version with inline CSS, system fonts, static HTML/CSS charts with visible values, and a packaged HTML template. No JavaScript is required for the first version. No external Tailwind, DaisyUI, chart CDN, or Lavish runtime is required in a generated report.

Add actual first-10 previews for accepted and rejected records, visible empty states, and source record numbers/reasons for rejections. Use a responsive grid, readable contrast, text labels in addition to status colors, and scroll containers around wide previews. Category totals use accepted net amounts across all supported statuses and are labeled accordingly.

Escape all interpolated CSV text, names, and error messages with standard-library HTML escaping. Use validated numeric values only for chart widths; handle zero maxima explicitly. Do not inject untrusted data into inline scripts or CSS. Include no credentials or environment dumps. Reports are local artifacts and can contain input values; documentation should warn users before sharing them.

**Alternative:** a live Flask/Streamlit app would introduce lifecycle and dependency costs the user explicitly chose to avoid.

## Risks / Trade-offs

- [Stricter business defaults than a general CSV cleaner] -> Publish the exact schema, statuses, numeric bounds, duplicate identity, and correction-count definition; test boundary examples.
- [CSV parser or type-cast differences between DuckDB versions] -> Pin the validated release, use explicit read settings and safe casts, and test against the documented fixture plus malformed/quoted-newline inputs.
- [HTML mockup mistaken for measured results] -> Compute metrics and previews from run relations; test report values against independently expected fixture outcomes.
- [A failure report cannot be written when the destination itself is broken] -> Make CLI error logging and nonzero exit the fallback, with no invented publication path.
- [Atomic directory rename is not full crash recovery] -> Keep staging local to the destination and unique; document the scope and leave unrelated files untouched.
- [Per-run output grows over time] -> Ignore generated output and document manual removal of specific completed run directories; automatic retention is outside this small exercise.
- [Mini-project could blur the repository's main CDC story] -> Add a clearly labeled optional exercise link and a narrow standalone-command note, without rewriting the architecture or starting services.

## Migration Plan

This is additive and has no database migrations. During implementation, add the mini-project, install its isolated dependency, run the automated suite and offline browser review, then add a root README link, focused generated-output ignore rules, and the standalone-exercise clarification in `AGENTS.md`.

Rollback consists of reverting only this feature's tracked additions and its small documentation/ignore edits. Do not remove shared environments, CDC volumes, unrelated user files, or previously generated reports without explicit authorization. The existing CDC workflow does not require deployment or restart.
