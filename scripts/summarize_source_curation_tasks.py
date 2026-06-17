#!/usr/bin/env python3
"""Summarize reviewed source-export curation tasks into one handoff table."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


TASK_COLUMNS = [
    "source_id",
    "query_id",
    "record_layer",
    "priority",
    "target_database",
    "expected_export_path",
    "template_path",
    "manifest_path",
    "import_id",
    "import_enabled",
    "catalog_enabled",
    "export_status",
    "manifest_status",
    "curation_status",
    "blocking_for_real_study",
    "required_export_columns",
    "identity_columns_required",
    "query_string",
    "next_action",
    "command_hint",
    "notes",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a source curation task table from Stage 0 planning outputs.")
    parser.add_argument("--source-query-plan", required=True, help="results/qc/source_query_plan.tsv")
    parser.add_argument("--template-manifest", required=True, help="results/qc/source_export_template_manifest.tsv")
    parser.add_argument("--export-validation", required=True, help="results/qc/source_export_validation.tsv")
    parser.add_argument("--source-acquisition-plan", required=True, help="results/qc/source_acquisition_plan.tsv")
    parser.add_argument("--source-readiness", required=True, help="results/qc/source_catalog_readiness.tsv")
    parser.add_argument("--tasks-output", required=True, help="Output source curation tasks TSV.")
    parser.add_argument("--report-output", required=True, help="Output source curation task report TSV.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
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


def by_key(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {row.get(key, ""): row for row in rows if not is_missing(row.get(key))}


def row_by_source(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("source_id", ""): row for row in rows if not is_missing(row.get("source_id"))}


def command_for(query: dict[str, str], acquisition: dict[str, str], validation: dict[str, str]) -> str:
    export_path = query.get("expected_export_path", "") or acquisition.get("import_input_path", "")
    manifest_path = acquisition.get("manifest_path", "")
    if validation.get("validation_status") == "export_ready" and acquisition.get("import_enabled") != "true":
        return f"Set import enabled=true for {acquisition.get('import_id', query.get('source_id', 'source'))} in config/source_imports.yaml, then rerun python scripts/run_workflow.py --config config/workflow.yaml"
    if validation.get("validation_status") == "export_ready" and acquisition.get("catalog_enabled") != "true":
        return f"Set catalog enabled=true for {query.get('source_id', 'source')} in config/source_catalog.yaml after reviewing {manifest_path}"
    if export_path:
        return f"Populate reviewed export: {export_path}; validate with python scripts/run_workflow.py --config config/workflow.yaml --stages stage_0_source_export_validation stage_0_source_curation_tasks"
    return "Populate a reviewed source export and rerun Stage 0 validation."


def curation_status(query: dict[str, str], validation: dict[str, str], acquisition: dict[str, str], readiness: dict[str, str]) -> tuple[str, str, str]:
    validation_status = validation.get("validation_status", "export_missing")
    acquisition_status = acquisition.get("acquisition_status", "")
    ready_status = readiness.get("ready_status", "")
    if ready_status in {"ready_enabled", "ready_with_defaults"}:
        return "ready_for_sample_build", "false", "No action required."
    if validation_status == "export_ready" and acquisition_status in {"local_export_ready_for_import", "local_export_ready_import_disabled"}:
        return "export_ready_import_or_enable_pending", "true", "Enable the matching import and catalog source after reviewing normalized manifest rows."
    if validation_status == "export_ready":
        return "export_ready_review_import_status", "true", "Review export/import status and enable source when normalized manifest is ready."
    if validation_status == "export_missing":
        return "waiting_for_reviewed_export", "true", "Create the reviewed local export at expected_export_path."
    if validation.get("blocking_issue") == "true" or validation_status.startswith("export_"):
        return "export_present_but_invalid", "true", "Fix required columns, identity fields, or row-level export validation errors."
    if acquisition_status in {"catalog_enabled_but_manifest_empty", "required_manifest_missing"}:
        return "catalog_enabled_but_not_ready", "true", "Disable the source or populate a schema-valid manifest before sample building."
    if query.get("query_status") == "planned_query_ready":
        return "query_planned_export_needed", "true", "Run/review the planned external query and save the export locally."
    return "needs_review", "true", "Review source planning and curation reports."


def build_tasks(
    query_rows: list[dict[str, str]],
    template_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    acquisition_rows: list[dict[str, str]],
    readiness_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    templates = by_key(template_rows, "query_id")
    validations = by_key(validation_rows, "query_id")
    acquisitions = row_by_source(acquisition_rows)
    readiness = row_by_source(readiness_rows)
    tasks = []
    for query in query_rows:
        source_id = query.get("source_id", "")
        template = templates.get(query.get("query_id", ""), {})
        validation = validations.get(query.get("query_id", ""), {})
        acquisition = acquisitions.get(source_id, {})
        ready = readiness.get(source_id, {})
        status, blocking, next_action = curation_status(query, validation, acquisition, ready)
        tasks.append(
            {
                "source_id": source_id,
                "query_id": query.get("query_id", ""),
                "record_layer": query.get("record_layer", acquisition.get("record_layer", "")),
                "priority": query.get("review_priority", acquisition.get("priority", "")),
                "target_database": query.get("target_database", ""),
                "expected_export_path": query.get("expected_export_path", validation.get("expected_export_path", acquisition.get("import_input_path", ""))),
                "template_path": template.get("template_path", ""),
                "manifest_path": acquisition.get("manifest_path", ready.get("path", "")),
                "import_id": acquisition.get("import_id", ""),
                "import_enabled": acquisition.get("import_enabled", ""),
                "catalog_enabled": acquisition.get("catalog_enabled", ready.get("enabled", "")),
                "export_status": validation.get("validation_status", query.get("query_status", "")),
                "manifest_status": ready.get("ready_status", acquisition.get("acquisition_status", "")),
                "curation_status": status,
                "blocking_for_real_study": blocking,
                "required_export_columns": query.get("expected_columns", template.get("header_columns", "")),
                "identity_columns_required": query.get("identity_columns_required", template.get("identity_columns_required", "")),
                "query_string": query.get("query_string", ""),
                "next_action": next_action,
                "command_hint": command_for(query, acquisition, validation),
                "notes": query.get("notes", acquisition.get("notes", "")),
            }
        )
    return tasks


def main() -> int:
    args = parse_args()
    _, query_rows = read_tsv(Path(args.source_query_plan))
    _, template_rows = read_tsv(Path(args.template_manifest))
    _, validation_rows = read_tsv(Path(args.export_validation))
    _, acquisition_rows = read_tsv(Path(args.source_acquisition_plan))
    _, readiness_rows = read_tsv(Path(args.source_readiness))

    tasks = build_tasks(query_rows, template_rows, validation_rows, acquisition_rows, readiness_rows)
    blocking = [row for row in tasks if row.get("blocking_for_real_study") == "true"]
    ready = [row for row in tasks if row.get("curation_status") == "ready_for_sample_build"]
    missing_exports = [row for row in tasks if row.get("curation_status") in {"waiting_for_reviewed_export", "query_planned_export_needed"}]
    invalid_exports = [row for row in tasks if row.get("curation_status") == "export_present_but_invalid"]

    report = [
        {
            "severity": "info",
            "item": "source_curation_tasks",
            "message": f"tasks={len(tasks)}; ready={len(ready)}; blocking={len(blocking)}; missing_exports={len(missing_exports)}; invalid_exports={len(invalid_exports)}",
        }
    ]
    if blocking:
        report.append(
            {
                "severity": "warning",
                "item": "source_curation_tasks",
                "message": "Real study sample generation is blocked until reviewed exports/imports/catalog sources are ready.",
            }
        )

    write_tsv(Path(args.tasks_output), TASK_COLUMNS, tasks)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Wrote {len(tasks)} source curation tasks; {len(blocking)} blocking for real study.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
