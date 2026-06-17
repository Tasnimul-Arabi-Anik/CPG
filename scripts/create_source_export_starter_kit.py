#!/usr/bin/env python3
"""Create a source-export starter kit for reviewed metadata curation."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


MANIFEST_COLUMNS = [
    "source_id",
    "query_id",
    "record_layer",
    "review_priority",
    "target_database",
    "starter_readme_path",
    "starter_template_path",
    "expected_export_path",
    "required_columns",
    "identity_columns_required",
    "query_string",
    "command_hint",
    "validation_command",
    "curation_status",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create per-source starter files for reviewed source exports.")
    parser.add_argument("--source-curation-tasks", required=True, help="Source curation tasks TSV.")
    parser.add_argument("--template-manifest", required=True, help="Source export template manifest TSV.")
    parser.add_argument("--column-dictionary", required=True, help="Source export column dictionary TSV.")
    parser.add_argument("--output-dir", required=True, help="Output directory for starter kit files.")
    parser.add_argument("--manifest-output", required=True, help="Output starter kit manifest TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    parser.add_argument("--root", default=".", help="Repository root for relative paths.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="	")
        fieldnames = reader.fieldnames or []
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    return fieldnames, rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="	")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def display_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def safe_name(value: str) -> str:
    cleaned = []
    for char in value:
        if char.isalnum() or char in {"_", "-"}:
            cleaned.append(char)
        else:
            cleaned.append("_")
    return "".join(cleaned).strip("_") or "source"


def split_joined(value: str) -> list[str]:
    if is_missing(value):
        return []
    return [token.strip() for token in value.split(";") if token.strip()]


def columns_for_source(dictionary_rows: list[dict[str, str]], source_id: str, query_id: str) -> list[dict[str, str]]:
    rows = [row for row in dictionary_rows if row.get("source_id") == source_id or row.get("query_id") == query_id]
    return sorted(rows, key=lambda row: (row.get("column_name", ""), row.get("column_role", "")))


def write_template(path: Path, header_columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="	")
        writer.writerow(header_columns)


def markdown_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "No dictionary rows were available for this source.\n"
    lines = ["| Column | Role | Description | Expected format | Missing value policy |", "| --- | --- | --- | --- | --- |"]
    seen = set()
    for row in rows:
        key = (row.get("column_name", ""), row.get("column_role", ""), row.get("description", ""))
        if key in seen:
            continue
        seen.add(key)
        lines.append(
            "| "
            + " | ".join([
                row.get("column_name", ""),
                row.get("column_role", ""),
                row.get("description", ""),
                row.get("expected_format", ""),
                row.get("missing_value_policy", ""),
            ])
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_readme(path: Path, root: Path, task: dict[str, str], template_path: Path, dictionary_rows: list[dict[str, str]]) -> None:
    header_columns = split_joined(task.get("required_export_columns", ""))
    identity = split_joined(task.get("identity_columns_required", ""))
    required_identity_text = "; ".join(identity) if identity else "NA"
    required_columns_text = "; ".join(header_columns) if header_columns else "NA"
    expected_export = task.get("expected_export_path", "")
    validation_command = "python scripts/run_workflow.py --config config/workflow.yaml --stages stage_0_source_export_validation stage_0_source_imports stage_0_source_plan stage_0_source_audit stage_0_source_curation_tasks stage_0_hypothesis_source_unlocks stage_0_samples stage_1_manifest"
    content = [
        f"# {task.get('source_id', 'source')} source export starter",
        "",
        f"- Source ID: `{task.get('source_id', '')}`",
        f"- Query ID: `{task.get('query_id', '')}`",
        f"- Record layer: `{task.get('record_layer', '')}`",
        f"- Priority: `{task.get('priority', '')}`",
        f"- Target database: `{task.get('target_database', '')}`",
        f"- Expected reviewed export path: `{expected_export}`",
        f"- Fillable starter template: `{display_path(root, template_path)}`",
        f"- Required identity columns: `{required_identity_text}`",
        "",
        "## Query",
        "",
        task.get("query_string", "NA") or "NA",
        "",
        "## Required columns",
        "",
        f"`{required_columns_text}`",
        "",
        "## Column dictionary",
        "",
        markdown_table(dictionary_rows).rstrip(),
        "",
        "## Curation checklist",
        "",
        "- Populate at least one identity column per row using the required identity columns.",
        "- Preserve source provenance and review notes in `notes` when available.",
        "- Keep metagenomic discovery rows separate from cultured phages unless the study design changes.",
        "- Save the reviewed TSV to the expected export path, not under `results/`.",
        "- Enable the relevant source/import only after the export passes validation.",
        "",
        "## Validation command",
        "",
        "```bash",
        validation_command,
        "```",
        "",
        "## Existing workflow hint",
        "",
        task.get("command_hint", "NA") or "NA",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(content), encoding="utf-8")


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    tasks_path = resolve(root, args.source_curation_tasks)
    template_manifest_path = resolve(root, args.template_manifest)
    dictionary_path = resolve(root, args.column_dictionary)
    output_dir = resolve(root, args.output_dir)
    manifest_output = resolve(root, args.manifest_output)
    report_output = resolve(root, args.report_output)

    _, tasks = read_tsv(tasks_path)
    _, template_rows = read_tsv(template_manifest_path)
    _, dictionary_rows = read_tsv(dictionary_path)
    template_by_query = {row.get("query_id", ""): row for row in template_rows}

    manifest_rows: list[dict[str, str]] = []
    for task in tasks:
        source_id = task.get("source_id", "")
        query_id = task.get("query_id", "")
        template_row = template_by_query.get(query_id, {})
        header_columns = split_joined(task.get("required_export_columns", "") or template_row.get("header_columns", ""))
        base = safe_name(source_id or query_id)
        starter_template = output_dir / f"{base}.template.tsv"
        starter_readme = output_dir / f"{base}.README.md"
        write_template(starter_template, header_columns)
        dict_rows = columns_for_source(dictionary_rows, source_id, query_id)
        write_readme(starter_readme, root, task, starter_template, dict_rows)
        manifest_rows.append({
            "source_id": source_id,
            "query_id": query_id,
            "record_layer": task.get("record_layer", ""),
            "review_priority": task.get("priority", ""),
            "target_database": task.get("target_database", ""),
            "starter_readme_path": display_path(root, starter_readme),
            "starter_template_path": display_path(root, starter_template),
            "expected_export_path": task.get("expected_export_path", ""),
            "required_columns": ";".join(header_columns),
            "identity_columns_required": task.get("identity_columns_required", ""),
            "query_string": task.get("query_string", ""),
            "command_hint": task.get("command_hint", ""),
            "validation_command": "python scripts/run_workflow.py --config config/workflow.yaml --stages stage_0_source_export_validation stage_0_source_imports stage_0_source_plan stage_0_source_audit stage_0_source_curation_tasks stage_0_hypothesis_source_unlocks stage_0_samples stage_1_manifest",
            "curation_status": task.get("curation_status", ""),
            "next_action": task.get("next_action", ""),
        })

    index_lines = [
        "# Source Export Starter Kit",
        "",
        "This directory collects per-source starter files for A01 source curation. These files are generated planning aids under `results/`; they are not biological data and should not be imported directly.",
        "",
        "For each source, copy or manually transcribe reviewed metadata into the configured `expected_export_path`, then rerun the validation command recorded in the manifest.",
        "",
        "| Source ID | Record layer | Starter README | Starter template | Expected export path |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in manifest_rows:
        index_lines.append(
            f"| `{row['source_id']}` | `{row['record_layer']}` | `{row['starter_readme_path']}` | `{row['starter_template_path']}` | `{row['expected_export_path']}` |"
        )
    (output_dir / "README.md").parent.mkdir(parents=True, exist_ok=True)
    (output_dir / "README.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    report_rows = [
        {"severity": "info", "item": "source_export_starter_kit", "message": f"sources={len(manifest_rows)}; output_dir={display_path(root, output_dir)}"},
    ]
    if not manifest_rows:
        report_rows.append({"severity": "warning", "item": "source_export_starter_kit", "message": "No source curation tasks were available for starter kit generation."})
    write_tsv(manifest_output, MANIFEST_COLUMNS, manifest_rows)
    write_tsv(report_output, REPORT_COLUMNS, report_rows)
    print(f"Wrote source export starter kit for {len(manifest_rows)} sources.")


if __name__ == "__main__":
    main()
