#!/usr/bin/env python3
"""Build a ranked dashboard for reviewed source export readiness and sample-support blockers."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


DASHBOARD_COLUMNS = [
    "source_id",
    "recommended_rank",
    "record_layer",
    "required_for_hypotheses",
    "expected_export_path",
    "export_exists",
    "export_row_count",
    "validation_status",
    "enablement_status",
    "enablement_action_status",
    "blocked_metric_count",
    "blocked_metrics",
    "fields_to_populate",
    "satisfying_row_count_total",
    "curation_priority",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge source validation, enablement, and sample-support preflight into one dashboard.")
    parser.add_argument("--minimum-source-plan", required=True, help="minimum_source_curation_plan.tsv.")
    parser.add_argument("--source-export-validation", required=True, help="source_export_validation.tsv.")
    parser.add_argument("--source-enablement-plan", required=True, help="source_enablement_plan.tsv.")
    parser.add_argument("--source-enablement-apply", required=True, help="source_enablement_apply_report.tsv.")
    parser.add_argument("--sample-support-preflight", required=True, help="sample_support_export_preflight.tsv.")
    parser.add_argument("--dashboard-output", required=True, help="Output dashboard TSV.")
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


def by_key(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {row.get(key, ""): row for row in rows if row.get(key)}


def split_values(value: str) -> list[str]:
    if is_missing(value):
        return []
    return [part.strip() for part in value.replace(",", ";").split(";") if part.strip()]


def join(values: Iterable[str]) -> str:
    output: list[str] = []
    for value in values:
        for part in split_values(value):
            if part not in output:
                output.append(part)
    return ";".join(output) if output else "NA"


def int_value(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def rank_tuple(row: dict[str, str]) -> tuple[int, str]:
    try:
        rank = int(row.get("recommended_rank", "999"))
    except ValueError:
        rank = 999
    return rank, row.get("source_id", "")


def priority_for(export_rows: int, validation_status: str, enablement_status: str, blocked_metric_count: int, rank: str) -> str:
    if validation_status in {"export_missing", "no_export_path_configured"}:
        return "create_reviewed_export"
    if validation_status == "export_empty" or export_rows == 0:
        return "populate_reviewed_rows"
    if validation_status not in {"export_ready", "valid", "valid_with_warnings", "ready"}:
        return "fix_export_validation"
    if enablement_status == "ready_for_enablement":
        return "enable_import_and_review_manifest"
    if enablement_status == "enabled_for_sample_build" and blocked_metric_count:
        return "add_metric_specific_fields_or_rows"
    if enablement_status == "enabled_for_sample_build":
        return "ready_for_downstream_sample_build"
    if int_value(rank) <= 2:
        return "high_priority_review"
    return "review_after_primary_sources"


def action_for(priority: str, fields: str, metrics: str) -> str:
    if priority == "create_reviewed_export":
        return "Create the reviewed export at expected_export_path using the starter template."
    if priority == "populate_reviewed_rows":
        return "Add reviewed rows with fields: " + fields
    if priority == "fix_export_validation":
        return "Fix source_export_validation.tsv errors before import or enablement."
    if priority == "enable_import_and_review_manifest":
        return "Run/apply import enablement, rerun imports, review the source manifest, then enable catalog source."
    if priority == "add_metric_specific_fields_or_rows":
        return "Populate fields for blocked metrics " + metrics + ": " + fields
    if priority == "ready_for_downstream_sample_build":
        return "No source curation action required; rerun sample builder and downstream stages."
    return "Review this source after higher-ranked source exports are populated."


def main() -> None:
    args = parse_args()
    _, minimum_rows = read_tsv(Path(args.minimum_source_plan))
    _, validation_rows = read_tsv(Path(args.source_export_validation))
    _, enablement_rows = read_tsv(Path(args.source_enablement_plan))
    _, apply_rows = read_tsv(Path(args.source_enablement_apply))
    _, preflight_rows = read_tsv(Path(args.sample_support_preflight))

    minimum_by_source = by_key(minimum_rows, "source_id")
    validation_by_source = by_key(validation_rows, "source_id")
    enablement_by_source = by_key(enablement_rows, "source_id")
    apply_by_source = by_key(apply_rows, "source_id")
    preflight_by_source: dict[str, list[dict[str, str]]] = {}
    for row in preflight_rows:
        source_id = row.get("source_id", "")
        if source_id:
            preflight_by_source.setdefault(source_id, []).append(row)

    source_ids = sorted(set(minimum_by_source) | set(validation_by_source) | set(enablement_by_source) | set(apply_by_source) | set(preflight_by_source))
    dashboard_rows: list[dict[str, str]] = []
    for source_id in source_ids:
        minimum = minimum_by_source.get(source_id, {})
        validation = validation_by_source.get(source_id, {})
        enablement = enablement_by_source.get(source_id, {})
        apply = apply_by_source.get(source_id, {})
        preflight = preflight_by_source.get(source_id, [])
        blocked = [row for row in preflight if row.get("blocking_issue") == "true"]
        blocked_metrics = join(row.get("metric", "") for row in blocked)
        fields = join(row.get("fields_to_populate", "") for row in blocked)
        satisfying_total = sum(int_value(row.get("satisfying_row_count", "0")) for row in preflight)
        export_rows = int_value(validation.get("export_row_count", enablement.get("export_row_count", "0")))
        validation_status = validation.get("validation_status", enablement.get("export_validation_status", "missing"))
        enablement_status = enablement.get("enablement_status", apply.get("enablement_status", "missing"))
        priority = priority_for(export_rows, validation_status, enablement_status, len(blocked), minimum.get("recommended_rank", "999"))
        dashboard_rows.append({
            "source_id": source_id,
            "recommended_rank": minimum.get("recommended_rank", enablement.get("recommended_rank", "999")),
            "record_layer": minimum.get("record_layer", enablement.get("record_layer", "NA")),
            "required_for_hypotheses": minimum.get("required_for_hypotheses", enablement.get("required_for_hypotheses", "NA")),
            "expected_export_path": validation.get("expected_export_path", enablement.get("export_path", minimum.get("expected_export_path", "NA"))),
            "export_exists": validation.get("export_exists", "false"),
            "export_row_count": str(export_rows),
            "validation_status": validation_status,
            "enablement_status": enablement_status,
            "enablement_action_status": apply.get("action_status", "missing"),
            "blocked_metric_count": str(len(blocked)),
            "blocked_metrics": blocked_metrics,
            "fields_to_populate": fields,
            "satisfying_row_count_total": str(satisfying_total),
            "curation_priority": priority,
            "next_action": action_for(priority, fields, blocked_metrics),
        })

    dashboard_rows.sort(key=rank_tuple)
    priority_counts: dict[str, int] = {}
    for row in dashboard_rows:
        priority_counts[row["curation_priority"]] = priority_counts.get(row["curation_priority"], 0) + 1
    report_rows = [
        {
            "severity": "info",
            "item": "source_readiness_dashboard",
            "message": f"sources={len(dashboard_rows)}; priority_counts=" + ";".join(f"{key}:{value}" for key, value in sorted(priority_counts.items())),
        }
    ]
    if any(row["curation_priority"] in {"create_reviewed_export", "populate_reviewed_rows", "fix_export_validation"} for row in dashboard_rows):
        report_rows.append({"severity": "warning", "item": "source_readiness_dashboard", "message": "One or more sources require curation before H1-H6 sample support can pass."})

    write_tsv(Path(args.dashboard_output), DASHBOARD_COLUMNS, dashboard_rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report_rows)
    print(f"Wrote source readiness dashboard for {len(dashboard_rows)} source(s).")


if __name__ == "__main__":
    main()
