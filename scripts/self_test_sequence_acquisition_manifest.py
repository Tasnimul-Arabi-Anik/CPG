#!/usr/bin/env python3
"""Self-test sequence acquisition manifest validation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import tempfile
from pathlib import Path
from typing import Callable, Iterable

import validate_sequence_acquisition_manifest as validator


TEST_COLUMNS = ["test_id", "scenario", "expected_status", "observed_status", "expected_severity", "observed_severity", "status", "notes"]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for sequence acquisition manifest validation.")
    parser.add_argument("--output", required=True, help="Output self-test result TSV.")
    parser.add_argument("--report-output", required=True, help="Output self-test report TSV.")
    return parser.parse_args()


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        digest.update(handle.read())
    return digest.hexdigest()


def case(test_id: str, scenario: str, expected_status: str, expected_severity: str, observed: dict[str, str]) -> dict[str, str]:
    passed = observed.get("status") == expected_status and observed.get("severity") == expected_severity
    return {
        "test_id": test_id,
        "scenario": scenario,
        "expected_status": expected_status,
        "observed_status": observed.get("status", ""),
        "expected_severity": expected_severity,
        "observed_severity": observed.get("severity", ""),
        "status": "pass" if passed else "fail",
        "notes": "NA" if passed else observed.get("message", "mismatch"),
    }


def run_case(root: Path, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    manifest = root / "manifest.tsv"
    write_tsv(manifest, validator.MANIFEST_COLUMNS, rows)
    validation, _report, _errors = validator.validate_manifest(manifest, root)
    return validation


def run_tests() -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="sequence-acquisition-manifest-") as tmp:
        root = Path(tmp)
        raw_dir = root / "data" / "raw" / "genomes"
        raw_dir.mkdir(parents=True)
        fasta = raw_dir / "fixture.fna"
        fasta.write_text(">fixture\nACGTACGT\n", encoding="utf-8")
        digest = sha256(fasta)
        base = {
            "entity_id": "fixture_entity",
            "accession": "NC_000000.1",
            "database": "NCBI RefSeq",
            "source_version": "fixture_snapshot",
            "retrieval_command": "efetch -db nuccore -id NC_000000.1 -format fasta > data/raw/genomes/fixture.fna",
            "retrieved_at": "2026-06-18",
            "expected_path": "data/raw/genomes/fixture.fna",
            "file_size": str(fasta.stat().st_size),
            "sha256": digest,
            "review_status": "reviewed_local_file",
            "notes": "fixture",
        }
        tests.append(case("reviewed_ok", "reviewed local file matches file size and checksum", "checksum_verified", "info", run_case(root, [base])[0]))
        bad_hash = dict(base, entity_id="bad_hash", sha256="0" * 64)
        tests.append(case("sha256_mismatch", "reviewed local file checksum mismatch is blocking", "sha256_mismatch", "error", run_case(root, [bad_hash])[0]))
        missing = dict(base, entity_id="missing_file", expected_path="data/raw/genomes/missing.fna")
        tests.append(case("reviewed_missing", "reviewed file status requires local file presence", "reviewed_file_missing", "error", run_case(root, [missing])[0]))
        pending = dict(base, entity_id="pending", expected_path="data/raw/genomes/pending.fna", file_size="NA", sha256="NA", review_status="pending_retrieval")
        tests.append(case("pending_retrieval", "pending retrieval is warning not blocking", "pending_retrieval", "warning", run_case(root, [pending])[0]))
        outside = dict(base, entity_id="outside", expected_path="tmp/outside.fna")
        tests.append(case("outside_raw", "expected path must remain under data/raw", "invalid_expected_path", "error", run_case(root, [outside])[0]))
    return tests


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [
        {"severity": "info", "item": "sequence_acquisition_manifest_self_test", "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}"}
    ]
    if failed:
        report.append({"severity": "error", "item": "sequence_acquisition_manifest_self_test", "message": "One or more sequence acquisition manifest self-tests failed."})
    else:
        report.append({"severity": "info", "item": "sequence_acquisition_manifest_self_test", "message": "All sequence acquisition manifest self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Sequence acquisition manifest self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
