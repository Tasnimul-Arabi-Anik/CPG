#!/usr/bin/env python3
"""Check configured external evidence TSVs for readiness and provenance lint."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


ACCEPTANCE_COLUMNS = [
    "evidence_id",
    "analysis_layer",
    "optional_input_key",
    "configured_input_path",
    "configured_input_exists",
    "configured_input_rows",
    "configured_input_schema_status",
    "evidence_status",
    "evidence_origin",
    "real_claim_use_status",
    "blocking_for_manuscript",
    "rows_with_evidence_source",
    "rows_with_notes",
    "provenance_lint",
    "content_lint",
    "acceptance_status",
    "blocking_issue",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}
GENERATED_RESULT_PREFIXES = (
    "results/annotations/",
    "results/clusters/",
    "results/defense_systems/",
    "results/figures/",
    "results/host_features/",
    "results/models/",
    "results/qc/",
    "results/rbp_depolymerase/",
    "results/validation/",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check external evidence TSV acceptance from the evidence plan.")
    parser.add_argument("--evidence-plan", required=True, help="External evidence plan TSV.")
    parser.add_argument("--acceptance-output", required=True, help="Output acceptance TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    parser.add_argument("--root", default=".", help="Repository root for resolving configured paths.")
    return parser.parse_args()


def normalize(value: object) -> str:
    return "" if value is None else str(value).strip()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def display_path(root: Path, path: Path | str) -> str:
    path_obj = Path(path)
    if not str(path_obj):
        return ""
    try:
        return path_obj.resolve().relative_to(root.resolve()).as_posix()
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


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def provenance_counts(path: Path) -> tuple[int, int, str]:
    fieldnames, rows = read_tsv(path)
    if not rows:
        return 0, 0, "NA"
    has_source_column = "evidence_source" in fieldnames or "tool" in fieldnames or "evidence" in fieldnames
    has_notes_column = "notes" in fieldnames
    source_count = 0
    notes_count = 0
    for row in rows:
        if not is_missing(row.get("evidence_source")) or not is_missing(row.get("tool")) or not is_missing(row.get("evidence")):
            source_count += 1
        if not is_missing(row.get("notes")):
            notes_count += 1
    lint: list[str] = []
    if not has_source_column:
        lint.append("missing_evidence_source_or_tool_column")
    if not has_notes_column:
        lint.append("missing_notes_column")
    if source_count == 0:
        lint.append("no_rows_with_evidence_source_or_tool")
    if notes_count == 0:
        lint.append("no_rows_with_notes")
    return source_count, notes_count, ";".join(lint) if lint else "NA"


def content_lint(root: Path, evidence_id: str, configured_path: Path) -> str:
    lint: list[str] = []
    configured_display = display_path(root, configured_path).replace("\\", "/")
    if any(configured_display.startswith(prefix) for prefix in GENERATED_RESULT_PREFIXES):
        lint.append("configured_path_is_workflow_generated_output")
    fieldnames, rows = read_tsv(configured_path)
    if evidence_id == "phage_antidefense_candidates" and "evidence_type" in fieldnames:
        inferred_rows = [row for row in rows if row.get("evidence_type") == "annotation_keyword_inference"]
        if inferred_rows:
            lint.append(f"annotation_keyword_inference_rows={len(inferred_rows)}")
    return ";".join(lint) if lint else "NA"


def classify(row: dict[str, str], source_count: int, notes_count: int, provenance_lint: str, evidence_content_lint: str) -> tuple[str, str, str]:
    status = row.get("evidence_status", "")
    schema = row.get("configured_input_schema_status", "")
    rows = row.get("configured_input_rows", "0")
    blocking_for_manuscript = row.get("blocking_for_manuscript", "false") == "true"
    if status == "provided_input_ready" and schema == "pass" and rows not in {"", "0"}:
        if evidence_content_lint != "NA":
            return (
                "content_rejected",
                "true",
                "Fix content lint before accepting this TSV as production external evidence.",
            )
        if provenance_lint == "NA":
            return "accepted", "false", "No action required; provenance fields are populated."
        return (
            "accepted_with_provenance_lint",
            "false",
            "Review provenance lint before manuscript use; keep claim-support audit conservative.",
        )
    if status == "configured_input_schema_invalid":
        return "schema_invalid", "true", "Fix missing required columns in the configured evidence TSV."
    if status == "configured_input_empty":
        return "configured_empty", "true", "Populate the configured evidence TSV or clear the optional input."
    if status == "configured_input_missing":
        return "configured_missing", "true", "Create the configured evidence TSV or update config/workflow.yaml."
    if status == "waiting_for_sequence_data":
        return "waiting_for_sequence_data", str(blocking_for_manuscript).lower(), "Acquire reviewed local sequences and rerun sequence QC."
    if status in {"missing_tool_or_input", "manual_evidence_required", "ready_to_run_external_tool"}:
        return status, str(blocking_for_manuscript).lower(), row.get("next_action", "")
    return "not_ready", str(blocking_for_manuscript).lower(), row.get("next_action", "")


def check_acceptance(root: Path, evidence_plan: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    fieldnames, plan_rows = read_tsv(evidence_plan)
    required = {"evidence_id", "configured_input_path", "evidence_status", "configured_input_schema_status"}
    missing = sorted(required - set(fieldnames))
    if missing:
        report = [{"severity": "error", "item": "external_evidence_acceptance", "message": "Missing evidence plan columns: " + ";".join(missing)}]
        return [], report

    acceptance: list[dict[str, str]] = []
    for row in plan_rows:
        configured_path_text = row.get("configured_input_path", "")
        configured_path = resolve(root, configured_path_text) if configured_path_text else Path("")
        has_configured_file = bool(configured_path_text and configured_path.exists() and configured_path.is_file())
        source_count, notes_count, lint = provenance_counts(configured_path) if has_configured_file else (0, 0, "NA")
        evidence_content_lint = content_lint(root, row.get("evidence_id", ""), configured_path) if has_configured_file else "NA"
        acceptance_status, blocking_issue, next_action = classify(row, source_count, notes_count, lint, evidence_content_lint)
        acceptance.append(
            {
                "evidence_id": row.get("evidence_id", ""),
                "analysis_layer": row.get("analysis_layer", ""),
                "optional_input_key": row.get("optional_input_key", ""),
                "configured_input_path": display_path(root, configured_path) if configured_path_text else "",
                "configured_input_exists": row.get("configured_input_exists", ""),
                "configured_input_rows": row.get("configured_input_rows", ""),
                "configured_input_schema_status": row.get("configured_input_schema_status", ""),
                "evidence_status": row.get("evidence_status", ""),
                "evidence_origin": row.get("evidence_origin", ""),
                "real_claim_use_status": row.get("real_claim_use_status", ""),
                "blocking_for_manuscript": row.get("blocking_for_manuscript", ""),
                "rows_with_evidence_source": str(source_count),
                "rows_with_notes": str(notes_count),
                "provenance_lint": lint,
                "content_lint": evidence_content_lint,
                "acceptance_status": acceptance_status,
                "blocking_issue": blocking_issue,
                "next_action": next_action,
            }
        )

    counts: dict[str, int] = {}
    for row in acceptance:
        counts[row["acceptance_status"]] = counts.get(row["acceptance_status"], 0) + 1
    blocking = sum(1 for row in acceptance if row["blocking_issue"] == "true")
    provenance_lint = sum(1 for row in acceptance if row["provenance_lint"] != "NA")
    content_lint_count = sum(1 for row in acceptance if row["content_lint"] != "NA")
    report = [
        {
            "severity": "warning" if blocking else "info",
            "item": "external_evidence_acceptance",
            "message": f"evidence={len(acceptance)}; blocking={blocking}; provenance_lint={provenance_lint}; content_lint={content_lint_count}; statuses="
            + ";".join(f"{key}:{value}" for key, value in sorted(counts.items())),
        }
    ]
    return acceptance, report


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    evidence_plan = resolve(root, args.evidence_plan)
    acceptance, report = check_acceptance(root, evidence_plan)
    write_tsv(resolve(root, args.acceptance_output), ACCEPTANCE_COLUMNS, acceptance)
    write_tsv(resolve(root, args.report_output), REPORT_COLUMNS, report)
    errors = sum(1 for row in report if row.get("severity") == "error")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
