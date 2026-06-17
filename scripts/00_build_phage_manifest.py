#!/usr/bin/env python3
"""Validate the project sample table and build the Stage 1 manifest."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


REQUIRED_COLUMNS = [
    "record_type",
    "genome_id",
    "accession",
    "source",
    "isolation_host",
    "host_species",
    "host_strain",
    "country",
    "year",
    "phage_lifestyle",
    "genome_length",
    "gc_percent",
    "K_type",
    "O_type",
    "ST",
    "AMR_markers",
    "virulence_markers",
    "raw_sequence_path",
    "notes",
]

VALID_RECORD_TYPES = {"phage", "prophage", "metagenomic_viral_contig", "host"}
VALID_LIFESTYLES = {"virulent", "temperate", "ambiguous", "NA", ""}

MANIFEST_EXTRA_COLUMNS = [
    "has_raw_sequence",
    "raw_sequence_exists",
    "validation_status",
    "validation_messages",
]

REPORT_COLUMNS = [
    "genome_id",
    "record_type",
    "severity",
    "field",
    "message",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate config/samples.tsv and write a normalized manifest."
    )
    parser.add_argument("--input", required=True, help="Input samples TSV.")
    parser.add_argument(
        "--manifest-output",
        required=True,
        help="Output manifest TSV with validation status.",
    )
    parser.add_argument(
        "--report-output",
        required=True,
        help="Output validation report TSV.",
    )
    parser.add_argument(
        "--excluded-output",
        required=True,
        help="Output TSV containing records excluded from downstream analysis.",
    )
    return parser.parse_args()


def normalize(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip()


def is_missing(value: str) -> bool:
    return normalize(value) in {"", "NA", "N/A", "na", "n/a", "None", "none"}


def read_samples(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(f"Input sample table does not exist: {path}")

    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="	")
        fieldnames = reader.fieldnames or []
        rows = [{key: normalize(value) for key, value in row.items()} for row in reader]
    return fieldnames, rows


def add_issue(
    issues: list[dict[str, str]],
    genome_id: str,
    record_type: str,
    severity: str,
    field: str,
    message: str,
) -> None:
    issues.append(
        {
            "genome_id": genome_id or "NA",
            "record_type": record_type or "NA",
            "severity": severity,
            "field": field,
            "message": message,
        }
    )


def parse_positive_int(value: str) -> bool:
    if is_missing(value):
        return True
    try:
        return int(value) > 0
    except ValueError:
        return False


def parse_gc_percent(value: str) -> bool:
    if is_missing(value):
        return True
    try:
        gc_percent = float(value)
    except ValueError:
        return False
    return 0 <= gc_percent <= 100


def raw_path_exists(raw_sequence_path: str, input_dir: Path) -> bool:
    if is_missing(raw_sequence_path):
        return False
    candidate = Path(raw_sequence_path)
    if not candidate.is_absolute():
        candidate = input_dir / candidate
    return candidate.exists()


def validate_rows(
    fieldnames: list[str],
    rows: list[dict[str, str]],
    input_path: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing_columns:
        add_issue(
            issues,
            "NA",
            "NA",
            "error",
            "header",
            "Missing required columns: " + ", ".join(missing_columns),
        )

    genome_counts: dict[str, int] = {}
    for row in rows:
        genome_id = row.get("genome_id", "")
        genome_counts[genome_id] = genome_counts.get(genome_id, 0) + 1

    manifest: list[dict[str, str]] = []
    input_dir = input_path.parent

    for row in rows:
        normalized = {column: row.get(column, "") for column in REQUIRED_COLUMNS}
        genome_id = normalized["genome_id"]
        record_type = normalized["record_type"]
        row_issues: list[str] = []

        def row_issue(severity: str, field: str, message: str) -> None:
            add_issue(issues, genome_id, record_type, severity, field, message)
            row_issues.append(f"{severity}:{field}:{message}")

        if is_missing(genome_id):
            row_issue("error", "genome_id", "genome_id is required")
        elif genome_counts.get(genome_id, 0) > 1:
            row_issue("error", "genome_id", "genome_id must be unique")

        if record_type not in VALID_RECORD_TYPES:
            row_issue(
                "error",
                "record_type",
                "record_type must be one of "
                + ", ".join(sorted(VALID_RECORD_TYPES)),
            )

        lifestyle = normalized["phage_lifestyle"]
        if lifestyle not in VALID_LIFESTYLES:
            row_issue(
                "warning",
                "phage_lifestyle",
                "phage_lifestyle should be virulent, temperate, ambiguous, or NA",
            )

        if not parse_positive_int(normalized["genome_length"]):
            row_issue("error", "genome_length", "genome_length must be a positive integer")

        if not parse_gc_percent(normalized["gc_percent"]):
            row_issue("error", "gc_percent", "gc_percent must be between 0 and 100")

        has_raw_sequence = "false" if is_missing(normalized["raw_sequence_path"]) else "true"
        sequence_exists = raw_path_exists(normalized["raw_sequence_path"], input_dir)
        if has_raw_sequence == "true" and not sequence_exists:
            row_issue(
                "warning",
                "raw_sequence_path",
                "raw_sequence_path is provided but does not exist",
            )

        error_count = sum(1 for issue in row_issues if issue.startswith("error:"))
        manifest_row = dict(normalized)
        manifest_row.update(
            {
                "has_raw_sequence": has_raw_sequence,
                "raw_sequence_exists": str(sequence_exists).lower(),
                "validation_status": "exclude" if error_count else "pass",
                "validation_messages": "; ".join(row_issues) if row_issues else "OK",
            }
        )
        manifest.append(manifest_row)

    if not rows and not missing_columns:
        add_issue(
            issues,
            "NA",
            "NA",
            "info",
            "rows",
            "No records found; manifest contains headers only",
        )

    return manifest, issues


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), delimiter="	")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in writer.fieldnames})


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    manifest_output = Path(args.manifest_output)
    report_output = Path(args.report_output)
    excluded_output = Path(args.excluded_output)

    fieldnames, rows = read_samples(input_path)
    manifest, issues = validate_rows(fieldnames, rows, input_path)
    excluded = [row for row in manifest if row["validation_status"] == "exclude"]

    write_tsv(manifest_output, REQUIRED_COLUMNS + MANIFEST_EXTRA_COLUMNS, manifest)
    write_tsv(report_output, REPORT_COLUMNS, issues)
    write_tsv(excluded_output, REQUIRED_COLUMNS + MANIFEST_EXTRA_COLUMNS, excluded)

    error_count = sum(1 for issue in issues if issue["severity"] == "error")
    warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
    print(
        f"Validated {len(rows)} records: "
        f"{len(manifest) - len(excluded)} passing, "
        f"{len(excluded)} excluded, "
        f"{error_count} errors, {warning_count} warnings."
    )
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
