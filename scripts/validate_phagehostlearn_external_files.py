#!/usr/bin/env python3
"""Validate local PhageHostLearn external files against a reviewed checksum manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from pathlib import Path
from typing import Iterable


MANIFEST_COLUMNS = [
    "file_id",
    "source_database",
    "source_record",
    "source_version",
    "retrieval_url",
    "retrieval_command",
    "expected_path",
    "expected_size_bytes",
    "expected_md5",
    "expected_sha256",
    "required_for",
    "notes",
]
VALIDATION_COLUMNS = [
    "file_id",
    "expected_path",
    "path_exists",
    "expected_size_bytes",
    "observed_size_bytes",
    "expected_md5",
    "observed_md5",
    "expected_sha256",
    "observed_sha256",
    "status",
    "severity",
    "message",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
HEX32 = re.compile(r"^[0-9a-fA-F]{32}$")
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


class PhageHostLearnFileValidationError(Exception):
    """Raised when the file manifest is malformed."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate local PhageHostLearn files against expected checksums.")
    parser.add_argument("--manifest", default="data/metadata/external/phagehostlearn/phagehostlearn_file_manifest.tsv")
    parser.add_argument("--validation-output", required=True)
    parser.add_argument("--report-output", required=True)
    parser.add_argument("--root", default=".")
    parser.add_argument("--require-present", action="store_true", help="Treat missing local files as errors instead of warnings.")
    parser.add_argument("--require-sha256", action="store_true", help="Treat missing expected_sha256 values as errors.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: object) -> bool:
    return normalize(value) in MISSING


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def display(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise PhageHostLearnFileValidationError(f"file manifest does not exist: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: normalize(value) for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def digest_file(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def result(row: dict[str, str], root: Path, status: str, severity: str, message: str, path_exists: bool, observed_size: str = "", observed_md5: str = "", observed_sha256: str = "") -> dict[str, str]:
    return {
        "file_id": row.get("file_id", ""),
        "expected_path": row.get("expected_path", ""),
        "path_exists": str(path_exists).lower(),
        "expected_size_bytes": row.get("expected_size_bytes", ""),
        "observed_size_bytes": observed_size,
        "expected_md5": row.get("expected_md5", ""),
        "observed_md5": observed_md5,
        "expected_sha256": row.get("expected_sha256", ""),
        "observed_sha256": observed_sha256,
        "status": status,
        "severity": severity,
        "message": message,
    }


def validate_row(row: dict[str, str], root: Path, seen_ids: set[str], seen_paths: set[str], require_present: bool, require_sha256: bool) -> dict[str, str]:
    required_columns = [column for column in MANIFEST_COLUMNS if column != "expected_sha256"]
    missing = [column for column in required_columns if is_missing(row.get(column, ""))]
    if missing:
        return result(row, root, "invalid_missing_required", "error", "Missing required fields: " + ";".join(missing), False)
    file_id = row["file_id"]
    if file_id in seen_ids:
        return result(row, root, "invalid_duplicate_file_id", "error", f"Duplicate file_id: {file_id}", False)
    seen_ids.add(file_id)
    expected_path = resolve(root, row["expected_path"])
    expected_display = display(root, expected_path)
    if expected_display in seen_paths:
        return result(row, root, "invalid_duplicate_expected_path", "error", f"Duplicate expected_path: {expected_display}", expected_path.exists())
    seen_paths.add(expected_display)
    if not expected_display.startswith("data/metadata/external/phagehostlearn/"):
        return result(row, root, "invalid_expected_path", "error", "expected_path must be under data/metadata/external/phagehostlearn/", expected_path.exists())
    if not row["expected_size_bytes"].isdigit():
        return result(row, root, "invalid_expected_size", "error", "expected_size_bytes must be an integer", expected_path.exists())
    if not HEX32.match(row["expected_md5"]):
        return result(row, root, "invalid_expected_md5", "error", "expected_md5 must be a 32-character hex digest", expected_path.exists())
    expected_sha256 = row.get("expected_sha256", "")
    if is_missing(expected_sha256) and require_sha256:
        return result(row, root, "missing_expected_sha256", "error", "expected_sha256 is required by this validation mode", expected_path.exists())
    if not is_missing(expected_sha256) and not HEX64.match(expected_sha256):
        return result(row, root, "invalid_expected_sha256", "error", "expected_sha256 must be a 64-character hex digest or NA pending local review", expected_path.exists())
    if not expected_path.exists():
        severity = "error" if require_present else "warning"
        return result(row, root, "local_file_missing", severity, "Local file is not present; retrieve it with retrieval_command before benchmark review.", False)
    observed_size = str(expected_path.stat().st_size)
    observed_md5 = digest_file(expected_path, "md5")
    observed_sha256 = digest_file(expected_path, "sha256")
    if observed_size != row["expected_size_bytes"]:
        return result(row, root, "size_mismatch", "error", "Observed file size does not match expected_size_bytes.", True, observed_size, observed_md5, observed_sha256)
    if observed_md5.lower() != row["expected_md5"].lower():
        return result(row, root, "md5_mismatch", "error", "Observed MD5 does not match expected_md5.", True, observed_size, observed_md5, observed_sha256)
    if is_missing(expected_sha256):
        return result(row, root, "sha256_pending_local_review", "warning", "Local file exists and matches expected size and MD5; expected_sha256 is pending local review.", True, observed_size, observed_md5, observed_sha256)
    if observed_sha256.lower() != expected_sha256.lower():
        return result(row, root, "sha256_mismatch", "error", "Observed SHA-256 does not match expected_sha256.", True, observed_size, observed_md5, observed_sha256)
    return result(row, root, "checksum_verified", "info", "Local file exists and matches expected size, MD5, and SHA-256.", True, observed_size, observed_md5, observed_sha256)


def validate_manifest(path: Path, root: Path, require_present: bool, require_sha256: bool = False) -> tuple[list[dict[str, str]], list[dict[str, str]], int]:
    fields, rows = read_tsv(path)
    missing_columns = [column for column in MANIFEST_COLUMNS if column not in fields]
    if missing_columns:
        raise PhageHostLearnFileValidationError("file manifest missing columns: " + ";".join(missing_columns))
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    validation = [validate_row(row, root, seen_ids, seen_paths, require_present, require_sha256) for row in rows]
    counts: dict[str, int] = {}
    for row in validation:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    report = [{"severity": "info", "item": "phagehostlearn_external_files", "message": f"validated_rows={len(validation)}"}]
    for status, count in sorted(counts.items()):
        severity = "error" if any(row["status"] == status and row["severity"] == "error" for row in validation) else "warning" if any(row["status"] == status and row["severity"] == "warning" for row in validation) else "info"
        report.append({"severity": severity, "item": status, "message": f"{count} row(s)."})
    report.append({"severity": "info", "item": "claim_boundary", "message": "Checksum verification supports benchmark-file provenance only; it does not approve assay rows or biological claims."})
    errors = sum(1 for row in validation if row["severity"] == "error")
    return validation, report, errors


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    manifest = resolve(root, args.manifest)
    try:
        validation, report, errors = validate_manifest(manifest, root, args.require_present, args.require_sha256)
    except PhageHostLearnFileValidationError as exc:
        validation = []
        report = [{"severity": "error", "item": "phagehostlearn_external_files", "message": str(exc)}]
        errors = 1
    write_tsv(Path(args.validation_output), VALIDATION_COLUMNS, validation)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"PhageHostLearn external file validation complete: rows={len(validation)}; errors={errors}.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
