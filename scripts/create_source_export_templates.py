#!/usr/bin/env python3
"""Create reviewed-export TSV templates from the source query plan."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable


MANIFEST_COLUMNS = [
    "query_id",
    "source_id",
    "record_layer",
    "target_database",
    "template_path",
    "expected_export_path",
    "expected_export_exists",
    "expected_export_row_count",
    "header_columns",
    "identity_columns_required",
    "identity_columns_in_template",
    "missing_identity_columns",
    "review_priority",
    "template_status",
    "next_action",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


class TemplateError(Exception):
    """Raised when export template generation cannot proceed."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create TSV templates for reviewed public-source exports.")
    parser.add_argument("--query-plan", required=True, help="Source query plan TSV from plan_source_queries.py.")
    parser.add_argument("--templates-dir", required=True, help="Directory where header-only reviewed-export templates are written.")
    parser.add_argument("--manifest-output", required=True, help="Template manifest TSV output.")
    parser.add_argument("--report-output", required=True, help="Summary report TSV output.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
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


def display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def split_list(value: str) -> list[str]:
    return [item.strip() for item in value.replace(",", ";").split(";") if item.strip()]


def unique(items: Iterable[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output


def safe_filename(value: str, fallback: str) -> str:
    raw = value or fallback
    raw = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("_")
    return raw or fallback


def row_count(path: Path) -> int:
    _, rows = read_tsv(path)
    return len(rows)


def template_headers(row: dict[str, str]) -> list[str]:
    expected = split_list(row.get("expected_columns", ""))
    identity = split_list(row.get("identity_columns_required", ""))
    headers = unique([*expected, *identity])
    if not headers:
        headers = unique(["genome_id", "accession", "raw_sequence_path", "notes"])
    return headers


def write_template(path: Path, headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, delimiter="\t")
        writer.writeheader()


def build_templates(root: Path, query_plan: Path, templates_dir: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    fieldnames, rows = read_tsv(query_plan)
    if not query_plan.exists():
        raise TemplateError(f"Source query plan does not exist: {query_plan}")
    required = {"query_id", "source_id", "expected_export_path", "expected_columns", "identity_columns_required"}
    missing = sorted(required - set(fieldnames))
    if missing:
        raise TemplateError("Source query plan is missing required columns: " + ";".join(missing))

    manifest: list[dict[str, str]] = []
    report: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=1):
        query_id = normalize(row.get("query_id")) or f"query_{index}"
        export_path_text = normalize(row.get("expected_export_path"))
        expected_export_path = resolve(root, export_path_text) if export_path_text else Path("")
        export_exists = bool(export_path_text and expected_export_path.exists())
        export_rows = row_count(expected_export_path) if export_exists else 0
        headers = template_headers(row)
        identity = split_list(row.get("identity_columns_required", ""))
        identity_present = [column for column in identity if column in headers]
        identity_missing = [column for column in identity if column not in headers]
        template_name = safe_filename(query_id, f"query_{index}") + ".tsv"
        template_path = templates_dir / template_name
        write_template(template_path, headers)
        if identity_missing:
            status = "template_missing_identity_column"
            next_action = "Add missing identity columns to the query config before using this template."
        elif export_exists and export_rows > 0:
            status = "export_already_populated"
            next_action = "Review the populated export and run source import when ready."
        else:
            status = "template_ready"
            next_action = "Populate the reviewed export using this header, then save it to expected_export_path."
        manifest.append(
            {
                "query_id": query_id,
                "source_id": normalize(row.get("source_id")),
                "record_layer": normalize(row.get("record_layer")),
                "target_database": normalize(row.get("target_database")),
                "template_path": display_path(root, template_path),
                "expected_export_path": export_path_text,
                "expected_export_exists": str(export_exists).lower(),
                "expected_export_row_count": str(export_rows),
                "header_columns": ";".join(headers),
                "identity_columns_required": ";".join(identity),
                "identity_columns_in_template": ";".join(identity_present),
                "missing_identity_columns": ";".join(identity_missing),
                "review_priority": normalize(row.get("review_priority")),
                "template_status": status,
                "next_action": next_action,
                "notes": normalize(row.get("notes")),
            }
        )

    ready = sum(1 for row in manifest if row["template_status"] == "template_ready")
    populated = sum(1 for row in manifest if row["template_status"] == "export_already_populated")
    identity_errors = sum(1 for row in manifest if row["template_status"] == "template_missing_identity_column")
    report.append({"severity": "info", "item": "templates", "message": f"Created {len(manifest)} reviewed-export template(s)."})
    report.append({"severity": "info", "item": "template_ready", "message": f"{ready} template(s) are ready for reviewed export population."})
    if populated:
        report.append({"severity": "info", "item": "export_already_populated", "message": f"{populated} expected export(s) already have data rows."})
    if identity_errors:
        report.append({"severity": "error", "item": "template_identity", "message": f"{identity_errors} template(s) are missing required identity columns."})
    return manifest, report


def main() -> int:
    args = parse_args()
    root = Path.cwd()
    query_plan = resolve(root, args.query_plan)
    templates_dir = resolve(root, args.templates_dir)
    try:
        manifest, report = build_templates(root, query_plan, templates_dir)
        write_tsv(resolve(root, args.manifest_output), MANIFEST_COLUMNS, manifest)
        write_tsv(resolve(root, args.report_output), REPORT_COLUMNS, report)
        errors = sum(1 for row in report if row.get("severity") == "error")
        print(f"Source export templates complete: {len(manifest)} templates, {errors} errors.")
        return 1 if errors else 0
    except TemplateError as exc:
        write_tsv(resolve(root, args.manifest_output), MANIFEST_COLUMNS, [])
        write_tsv(resolve(root, args.report_output), REPORT_COLUMNS, [{"severity": "error", "item": "template_generation", "message": str(exc)}])
        print(f"Source export templates failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
