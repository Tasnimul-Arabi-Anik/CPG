#!/usr/bin/env python3
"""Self-test PhageHostLearn external file validator."""

from __future__ import annotations

import argparse
import csv
import hashlib
import tempfile
from pathlib import Path
from typing import Iterable

import validate_phagehostlearn_external_files as validator


TEST_COLUMNS = ["test_id", "scenario", "expected_status", "observed_status", "status", "notes"]
REPORT_COLUMNS = ["severity", "item", "message"]
MANIFEST_COLUMNS = validator.MANIFEST_COLUMNS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run self-tests for the PhageHostLearn external file validator.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--report-output", required=True)
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


def md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest_row(file_id: str, expected_path: str, data: bytes | None = None, bad_md5: bool = False) -> dict[str, str]:
    payload = data if data is not None else b"fixture"
    return {
        "file_id": file_id,
        "source_database": "fixture_db",
        "source_record": "fixture_record",
        "source_version": "fixture_version",
        "retrieval_url": "https://example.invalid/file",
        "retrieval_command": "curl -L -o fixture https://example.invalid/file",
        "expected_path": expected_path,
        "expected_size_bytes": str(len(payload)),
        "expected_md5": "0" * 32 if bad_md5 else md5(payload),
        "expected_sha256": sha256(payload),
        "required_for": "fixture",
        "notes": "fixture",
    }


def run_validation(root: Path, rows: list[dict[str, str]], require_present: bool = False) -> tuple[int, list[dict[str, str]]]:
    manifest = root / "manifest.tsv"
    validation = root / "validation.tsv"
    report = root / "report.tsv"
    write_tsv(manifest, MANIFEST_COLUMNS, rows)
    validation_rows, report_rows, errors = validator.validate_manifest(manifest, root.resolve(), require_present)
    write_tsv(validation, validator.VALIDATION_COLUMNS, validation_rows)
    write_tsv(report, validator.REPORT_COLUMNS, report_rows)
    return (1 if errors else 0), validation_rows


def run_tests() -> list[dict[str, str]]:
    tests: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="phagehostlearn-files-") as tmp:
        root = Path(tmp)
        file_path = root / "data" / "metadata" / "external" / "phagehostlearn" / "fixture.csv"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = b"a,b\n1,2\n"
        file_path.write_bytes(payload)
        rc, rows = run_validation(root, [manifest_row("ok", "data/metadata/external/phagehostlearn/fixture.csv", payload)])
        tests.append(result("checksum_verified", "matching local file passes", "checksum_verified", rows[0]["status"] if rc == 0 else "failed"))

        rc, rows = run_validation(root, [manifest_row("missing", "data/metadata/external/phagehostlearn/missing.csv", b"missing")])
        observed = rows[0]["status"] + ":" + rows[0]["severity"]
        tests.append(result("missing_warns", "missing local file is warning by default", "local_file_missing:warning", observed))

        rc, rows = run_validation(root, [manifest_row("missing", "data/metadata/external/phagehostlearn/missing.csv", b"missing")], require_present=True)
        observed = rows[0]["status"] + ":" + rows[0]["severity"]
        tests.append(result("missing_errors_when_required", "missing local file is error with --require-present", "local_file_missing:error", observed))

        rc, rows = run_validation(root, [manifest_row("badmd5", "data/metadata/external/phagehostlearn/fixture.csv", payload, bad_md5=True)])
        tests.append(result("md5_mismatch", "bad MD5 is blocking", "md5_mismatch", rows[0]["status"]))

        rc, rows = run_validation(root, [manifest_row("badpath", "data/raw/fixture.csv", payload)])
        tests.append(result("invalid_path", "expected path must remain under PhageHostLearn metadata directory", "invalid_expected_path", rows[0]["status"]))
    return tests


def main() -> int:
    args = parse_args()
    rows = run_tests()
    failed = [row for row in rows if row["status"] != "pass"]
    report = [{"severity": "info", "item": "phagehostlearn_external_files_self_test", "message": f"tests={len(rows)}; pass={len(rows) - len(failed)}; fail={len(failed)}"}]
    if failed:
        report.append({"severity": "error", "item": "phagehostlearn_external_files_self_test", "message": "One or more external-file self-tests failed."})
    else:
        report.append({"severity": "info", "item": "phagehostlearn_external_files_self_test", "message": "All external-file self-tests passed."})
    write_tsv(Path(args.output), TEST_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"PhageHostLearn external file self-test complete: {len(rows) - len(failed)} pass, {len(failed)} fail.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
