import csv
import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from csv_etl import HEADERS
from csv_etl.pipeline import (
    CLEANED_HEADERS, REJECTED_HEADERS, classification_summary, connect,
    execute_sql, export_csvs, load_raw, transformed_summary,
    check_source_safety, cleanup_staging, new_run_id, prepare_output, publish,
    run,
)


FIXTURE = Path(__file__).resolve().parents[1] / "data" / "orders.csv"

ROW = ["001", "C001", "2026-01-01", "Widget", "home", "2", "10.00", "10.00", "US", "paid"]


class PipelineCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.source = Path(self.temporary.name) / "orders.csv"
        self.connection = connect()
        self.addCleanup(self.connection.close)

    def write_rows(self, rows, headers=HEADERS):
        with self.source.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(headers)
            writer.writerows(rows)
        return self.source


class IngestionTests(PipelineCase):
    def test_text_and_record_numbers(self):
        self.write_rows([ROW, ROW[:3] + ["quoted\nproduct"] + ROW[4:]])
        self.assertEqual(load_raw(self.connection, self.source), 2)
        values = self.connection.execute("SELECT source_record_number, order_id, product_name FROM raw ORDER BY 1").fetchall()
        self.assertEqual(values, [(1, "001", "Widget"), (2, "001", "quoted\nproduct")])
        types = self.connection.execute("DESCRIBE raw").fetchall()
        self.assertTrue(all(column[1] == "VARCHAR" for column in types[1:]))

    def test_empty_fields_are_text(self):
        row = ROW.copy()
        row[4] = ""
        self.write_rows([row])
        load_raw(self.connection, self.source)
        self.assertEqual(self.connection.execute("SELECT category FROM raw").fetchone()[0], "")

    def test_header_only(self):
        self.write_rows([])
        self.assertEqual(load_raw(self.connection, self.source), 0)

    def test_header_variants(self):
        for headers in (HEADERS[:-1], HEADERS + ("extra",), HEADERS[::-1], (HEADERS[1],) + HEADERS[1:]):
            with self.subTest(headers=headers):
                self.write_rows([], headers)
                with self.assertRaisesRegex(ValueError, "headers"):
                    load_raw(self.connection, self.source)

    def test_bad_record_width(self):
        for row in (ROW[:-1], ROW + ["extra"], []):
            with self.subTest(row=row):
                self.write_rows([row])
                with self.assertRaisesRegex(ValueError, "expected 10 fields"):
                    load_raw(self.connection, self.source)

    def test_bad_encoding_and_quoting(self):
        for data in (b"\xff", (",".join(HEADERS) + '\n"unterminated').encode(),
                     (",".join(HEADERS) + '\n"wrong"suffix,a,b,c,d,e,f,g,h,i').encode()):
            with self.subTest(data=data):
                self.source.write_bytes(data)
                with self.assertRaises((ValueError, UnicodeError, csv.Error)):
                    load_raw(self.connection, self.source)

    def test_any_positive_record_count(self):
        self.write_rows([ROW] * 3)
        self.assertEqual(load_raw(self.connection, self.source), 3)


class NormalizationTests(PipelineCase):
    def normalize(self, rows):
        self.write_rows(rows)
        load_raw(self.connection, self.source)
        execute_sql(self.connection, "normalize.sql")

    def test_trim_case_default_and_single_correction(self):
        row = ["\t001\n", " C001 ", " 2026-01-01 ", " Widget ", "", " 2 ", "10.00", "10.00", " us ", " PAID "]
        self.normalize([row])
        actual = self.connection.execute("SELECT order_id, customer_id, category, country, order_status, corrected FROM normalized").fetchone()
        self.assertEqual(actual, ("001", "C001", "Unknown", "US", "paid", True))
        self.assertEqual(self.connection.execute("SELECT product_name FROM raw").fetchone()[0], " Widget ")

    def test_unicode_surrounding_whitespace(self):
        row = [f"\u00a0\u2003\u0085{value}\u2029\u00a0" for value in ROW]
        self.normalize([row])
        actual = self.connection.execute("SELECT " + ", ".join(HEADERS) + " FROM normalized").fetchone()
        self.assertEqual(actual, tuple(ROW))

    def test_earliest_duplicate_and_distinct_order_lines(self):
        second = ROW.copy()
        second[3] = "Other product"
        copy = [f" {value} " for value in ROW]
        self.normalize([ROW, second, copy])
        self.assertEqual(self.connection.execute("SELECT source_record_number, duplicate_rank FROM ranked ORDER BY 1").fetchall(), [(1, 1), (2, 1), (3, 2)])

    def test_duplicate_invalid_records_are_ranked_before_validation(self):
        bad = ROW.copy()
        bad[2] = "not-a-date"
        self.normalize([bad, bad])
        self.assertEqual(self.connection.execute("SELECT duplicate_rank FROM ranked ORDER BY source_record_number").fetchall(), [(1,), (2,)])

    def test_numeric_text_is_not_coerced_for_duplicate_identity(self):
        other = ROW.copy()
        other[5] = "2.0"
        self.normalize([ROW, other])
        self.assertEqual(self.connection.execute("SELECT count(*) FROM ranked WHERE duplicate_rank = 1").fetchone()[0], 2)

    def test_corrections_count_source_records_not_fields(self):
        self.normalize([ROW, [f" {v} " for v in ROW]])
        self.assertEqual(self.connection.execute("SELECT count(*) FILTER (WHERE corrected) FROM ranked").fetchone()[0], 1)


class ClassificationTests(PipelineCase):
    def classify(self, rows):
        self.write_rows(rows)
        load_raw(self.connection, self.source)
        execute_sql(self.connection, "normalize.sql")
        execute_sql(self.connection, "classify.sql")
        return self.connection.execute("SELECT reasons FROM classified ORDER BY source_record_number").fetchall()

    def test_multiple_reasons_and_duplicate_invalid(self):
        bad = ROW.copy()
        bad[2], bad[5] = "2026-02-30", "-1"
        self.assertEqual(self.classify([ROW, bad, bad]), [([],), (["order_date_invalid", "quantity_invalid"],)])
        self.assertEqual(self.connection.execute("SELECT source_record_number FROM rejected").fetchall(), [(2,)])

    def test_required_fields_and_status(self):
        bad = ROW.copy()
        for index in (0, 1, 3, 6, 7, 8, 9):
            bad[index] = ""
        reasons = self.classify([bad])[0][0]
        self.assertEqual(reasons, ["order_id_required", "customer_id_required", "product_name_required", "unit_price_invalid", "discount_pct_invalid", "country_required", "order_status_invalid"])

    def test_dates(self):
        dates = ["2026-02-30", "2026-1-01", "01/01/2026", "", "0000-01-01", "2024-02-29"]
        rows = []
        for date in dates:
            row = ROW.copy()
            row[2] = date
            rows.append(row)
        self.assertEqual(self.classify(rows), [(["order_date_invalid"],)] * 5 + [([],)] )

    def test_numeric_syntax_bounds_and_precision(self):
        cases = [
            (5, "0", False), (5, "-1", False), (5, "1.5", False), (5, "1000001", False),
            (5, "2.0", True), (5, "+1", True), (5, "1e2", False),
            (6, "-0.01", False), (6, "1000000000", False), (6, "1.001", False),
            (6, "1.230000", True), (6, "$1", False), (6, "NaN", False),
            (6, "inf", False), (6, "1e2", False), (6, "0", True),
            (7, "-1", False), (7, "101", False), (7, "1.001", False),
            (7, "100.000", True), (7, "oops", False), (7, "", False),
            (6, "9" * 70, False), (5, "9" * 70, False), (7, "9" * 70, False),
        ]
        rows = []
        for index, (field, value, _) in enumerate(cases):
            row = ROW.copy()
            row[0], row[field] = str(index), value
            rows.append(row)
        outcomes = self.classify(rows)
        for case, outcome in zip(cases, outcomes):
            with self.subTest(case=case):
                self.assertEqual(not outcome[0], case[2])

    def test_nulls_cannot_pass_required_checks(self):
        self.write_rows([ROW])
        load_raw(self.connection, self.source)
        self.connection.execute("UPDATE raw SET quantity=NULL, order_status=NULL")
        execute_sql(self.connection, "normalize.sql")
        execute_sql(self.connection, "classify.sql")
        self.assertEqual(self.connection.execute("SELECT reasons FROM classified").fetchone()[0], ["quantity_invalid", "order_status_invalid"])

    def test_supported_statuses(self):
        rows = []
        for status in ("new", "paid", "shipped", "completed", "cancelled", "mystery"):
            row = ROW.copy()
            row[9] = status
            rows.append(row)
        self.assertEqual(self.classify(rows), [([],)] * 5 + [(["order_status_invalid"],)])


class TransformationTests(PipelineCase):
    def transform(self, rows=None):
        self.write_rows(rows) if rows is not None else None
        load_raw(self.connection, self.source)
        for stage in ("normalize.sql", "classify.sql", "transform.sql"):
            execute_sql(self.connection, stage)

    def test_exact_money_and_maxima(self):
        cases = [
            ("3", "19.99", "10", "59.97", "53.97"),
            ("1", "0.05", "10", "0.05", "0.05"),
            ("2", "10", "100", "20.00", "0.00"),
            ("2", "0", "10", "0.00", "0.00"),
            ("1000000", "999999999.99", "0", "999999999990000.00", "999999999990000.00"),
            ("1000000", "999999999.99", "99.99", "999999999990000.00", "99999999999.00"),
        ]
        rows = []
        for index, (quantity, price, discount, _, _) in enumerate(cases):
            row = ROW.copy()
            row[0], row[5], row[6], row[7] = str(index), quantity, price, discount
            rows.append(row)
        self.transform(rows)
        amounts = self.connection.execute("SELECT gross_amount, net_amount FROM accepted ORDER BY source_record_number").fetchall()
        self.assertEqual(amounts, [(Decimal(gross), Decimal(net)) for *_, gross, net in cases])

    def test_only_accepted_rows_and_stable_order(self):
        bad = ROW.copy()
        bad[5] = "1.5"
        other = ROW.copy()
        other[0] = "000"
        self.transform([ROW, bad, other])
        self.assertEqual(self.connection.execute("SELECT source_record_number, order_id FROM accepted ORDER BY source_record_number").fetchall(), [(1, "001"), (3, "000")])


class MetricsTests(PipelineCase):
    def summarize(self):
        load_raw(self.connection, self.source)
        for stage in ("normalize.sql", "classify.sql", "metrics.sql", "transform.sql"):
            execute_sql(self.connection, stage)
        return classification_summary(self.connection), transformed_summary(self.connection)

    def test_fixture_outcomes_and_categories(self):
        self.source = FIXTURE
        classified, transformed = self.summarize()
        self.assertEqual(classified["metrics"], dict(rows_read=60, rows_accepted=50, rows_rejected=5, duplicates_removed=5, corrected_records=5))
        self.assertEqual(transformed["categories"], [{"category": "Unknown", "net_amount": Decimal("18.00")}, {"category": "home", "net_amount": Decimal("882.00")}])
        self.assertEqual([r["source_record_number"] for r in classified["rejected_preview"]], list(range(56, 61)))
        self.assertEqual(sum(issue["row_count"] for issue in classified["issues"]), 5)

    def test_preview_bounds_order_and_multiple_reasons(self):
        rows = []
        for index in range(30):
            row = ROW.copy()
            row[0] = str(index)
            if index >= 15:
                row[2], row[5] = "bad", "0"
            rows.append(row)
        self.write_rows(rows)
        classified, transformed = self.summarize()
        self.assertEqual([r["source_record_number"] for r in transformed["accepted_preview"]], list(range(1, 11)))
        self.assertEqual([r["source_record_number"] for r in classified["rejected_preview"]], list(range(16, 26)))
        self.assertEqual(classified["issues"], [{"reason": "order_date_invalid", "row_count": 15}, {"reason": "quantity_invalid", "row_count": 15}])

    def test_empty_and_zero_valued_category(self):
        row = ROW.copy()
        row[6] = "0"
        self.write_rows([row])
        classified, transformed = self.summarize()
        self.assertEqual(classified["rejected_preview"], [])
        self.assertEqual(transformed["categories"], [{"category": "home", "net_amount": Decimal("0.00")}])

    def test_empty_classification(self):
        self.write_rows([])
        classified, transformed = self.summarize()
        self.assertTrue(all(value == 0 for value in classified["metrics"].values()))
        self.assertEqual(transformed["categories"], [])


class ExportTests(PipelineCase):
    def export(self, rows):
        self.write_rows(rows)
        load_raw(self.connection, self.source)
        for stage in ("normalize.sql", "classify.sql", "transform.sql"):
            execute_sql(self.connection, stage)
        output = Path(self.temporary.name) / "Owner's data"
        output.mkdir()
        export_csvs(self.connection, output)
        return output

    def read_csv(self, path):
        with path.open(encoding="utf-8", newline="") as stream:
            return list(csv.reader(stream))

    def test_headers_and_formats(self):
        output = self.export([ROW])
        cleaned = self.read_csv(output / "cleaned.csv")
        rejected = self.read_csv(output / "rejected.csv")
        self.assertEqual(tuple(cleaned[0]), CLEANED_HEADERS)
        self.assertEqual(tuple(rejected[0]), REJECTED_HEADERS)
        self.assertEqual(len(cleaned[1]), 12)
        self.assertEqual(cleaned[1][0], "001")
        self.assertEqual(cleaned[1][2], "2026-01-01")
        self.assertEqual(cleaned[1][-2:], ["20.00", "18.00"])
        self.assertEqual(len(rejected), 1)
        self.assertNotIn(b"\r\n", (output / "cleaned.csv").read_bytes())

    def test_rejected_original_values_quoting_and_source_record(self):
        bad = ROW.copy()
        bad[3], bad[5] = ' product, with "quotes"\nand newline ', "0"
        output = self.export([ROW, bad])
        rejected = self.read_csv(output / "rejected.csv")
        self.assertEqual(rejected[1], ["2"] + bad + ["quantity_invalid"])

    def test_counts_after_duplicates_and_rejections(self):
        bad = ROW.copy()
        bad[2] = "invalid"
        output = self.export([ROW, ROW, bad, bad])
        self.assertEqual(len(self.read_csv(output / "cleaned.csv")), 2)
        self.assertEqual(len(self.read_csv(output / "rejected.csv")), 2)


class PublicationTests(PipelineCase):
    def test_repeatable_exports_and_unchanged_source(self):
        self.write_rows([ROW])
        before = self.source.read_bytes()
        load_raw(self.connection, self.source)
        for stage in ("normalize.sql", "classify.sql", "transform.sql"):
            execute_sql(self.connection, stage)
        outputs = []
        for _ in range(2):
            staging, final = prepare_output(self.source, Path(self.temporary.name) / "output", new_run_id())
            export_csvs(self.connection, staging)
            (staging / "dashboard.html").write_text("test report", encoding="utf-8")
            self.assertFalse(final.exists())
            publish(staging, final)
            outputs.append(final)
        self.assertNotEqual(outputs[0], outputs[1])
        self.assertEqual((outputs[0] / "cleaned.csv").read_bytes(), (outputs[1] / "cleaned.csv").read_bytes())
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(len(list(outputs[0].iterdir())), 3)

    def test_collision_and_existing_destinations_are_not_overwritten(self):
        self.write_rows([ROW])
        with self.assertRaisesRegex(ValueError, "replace source"):
            check_source_safety(self.source, [self.source])
        parent = Path(self.temporary.name) / "out"
        staging, final = prepare_output(self.source, parent, "fixed-run")
        final.mkdir()
        (final / "keep.txt").write_text("user work")
        with self.assertRaises(FileExistsError):
            publish(staging, final)
        with self.assertRaises(FileExistsError):
            prepare_output(self.source, parent, "fixed-run")
        self.assertEqual((final / "keep.txt").read_text(), "user work")

    def test_aliases_are_detected(self):
        self.write_rows([ROW])
        alias = Path(self.temporary.name) / "alias.csv"
        try:
            os.link(self.source, alias)
        except OSError as exc:
            self.skipTest(str(exc))
        with self.assertRaisesRegex(ValueError, "alias"):
            check_source_safety(self.source, [alias])

    def test_cleanup_is_bounded(self):
        self.write_rows([ROW])
        staging, _ = prepare_output(self.source, Path(self.temporary.name) / "out", "run")
        (staging / "cleaned.csv").write_text("partial")
        (staging / "unrelated.txt").write_text("do not remove")
        with self.assertLogs("csv_etl.pipeline", level="WARNING"):
            cleanup_staging(staging)
        self.assertFalse((staging / "cleaned.csv").exists())
        self.assertEqual((staging / "unrelated.txt").read_text(), "do not remove")


class RunnerTests(PipelineCase):
    def attempt(self, rows=None):
        if rows is not None:
            self.write_rows(rows)
        with self.assertLogs("csv_etl.pipeline", level="INFO") as logged:
            result = run(self.source, Path(self.temporary.name) / "output", renderer=lambda r: f"{r.status} written={r.metrics['rows_written']}")
        return result, "\n".join(logged.output)

    def test_success_and_warning_statuses(self):
        result, _ = self.attempt([ROW])
        self.assertEqual(result.status, "Success")
        self.assertEqual(result.metrics["rows_written"], 1)
        self.assertTrue(all(stage == "complete" for stage in result.stages.values()))
        self.assertEqual(set(p.name for p in result.artifact_dir.iterdir()), set(("cleaned.csv", "rejected.csv", "dashboard.html")))
        corrected = ROW.copy()
        corrected[9] = " PAID "
        result, _ = self.attempt([corrected])
        self.assertEqual(result.status, "Success with warnings")

    def test_missing_input_and_unavailable_counts(self):
        result, logged = self.attempt()
        self.assertEqual(result.status, "Failed")
        self.assertIsNone(result.metrics["rows_read"])
        self.assertEqual(result.stages["extract"], "failed")
        self.assertEqual(result.stages["transform"], "not run")
        self.assertEqual([p.name for p in result.artifact_dir.iterdir()], ["dashboard.html"])
        self.assertIn("failure dashboard:", logged)

    def test_no_accepted_data(self):
        for rows in ([], [ROW[:5] + ["0"] + ROW[6:]]):
            with self.subTest(rows=rows):
                result, _ = self.attempt(rows)
                self.assertEqual(result.status, "Failed")
                self.assertEqual(result.metrics["rows_accepted"], 0)
                self.assertEqual(result.metrics["rows_written"], 0)
                self.assertEqual(result.stages["transform"], "not run")
                self.assertFalse((result.artifact_dir / "cleaned.csv").exists())

    def test_export_failure_preserves_prior_success(self):
        prior, _ = self.attempt([ROW])
        original = (prior.artifact_dir / "cleaned.csv").read_bytes()
        def fail(connection, directory):
            (directory / "cleaned.csv").write_text("partial")
            raise OSError("Injected export failure")
        with patch("csv_etl.pipeline.export_csvs", side_effect=fail):
            result, _ = self.attempt([ROW])
        self.assertEqual(result.metrics["rows_accepted"], 1)
        self.assertEqual(result.metrics["rows_written"], 0)
        self.assertEqual(result.stages["load"], "failed")
        self.assertFalse((result.artifact_dir / "cleaned.csv").exists())
        self.assertEqual((prior.artifact_dir / "cleaned.csv").read_bytes(), original)

    def test_rename_failure_falls_back_to_report_only(self):
        actual_publish = publish
        calls = []
        def fail_once(staging, final):
            calls.append(final)
            if len(calls) == 1:
                raise OSError("Injected rename failure")
            actual_publish(staging, final)
        with patch("csv_etl.pipeline.publish", side_effect=fail_once):
            result, _ = self.attempt([ROW])
        self.assertEqual(result.status, "Failed")
        self.assertEqual([p.name for p in result.artifact_dir.iterdir()], ["dashboard.html"])

    def test_unwritable_output_and_no_false_report_path(self):
        self.write_rows([ROW])
        with patch("csv_etl.pipeline.prepare_output", side_effect=PermissionError("Injected permission denied")):
            result, logged = self.attempt()
        self.assertEqual(result.status, "Failed")
        self.assertIsNone(result.artifact_dir)
        self.assertIn("could not publish failure report", logged)
        self.assertNotIn("dashboard:", logged)

    def test_corrupt_export_is_not_published(self):
        with patch("csv_etl.pipeline.verify_exports", side_effect=ValueError("Export count mismatch")):
            result, _ = self.attempt([ROW])
        self.assertEqual(result.status, "Failed")
        self.assertEqual(result.metrics["rows_written"], 0)
        self.assertEqual([p.name for p in result.artifact_dir.iterdir()], ["dashboard.html"])


class FixtureTests(unittest.TestCase):
    def test_fixture_shape_and_independent_expectations(self):
        with FIXTURE.open(encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream)
            self.assertEqual(tuple(next(reader)), HEADERS)
            rows = list(reader)
        self.assertEqual(len(rows), 60)
        self.assertTrue(all(len(row) == 10 for row in rows))
        self.assertEqual(rows[50:55], rows[:5])
        self.assertEqual(rows[0][0], rows[1][0])
        self.assertNotEqual(rows[0][3], rows[1][3])
        self.assertEqual(sum(Decimal(row[5]) * Decimal(row[6]) for row in rows[:50]), Decimal("1000"))
        self.assertEqual(sum(Decimal(row[5]) * Decimal(row[6]) * (1 - Decimal(row[7]) / 100) for row in rows[:50]), Decimal("900"))
        self.assertEqual(rows[55][2], "2026-02-30")
        self.assertEqual(rows[56][5], "0")
        self.assertEqual(rows[57][6], "-1.00")
        self.assertEqual(rows[58][7], "101.00")
        self.assertEqual(rows[59][9], "mystery")


if __name__ == "__main__":
    unittest.main()
