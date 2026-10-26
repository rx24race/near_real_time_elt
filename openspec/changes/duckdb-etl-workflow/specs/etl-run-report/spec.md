# Spec Delta

## Purpose

Make each CSV ETL attempt reviewable through an attractive, self-contained HTML artifact that communicates execution status, data-quality outcomes, and actual transformed results without a running application.

## ADDED Requirements

### Requirement: Offline post-run HTML artifact
Each attempt SHALL produce `dashboard.html` in its own run directory when that destination is writable. The report SHALL open directly in a browser without a server, internet connection, external assets, Lavish, or CDN dependencies. It SHALL describe a completed attempt, not simulate live progress.

#### Scenario: Open without network access
- **WHEN** a completed report is opened as a local HTML file with networking disabled
- **THEN** its styling, metrics, charts, previews, and status remain readable and functional

#### Scenario: Move the report
- **WHEN** only `dashboard.html` is copied to another local folder
- **THEN** its report content and visual summaries remain available without sibling assets

### Requirement: Accurate run status and stage outcomes
The report SHALL display a run identifier, source name, start time, end time, duration, and stage outcomes. Status SHALL be `Success` when data is accepted with no normalization corrections, duplicates, or rejections; `Success with warnings` when data is accepted with any such issue; and `Failed` for fatal errors or no accepted data. Incomplete stages SHALL NOT be marked complete.

#### Scenario: Successful run
- **WHEN** a run accepts at least one record, changes no normalized fields, removes no duplicates, rejects no records, and publishes all outputs
- **THEN** the report displays `Success` and complete outcomes for extract, validate, transform, and load

#### Scenario: Corrections-only warning
- **WHEN** all records are accepted but at least one input field was normalized
- **THEN** the report displays `Success with warnings` and the corrected-record count

#### Scenario: Failure after extraction
- **WHEN** a fatal error prevents transformation or publication
- **THEN** the failure report identifies the error and accurately marks the failed, completed, and not-run stages rather than showing a successful load

### Requirement: Metrics derived from actual run outcomes
The report SHALL display rows read, accepted, written, rejected, duplicate copies removed, and corrected records from the same run outcomes used for CSV export. It SHALL show the row-accounting invariant when classification completes. Unavailable counts SHALL be labeled unavailable rather than invented or replaced with zero. Rows written SHALL count only published cleaned records.

#### Scenario: CSV and report agree
- **WHEN** a mixed-quality run publishes cleaned and rejected CSVs
- **THEN** their data-record counts match the report's written and rejected counts and the classification totals reconcile

#### Scenario: Unreadable input
- **WHEN** extraction fails before a reliable input count is available
- **THEN** the failure report labels unavailable metrics explicitly and does not imply an empty successful dataset

#### Scenario: No accepted data
- **WHEN** classification completes with no accepted records
- **THEN** the report displays `Failed`, zero written records, and the known input, duplicate, and rejection counts

### Requirement: Visual quality and result summaries
The report SHALL provide a responsive dashboard with prominent status and metric cards, a stage summary, a labeled net-sales-by-category chart, quality-issue counts, and accepted and rejected previews of up to 10 records each. Charts SHALL reflect accepted output amounts, not fixture constants. Status and chart values SHALL be understandable without relying on color alone.

#### Scenario: Review transformed results
- **WHEN** a run accepts records in multiple categories
- **THEN** the category chart totals equal the exported net amounts grouped by normalized category, including zero-valued categories

#### Scenario: Preview bounds and rejection context
- **WHEN** a run accepts and rejects more than 10 records each
- **THEN** each preview shows the first 10 applicable records in source order, labels its limit, and includes source record numbers and reasons for rejected records

#### Scenario: Empty summaries and narrow screens
- **WHEN** a report has no available sales results or is viewed on a narrow screen
- **THEN** it shows an explicit empty or unavailable state, avoids invalid chart scales, and confines wide previews to horizontally scrollable containers

### Requirement: Safe rendering of input and errors
CSV values, source names, and error messages SHALL render as escaped text, never executable HTML or script. The report SHALL NOT embed credentials or unrelated environment variables. Source files SHALL NOT be uploaded to a third-party service as part of report generation.

#### Scenario: HTML-shaped source data
- **WHEN** a product name or rejected field contains `<script>` or HTML event-handler text
- **THEN** the preview displays it literally without executing code or changing page structure

#### Scenario: Error message contains markup
- **WHEN** a file or validation error includes angle brackets or quotes
- **THEN** the failure report displays the message as text without interpreting it as markup

### Requirement: Honest failure-report fallback
For failed attempts, the workflow SHALL attempt to publish a report containing the failure and available metrics without a cleaned CSV. If the report cannot be written or published, the command SHALL log that failure and exit nonzero without claiming a dashboard exists. Previous successful run artifacts SHALL remain associated with their original run identifiers.

#### Scenario: Failure with a writable report destination
- **WHEN** an input is missing or invalid and the output parent is writable
- **THEN** the attempt publishes an identified failure report and logs its path while returning nonzero

#### Scenario: Unwritable report destination
- **WHEN** the output parent cannot be written
- **THEN** the command logs the destination error, returns nonzero, and does not claim report publication succeeded

#### Scenario: Failure after an earlier success
- **WHEN** a later attempt fails after a previous successful run exists
- **THEN** it does not overwrite or present that earlier success as its own result
