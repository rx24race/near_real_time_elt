"""Cross-component checks: SQL -> CSV -> HTML and isolated repeated CLI runs."""

import csv
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from csv_etl.pipeline import run
from csv_etl.tests.test_pipeline import FIXTURE
from csv_etl.tests.test_report import HtmlAudit


ROOT = Path(__file__).resolve().parents[2]


class IntegrationTests(unittest.TestCase):
    def test_no_credentials_or_network_and_csv_report_agreement(self):
        environment = {key: value for key, value in os.environ.items() if not key.startswith(
            ("GOOGLE_", "GCP_", "BIGQUERY_", "KAFKA_", "DATAFORM_")
        )}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, environment, clear=True), patch(
            "socket.create_connection", side_effect=AssertionError("Network must not be used")
        ), patch("subprocess.run", side_effect=AssertionError("No external service commands")):
            with self.assertLogs("csv_etl.pipeline", level="INFO"):
                result = run(FIXTURE, Path(directory))
            self.assertEqual(result.status, "Success with warnings")
            with (result.artifact_dir / "cleaned.csv").open(encoding="utf-8", newline="") as stream:
                accepted = list(csv.DictReader(stream))
            with (result.artifact_dir / "rejected.csv").open(encoding="utf-8", newline="") as stream:
                rejected = list(csv.DictReader(stream))
            html = (result.artifact_dir / "dashboard.html").read_text(encoding="utf-8")
        self.assertEqual(len(accepted), 50)
        self.assertEqual(len(rejected), 5)
        self.assertEqual(result.metrics["rows_read"], len(accepted) + len(rejected) + result.metrics["duplicates_removed"])
        totals = {}
        for row in accepted:
            totals[row["category"]] = totals.get(row["category"], Decimal(0)) + Decimal(row["net_amount"])
        displayed = {
            attrs["data-category"]: Decimal(attrs["data-net-amount"])
            for _, attrs in HtmlAudit(html).tags if "data-category" in attrs
        }
        self.assertEqual(displayed, totals)
        self.assertEqual(sum(totals.values()), Decimal("900.00"))
        self.assertEqual(HtmlAudit(html).table_rows, {"accepted-preview": 11, "rejected-preview": 6})
        self.assertIn("60 read = 50 accepted + 5 duplicate copies + 5 rejected", html)

    def test_two_cli_successes_then_failure_have_no_stale_or_partial_results(self):
        before = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "out"
            command = [sys.executable, "-m", "csv_etl", "--output-dir", str(parent), "--input"]
            for _ in range(2):
                completed = subprocess.run(command + [str(FIXTURE)], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(completed.returncode, 0, completed.stderr)
            successes = sorted(parent.iterdir())
            self.assertEqual(len(successes), 2)
            original = {path: path.read_bytes() for run_dir in successes for path in run_dir.iterdir()}
            self.assertEqual((successes[0] / "cleaned.csv").read_bytes(), (successes[1] / "cleaned.csv").read_bytes())
            failed = subprocess.run(command + [str(Path(directory) / "missing.csv")], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(failed.returncode, 1)
            final_dirs = list(parent.iterdir())
            self.assertEqual(len(final_dirs), 3)
            self.assertTrue(all(not path.name.startswith(".") for path in final_dirs))
            failure_dir = next(path for path in final_dirs if path not in successes)
            self.assertEqual([path.name for path in failure_dir.iterdir()], ["dashboard.html"])
            self.assertIn('id="run-status">Failed', (failure_dir / "dashboard.html").read_text(encoding="utf-8"))
            for path, contents in original.items():
                self.assertEqual(path.read_bytes(), contents)
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()
