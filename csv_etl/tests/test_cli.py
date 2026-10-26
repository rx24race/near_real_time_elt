import csv
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from csv_etl import HEADERS
from csv_etl.__main__ import main
from csv_etl.pipeline import publish
from csv_etl.tests.test_pipeline import FIXTURE, ROW


ROOT = Path(__file__).resolve().parents[2]


class CliTests(unittest.TestCase):
    def invoke(self, source, output):
        # Explicitly remove cloud/streaming configuration rather than depend on
        # the developer's configured credentials or a running service.
        environment = {key: value for key, value in os.environ.items() if not key.startswith(
            ("GOOGLE_", "GCP_", "BIGQUERY_", "KAFKA_", "DATAFORM_")
        )}
        return subprocess.run(
            [sys.executable, "-m", "csv_etl", "--input", str(source), "--output-dir", str(output)],
            cwd=ROOT, capture_output=True, text=True, env=environment,
        )

    def test_help(self):
        completed = subprocess.run(
            [sys.executable, "-m", "csv_etl", "--help"], cwd=ROOT,
            capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--input", completed.stdout)
        self.assertIn("--output-dir", completed.stdout)

    def test_input_required(self):
        completed = subprocess.run(
            [sys.executable, "-m", "csv_etl"], cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 2)

    def test_documented_sample_command_without_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            completed = self.invoke(FIXTURE.relative_to(ROOT), Path(directory) / "out")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("Success with warnings", completed.stderr)
            runs = list((Path(directory) / "out").iterdir())
            self.assertEqual(len(runs), 1)
            self.assertTrue((runs[0] / "dashboard.html").exists())

    def test_space_and_apostrophe_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "Owner's input data.csv"
            with source.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(HEADERS)
                writer.writerow(ROW)
            output = Path(directory) / "Owner's output data"
            completed = self.invoke(source, output)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("Success; dashboard:", completed.stderr)
            self.assertEqual(len(list(output.glob("*/cleaned.csv"))), 1)

    def test_default_output_is_package_relative(self):
        with patch("sys.argv", ["csv_etl", "--input", "relative.csv"]), patch(
            "csv_etl.pipeline.run", return_value=SimpleNamespace(status="Success")
        ) as mocked:
            self.assertEqual(main(), 0)
        source, output = mocked.call_args.args
        self.assertEqual(source, Path("relative.csv"))
        self.assertEqual(output.resolve(), ROOT / "csv_etl" / "output")

    def test_missing_input_reports_failure_and_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out"
            completed = self.invoke(Path(directory) / "missing.csv", output)
            self.assertEqual(completed.returncode, 1)
            reports = list(output.glob("*/dashboard.html"))
            self.assertEqual(len(reports), 1)
            self.assertIn(str(reports[0]), completed.stderr)
            self.assertIn('id="run-status">Failed', reports[0].read_text(encoding="utf-8"))
            self.assertEqual(list(output.glob("*/*.csv")), [])

    def test_header_only_and_all_invalid_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "empty.csv"
            for rows in ([], [ROW[:5] + ["0"] + ROW[6:]]):
                with self.subTest(rows=rows):
                    with source.open("w", encoding="utf-8", newline="") as stream:
                        writer = csv.writer(stream)
                        writer.writerow(HEADERS)
                        writer.writerows(rows)
                    output = Path(directory) / ("invalid" if rows else "empty")
                    completed = self.invoke(source, output)
                    self.assertEqual(completed.returncode, 1)
                    html = next(output.glob("*/dashboard.html")).read_text(encoding="utf-8")
                    self.assertIn('data-metric="rows_written"><dt>Rows written</dt><dd>0</dd>', html)
                    self.assertEqual(list(output.glob("*/*.csv")), [])

    def test_actual_unusable_output_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "not-a-directory"
            output.write_text("preserve this file")
            completed = self.invoke(FIXTURE, output)
            self.assertEqual(completed.returncode, 1)
            self.assertIn("could not publish failure report", completed.stderr)
            self.assertNotIn("dashboard:", completed.stderr)
            self.assertEqual(output.read_text(), "preserve this file")

    def test_cli_export_and_rename_errors_return_failure_with_honest_report(self):
        for operation in ("export_csvs", "publish"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "out"
                calls = []
                def fail_once(*args):
                    calls.append(args)
                    if len(calls) == 1:
                        raise OSError("Injected " + operation + " failure")
                    return publish(*args)
                with patch("sys.argv", ["csv_etl", "--input", str(FIXTURE), "--output-dir", str(output)]), patch(
                    "csv_etl.pipeline." + operation, side_effect=fail_once
                ), self.assertLogs("csv_etl.pipeline", level="INFO") as logged:
                    code = main()
                self.assertEqual(code, 1)
                reports = list(output.glob("*/dashboard.html"))
                self.assertEqual(len(reports), 1)
                html = reports[0].read_text(encoding="utf-8")
                self.assertIn('id="run-status">Failed', html)
                self.assertIn('data-metric="rows_accepted"><dt>Rows accepted</dt><dd>50</dd>', html)
                self.assertIn('data-metric="rows_written"><dt>Rows written</dt><dd>0</dd>', html)
                self.assertIn("failure dashboard:", "\n".join(logged.output))
                self.assertEqual(list(output.glob("*/*.csv")), [])

    def test_report_write_failure_does_not_claim_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out"
            with patch("sys.argv", ["csv_etl", "--input", str(FIXTURE), "--output-dir", str(output)]), patch(
                "pathlib.Path.write_text", side_effect=PermissionError("Injected report write failure")
            ), self.assertLogs("csv_etl.pipeline", level="INFO") as logged:
                code = main()
            self.assertEqual(code, 1)
            self.assertIn("could not publish failure report", "\n".join(logged.output))
            self.assertNotIn("dashboard:", "\n".join(logged.output))
            self.assertEqual(list(output.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
