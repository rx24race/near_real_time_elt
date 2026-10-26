# Tasks

## 1. Standalone runner and reproducible input

- [x] 1.1 Add the isolated `csv_etl/` package, CLI entry point, and standalone requirements file with a tested, pinned DuckDB release compatible with Python 3.10+; verify installation and `python -m csv_etl --help` without adding dependencies to the consumer or Airflow.
- [x] 1.2 Create `data/orders.csv` with exactly 60 synthetic order-line records and the specified 10-column header, including deliberate corrections, duplicate copies, valid repeated order IDs, and invalid records; verify its shape with a fixture test and document independently calculated expected row outcomes in `csv_etl/README.md`.
- [x] 1.3 Implement strict structural preflight and all-text DuckDB ingestion with stable logical source record numbers; verify tests for headers/order, record widths, invalid UTF-8, malformed quoting, quoted newlines, header-only input, and arbitrary valid row counts.
- [x] 1.4 Document PowerShell and Bash environment setup, the required `--input` argument, output-parent/default behavior, and the absence of service/credential prerequisites; verify documented commands and quoted input/output paths containing spaces and apostrophes using CLI tests.

## 2. SQL transformation and data-quality contract

- [x] 2.1 Add readable normalization and deduplication SQL stages preserving original values and record ordinals; verify tests for trimming/case/defaults, corrected-record counting, earliest-copy retention, duplicate invalid records, and distinct lines sharing an order ID.
- [x] 2.2 Add safe-cast classification SQL with all applicable field rejection reasons; verify tests for required fields, strict dates, supported statuses, NULL handling, integral quantity, numeric syntax/bounds, excess fractional precision, and non-finite values.
- [x] 2.3 Add decimal gross/net calculations and deterministic accepted/rejected ordering; verify tests for 3 x 19.99 at 10 percent, half-cent rounding, zero price, full discounts, and documented numeric maxima without overflow or unintended floating-point rounding.
- [x] 2.4 Add SQL summary queries for classification totals, corrections, issue counts, category totals, and first-10 previews; verify the row-accounting invariant, preview limits/source order, and independently expected fixture values.
- [x] 2.5 Document the normalization order, text-based duplicate identity, status list, numeric syntax/ranges, precision/rounding, rejection codes, correction-count overlap, and order-value interpretation of category totals; verify the documentation against the SQL tests and both delta specs.

## 3. CSV export and safe run publication

- [x] 3.1 Export `cleaned.csv` and `rejected.csv` through DuckDB with exact headers, stable formatting and ordering, original rejected values, source ordinals, and ordered reasons; verify tests for header-only rejected output, quoting/newlines, 12 cleaned columns, and counts matching classified relations.
- [x] 3.2 Implement unique run IDs, staging directories, collision checks, bounded cleanup, and same-filesystem complete-directory publication; verify repeated-run tests yield distinct directories, byte-identical cleaned exports, and unchanged source bytes without overwriting existing artifacts.
- [x] 3.3 Implement nonzero failure paths for missing/invalid input, no accepted records, and export/publication errors, with structured stage/metric results for the reporter; verify injected filesystem failures leave no published partial cleaned output and preserve previous successful runs.
- [x] 3.4 Document output layout, exit codes, repeatability limits, failure/staging behavior, and report/CSV sharing caveats; verify examples against CLI output and unit tests, including source-path alias/collision protections where supported by the platform.

## 4. Offline dashboard and failure reporting

- [x] 4.1 Add the report template and renderer with inline styling, system fonts, dark-and-gold visual direction, status/metric cards, stage outcomes, and actual run metadata; verify renderer tests for success, corrections-only warnings, mixed-quality warnings, failed stages, and unavailable versus zero metrics.
- [x] 4.2 Add category bars with numeric labels, quality counts, empty states, and scrollable first-10 accepted/rejected previews; verify report totals match accepted SQL results, all-zero categories render safely, preview limits/order hold, and no external asset URLs are generated.
- [x] 4.3 Escape all source values, names, and errors and restrict chart geometry to validated numbers; verify HTML-parsing tests show malicious markup as text with no executable elements, attributes, or unintended network references.
- [x] 4.4 Integrate success-report publication and report-only failure fallback with the runner; verify CLI tests for missing input, all-invalid/header-only input, unwritable output, failed export/rename, correct published-written counts, and truthful report-path logging.
- [x] 4.5 Document direct browser opening, the distinction between an offline report and live progress, metric definitions, failure-report limitations, and privacy when sharing previews; verify by opening a moved report with networking disabled and checking desktop and narrow-screen layouts.

## 5. Repository integration and end-to-end verification

- [x] 5.1 Add a focused optional-exercise link in the root README, generated-output ignore rules, and a narrow standalone-command exception in `AGENTS.md`; verify `git diff` leaves CDC configuration, existing dependencies, DAGs, models, credentials, and source tables unchanged.
- [x] 5.2 Run `python -m unittest discover -s csv_etl/tests` and the documented sample command with services stopped and no cloud credentials; verify published CSV counts, chart aggregates, status, previews, and the row invariant against the fixture expectations.
- [x] 5.3 Execute the full workflow twice, then a failing attempt under the same output parent; verify repeatable cleaned bytes, unchanged input, separate run identities, correct nonzero failure exit, and no stale/partial success artifacts.
- [x] 5.4 Review generated success/warning and failure reports directly in a browser offline at desktop and narrow widths; verify text status labels, readable contrast, zero/unavailable states, safe HTML previews, and that root documentation links and mini-project instructions work without the original local planning HTML.

## Workflow follow-up

- Review the completed implementation and archive this change only after its acceptance checks pass and the user requests finalization.
