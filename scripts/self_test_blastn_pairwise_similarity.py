#!/usr/bin/env python3
"""Self-test BLASTN pairwise similarity generation, including ZIP-member FASTA paths."""

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
    parser = argparse.ArgumentParser(description="Run self-tests for BLASTN pairwise similarity generation.")
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


def make_fake_blastn(path: Path) -> Path:
    script = path / "fake_blastn.py"
    script.write_text(
        """#!/usr/bin/env python3
import sys
from pathlib import Path
args = sys.argv[1:]
query = Path(args[args.index('-query') + 1])
subject = Path(args[args.index('-subject') + 1])
out = Path(args[args.index('-out') + 1])

def length(path):
    total = 0
    for line in path.read_text().splitlines():
        if not line.startswith('>'):
            total += len(line.strip())
    return total
aligned = min(length(query), length(subject))
out.write_text(f'q\\ts\\t97.5\\t{aligned}\\t1\\t{aligned}\\t1\\t{aligned}\\t1e-20\\t100\\n')
""",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | 0o111)
    return script


def run_builder(manifest: Path, sequence_qc: Path, outdir: Path, fake_blastn: Path) -> subprocess.CompletedProcess[str]:
    script = Path(__file__).with_name("build_blastn_pairwise_similarity.py")
    return subprocess.run(
        [
            sys.executable,
            script.as_posix(),
            "--manifest",
            manifest.as_posix(),
            "--sequence-qc",
            sequence_qc.as_posix(),
            "--output",
            (outdir / "pairwise.tsv").as_posix(),
            "--report-output",
            (outdir / "report.tsv").as_posix(),
            "--blastn",
            fake_blastn.as_posix(),
            "--min-hsp-length",
            "5",
        ],
        check=False,
        text=True,
        capture_output=True,
    )


def run_tests() -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="blastn-pairwise-") as tmp:
        root = Path(tmp)
        fake_blastn = make_fake_blastn(root)
        archive = root / "phages.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("members/phageA.fasta", ">phageA\n" + "ATGC" * 5 + "\n")
            zf.writestr("members/phageB.fasta", ">phageB\n" + "ATGC" * 5 + "\n")
        manifest = root / "manifest.tsv"
        write_tsv(
            manifest,
            ["record_type", "genome_id", "raw_sequence_path", "validation_status"],
            [
                {"record_type": "phage", "genome_id": "phageA", "raw_sequence_path": f"{archive}::members/phageA.fasta", "validation_status": "pass"},
                {"record_type": "phage", "genome_id": "phageB", "raw_sequence_path": f"{archive}::members/phageB.fasta", "validation_status": "pass"},
            ],
        )
        qc = root / "qc.tsv"
        write_tsv(
            qc,
            ["genome_id", "resolved_sequence_path", "sequence_qc_status", "passes_sequence_qc"],
            [
                {"genome_id": "phageA", "resolved_sequence_path": f"{archive}::members/phageA.fasta", "sequence_qc_status": "pass", "passes_sequence_qc": "true"},
                {"genome_id": "phageB", "resolved_sequence_path": f"{archive}::members/phageB.fasta", "sequence_qc_status": "pass", "passes_sequence_qc": "true"},
            ],
        )
        outdir = root / "out"
        completed = run_builder(manifest, qc, outdir, fake_blastn)
        rows = read_rows(outdir / "pairwise.tsv")
        report_rows = read_rows(outdir / "report.tsv")
        zip_ok = (
            completed.returncode == 0
            and len(rows) == 1
            and rows[0]["genome_id_1"] == "phageA"
            and rows[0]["genome_id_2"] == "phageB"
            and rows[0]["identity_percent"] == "97.500"
            and rows[0]["coverage_percent"] == "100.000"
            and any(row["item"] == "zip_member_records" for row in report_rows)
        )
        tests.append(result("zip_member_pairwise_passes", "ZIP-member FASTA paths are materialized for BLASTN", "ok", "ok" if zip_ok else "bad_output"))

        bad_qc = root / "bad_qc.tsv"
        write_tsv(
            bad_qc,
            ["genome_id", "resolved_sequence_path", "sequence_qc_status", "passes_sequence_qc"],
            [
                {"genome_id": "phageA", "resolved_sequence_path": f"{archive}::../bad.fasta", "sequence_qc_status": "pass", "passes_sequence_qc": "true"},
                {"genome_id": "phageB", "resolved_sequence_path": f"{archive}::members/phageB.fasta", "sequence_qc_status": "pass", "passes_sequence_qc": "true"},
            ],
        )
        bad_out = root / "bad_out"
        completed = run_builder(manifest, bad_qc, bad_out, fake_blastn)
        bad_rows = read_rows(bad_out / "pairwise.tsv")
        bad_report = read_rows(bad_out / "report.tsv")
        rejected = completed.returncode == 0 and len(bad_rows) == 0 and any("Archive member path is not allowed" in row["message"] for row in bad_report)
        tests.append(result("zip_member_path_traversal_skipped", "Archive member path traversal is rejected before BLASTN", "ok", "ok" if rejected else "bad_output"))
    return tests


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [
        {
            "severity": "info",
            "item": "blastn_pairwise_similarity_self_test",
            "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}",
        }
    ]
    if failed:
        report.append({"severity": "error", "item": "blastn_pairwise_similarity_self_test", "message": "One or more self-tests failed."})
    else:
        report.append({"severity": "info", "item": "blastn_pairwise_similarity_self_test", "message": "All self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"BLASTN pairwise similarity self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
