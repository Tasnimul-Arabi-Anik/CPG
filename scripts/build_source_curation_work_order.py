#!/usr/bin/env python3
"""Build source-specific curation work orders from the readiness dashboard and sample thresholds."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


WORK_ORDER_COLUMNS = [
    "work_order_id",
    "source_id",
    "recommended_rank",
    "record_layer",
    "expected_export_path",
    "required_for_hypotheses",
    "curation_priority",
    "blocked_metrics",
    "required_fields",
    "minimum_rows_to_add",
    "current_export_rows",
    "current_satisfying_rows",
    "completion_check",
    "validation_command",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create reviewed-source curation work orders.")
    parser.add_argument("--dashboard", required=True, help="source_readiness_dashboard.tsv.")
    parser.add_argument("--sample-support-summary", required=True, help="sample_support_summary.tsv.")
    parser.add_argument("--work-order-output", required=True, help="Output work-order TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
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


def split_values(value: str) -> list[str]:
    if is_missing(value):
        return []
    return [part.strip() for part in value.replace(",", ";").split(";") if part.strip()]


def int_value(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def metric_deficits(summary_rows: list[dict[str, str]]) -> dict[str, int]:
    deficits: dict[str, int] = {}
    for row in summary_rows:
        metric = row.get("metric", "")
        threshold = int_value(row.get("threshold", "0"))
        value = int_value(row.get("value", "0"))
        deficits[metric] = max(0, threshold - value)
    return deficits


def row_rank(row: dict[str, str]) -> tuple[int, str]:
    try:
        rank = int(row.get("recommended_rank", "999"))
    except ValueError:
        rank = 999
    return rank, row.get("source_id", "")


def minimum_rows_for(blocked_metrics: list[str], deficits: dict[str, int]) -> int:
    values = [deficits.get(metric, 1) for metric in blocked_metrics]
    values = [value for value in values if value > 0]
    return max(values) if values else 0


def completion_check_for(source_id: str) -> str:
    return (
        "Populate reviewed export, rerun workflow through source export validation, import/enablement planning, "
        "sample-support export preflight, and source readiness dashboard; then confirm this source is no longer "
        f"populate_reviewed_rows in source_readiness_dashboard.tsv ({source_id})."
    )


def main() -> None:
    args = parse_args()
    _, dashboard_rows = read_tsv(Path(args.dashboard))
    _, summary_rows = read_tsv(Path(args.sample_support_summary))
    deficits = metric_deficits(summary_rows)

    work_rows: list[dict[str, str]] = []
    for index, row in enumerate(sorted(dashboard_rows, key=row_rank), start=1):
        priority = row.get("curation_priority", "")
        if priority in {"ready_for_downstream_sample_build", "review_after_primary_sources"}:
            continue
        blocked_metrics = split_values(row.get("blocked_metrics", ""))
        rows_to_add = minimum_rows_for(blocked_metrics, deficits)
        if priority in {"populate_reviewed_rows", "create_reviewed_export"} and rows_to_add == 0:
            rows_to_add = 1
        source_id = row.get("source_id", "")
        work_rows.append({
            "work_order_id": f"WO{index:03d}",
            "source_id": source_id,
            "recommended_rank": row.get("recommended_rank", "999"),
            "record_layer": row.get("record_layer", "NA"),
            "expected_export_path": row.get("expected_export_path", "NA"),
            "required_for_hypotheses": row.get("required_for_hypotheses", "NA"),
            "curation_priority": priority,
            "blocked_metrics": row.get("blocked_metrics", "NA"),
            "required_fields": row.get("fields_to_populate", "NA"),
            "minimum_rows_to_add": str(rows_to_add),
            "current_export_rows": row.get("export_row_count", "0"),
            "current_satisfying_rows": row.get("satisfying_row_count_total", "0"),
            "completion_check": completion_check_for(source_id),
            "validation_command": "python scripts/run_workflow.py --config config/workflow.yaml --stages stage_0_source_export_validation stage_0_source_imports stage_0_source_plan stage_0_source_audit stage_0_source_curation_tasks stage_0_hypothesis_source_unlocks stage_0_minimum_source_curation stage_0_source_enablement stage_0_source_enablement_apply stage_0_sample_support_export_preflight stage_0_source_readiness_dashboard",
            "next_action": row.get("next_action", "NA"),
        })

    priority_counts: dict[str, int] = {}
    for row in work_rows:
        priority_counts[row["curation_priority"]] = priority_counts.get(row["curation_priority"], 0) + 1
    report_rows = [
        {
            "severity": "info",
            "item": "source_curation_work_order",
            "message": f"work_orders={len(work_rows)}; priority_counts=" + ";".join(f"{key}:{value}" for key, value in sorted(priority_counts.items())),
        }
    ]
    if work_rows:
        first = work_rows[0]
        report_rows.append({
            "severity": "warning",
            "item": "next_work_order",
            "message": f"Start with {first['work_order_id']} {first['source_id']}: add at least {first['minimum_rows_to_add']} reviewed row(s) with {first['required_fields']}.",
        })

    write_tsv(Path(args.work_order_output), WORK_ORDER_COLUMNS, work_rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report_rows)
    print(f"Wrote {len(work_rows)} source curation work order(s).")


if __name__ == "__main__":
    main()
