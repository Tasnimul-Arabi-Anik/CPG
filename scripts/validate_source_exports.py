#!/usr/bin/env python3
"""Validate reviewed source exports before normalizing them into source manifests."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


VALIDATION_COLUMNS = [
    "query_id",
    "source_id",
    "record_layer",
    "target_database",
    "expected_export_path",
    "export_exists",
    "export_row_count",
    "header_columns",
    "expected_columns",
    "missing_expected_columns",
    "identity_columns_required",
    "identity_columns_present",
    "identity_columns_missing",
    "rows_missing_all_identity",
    "duplicate_identity_columns",
    "duplicate_identity_values",
    "row_format_issue_count",
    "row_format_issues",
    "provenance_warning_count",
    "provenance_warnings",
    "validation_status",
    "blocking_issue",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
LIFESTYLE_VALUES = {"virulent", "temperate", "ambiguous", "chronic", "lysogenic"}


class ExportValidationError(Exception):
    """Raised for invalid validator inputs."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate reviewed source export TSVs before source import.")
    parser.add_argument("--query-plan", required=True, help="Source query plan TSV.")
    parser.add_argument("--template-manifest", required=True, help="Source export template manifest TSV.")
    parser.add_argument("--validation-output", required=True, help="Source export validation TSV.")
    parser.add_argument("--report-output", required=True, help="Summary report TSV.")
    parser.add_argument("--root", default=".", help="Repository root for relative paths.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def split_list(value: str) -> list[str]:
    return [item.strip() for item in value.replace(",", ";").split(";") if item.strip()]


def delimiter_for(path: Path) -> str:
    return "," if path.suffix.lower() == ".csv" else "\t"


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def display_path(root: Path, path: Path | str) -> str:
    path_obj = Path(path)
    if str(path_obj) in {"", "."}:
        return ""
    try:
        return path_obj.relative_to(root).as_posix()
    except ValueError:
        return path_obj.as_posix()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: normalize(value) for key, value in row.items()} for row in reader]
    return fieldnames, rows


def read_export(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter_for(path))
        fieldnames = reader.fieldnames or []
        rows = [{key: normalize(value) for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def add_report(report: list[dict[str, str]], severity: str, item: str, message: str) -> None:
    report.append({"severity": severity, "item": item, "message": message})


def template_by_query(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("query_id", ""): row for row in rows if row.get("query_id")}


def is_int(value: str) -> bool:
    try:
        int(value)
    except ValueError:
        return False
    return True


def is_float(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def row_quality_issues(rows: list[dict[str, str]]) -> tuple[list[str], list[str]]:
    format_issues: list[str] = []
    provenance_warnings: list[str] = []
    for index, row in enumerate(rows, start=2):
        year = normalize(row.get("year"))
        if not is_missing(year) and (not is_int(year) or not 1800 <= int(year) <= 2100):
            format_issues.append(f"row{index}:year:{year}")
        genome_length = normalize(row.get("genome_length"))
        if not is_missing(genome_length) and (not is_int(genome_length) or int(genome_length) <= 0):
            format_issues.append(f"row{index}:genome_length:{genome_length}")
        gc_percent = normalize(row.get("gc_percent"))
        if not is_missing(gc_percent) and (not is_float(gc_percent) or not 0 <= float(gc_percent) <= 100):
            format_issues.append(f"row{index}:gc_percent:{gc_percent}")
        lifestyle = normalize(row.get("phage_lifestyle"))
        if not is_missing(lifestyle) and lifestyle.lower() not in LIFESTYLE_VALUES:
            format_issues.append(f"row{index}:phage_lifestyle:{lifestyle}")
        if "notes" in row and is_missing(row.get("notes")):
            provenance_warnings.append(f"row{index}:notes_missing")
    return format_issues, provenance_warnings


def duplicate_values(rows: list[dict[str, str]], identity_columns: list[str]) -> tuple[list[str], list[str]]:
    duplicate_columns = []
    duplicates = []
    for column in identity_columns:
        seen = set()
        column_duplicates = set()
        for row in rows:
            value = normalize(row.get(column))
            if is_missing(value):
                continue
            if value in seen:
                column_duplicates.add(value)
            seen.add(value)
        if column_duplicates:
            duplicate_columns.append(column)
            for value in sorted(column_duplicates):
                duplicates.append(f"{column}:{value}")
    return duplicate_columns, duplicates


def validate_one(root: Path, query: dict[str, str], template: dict[str, str]) -> dict[str, str]:
    query_id = normalize(query.get("query_id"))
    export_text = normalize(query.get("expected_export_path"))
    expected = split_list(query.get("expected_columns") or template.get("header_columns", ""))
    identity = split_list(query.get("identity_columns_required") or template.get("identity_columns_required", ""))
    if not export_text:
        return {
            "query_id": query_id,
            "source_id": normalize(query.get("source_id")),
            "record_layer": normalize(query.get("record_layer")),
            "target_database": normalize(query.get("target_database")),
            "expected_export_path": "",
            "export_exists": "false",
            "export_row_count": "0",
            "header_columns": "",
            "expected_columns": ";".join(expected),
            "missing_expected_columns": "",
            "identity_columns_required": ";".join(identity),
            "identity_columns_present": "",
            "identity_columns_missing": ";".join(identity),
            "rows_missing_all_identity": "0",
            "duplicate_identity_columns": "",
            "duplicate_identity_values": "",
            "row_format_issue_count": "0",
            "row_format_issues": "",
            "provenance_warning_count": "0",
            "provenance_warnings": "",
            "validation_status": "no_export_path_configured",
            "blocking_issue": "false",
            "next_action": "Populate the source manifest directly or add an expected export path.",
        }
    export_path = resolve(root, export_text)
    if not export_path.exists():
        return {
            "query_id": query_id,
            "source_id": normalize(query.get("source_id")),
            "record_layer": normalize(query.get("record_layer")),
            "target_database": normalize(query.get("target_database")),
            "expected_export_path": display_path(root, export_path),
            "export_exists": "false",
            "export_row_count": "0",
            "header_columns": "",
            "expected_columns": ";".join(expected),
            "missing_expected_columns": ";".join(expected),
            "identity_columns_required": ";".join(identity),
            "identity_columns_present": "",
            "identity_columns_missing": ";".join(identity),
            "rows_missing_all_identity": "0",
            "duplicate_identity_columns": "",
            "duplicate_identity_values": "",
            "row_format_issue_count": "0",
            "row_format_issues": "",
            "provenance_warning_count": "0",
            "provenance_warnings": "",
            "validation_status": "export_missing",
            "blocking_issue": "false",
            "next_action": "Create reviewed export TSV at expected_export_path before source import.",
        }

    fieldnames, rows = read_export(export_path)
    missing_expected = [column for column in expected if column not in fieldnames]
    identity_present = [column for column in identity if column in fieldnames]
    identity_missing = [column for column in identity if column not in fieldnames]
    rows_missing_identity = 0
    if identity_present:
        for row in rows:
            if all(is_missing(row.get(column)) for column in identity_present):
                rows_missing_identity += 1
    duplicate_columns, duplicates = duplicate_values(rows, identity_present)
    format_issues, provenance_warnings = row_quality_issues(rows)

    if not rows:
        status = "export_empty"
        blocking = False
        action = "Add reviewed data rows before import; header-only skeletons are allowed for scaffold runs but do not support H1-H6."
    elif missing_expected:
        status = "export_missing_expected_columns"
        blocking = True
        action = "Add missing expected columns or update source_queries.yaml if the export schema changed intentionally."
    elif not identity_present:
        status = "export_missing_identity_columns"
        blocking = True
        action = "Add at least one required identity column before import."
    elif rows_missing_identity:
        status = "export_rows_missing_identity"
        blocking = True
        action = "Fill at least one identity value for every export row before import."
    elif duplicates:
        status = "export_duplicate_identity"
        blocking = True
        action = "Resolve duplicate identity values before import/dereplication."
    elif format_issues:
        status = "export_row_format_invalid"
        blocking = True
        action = "Fix malformed year, genome_length, gc_percent, or phage_lifestyle values before import."
    else:
        status = "export_ready"
        blocking = False
        action = "Review provenance, enable source import when ready, and rerun workflow."

    return {
        "query_id": query_id,
        "source_id": normalize(query.get("source_id")),
        "record_layer": normalize(query.get("record_layer")),
        "target_database": normalize(query.get("target_database")),
        "expected_export_path": display_path(root, export_path),
        "export_exists": "true",
        "export_row_count": str(len(rows)),
        "header_columns": ";".join(fieldnames),
        "expected_columns": ";".join(expected),
        "missing_expected_columns": ";".join(missing_expected),
        "identity_columns_required": ";".join(identity),
        "identity_columns_present": ";".join(identity_present),
        "identity_columns_missing": ";".join(identity_missing),
        "rows_missing_all_identity": str(rows_missing_identity),
        "duplicate_identity_columns": ";".join(duplicate_columns),
        "duplicate_identity_values": ";".join(duplicates[:50]),
        "row_format_issue_count": str(len(format_issues)),
        "row_format_issues": ";".join(format_issues[:50]),
        "provenance_warning_count": str(len(provenance_warnings)),
        "provenance_warnings": ";".join(provenance_warnings[:50]),
        "validation_status": status,
        "blocking_issue": str(blocking).lower(),
        "next_action": action,
    }


def validate_exports(root: Path, query_plan: Path, template_manifest: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    query_fields, query_rows = read_tsv(query_plan)
    if not query_plan.exists():
        raise ExportValidationError(f"Source query plan does not exist: {query_plan}")
    required = {"query_id", "source_id", "expected_export_path", "expected_columns", "identity_columns_required"}
    missing = sorted(required - set(query_fields))
    if missing:
        raise ExportValidationError("Source query plan is missing required columns: " + ";".join(missing))
    _, template_rows = read_tsv(template_manifest)
    templates = template_by_query(template_rows)
    rows = [validate_one(root, query, templates.get(query.get("query_id", ""), {})) for query in query_rows]

    report: list[dict[str, str]] = []
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["validation_status"]] = status_counts.get(row["validation_status"], 0) + 1
    add_report(report, "info", "exports", f"Validated {len(rows)} planned source export(s).")
    for status, count in sorted(status_counts.items()):
        if status == "export_ready":
            severity = "info"
        elif status in {"export_missing", "export_empty", "no_export_path_configured"}:
            severity = "warning"
        else:
            severity = "error"
        add_report(report, severity, status, f"{count} export(s).")
    provenance_warning_count = sum(int(row.get("provenance_warning_count") or 0) for row in rows)
    if provenance_warning_count:
        add_report(report, "warning", "provenance_warnings", f"{provenance_warning_count} populated row(s) lack notes/provenance text.")
    return rows, report


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    try:
        rows, report = validate_exports(root, resolve(root, args.query_plan), resolve(root, args.template_manifest))
        write_tsv(resolve(root, args.validation_output), VALIDATION_COLUMNS, rows)
        write_tsv(resolve(root, args.report_output), REPORT_COLUMNS, report)
        errors = sum(1 for row in report if row.get("severity") == "error")
        warnings = sum(1 for row in report if row.get("severity") == "warning")
        print(f"Source export validation complete: {len(rows)} exports, {errors} errors, {warnings} warnings.")
        return 1 if errors else 0
    except ExportValidationError as exc:
        write_tsv(resolve(root, args.validation_output), VALIDATION_COLUMNS, [])
        write_tsv(resolve(root, args.report_output), REPORT_COLUMNS, [{"severity": "error", "item": "source_export_validation", "message": str(exc)}])
        print(f"Source export validation failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
