#!/usr/bin/env python3
"""Create non-overwriting skeleton TSVs for reviewed source exports."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


REPORT_COLUMNS = [
    "source_id",
    "query_id",
    "expected_export_path",
    "status",
    "header_columns",
    "template_path",
    "next_action",
]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


class BootstrapError(Exception):
    """Raised when source export bootstrapping inputs are invalid."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create skeleton reviewed-export TSVs from source query planning outputs.")
    parser.add_argument("--query-plan", required=True, help="Source query plan TSV with expected export paths and columns.")
    parser.add_argument("--template-manifest", required=True, help="Source export template manifest TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    parser.add_argument("--root", default=".", help="Repository root for relative paths.")
    parser.add_argument("--sources", nargs="*", default=[], help="Optional source_id subset to bootstrap.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing skeleton/export files. Use only before manual curation.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def split_list(value: str) -> list[str]:
    if is_missing(value):
        return []
    return [item.strip() for item in value.replace(",", ";").split(";") if item.strip()]


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def display_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise BootstrapError(f"Required TSV does not exist: {path}")
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


def template_by_query(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("query_id", ""): row for row in rows if row.get("query_id")}


def header_for(query: dict[str, str], template: dict[str, str]) -> list[str]:
    columns = split_list(query.get("expected_columns", ""))
    if not columns:
        columns = split_list(template.get("header_columns", ""))
    if not columns:
        columns = split_list(query.get("identity_columns_required", ""))
    return columns


def row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return sum(1 for _ in reader)


def bootstrap(args: argparse.Namespace) -> list[dict[str, str]]:
    root = Path(args.root).resolve()
    query_fields, query_rows = read_tsv(resolve(root, args.query_plan))
    _, template_rows = read_tsv(resolve(root, args.template_manifest))
    required = {"query_id", "source_id", "expected_export_path", "expected_columns"}
    missing = sorted(required - set(query_fields))
    if missing:
        raise BootstrapError("Source query plan is missing required columns: " + ";".join(missing))

    selected = set(args.sources or [])
    templates = template_by_query(template_rows)
    report_rows: list[dict[str, str]] = []
    for query in query_rows:
        source_id = query.get("source_id", "")
        query_id = query.get("query_id", "")
        if selected and source_id not in selected:
            continue
        export_text = query.get("expected_export_path", "")
        if is_missing(export_text):
            report_rows.append({
                "source_id": source_id,
                "query_id": query_id,
                "expected_export_path": "NA",
                "status": "skipped_no_export_path",
                "header_columns": "NA",
                "template_path": "NA",
                "next_action": "Add expected_export_path to the source query configuration.",
            })
            continue
        export_path = resolve(root, export_text)
        template = templates.get(query_id, {})
        columns = header_for(query, template)
        template_path = template.get("template_path", "NA")
        if not columns:
            report_rows.append({
                "source_id": source_id,
                "query_id": query_id,
                "expected_export_path": display_path(root, export_path),
                "status": "skipped_no_columns",
                "header_columns": "NA",
                "template_path": template_path,
                "next_action": "Add expected_columns or template header_columns before bootstrapping this source.",
            })
            continue
        if export_path.exists() and not args.force:
            rows = row_count(export_path)
            status = "existing_export_with_rows" if rows else "existing_export_empty"
            action = "Review/fill this existing export, then rerun source validation. Use --force only before manual curation."
        else:
            write_tsv(export_path, columns, [])
            status = "created_skeleton" if not args.force else "overwrote_skeleton"
            action = "Fill reviewed metadata rows in this export, then run source export validation."
        report_rows.append({
            "source_id": source_id,
            "query_id": query_id,
            "expected_export_path": display_path(root, export_path),
            "status": status,
            "header_columns": ";".join(columns),
            "template_path": template_path,
            "next_action": action,
        })
    return report_rows


def main() -> None:
    args = parse_args()
    rows = bootstrap(args)
    write_tsv(resolve(Path(args.root).resolve(), args.report_output), REPORT_COLUMNS, rows)
    created = sum(1 for row in rows if row["status"] in {"created_skeleton", "overwrote_skeleton"})
    print(f"Wrote bootstrap report for {len(rows)} source(s); created_or_overwrote={created}.")


if __name__ == "__main__":
    main()
