# CSV Studio: DuckDB SQL ETL

A standalone e-commerce CSV exercise, independent of the repository's CDC stack.
Transforms run in embedded DuckDB SQL, not pandas. Python handles the CLI,
logging, input structure checks, and offline HTML presentation.

## Setup and run

Requires Python 3.10+; DuckDB 1.4.4 is the only third-party dependency. No Docker
services, database server, cloud credentials, pandas, or frontend build are needed.
From the repository root, create an isolated environment:

PowerShell:

```powershell
python -m venv csv_etl/.venv
.\csv_etl\.venv\Scripts\python.exe -m pip install -r csv_etl/requirements.txt
.\csv_etl\.venv\Scripts\python.exe -m csv_etl --input csv_etl/data/orders.csv --output-dir csv_etl/output
.\csv_etl\.venv\Scripts\python.exe -m unittest discover -s csv_etl/tests
```

Bash (Linux/macOS):

```bash
python3 -m venv csv_etl/.venv
csv_etl/.venv/bin/python -m pip install -r csv_etl/requirements.txt
csv_etl/.venv/bin/python -m csv_etl --input csv_etl/data/orders.csv --output-dir csv_etl/output
csv_etl/.venv/bin/python -m unittest discover -s csv_etl/tests
```

On Windows Git Bash, use `csv_etl/.venv/Scripts/python.exe` instead of `bin/python`.
`--input` is required. `--output-dir` is a parent for unique run directories;
omitting it defaults to this package's `output/`, independent of the current
working directory. Relative explicit paths are resolved from the current directory.
Quote paths containing spaces or apostrophes using your shell's quoting rules.
`python -m csv_etl --help` describes the arguments; help needs no DuckDB import.

## Demonstration fixture

`data/orders.csv` contains 60 synthetic data records and exactly 10 columns:
`order_id`, `customer_id`, `order_date`, `product_name`, `category`, `quantity`,
`unit_price`, `discount_pct`, `country`, `order_status`.

Expected outcomes, calculated independently of the SQL and mockup:

| Source data records (1-based, excluding the header) | Outcome |
| --- | --- |
| 1-45 | Already-normalized accepted order lines |
| 46-50 | Accepted after normalization; record 50 defaults category to `Unknown` |
| 51-55 | Exact duplicate copies of records 1-5 |
| 56-60 | Rejected: invalid date, zero quantity, negative price, discount above 100, unsupported status |

Totals: **60 read = 50 accepted + 5 duplicates + 5 rejected**; **5 corrected**.
Every accepted line has quantity 2, price 10.00, and discount 10.00 percent:
gross total **1000.00**, net total **900.00**. Net category totals are `home`:
**882.00** (49 lines), `Unknown`: **18.00** (1 line). Order `1001` intentionally
appears on two distinct lines; an order ID alone is not a duplicate key.

## Transformation contract

The input must be UTF-8 comma-separated CSV with exactly the documented header
names and order. CSV quoting (including quoted newlines) is supported. A source
record number counts logical records starting at 1 after the header, not lines.
Malformed quoting, wrong widths, reordered/missing/extra/duplicate headers, and
encoding errors fail the attempt. Other inputs need not have 60 records.

SQL stages are deliberately small and inspectable:

1. `sql/normalize.sql`: trim surrounding whitespace from every field; lowercase
   category/status, uppercase country, and default blank category to `Unknown`.
   Identifier and product-name case and identifier leading zeros are preserved.
2. In the same stage, rank duplicates by **all 10 normalized text fields**, before
   casting or validation, keeping the earliest record. `2` and `2.0` are distinct
   text values. A repeated order ID can have multiple distinct lines.
3. `sql/classify.sql`: validate retained records and collect all applicable
   reasons. A duplicate invalid record is removed as a duplicate copy, not counted
   again as a rejection. Original fields remain available for rejection output.
4. `sql/metrics.sql`: query classification counts, issue counts, and rejected
   previews from those same relations. No hardcoded mockup metrics are used.
5. `sql/transform.sql`: calculate accepted amounts, category totals, and accepted
   previews. Source order determines export/preview order.

Value rules:

| Fields | Accepted values |
| --- | --- |
| Identifiers, product, country | Nonempty text; country is not checked against a country-code registry |
| Date | Valid calendar date, exactly `YYYY-MM-DD`, year 0001 through 9999 (no year zero/BC dates) |
| Quantity | Integral value from 1 to 1,000,000; `2.0` and `+2` are accepted, `2.5` is not |
| Unit price | 0 through 999,999,999.99 |
| Discount percent | 0 through 100 |
| Status | `new`, `paid`, `shipped`, `completed`, `cancelled` after normalization |

Numeric syntax requires digits, with an optional leading sign and fractional
part. Price/discount permit two decimal places and additional trailing zeros,
but any nonzero digits beyond the second decimal place are rejected. Blank,
non-finite (`NaN`/`inf`), exponent-form (`1e2`), currency-decorated (`$10`), and
out-of-range numbers are invalid. Numeric casts never silently repair such input.

`gross_amount = quantity * unit_price` and
`net_amount = gross_amount * (1 - discount_pct / 100)`. Fixed-point cents and exact
integer division avoid DuckDB's floating-point `/` operator. Final monetary values
are half-up rounded and exported with two decimal places: 3 x 19.99 at 10 percent
gives 59.97 gross and 53.97 net; 0.05 at 10 percent gives 0.05 net.

Rejection codes are stable, field-specific, and ordered as follows:
`order_id_required`, `customer_id_required`, `order_date_invalid`,
`product_name_required`, `quantity_invalid`, `unit_price_invalid`,
`discount_pct_invalid`, `country_required`, `order_status_invalid`.
Multiple reasons are separated with `;`. Issue counts count each reason once per
rejected record, so their sum can exceed the rejected-record count.

Corrections count original records with any normalization change **once per
record**, not per changed field. Corrections can overlap duplicates/rejections.
Type formatting (such as `2.0` to `2`) and derived amounts are not corrections.
The row invariant is **read = accepted + duplicates removed + rejected**.
Category summaries sum accepted net amounts across **all supported statuses**,
including cancelled lines; they describe transformed order value, not recognized
revenue. No currency conversion is performed; input amounts must share a unit.

## Outputs, repeatability, and failures

The command logs its run identifier, stage outcomes, counts, and published report
path. Each attempt gets a new UTC-time/UUID run directory beneath the output
parent. There is no shared `latest` pointer that could show a stale success.

```text
csv_etl/output/
  <run-id>/
    cleaned.csv
    rejected.csv
    dashboard.html
```

Successful/warning runs publish all three files together. Cleaned CSV has the 10
normalized input columns followed by `gross_amount` and `net_amount`. Rejected
CSV has `source_record_number`, the original 10 fields, and `rejection_reasons`.
Both have headers, even if rejected output is empty. Original values, including
quoted newlines and whitespace, are retained in rejected output. Cleaned dates,
integers, two-decimal amounts, column order, quoting, and LF newlines are stable.

Exit codes: **0** for success or success with warnings, **1** for data/runtime/I/O
failure, **2** for invalid CLI usage. A header-only or all-invalid input is a failed
attempt. When possible it publishes only `dashboard.html`, with known counts and
an error, never a partially successful cleaned CSV. If the output parent itself
cannot be written, the command logs the error and exits nonzero without claiming
a report exists. CLI argument errors occur before an attempt and need no report.

Each attempt generates files in its own hidden staging directory on the same
filesystem, validates exports, then renames the complete directory into place.
Handled failures clean up only that attempt's known staged artifacts. Existing
source bytes and prior successful runs are never overwritten; resolved path and
hard-link alias checks guard source/artifact collisions. Unexpected files are not
recursively deleted. A hard process crash can leave an unpublished staging folder;
automatic crash recovery and input modification during a run are out of scope.

Repeatability means identical cleaned CSV bytes for identical input/rules, not
identical run identifiers, timestamps, or durations. Duration is the elapsed time
to the outcome snapshot immediately before report rendering/publication, rather
than a simulated live timer. Generated outputs accumulate; remove only specific
completed directories you no longer need. Reports and rejected CSVs can contain
source data: review them before sharing. CSVs are data artifacts; use suitable
spreadsheet import settings rather than assuming formula-like text is harmless.

## View the offline dashboard

Open the `dashboard.html` path printed in the log with any modern browser
(double-click the file, or use `Invoke-Item "<path-to-dashboard.html>"` in
PowerShell). This is a **post-run snapshot**, not a live progress application.
You can move just this HTML file elsewhere and open it with networking disabled:
all styles, chart bars, metrics, and previews are contained in the file. It does
not need sibling CSVs, Lavish, a server, JavaScript, fonts, or CDN assets.

The dark-and-gold dashboard shows:

- **Success**: accepted data and no corrections, duplicate copies, or rejections.
- **Success with warnings**: accepted data plus any normalization corrections,
  duplicate copies, or rejections. This still exits 0.
- **Failed**: an input/runtime/output error or no accepted data. Later stages are
  labeled `not run`, not complete; the failing stage is labeled `failed`.

| Metric | Meaning |
| --- | --- |
| Rows read | Logical input records; unavailable if extraction did not finish |
| Rows accepted | Retained records passing validation, whether or not publication succeeds |
| Rows written | Published cleaned records; zero on failed attempts |
| Rows rejected | Retained records failing one or more value checks |
| Duplicates removed | Extra copies of exact normalized records, removed before validation |
| Corrected records | Original records with any normalization change, including copies or rejected records |

Known zero counts remain zero; unknown counts say **Unavailable**. Row accounting
appears only after classification completes. Quality counts can overlap, and the
previews show only the first 10 accepted/rejected records in source order. Scroll
wide preview tables horizontally; source record numbers refer to logical CSV
records, not physical lines. The category bars display actual net amounts with
numeric labels, including zero-valued categories.

Failure reports include the error and available metrics but no cleaned CSV.
Writing the failure report cannot itself be guaranteed when the destination is
unusable; in that case the nonzero exit and log are the only output. Text from
CSV fields, filenames, and errors is HTML-escaped. Previews and errors may still
contain sensitive source data or local paths, so inspect reports before sharing.
