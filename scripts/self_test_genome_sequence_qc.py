#!/usr/bin/env python3
"""Self-test genome sequence QC, including ZIP-member FASTA paths."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable


TEST_COLUMNS = ["test_id", "scenario", "expected_status", "observed_status", "status", "notes"]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for genome sequence QC.")
    parser.add_argument("--output", required=True, help="Output self-test result TSV.")
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


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


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


def run_qc(root: Path, manifest: Path, thresholds: Path, outdir: Path) -> subprocess.CompletedProcess[str]:
    script = Path(__file__).with_name("00_qc_genome_sequences.py")
    return subprocess.run(
        [
            sys.executable,
            script.as_posix(),
            "--manifest",
            manifest.as_posix(),
            "--thresholds",
            thresholds.as_posix(),
            "--qc-output",
            (outdir / "qc.tsv").as_posix(),
            "--report-output",
            (outdir / "report.tsv").as_posix(),
            "--root",
            root.as_posix(),
        ],
        check=False,
        text=True,
        capture_output=True,
    )


def run_tests() -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="genome-sequence-qc-") as tmp:
        root = Path(tmp)
        archive = root / "sequences.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("members/phageA.fasta", ">phageA\n" + "ATGC" * 25 + "\n")
        thresholds = root / "thresholds.yaml"
        thresholds.write_text(
            "genome_qc:\n"
            "  min_genome_length_bp: 1\n"
            "  max_genome_length_bp: 1000000\n"
            "  max_host_genome_length_bp: 10000000\n"
            "  min_gc_percent: 0\n"
            "  max_gc_percent: 100\n"
            "  max_n_percent: 5\n"
            "  max_ambiguous_percent: 1\n"
            "  metadata_length_tolerance_bp: 0\n"
            "  metadata_gc_tolerance_percent: 1\n",
            encoding="utf-8",
        )
        manifest = root / "manifest.tsv"
        write_tsv(
            manifest,
            ["record_type", "genome_id", "raw_sequence_path", "genome_length", "gc_percent"],
            [
                {
                    "record_type": "phage",
                    "genome_id": "phageA",
                    "raw_sequence_path": "sequences.zip::members/phageA.fasta",
                    "genome_length": "100",
                    "gc_percent": "50",
                }
            ],
        )
        outdir = root / "outputs"
        completed = run_qc(root, manifest, thresholds, outdir)
        rows = read_rows(outdir / "qc.tsv")
        archive_ok = (
            completed.returncode == 0
            and rows[0]["sequence_qc_status"] == "pass"
            and rows[0]["passes_sequence_qc"] == "true"
            and rows[0]["total_length_bp"] == "100"
            and rows[0]["resolved_sequence_path"].endswith("sequences.zip::members/phageA.fasta")
        )
        tests.append(result("zip_member_fasta_passes", "ZIP-member FASTA path is read and QCed", "ok", "ok" if archive_ok else "bad_output"))

        bad_manifest = root / "bad_manifest.tsv"
        write_tsv(
            bad_manifest,
            ["record_type", "genome_id", "raw_sequence_path", "genome_length", "gc_percent"],
            [
                {
                    "record_type": "phage",
                    "genome_id": "badPhage",
                    "raw_sequence_path": "sequences.zip::../bad.fasta",
                    "genome_length": "100",
                    "gc_percent": "50",
                }
            ],
        )
        bad_out = root / "bad_outputs"
        completed = run_qc(root, bad_manifest, thresholds, bad_out)
        bad_rows = read_rows(bad_out / "qc.tsv")
        rejected = completed.returncode != 0 and bad_rows[0]["sequence_qc_status"] == "invalid_sequence_path"
        tests.append(result("zip_member_path_traversal_fails", "Archive member path traversal is rejected", "ok", "ok" if rejected else "bad_output"))
    return tests


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [
        {
            "severity": "info",
            "item": "genome_sequence_qc_self_test",
            "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}",
        }
    ]
    if failed:
        report.append({"severity": "error", "item": "genome_sequence_qc_self_test", "message": "One or more self-tests failed."})
    else:
        report.append({"severity": "info", "item": "genome_sequence_qc_self_test", "message": "All self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Genome sequence QC self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
