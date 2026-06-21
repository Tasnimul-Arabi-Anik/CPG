#!/usr/bin/env python3
"""Self-test sequence acquisition planning for local and ZIP-member raw paths."""

from __future__ import annotations

import argparse
import csv
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable

import plan_sequence_acquisition as planner


TEST_COLUMNS = ["test_id", "scenario", "expected_status", "observed_status", "status", "notes"]
REPORT_COLUMNS = ["severity", "item", "message"]
MANIFEST_COLUMNS = ["genome_id", "record_type", "accession", "source", "validation_status", "raw_sequence_path", "notes"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for sequence acquisition planning.")
    parser.add_argument("--output", required=True, help="Output self-test TSV.")
    parser.add_argument("--report-output", required=True, help="Output self-test report TSV.")
    return parser.parse_args()


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def result(test_id: str, scenario: str, expected: str, observed: str, notes: str = "NA") -> dict[str, str]:
    passed = expected == observed
    return {
        "test_id": test_id,
        "scenario": scenario,
        "expected_status": expected,
        "observed_status": observed,
        "status": "pass" if passed else "fail",
        "notes": "NA" if passed else notes,
    }


def run_tests() -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="sequence-acquisition-test-") as tmp:
        root = Path(tmp)
        archive_path = root / "data" / "archives" / "genomes.zip"
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("fasta_files/genomeA.fasta", ">genomeA\nACGT\n")
        manifest = root / "manifest.tsv"
        rows = [
            {
                "genome_id": "genomeA",
                "record_type": "host",
                "accession": "NA",
                "source": "fixture",
                "validation_status": "include",
                "raw_sequence_path": "data/archives/genomes.zip::fasta_files/genomeA.fasta",
                "notes": "fixture archive member",
            },
            {
                "genome_id": "genomeB",
                "record_type": "host",
                "accession": "NA",
                "source": "fixture",
                "validation_status": "include",
                "raw_sequence_path": "data/archives/genomes.zip::../genomeB.fasta",
                "notes": "unsafe archive member",
            },
        ]
        write_tsv(manifest, MANIFEST_COLUMNS, rows)
        plan, report = planner.plan_sequences(manifest, root, root / "data" / "raw" / "genomes")
        by_id = {row["genome_id"]: row for row in plan}
        observed = by_id["genomeA"].get("acquisition_status", "")
        tests.append(result("zip_member_available", "reviewed ZIP member is treated as local sequence", "local_sequence_available", observed))
        observed = by_id["genomeA"].get("raw_sequence_exists", "")
        tests.append(result("zip_member_exists_flag", "ZIP member sets raw_sequence_exists true", "true", observed))
        observed = by_id["genomeB"].get("acquisition_status", "")
        tests.append(result("unsafe_zip_member_not_available", "unsafe ZIP member is not treated as local sequence", "configured_path_missing_no_accession", observed))
        observed = "ok" if any(row.get("item") == "configured_path_missing_no_accession" for row in report) else "missing_report"
        tests.append(result("missing_reported", "unsafe/missing locator remains acquisition-needed", "ok", observed))
    return tests


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [
        {
            "severity": "info",
            "item": "sequence_acquisition_self_test",
            "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}",
        }
    ]
    if failed:
        report.append({"severity": "error", "item": "sequence_acquisition_self_test", "message": "One or more sequence acquisition self-tests failed."})
    else:
        report.append({"severity": "info", "item": "sequence_acquisition_self_test", "message": "All sequence acquisition self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Sequence acquisition self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
