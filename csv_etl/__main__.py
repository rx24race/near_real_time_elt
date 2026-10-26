"""Run with python -m csv_etl from the repository root."""

import argparse
import logging
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Transform an order-line CSV using DuckDB SQL.")
    parser.add_argument("--input", required=True, type=Path, help="UTF-8 input CSV path")
    parser.add_argument(
        "--output-dir", type=Path, default=Path(__file__).parent / "output",
        help="Parent for uniquely identified run directories (default: csv_etl/output)",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # Keep CLI help available even before the isolated runtime dependency is installed.
    from csv_etl.pipeline import run

    result = run(args.input, args.output_dir)
    return 1 if result.status == "Failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
