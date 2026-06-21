#!/usr/bin/env python3
"""Audit the original project goal against current workflow evidence."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


AUDIT_COLUMNS = [
    "requirement_id",
    "objective_requirement",
    "evidence_paths",
    "evidence_summary",
    "status",
    "blocking_for_goal",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
HYPOTHESES = {"H1", "H2", "H3", "H4", "H5", "H6"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit project-goal completion from current workflow evidence.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--results-dir", default="results", help="Audited results directory.")
    parser.add_argument("--audit-output", required=True, help="Output objective audit TSV.")
    parser.add_argument("--report-output", required=True, help="Output objective audit report TSV.")
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


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def display_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def row_by_item(rows: list[dict[str, str]], item: str) -> dict[str, str]:
    for row in rows:
        if row.get("item") == item:
            return row
    return {}


def add(requirements: list[dict[str, str]], req_id: str, text: str, paths: list[Path], root: Path, summary: str, status: str, blocking: bool, action: str) -> None:
    requirements.append({
        "requirement_id": req_id,
        "objective_requirement": text,
        "evidence_paths": ";".join(display_path(root, path) for path in paths),
        "evidence_summary": summary,
        "status": status,
        "blocking_for_goal": str(blocking).lower(),
        "next_action": action,
    })


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    results_dir = resolve(root, args.results_dir)
    audit_output = resolve(root, args.audit_output)
    report_output = resolve(root, args.report_output)

    _, run_rows = read_tsv(results_dir / "validation/workflow_run_report.tsv")
    _, validation_rows = read_tsv(results_dir / "validation/workflow_validation_report.tsv")
    _, schema_rows = read_tsv(results_dir / "validation/schema_validation.tsv")
    _, hypothesis_rows = read_tsv(results_dir / "validation/hypothesis_coverage.tsv")
    _, readiness_rows = read_tsv(results_dir / "validation/study_readiness.tsv")
    _, sample_support_rows = read_tsv(results_dir / "qc/sample_support_by_hypothesis.tsv")
    _, sample_rows = read_tsv(results_dir / "source_builder/samples.tsv")

    requirements: list[dict[str, str]] = []

    run_pass = [row for row in run_rows if row.get("status") == "pass"]
    run_fail = [row for row in run_rows if row.get("status") == "fail"]
    add(
        requirements,
        "G01",
        "Workflow scripts run from config without failed stages.",
        [results_dir / "validation/workflow_run_report.tsv"],
        root,
        f"stages={len(run_rows)}; pass={len(run_pass)}; fail={len(run_fail)}",
        "pass" if run_rows and not run_fail else "fail",
        bool(run_fail or not run_rows),
        "Rerun `python scripts/run_workflow.py --config config/workflow.yaml` and fix failed stages." if run_fail or not run_rows else "No action required.",
    )

    missing_outputs = [row for row in schema_rows if row.get("exists") != "true"]
    schema_fail = [row for row in schema_rows if row.get("status") == "fail"]
    non_result_paths = [row.get("path", "") for row in schema_rows if row.get("path", "").startswith("results/") is False]
    add(
        requirements,
        "G02",
        "Required workflow outputs are written under results/ with valid schemas.",
        [results_dir / "validation/schema_validation.tsv"],
        root,
        f"schemas={len(schema_rows)}; missing_outputs={len(missing_outputs)}; schema_fail={len(schema_fail)}; non_results_paths={len(non_result_paths)}",
        "pass" if schema_rows and not missing_outputs and not schema_fail and not non_result_paths else "fail",
        bool(missing_outputs or schema_fail or non_result_paths or not schema_rows),
        "Fix missing/invalid outputs or route outputs under results/." if missing_outputs or schema_fail or non_result_paths or not schema_rows else "No action required.",
    )

    observed_hypotheses = {row.get("hypothesis", "") for row in hypothesis_rows}
    pass_hypotheses = {row.get("hypothesis", "") for row in hypothesis_rows if row.get("status") == "pass"}
    warn_hypotheses = {row.get("hypothesis", "") for row in hypothesis_rows if row.get("status") == "warn"}
    fail_hypotheses = {row.get("hypothesis", "") for row in hypothesis_rows if row.get("status") == "fail"}
    missing_hypotheses = HYPOTHESES - observed_hypotheses
    h4_endpoint_limited = any(
        row.get("hypothesis") == "H4"
        and row.get("analysis_available") == "false"
        and row.get("data_adequate") == "false"
        and "blocked_no_productive_infection_labels" in row.get("notes", "")
        for row in hypothesis_rows
    )
    only_nonblocking_h4 = warn_hypotheses <= {"H4"} and h4_endpoint_limited and not fail_hypotheses and not missing_hypotheses
    if pass_hypotheses == HYPOTHESES or (len(pass_hypotheses) >= 5 and only_nonblocking_h4):
        status = "pass"
        blocking = False
        action = "No action required for the current dry-lab benchmark; H4 remains future work until productive-infection, plaque, or EOP outcomes are curated." if only_nonblocking_h4 else "No action required."
    elif observed_hypotheses == HYPOTHESES and not fail_hypotheses:
        status = "warn"
        blocking = True
        action = "Populate source/sequence/evidence inputs until H1-H6 coverage rows pass, or explicitly scope unsupported endpoints as future work."
    else:
        status = "fail"
        blocking = True
        action = "Populate source/sequence/evidence inputs until H1-H6 coverage rows exist and pass, or explicitly scope unsupported endpoints as future work."
    add(
        requirements,
        "G03",
        "Each major hypothesis H1-H6 has a quantitative test, analysis-ready row, or explicitly scoped not-testable endpoint limitation.",
        [results_dir / "validation/hypothesis_coverage.tsv", results_dir / "models/model_comparison.tsv"],
        root,
        f"observed={';'.join(sorted(observed_hypotheses)) or 'NA'}; pass={';'.join(sorted(pass_hypotheses)) or 'NA'}; warn={';'.join(sorted(warn_hypotheses)) or 'NA'}; missing={';'.join(sorted(missing_hypotheses)) or 'NA'}; nonblocking_endpoint_limited={'H4' if only_nonblocking_h4 else 'NA'}",
        status,
        blocking,
        action,
    )

    ready_support = [row for row in sample_support_rows if row.get("support_status") == "ready_minimum_sample_support"]
    blocked_support = [row for row in sample_support_rows if row.get("support_status") == "blocked_minimum_sample_support"]
    add(
        requirements,
        "G04",
        "Audited sample support is sufficient for H1-H6 interpretation.",
        [results_dir / "source_builder/samples.tsv", results_dir / "qc/sample_support_by_hypothesis.tsv"],
        root,
        f"sample_rows={len(sample_rows)}; ready_hypotheses={len(ready_support)}; blocked_hypotheses={len(blocked_support)}",
        "pass" if len(sample_rows) > 0 and len(ready_support) >= 6 and not blocked_support else "fail",
        not (len(sample_rows) > 0 and len(ready_support) >= 6 and not blocked_support),
        "Populate reviewed source exports and enable source manifests until sample support passes for H1-H6." if len(sample_rows) == 0 or blocked_support else "No action required.",
    )

    blocking_readiness = [row for row in readiness_rows if row.get("blocking_for_manuscript") == "true"]
    fail_readiness = [row for row in readiness_rows if row.get("status") == "fail"]
    add(
        requirements,
        "G05",
        "Study readiness has no blocking dry-lab benchmark requirements.",
        [results_dir / "validation/study_readiness.tsv"],
        root,
        f"readiness_rows={len(readiness_rows)}; fail={len(fail_readiness)}; blocking={len(blocking_readiness)}",
        "pass" if readiness_rows and not blocking_readiness and not fail_readiness else "fail",
        bool(blocking_readiness or fail_readiness or not readiness_rows),
        "Complete readiness action plan items before claiming the dry-lab benchmark endpoint is achieved." if blocking_readiness or fail_readiness or not readiness_rows else "No action required.",
    )

    doc_items = {item: row_by_item(validation_rows, item).get("status", "") for item in ["documentation", "limitations", "claim_ledger", "figures"]}
    docs_pass = all(status_value == "pass" for status_value in doc_items.values())
    add(
        requirements,
        "G06",
        "Documentation captures methods, figures, novelty/claims, limitations, and speculative claims.",
        [results_dir / "validation/workflow_validation_report.tsv", root / "docs/methods.md", root / "docs/figure_plan.md", root / "docs/limitations.md", root / "docs/claim_ledger.md"],
        root,
        ";".join(f"{key}={value or 'missing'}" for key, value in doc_items.items()),
        "pass" if docs_pass else "fail",
        not docs_pass,
        "Update required docs and validation checks." if not docs_pass else "No action required.",
    )

    blocking = [row for row in requirements if row.get("blocking_for_goal") == "true"]
    fail = [row for row in requirements if row.get("status") == "fail"]
    warn = [row for row in requirements if row.get("status") == "warn"]
    pass_rows = [row for row in requirements if row.get("status") == "pass"]
    report_rows = [
        {"severity": "info", "item": "goal_completion", "message": f"pass={len(pass_rows)}; warn={len(warn)}; fail={len(fail)}; blocking={len(blocking)}"}
    ]
    if blocking or fail or warn:
        report_rows.append({"severity": "warning", "item": "goal_completion", "message": "Goal is not complete; inspect objective audit rows with blocking_for_goal=true."})
    else:
        report_rows.append({"severity": "info", "item": "goal_completion", "message": "All objective-level completion requirements passed."})

    write_tsv(audit_output, AUDIT_COLUMNS, requirements)
    write_tsv(report_output, REPORT_COLUMNS, report_rows)
    print(f"Goal completion audit complete: {len(pass_rows)} pass, {len(warn)} warn, {len(fail)} fail.")


if __name__ == "__main__":
    main()
