#!/usr/bin/env python3
"""Preflight the highest-priority reviewed source exports before enablement."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


PREFLIGHT_COLUMNS = [
    "source_id",
    "recommended_rank",
    "record_layer",
    "required_for_hypotheses",
    "expected_export_path",
    "export_exists",
    "export_row_count",
    "preflight_status",
    "blocking_issue_count",
    "warning_count",
    "identity_columns_required",
    "required_content_checks",
    "next_action",
]
ISSUE_COLUMNS = [
    "source_id",
    "recommended_rank",
    "row_number",
    "issue_severity",
    "issue_code",
    "field",
    "message",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}

CONTENT_CHECKS = {
    "cultured_phages": ["host_species", "genome_length", "gc_percent"],
    "literature_curated_phages": ["host_species", "phage_lifestyle"],
    "host_genomes": ["host_species", "K_type", "O_type", "ST"],
    "prophages": ["host_species", "K_type", "O_type", "ST"],
    "metagenomic_discovery": ["source", "genome_length", "gc_percent"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight highest-priority source exports before source enablement.")
    parser.add_argument("--minimum-source-plan", required=True, help="Minimum source curation plan TSV.")
    parser.add_argument("--max-rank", type=int, default=2, help="Highest recommended rank to preflight. Defaults to 2.")
    parser.add_argument("--preflight-output", required=True, help="Output source-level preflight TSV.")
    parser.add_argument("--issue-output", required=True, help="Output row-level issue TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    parser.add_argument("--root", default=".", help="Repository root.")
    return parser.parse_args()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    return fieldnames, rows


def read_export(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    delimiter = "," if path.suffix.lower() == ".csv" else "\t"
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        fieldnames = reader.fieldnames or []
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def split_values(value: str) -> list[str]:
    if is_missing(value):
        return []
    return [token.strip() for token in value.replace(",", ";").split(";") if token.strip()]


def rank_value(row: dict[str, str]) -> int:
    try:
        return int(row.get("recommended_rank", "999"))
    except ValueError:
        return 999


def add_issue(issues: list[dict[str, str]], source: dict[str, str], row_number: str, severity: str, code: str, field: str, message: str) -> None:
    issues.append({
        "source_id": source.get("source_id", ""),
        "recommended_rank": source.get("recommended_rank", ""),
        "row_number": row_number,
        "issue_severity": severity,
        "issue_code": code,
        "field": field,
        "message": message,
    })


def preflight_one(root: Path, source: dict[str, str]) -> tuple[dict[str, str], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    export_text = source.get("expected_export_path", "")
    export_path = resolve(root, export_text) if not is_missing(export_text) else Path("")
    identity_columns = split_values(source.get("identity_columns_required", ""))
    content_checks = CONTENT_CHECKS.get(source.get("record_layer", ""), [])
    if is_missing(export_text):
        add_issue(issues, source, "NA", "blocking", "export_path_missing", "expected_export_path", "No reviewed export path is configured for this source.")
        return {
            "source_id": source.get("source_id", ""),
            "recommended_rank": source.get("recommended_rank", ""),
            "record_layer": source.get("record_layer", ""),
            "required_for_hypotheses": source.get("required_for_hypotheses", ""),
            "expected_export_path": "NA",
            "export_exists": "false",
            "export_row_count": "0",
            "preflight_status": "missing_export_path",
            "blocking_issue_count": "1",
            "warning_count": "0",
            "identity_columns_required": ";".join(identity_columns),
            "required_content_checks": ";".join(content_checks),
            "next_action": "Configure an expected reviewed export path or remove this source from priority preflight.",
        }, issues
    if not export_path.exists():
        add_issue(issues, source, "NA", "blocking", "export_missing", "expected_export_path", "Reviewed export file does not exist.")
        return {
            "source_id": source.get("source_id", ""),
            "recommended_rank": source.get("recommended_rank", ""),
            "record_layer": source.get("record_layer", ""),
            "required_for_hypotheses": source.get("required_for_hypotheses", ""),
            "expected_export_path": display_path(root, export_path),
            "export_exists": "false",
            "export_row_count": "0",
            "preflight_status": "missing_export",
            "blocking_issue_count": "1",
            "warning_count": "0",
            "identity_columns_required": ";".join(identity_columns),
            "required_content_checks": ";".join(content_checks),
            "next_action": "Create the reviewed export using the source starter template, then rerun preflight.",
        }, issues

    fieldnames, rows = read_export(export_path)
    if not rows:
        add_issue(issues, source, "NA", "blocking", "export_empty", "expected_export_path", "Reviewed export has a header but no data rows.")
    missing_identity_headers = [column for column in identity_columns if column not in fieldnames]
    if missing_identity_headers:
        add_issue(issues, source, "NA", "blocking", "missing_identity_headers", ";".join(missing_identity_headers), "Required identity columns are missing from the export header.")
    missing_content_headers = [column for column in content_checks if column not in fieldnames]
    if missing_content_headers:
        add_issue(issues, source, "NA", "warning", "missing_content_headers", ";".join(missing_content_headers), "Recommended downstream metadata columns are missing from the export header.")

    usable_identity = [column for column in identity_columns if column in fieldnames]
    seen: dict[tuple[str, str], int] = {}
    for row_number, row in enumerate(rows, start=2):
        if usable_identity and all(is_missing(row.get(column)) for column in usable_identity):
            add_issue(issues, source, str(row_number), "blocking", "row_missing_identity", ";".join(usable_identity), "Row has no value in any accepted identity column.")
        if "raw_sequence_path" in fieldnames and "accession" in fieldnames:
            if is_missing(row.get("raw_sequence_path")) and is_missing(row.get("accession")):
                add_issue(issues, source, str(row_number), "warning", "row_missing_sequence_locator", "raw_sequence_path;accession", "Row lacks both local sequence path and accession; sequence acquisition will need manual curation.")
        for column in content_checks:
            if column in fieldnames and is_missing(row.get(column)):
                add_issue(issues, source, str(row_number), "warning", "row_missing_recommended_metadata", column, "Recommended metadata is missing for downstream analysis.")
        for column in usable_identity:
            value = row.get(column, "")
            if is_missing(value):
                continue
            key = (column, value)
            if key in seen:
                add_issue(issues, source, str(row_number), "blocking", "duplicate_identity_value", column, f"Duplicate identity value also seen on row {seen[key]}.")
            else:
                seen[key] = row_number

    blocking = sum(1 for issue in issues if issue["issue_severity"] == "blocking")
    warnings = sum(1 for issue in issues if issue["issue_severity"] == "warning")
    if blocking:
        status = "blocking_issues"
        next_action = "Fix blocking preflight issues before source export validation/import."
    elif warnings:
        status = "ready_with_warnings"
        next_action = "Review warnings, then run source export validation and enable import only after review."
    else:
        status = "preflight_ready"
        next_action = "Run source export validation, then use source_enablement_plan.tsv to decide enablement."
    return {
        "source_id": source.get("source_id", ""),
        "recommended_rank": source.get("recommended_rank", ""),
        "record_layer": source.get("record_layer", ""),
        "required_for_hypotheses": source.get("required_for_hypotheses", ""),
        "expected_export_path": display_path(root, export_path),
        "export_exists": "true",
        "export_row_count": str(len(rows)),
        "preflight_status": status,
        "blocking_issue_count": str(blocking),
        "warning_count": str(warnings),
        "identity_columns_required": ";".join(identity_columns),
        "required_content_checks": ";".join(content_checks),
        "next_action": next_action,
    }, issues


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    minimum_path = resolve(root, args.minimum_source_plan)
    preflight_output = resolve(root, args.preflight_output)
    issue_output = resolve(root, args.issue_output)
    report_output = resolve(root, args.report_output)

    _, sources = read_tsv(minimum_path)
    selected = [row for row in sources if rank_value(row) <= args.max_rank]
    selected = sorted(selected, key=lambda row: (rank_value(row), row.get("source_id", "")))
    preflight_rows: list[dict[str, str]] = []
    issue_rows: list[dict[str, str]] = []
    for source in selected:
        row, issues = preflight_one(root, source)
        preflight_rows.append(row)
        issue_rows.extend(issues)

    blocking = sum(1 for issue in issue_rows if issue["issue_severity"] == "blocking")
    warnings = sum(1 for issue in issue_rows if issue["issue_severity"] == "warning")
    ready = sum(1 for row in preflight_rows if row["preflight_status"] in {"preflight_ready", "ready_with_warnings"})
    report_rows = [
        {"severity": "info", "item": "priority_source_preflight", "message": f"sources={len(preflight_rows)}; ready_or_warning={ready}; blocking_issues={blocking}; warnings={warnings}; max_rank={args.max_rank}"},
    ]
    if blocking:
        report_rows.append({"severity": "warning", "item": "priority_source_preflight", "message": "One or more priority exports are missing or have blocking issues."})
    write_tsv(preflight_output, PREFLIGHT_COLUMNS, preflight_rows)
    write_tsv(issue_output, ISSUE_COLUMNS, issue_rows)
    write_tsv(report_output, REPORT_COLUMNS, report_rows)
    print(f"Preflighted {len(preflight_rows)} priority source exports with {blocking} blocking issues.")


if __name__ == "__main__":
    main()
