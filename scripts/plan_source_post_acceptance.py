#!/usr/bin/env python3
"""Plan downstream actions after source curation work orders are accepted."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


PLAN_COLUMNS = [
    "source_id",
    "work_order_ids",
    "acceptance_statuses",
    "accepted_work_orders",
    "blocking_work_orders",
    "enablement_status",
    "import_enabled",
    "catalog_enabled",
    "manifest_row_count",
    "transition_status",
    "next_command",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan source transition after work-order acceptance.")
    parser.add_argument("--acceptance", required=True, help="source_work_order_acceptance.tsv.")
    parser.add_argument("--enablement-plan", required=True, help="source_enablement_plan.tsv.")
    parser.add_argument("--enablement-apply", required=True, help="source_enablement_apply_report.tsv.")
    parser.add_argument("--plan-output", required=True, help="Output transition plan TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    return parser.parse_args()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
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
    return {row.get(key, ""): row for row in rows if row.get(key)}


def grouped(rows: list[dict[str, str]], key: str) -> dict[str, list[dict[str, str]]]:
    output: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        value = row.get(key, "")
        if value:
            output.setdefault(value, []).append(row)
    return output


def join(values: Iterable[str]) -> str:
    cleaned: list[str] = []
    for value in values:
        if value and value not in cleaned:
            cleaned.append(value)
    return ";".join(cleaned) if cleaned else "NA"


def transition_for(rows: list[dict[str, str]], enablement: dict[str, str], apply: dict[str, str]) -> tuple[str, str, str]:
    accepted = [row for row in rows if row.get("acceptance_status") == "accepted"]
    blocking = [row for row in rows if row.get("blocking_issue") == "true"]
    if blocking:
        return (
            "waiting_for_work_order_acceptance",
            "NA",
            "Complete source curation work orders before enabling import or catalog entries.",
        )
    status = enablement.get("enablement_status", "missing")
    if accepted and status == "ready_for_enablement":
        return (
            "ready_to_enable_import",
            "python scripts/apply_source_enablement.py --enablement-plan results/qc/source_enablement_plan.tsv --imports-config config/source_imports.yaml --catalog config/source_catalog.yaml --report-output results/qc/source_enablement_apply_report.tsv --enable-imports --apply --root .",
            "Apply import enablement, rerun source imports, then review generated source manifest.",
        )
    if accepted and enablement.get("import_enabled") == "true" and int(enablement.get("manifest_row_count", "0") or "0") == 0:
        return (
            "ready_to_run_import",
            "python scripts/run_workflow.py --config config/workflow.yaml --stages stage_0_source_imports stage_0_source_plan stage_0_source_audit stage_0_source_enablement",
            "Run source imports and review the populated source manifest before catalog enablement.",
        )
    if accepted and enablement.get("catalog_enabled") != "true" and int(enablement.get("manifest_row_count", "0") or "0") > 0:
        return (
            "ready_to_enable_catalog",
            "python scripts/apply_source_enablement.py --enablement-plan results/qc/source_enablement_plan.tsv --imports-config config/source_imports.yaml --catalog config/source_catalog.yaml --report-output results/qc/source_enablement_apply_report.tsv --enable-catalog --apply --root .",
            "Enable reviewed catalog source, then rerun sample builder and downstream checks.",
        )
    if accepted and status == "enabled_for_sample_build":
        return (
            "ready_for_sample_support_rerun",
            "python scripts/run_workflow.py --config config/workflow.yaml --stages stage_0_samples stage_0_source_overlap stage_0_sample_support stage_1_manifest stage_1_sequence_acquisition stage_1_sequence_qc stage_7_models stage_8_figures stage_9_validation stage_10_study_readiness stage_11_hypothesis_traceability stage_11_goal_completion_audit",
            "Rerun sample support and downstream analysis scaffolds.",
        )
    return (
        "waiting_for_enablement_plan_update",
        "python scripts/run_workflow.py --config config/workflow.yaml --stages stage_0_source_export_validation stage_0_source_imports stage_0_source_plan stage_0_source_audit stage_0_source_enablement stage_0_source_enablement_apply",
        "Regenerate validation and enablement plans after source curation changes.",
    )


def main() -> None:
    args = parse_args()
    _, acceptance_rows = read_tsv(Path(args.acceptance))
    _, enablement_rows = read_tsv(Path(args.enablement_plan))
    _, apply_rows = read_tsv(Path(args.enablement_apply))
    acceptance_by_source = grouped(acceptance_rows, "source_id")
    enablement_by_source = by_key(enablement_rows, "source_id")
    apply_by_source = by_key(apply_rows, "source_id")
    source_ids = sorted(set(acceptance_by_source) | set(enablement_by_source) | set(apply_by_source))

    plan_rows: list[dict[str, str]] = []
    for source_id in source_ids:
        rows = acceptance_by_source.get(source_id, [])
        enablement = enablement_by_source.get(source_id, {})
        apply = apply_by_source.get(source_id, {})
        transition_status, command, action = transition_for(rows, enablement, apply)
        accepted_count = sum(1 for row in rows if row.get("acceptance_status") == "accepted")
        blocking_count = sum(1 for row in rows if row.get("blocking_issue") == "true")
        plan_rows.append({
            "source_id": source_id,
            "work_order_ids": join(row.get("work_order_id", "") for row in rows),
            "acceptance_statuses": join(row.get("acceptance_status", "") for row in rows),
            "accepted_work_orders": str(accepted_count),
            "blocking_work_orders": str(blocking_count),
            "enablement_status": enablement.get("enablement_status", apply.get("enablement_status", "missing")),
            "import_enabled": enablement.get("import_enabled", apply.get("import_enabled_after", "false")),
            "catalog_enabled": enablement.get("catalog_enabled", apply.get("catalog_enabled_after", "false")),
            "manifest_row_count": enablement.get("manifest_row_count", "0"),
            "transition_status": transition_status,
            "next_command": command,
            "next_action": action,
        })

    counts: dict[str, int] = {}
    for row in plan_rows:
        counts[row["transition_status"]] = counts.get(row["transition_status"], 0) + 1
    report_rows = [
        {"severity": "info", "item": "source_post_acceptance", "message": f"sources={len(plan_rows)}; transition_counts=" + ";".join(f"{k}:{v}" for k, v in sorted(counts.items()))}
    ]
    if any(row["transition_status"] == "waiting_for_work_order_acceptance" for row in plan_rows):
        report_rows.append({"severity": "warning", "item": "source_post_acceptance", "message": "One or more sources are still waiting for accepted curation work orders."})

    write_tsv(Path(args.plan_output), PLAN_COLUMNS, plan_rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report_rows)
    print(f"Wrote post-acceptance transition plan for {len(plan_rows)} source(s).")


if __name__ == "__main__":
    main()
