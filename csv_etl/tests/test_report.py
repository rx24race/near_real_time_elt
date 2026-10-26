import tempfile
import unittest
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

from csv_etl.pipeline import RunResult, run
from csv_etl.report import render_report
from csv_etl.tests.test_pipeline import FIXTURE, HEADERS, ROW
import csv


class HtmlAudit(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.table_rows = {}
        self.current_table = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.tags.append((tag, attributes))
        if tag == "table":
            self.current_table = attributes.get("id")
            self.table_rows[self.current_table] = 0
        if tag == "tr" and self.current_table:
            self.table_rows[self.current_table] += 1

    def handle_endtag(self, tag):
        if tag == "table":
            self.current_table = None


class ReportTests(unittest.TestCase):
    def result(self, **kwargs):
        result = RunResult(source="orders.csv", **kwargs)
        result.ended_at = "2026-01-01T00:00:01+00:00"
        result.duration_seconds = 1.25
        return result

    def test_core_metadata_status_and_stages(self):
        for status in ("Success", "Success with warnings", "Failed"):
            with self.subTest(status=status):
                result = self.result(status=status)
                result.stages["extract"] = "complete"
                result.stages["validate"] = "failed" if status == "Failed" else "complete"
                html = render_report(result)
                self.assertIn(f'id="run-status">{status}</span>', html)
                self.assertIn(result.run_id, html)
                self.assertIn("1.250 seconds", html)
                self.assertIn("not run", html)
                self.assertIn("Unavailable", html)
                self.assertIn('data-metric="rows_written"><dt>Rows written</dt><dd>0</dd>', html)

    def test_accounting_and_real_fixture_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertLogs("csv_etl.pipeline", level="INFO"):
                result = run(FIXTURE, Path(directory))
            html = (result.artifact_dir / "dashboard.html").read_text(encoding="utf-8")
        self.assertEqual(result.status, "Success with warnings")
        self.assertIn("60 read = 50 accepted + 5 duplicate copies + 5 rejected", html)
        self.assertIn('data-metric="rows_written"><dt>Rows written</dt><dd>50</dd>', html)
        self.assertIn('data-category="home" data-net-amount="882.00"', html)
        self.assertIn('data-category="Unknown" data-net-amount="18.00"', html)
        self.assertIn("order_date_invalid", html)
        self.assertEqual(HtmlAudit(html).table_rows, {"accepted-preview": 11, "rejected-preview": 6})

    def test_corrections_only_warnings(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.csv"
            with source.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(HEADERS)
                row = ROW.copy()
                row[9] = "PAID"
                writer.writerow(row)
            with self.assertLogs("csv_etl.pipeline", level="INFO"):
                result = run(source, Path(directory) / "out")
            self.assertEqual(result.status, "Success with warnings")
            self.assertEqual(result.metrics["rows_rejected"], 0)
            self.assertEqual(result.metrics["corrected_records"], 1)

    def test_failure_preserves_unavailable_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertLogs("csv_etl.pipeline", level="INFO"):
                result = run(Path(directory) / "missing.csv", Path(directory) / "out")
            html = (result.artifact_dir / "dashboard.html").read_text(encoding="utf-8")
        self.assertEqual(result.status, "Failed")
        self.assertIn("Run failed", html)
        self.assertIn("No cleaned CSV was published", html)
        self.assertIn("classification did not finish", html)
        self.assertIn("not run", html)

    def test_preview_limits_and_no_external_assets(self):
        result = self.result(status="Success")
        row = dict(zip(HEADERS, ROW))
        result.accepted_preview = [dict(row, source_record_number=n, gross_amount=Decimal("20"), net_amount=Decimal("18")) for n in range(1, 16)]
        result.rejected_preview = [dict(row, source_record_number=n, rejection_reasons="example") for n in range(16, 31)]
        result.metrics.update(rows_accepted=15, rows_rejected=15)
        audit = HtmlAudit(render_report(result))
        self.assertEqual(audit.table_rows, {"accepted-preview": 11, "rejected-preview": 11})
        for tag, attributes in audit.tags:
            self.assertNotIn(tag, ("script", "link", "img", "iframe"))
            self.assertFalse(any(key in attributes for key in ("src", "href")))

    def test_zero_empty_and_unavailable_chart_states(self):
        result = self.result()
        result.categories = [{"category": "zero", "net_amount": Decimal("0.00")}]
        html = render_report(result)
        self.assertIn('style="width:0.0%"', html)
        self.assertIn('data-net-amount="0.00"', html)
        result.categories, result.issues = [], []
        result.accepted_preview, result.rejected_preview = [], []
        html = render_report(result)
        self.assertIn("No accepted category amounts", html)
        self.assertIn("No rejected-row issues", html)
        self.assertIn("No accepted records", html)
        self.assertIn("No rejected records", html)

    def test_untrusted_values_names_and_errors_are_escaped(self):
        payload = '</style><script>alert("x")</script><img src="https://example.invalid/" onerror="alert(1)">'
        result = self.result()
        result.source = payload
        result.error = payload + " & quoted 'error'"
        result.categories = [{"category": payload, "net_amount": Decimal("18.00")}]
        result.issues = [{"reason": payload, "row_count": 1}]
        row = dict(zip(HEADERS, ROW))
        row["product_name"] = payload
        result.accepted_preview = [dict(row, source_record_number=1, gross_amount=20, net_amount=18)]
        result.rejected_preview = [dict(row, source_record_number=2, rejection_reasons=payload)]
        html = render_report(result)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&quot;x&quot;", html)
        audit = HtmlAudit(html)
        for tag, attributes in audit.tags:
            self.assertNotIn(tag, ("script", "img", "iframe", "link", "object", "embed"))
            self.assertFalse(any(key.lower().startswith("on") for key in attributes))
            self.assertFalse(any(key in attributes for key in ("src", "href")))
            if "style" in attributes:
                self.assertRegex(attributes["style"], r"^width:[0-9]+\.[0-9]%$")
        self.assertEqual(sum(tag == "style" for tag, _ in audit.tags), 2)

    def test_chart_rejects_untrusted_or_nonfinite_geometry(self):
        for amount in (Decimal("NaN"), Decimal("Infinity"), Decimal("-1"), '0%;background:url(https://example.invalid/)'):
            with self.subTest(amount=amount):
                result = self.result()
                result.categories = [{"category": "test", "net_amount": amount}]
                html = render_report(result)
                self.assertIn("invalid numeric totals", html)
                self.assertNotIn('class="bar" style=', html)
                self.assertNotIn("example.invalid", html)

    def test_html_shaped_values_survive_real_sql_pipeline_safely(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.csv"
            row = ROW.copy()
            row[3] = '<script>alert("x")</script>'
            with source.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(HEADERS)
                writer.writerow(row)
            with self.assertLogs("csv_etl.pipeline", level="INFO"):
                result = run(source, Path(directory) / "out")
            html = (result.artifact_dir / "dashboard.html").read_text(encoding="utf-8")
        self.assertEqual(result.status, "Success")
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("script", [tag for tag, _ in HtmlAudit(html).tags])


if __name__ == "__main__":
    unittest.main()
