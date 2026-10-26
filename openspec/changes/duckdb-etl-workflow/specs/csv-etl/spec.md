# Spec Delta

## Purpose

Provide an independent local CSV transformation exercise with explicit data-quality rules, traceable row outcomes, and reproducible exports that do not depend on the existing CDC infrastructure.

## ADDED Requirements

### Requirement: Independent command-line execution
The workflow SHALL accept an input CSV path and an output parent directory through a documented local command, without running Docker services, contacting cloud services, or requiring credentials. Successful and warning runs SHALL exit with code 0; failed attempts SHALL exit nonzero and log an actionable error.

#### Scenario: Run without the CDC stack
- **WHEN** the documented command runs against a valid local CSV with the CDC services stopped and no cloud credentials
- **THEN** it produces the CSV exports and run report without using those services

#### Scenario: Paths containing spaces
- **WHEN** the command receives quoted local paths containing spaces
- **THEN** it reads and writes those paths correctly without interpreting their contents as SQL

### Requirement: Input structure and demonstration fixture
Input SHALL be UTF-8 comma-separated CSV with a header containing exactly these columns in order: `order_id`, `customer_id`, `order_date`, `product_name`, `category`, `quantity`, `unit_price`, `discount_pct`, `country`, `order_status`. A bundled synthetic fixture SHALL contain exactly 60 data records with known corrections, duplicate copies, and invalid values. Other valid inputs SHALL NOT be restricted to 60 records.

#### Scenario: Inspect the bundled fixture
- **WHEN** the fixture is read as CSV
- **THEN** it has exactly 10 headers and 60 data records, with documented expected outcomes computed independently of the dashboard mockup

#### Scenario: Incorrect structure
- **WHEN** an input has missing, extra, duplicate, or reordered headers, invalid encoding, or malformed CSV structure
- **THEN** the attempt fails explicitly rather than silently skipping records or publishing a cleaned CSV

#### Scenario: Input size is not a production constraint
- **WHEN** a structurally valid CSV contains a different positive number of data records
- **THEN** the same transformation rules apply without a minimum 50-row requirement

### Requirement: Deterministic normalization
The workflow SHALL trim surrounding whitespace from every field, lowercase category and status, uppercase country, and replace blank categories with `Unknown`. It SHALL retain identifier and product-name case, preserve source record order, and count a corrected record once when any field changes during normalization, excluding type formatting and derived columns.

#### Scenario: Normalize a messy record
- **WHEN** a record has country ` us `, status ` PAID `, and a blank category
- **THEN** its normalized country is `US`, status is `paid`, category is `Unknown`, and it contributes one corrected record regardless of the number of changed fields

### Requirement: Exact normalized duplicate handling
The workflow SHALL remove duplicate copies based on all 10 normalized text fields before type conversion and row validation, retaining the earliest source record. Repeated order IDs alone SHALL NOT identify duplicates. Removed duplicate copies SHALL be counted separately from rejected records.

#### Scenario: Equivalent text after normalization
- **WHEN** two records have identical normalized text values across all 10 fields
- **THEN** only the earlier record proceeds to validation and the other counts as one duplicate copy removed

#### Scenario: Distinct lines on the same order
- **WHEN** two records share an order ID but differ in any normalized field
- **THEN** both proceed to validation

#### Scenario: Duplicate invalid records
- **WHEN** two normalized-identical records both contain an invalid date
- **THEN** the later copy counts as a duplicate and only the retained record counts as rejected

### Requirement: Row validation and rejection reasons
The workflow SHALL reject records with blank identifiers, product name, country, or status; non-ISO or invalid dates; invalid or out-of-range numbers; non-positive or non-integral quantities; negative prices; discounts outside 0-100; or unsupported status values. Supported statuses SHALL be `new`, `paid`, `shipped`, `completed`, and `cancelled`. Each rejection SHALL identify the source record and all applicable reasons.

#### Scenario: Invalid values do not terminate a mixed run
- **WHEN** an input contains valid records and a record with an impossible date and a negative quantity
- **THEN** the invalid record is rejected with both reasons and the valid records remain eligible for export

#### Scenario: Missing and unsupported values
- **WHEN** retained records have a blank price, non-numeric discount, or status `mystery`
- **THEN** each affected record is rejected with reasons naming the invalid fields

#### Scenario: Date and precision boundaries
- **WHEN** records contain `2026-02-30`, a date not formatted as `YYYY-MM-DD`, or a price or discount with nonzero precision beyond two decimal places
- **THEN** the affected records are rejected without silently repairing dates or rounding input values

### Requirement: Derived monetary values
Accepted records SHALL include `gross_amount = quantity * unit_price` and `net_amount = gross_amount * (1 - discount_pct / 100)`, using decimal arithmetic and rounding final monetary values to two decimal places with half-up rounding. Values outside the documented numeric range SHALL be rejected, not silently truncated or allowed to abort an otherwise valid batch.

#### Scenario: Discounted order line
- **WHEN** an accepted record has quantity 3, unit price 19.99, and discount 10
- **THEN** gross amount is 59.97 and net amount is 53.97

#### Scenario: Half-cent rounding
- **WHEN** an accepted record has quantity 1, unit price 0.05, and discount 10
- **THEN** net amount is 0.05 after half-up rounding

#### Scenario: Full discount and zero price
- **WHEN** a record otherwise passes validation and has a zero unit price or a 100 percent discount
- **THEN** zero-valued monetary results are accepted

### Requirement: Traceable CSV exports and row accounting
A run with accepted data SHALL export `cleaned.csv` with the 10 normalized, typed input columns followed by the two amount columns, and `rejected.csv` with original input values, a 1-based source data-record number, and rejection reasons. Both SHALL contain headers, even when no records are rejected. For completed classification, rows read SHALL equal rows accepted plus duplicate copies removed plus rejected records.

#### Scenario: Mixed outcomes
- **WHEN** an input finishes classification with accepted records, duplicate copies, and rejections
- **THEN** the exported counts satisfy the invariant and both exports are ordered by original source record position

#### Scenario: Rejected traceability with quoted newlines
- **WHEN** a rejected CSV record contains a quoted newline within a field
- **THEN** its source record number identifies its logical data-record position, not its physical line number

#### Scenario: No valid records
- **WHEN** an empty input with valid headers or an input with only rejected records finishes classification
- **THEN** the attempt fails with no cleaned CSV publication and reports the available classification counts

### Requirement: Repeatable and source-safe output publication
The workflow SHALL leave source bytes unchanged and create a distinct, identified run directory per attempt under the output parent. Successful outputs SHALL become visible as a complete set only after generation succeeds. Failed attempts SHALL NOT present partial cleaned output or an earlier run's report as their own success. The same input and rules SHALL yield byte-identical cleaned CSV data across runs.

#### Scenario: Repeat a run
- **WHEN** the same source is processed twice with unchanged rules
- **THEN** the runs have separate identifiers, identical cleaned CSV bytes, and an unchanged source file; report timestamps and durations can differ

#### Scenario: Output publication fails
- **WHEN** an export or report cannot be written or published
- **THEN** the command exits nonzero, logs the affected destination, and does not publish a partially successful run directory

#### Scenario: Source collides with an artifact path
- **WHEN** an output configuration would replace the source through a resolved path or alias
- **THEN** the command refuses that configuration without altering the source
