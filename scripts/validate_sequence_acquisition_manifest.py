#!/usr/bin/env python3
"""Validate reviewed raw-sequence acquisition manifests without downloading data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from pathlib import Path
from typing import Iterable


MANIFEST_COLUMNS = [
    "entity_id",
    "accession",
    "database",
    "source_version",
    "retrieval_command",
    "retrieved_at",
    "expected_path",
    "file_size",
    "sha256",
    "review_status",
    "notes",
]
VALIDATION_COLUMNS = [
    "entity_id",
    "accession",
    "expected_path",
    "review_status",
    "path_exists",
    "expected_file_size",
    "observed_file_size",
    "expected_sha256",
    "observed_sha256",
    "status",
    "severity",
    "message",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
REVIEWED_STATUSES = {"reviewed_local_file", "checksum_verified"}
PENDING_STATUSES = {"pending_retrieval", "pending_checksum", "manual_review_required"}
ALLOWED_STATUSES = REVIEWED_STATUSES | PENDING_STATUSES
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class AcquisitionManifestError(Exception):
    """Raised for malformed acquisition manifests."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a reviewed raw sequence acquisition manifest.")
    parser.add_argument("--manifest", required=True, help="Reviewed sequence acquisition manifest TSV.")
    parser.add_argument("--validation-output", required=True, help="Per-row validation output TSV.")
    parser.add_argument("--report-output", required=True, help="Summary report TSV.")
    parser.add_argument("--root", default=".", help="Repository root for resolving relative expected_path values.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: object) -> bool:
    return normalize(value) in MISSING


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise AcquisitionManifestError(f"Acquisition manifest does not exist: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: normalize(value) for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_report(report: list[dict[str, str]], severity: str, item: str, message: str) -> None:
    report.append({"severity": severity, "item": item, "message": message})


def row_result(
    row: dict[str, str],
    root: Path,
    status: str,
    severity: str,
    message: str,
    path_exists: bool,
    observed_file_size: str = "",
    observed_sha256: str = "",
) -> dict[str, str]:
    return {
        "entity_id": row.get("entity_id", ""),
        "accession": row.get("accession", ""),
        "expected_path": row.get("expected_path", ""),
        "review_status": row.get("review_status", ""),
        "path_exists": str(path_exists).lower(),
        "expected_file_size": row.get("file_size", ""),
        "observed_file_size": observed_file_size,
        "expected_sha256": row.get("sha256", ""),
        "observed_sha256": observed_sha256,
        "status": status,
        "severity": severity,
        "message": message,
    }


def validate_one(row: dict[str, str], root: Path, seen: set[str]) -> dict[str, str]:
    entity_id = row.get("entity_id", "")
    accession = row.get("accession", "")
    expected_path_text = row.get("expected_path", "")
    review_status = row.get("review_status", "")

    missing_required = [column for column in MANIFEST_COLUMNS if column not in {"notes", "file_size", "sha256"} and is_missing(row.get(column, ""))]
    if missing_required:
        return row_result(row, root, "invalid_missing_required", "error", "Missing required columns: " + ";".join(missing_required), False)
    if entity_id in seen:
        return row_result(row, root, "invalid_duplicate_entity_id", "error", f"Duplicate entity_id: {entity_id}", False)
    seen.add(entity_id)
    if review_status not in ALLOWED_STATUSES:
        return row_result(row, root, "invalid_review_status", "error", f"Unsupported review_status: {review_status}", False)
    if not DATE_RE.match(row.get("retrieved_at", "")):
        return row_result(row, root, "invalid_retrieved_at", "error", "retrieved_at must use YYYY-MM-DD", False)

    expected_path = resolve_path(root, expected_path_text)
    path_exists = expected_path.exists()
    if not display_path(root, expected_path).startswith("data/raw/"):
        return row_result(row, root, "invalid_expected_path", "error", "expected_path must be under data/raw/", path_exists)

    observed_size = str(expected_path.stat().st_size) if path_exists else ""
    observed_hash = sha256_file(expected_path) if path_exists else ""

    if review_status in REVIEWED_STATUSES:
        if not path_exists:
            return row_result(row, root, "reviewed_file_missing", "error", "review_status requires expected_path to exist locally", False)
        if not row.get("file_size", "").isdigit():
            return row_result(row, root, "invalid_file_size", "error", "file_size must be an integer byte count for reviewed files", True, observed_size, observed_hash)
        if row.get("file_size") != observed_size:
            return row_result(row, root, "file_size_mismatch", "error", "file_size does not match local file", True, observed_size, observed_hash)
        if not re.fullmatch(r"[0-9a-fA-F]{64}", row.get("sha256", "")):
            return row_result(row, root, "invalid_sha256", "error", "sha256 must be a 64-character hex digest for reviewed files", True, observed_size, observed_hash)
        if row.get("sha256", "").lower() != observed_hash.lower():
            return row_result(row, root, "sha256_mismatch", "error", "sha256 does not match local file", True, observed_size, observed_hash)
        return row_result(row, root, "checksum_verified", "info", "Reviewed local file exists and matches file_size and sha256.", True, observed_size, observed_hash)

    if review_status == "pending_checksum" and not path_exists:
        return row_result(row, root, "pending_checksum_file_missing", "warning", "File is pending checksum review but expected_path is not present in this checkout.", False)
    if review_status == "pending_checksum" and path_exists:
        return row_result(row, root, "pending_checksum", "warning", "File exists but checksum review is still pending.", True, observed_size, observed_hash)
    if review_status == "pending_retrieval":
        return row_result(row, root, "pending_retrieval", "warning", "Sequence retrieval is pending; raw file is not required yet.", path_exists, observed_size, observed_hash)
    return row_result(row, root, "manual_review_required", "warning", "Manual review is required before production use.", path_exists, observed_size, observed_hash)


def validate_manifest(path: Path, root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], int]:
    fieldnames, rows = read_tsv(path)
    report: list[dict[str, str]] = []
    missing_columns = [column for column in MANIFEST_COLUMNS if column not in fieldnames]
    if missing_columns:
        raise AcquisitionManifestError("Acquisition manifest missing columns: " + ";".join(missing_columns))
    if not rows:
        add_report(report, "warning", "sequence_acquisition_manifest", "Manifest has no rows; production raw-data provenance is not established.")
        return [], report, 0
    seen: set[str] = set()
    validation = [validate_one(row, root, seen) for row in rows]
    counts: dict[str, int] = {}
    for row in validation:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    add_report(report, "info", "sequence_acquisition_manifest", f"validated_rows={len(validation)}")
    for status, count in sorted(counts.items()):
        severity = "error" if any(row["status"] == status and row["severity"] == "error" for row in validation) else "warning" if any(row["status"] == status and row["severity"] == "warning" for row in validation) else "info"
        add_report(report, severity, status, f"{count} row(s).")
    errors = sum(1 for row in validation if row.get("severity") == "error")
    return validation, report, errors


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    manifest = resolve_path(root, args.manifest)
    try:
        validation, report, errors = validate_manifest(manifest, root)
    except AcquisitionManifestError as exc:
        validation = []
        report = [{"severity": "error", "item": "sequence_acquisition_manifest", "message": str(exc)}]
        errors = 1
    write_tsv(Path(args.validation_output), VALIDATION_COLUMNS, validation)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Sequence acquisition manifest validation complete: rows={len(validation)}; errors={errors}.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
