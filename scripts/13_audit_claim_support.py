#!/usr/bin/env python3
"""Audit manuscript claim support against current workflow evidence."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


AUDIT_COLUMNS = [
    "claim_id",
    "linked_hypotheses",
    "claim_type",
    "ledger_status",
    "evidence_sources",
    "workflow_support_status",
    "hypothesis_trace_status",
    "model_summary_status",
    "external_evidence_origin_status",
    "real_claim_use_status",
    "allowed_current_claim_level",
    "manuscript_use_status",
    "forbidden_claim_reason",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "status", "message"]
HYPOTHESES = ["H1", "H2", "H3", "H4", "H5", "H6"]
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit claim support against current workflow outputs.")
    parser.add_argument("--claim-ledger", required=True, help="docs/claim_ledger.md.")
    parser.add_argument("--workflow-validation", required=True, help="workflow_validation_report.tsv.")
    parser.add_argument("--hypothesis-summary", required=True, help="models/hypothesis_summary.tsv.")
    parser.add_argument("--hypothesis-traceability", required=True, help="hypothesis_traceability.tsv.")
    parser.add_argument("--external-evidence-plan", required=True, help="external_evidence_plan.tsv.")
    parser.add_argument("--audit-output", required=True, help="Output claim support audit TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
        return reader.fieldnames or [], rows


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(columns)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def split_values(value: str) -> list[str]:
    if is_missing(value):
        return []
    cleaned = value.replace(",", ";")
    return [part.strip() for part in cleaned.split(";") if part.strip()]


def join(values: Iterable[str]) -> str:
    output: list[str] = []
    for value in values:
        if not is_missing(value) and value not in output:
            output.append(value)
    return ";".join(output) if output else "NA"


def by_key(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {row.get(key, ""): row for row in rows if row.get(key)}


def parse_claim_ledger(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not path.exists():
        return rows
    headers: list[str] = []
    in_claims = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line == "## Claims":
            in_claims = True
            continue
        if in_claims and line.startswith("## "):
            break
        if not in_claims or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if cells and cells[0] == "Claim ID":
            headers = cells
            continue
        if not headers or not cells or not cells[0].startswith("C"):
            continue
        rows.append({headers[index]: cells[index] if index < len(cells) else "" for index in range(len(headers))})
    return rows


def workflow_status(validation_rows: list[dict[str, str]]) -> str:
    if not validation_rows:
        return "missing_validation_report"
    if any(row.get("severity") == "error" or row.get("status") == "fail" for row in validation_rows):
        return "workflow_validation_has_errors"
    required_pass = {"documentation", "claim_ledger", "scripts", "figures"}
    statuses = {row.get("item"): row.get("status") for row in validation_rows}
    missing = sorted(item for item in required_pass if statuses.get(item) != "pass")
    if missing:
        return "workflow_supported_with_gaps:" + ";".join(missing)
    return "workflow_supported"


def evidence_origin_for_hypotheses(evidence_rows: list[dict[str, str]], hypotheses: list[str]) -> tuple[str, str]:
    if not hypotheses:
        return "not_applicable", "not_applicable"
    relevant: list[dict[str, str]] = []
    for row in evidence_rows:
        supported = split_values(row.get("hypotheses_supported", ""))
        if any(hypothesis in supported for hypothesis in hypotheses):
            relevant.append(row)
    origins = join(row.get("evidence_origin", "") for row in relevant)
    real_use = join(row.get("real_claim_use_status", "") for row in relevant)
    if not relevant:
        return "missing_external_evidence_rows", "not_usable_for_real_claims"
    return origins, real_use


def linked_hypotheses(value: str) -> list[str]:
    if "H1-H6" in value:
        return HYPOTHESES
    return [hypothesis for hypothesis in HYPOTHESES if hypothesis in value]


def summarize_statuses(hypotheses: list[str], row_map: dict[str, dict[str, str]], column: str) -> str:
    if not hypotheses:
        return "not_applicable"
    return join(row_map.get(hypothesis, {}).get(column, "missing") for hypothesis in hypotheses)


def decide_claim_level(
    claim_id: str,
    ledger_status: str,
    workflow_support: str,
    trace_status: str,
    model_status: str,
    evidence_origins: str,
    real_use: str,
) -> tuple[str, str, str, str]:
    if claim_id == "C9" or "experimental_validation_required" in ledger_status:
        return (
            "experimental_validation_required",
            "do_not_use_as_result_claim",
            "This workflow does not generate therapeutic, biochemical, adsorption, EOP, or infection-assay validation.",
            "Add experimental validation before making this claim.",
        )
    if claim_id == "C1":
        if workflow_support == "workflow_supported":
            return (
                "workflow_supported",
                "methods_or_resource_claim_allowed",
                "NA",
                "No action required for workflow/resource wording; biological conclusions still require real evidence.",
            )
        return (
            "workflow_gap",
            "do_not_use_until_workflow_validation_passes",
            workflow_support,
            "Resolve workflow validation gaps before presenting the repository as a reproducible framework.",
        )
    if "mock_fixture" in evidence_origins:
        return (
            "mock_only_scaffold_support",
            "mock_only_not_real_claims",
            "Mock fixtures verify workflow plumbing but cannot support real biological conclusions.",
            "Replace mock inputs with reviewed real evidence exports and rerun the workflow.",
        )
    if "not_usable_for_real_claims" in real_use or "not_configured" in evidence_origins:
        return (
            "data_dependent_not_supported",
            "hypothesis_or_planned_test_only",
            "Required external evidence is not configured or is not usable for real claims.",
            "Configure reviewed real evidence TSVs, populate samples, and rerun model comparisons.",
        )
    if "blocked" in trace_status or "warn" in model_status or "missing" in model_status:
        return (
            "data_dependent_not_supported",
            "hypothesis_or_planned_test_only",
            "Traceability or model summary rows are not ready for interpretation.",
            "Resolve traceability blockers and obtain ok model rows before strengthening the claim.",
        )
    if "ok" in model_status or "pass" in model_status or "ready" in trace_status:
        return (
            "computational_inference",
            "cautious_computational_claim_allowed",
            "Experimental validation is still required for function, specificity, and infection success.",
            "Use cautious language and keep assay-dependent claims in limitations.",
        )
    return (
        "limited_workflow_support",
        "hypothesis_or_planned_test_only",
        "Current evidence is insufficient for a biological claim.",
        "Inspect hypothesis traceability and model summaries for the next missing evidence layer.",
    )


def main() -> None:
    args = parse_args()
    claims = parse_claim_ledger(Path(args.claim_ledger))
    _, validation_rows = read_tsv(Path(args.workflow_validation))
    _, summary_rows = read_tsv(Path(args.hypothesis_summary))
    _, trace_rows = read_tsv(Path(args.hypothesis_traceability))
    _, evidence_rows = read_tsv(Path(args.external_evidence_plan))

    summary_map = by_key(summary_rows, "hypothesis")
    trace_map = by_key(trace_rows, "hypothesis")
    workflow_support = workflow_status(validation_rows)
    audit_rows: list[dict[str, str]] = []
    for claim in claims:
        claim_id = claim.get("Claim ID", "")
        hypotheses = linked_hypotheses(claim.get("Linked hypothesis", ""))
        trace_status = summarize_statuses(hypotheses, trace_map, "overall_trace_status")
        model_status = summarize_statuses(hypotheses, summary_map, "summary_status")
        evidence_origins, real_use = evidence_origin_for_hypotheses(evidence_rows, hypotheses)
        level, use_status, forbidden_reason, next_action = decide_claim_level(
            claim_id,
            claim.get("Current status", ""),
            workflow_support,
            trace_status,
            model_status,
            evidence_origins,
            real_use,
        )
        audit_rows.append(
            {
                "claim_id": claim_id,
                "linked_hypotheses": join(hypotheses),
                "claim_type": claim.get("Claim type", ""),
                "ledger_status": claim.get("Current status", ""),
                "evidence_sources": claim.get("Current evidence source", ""),
                "workflow_support_status": workflow_support,
                "hypothesis_trace_status": trace_status,
                "model_summary_status": model_status,
                "external_evidence_origin_status": evidence_origins,
                "real_claim_use_status": real_use,
                "allowed_current_claim_level": level,
                "manuscript_use_status": use_status,
                "forbidden_claim_reason": forbidden_reason,
                "next_action": next_action,
            }
        )

    real_claim_ready = [row for row in audit_rows if row["manuscript_use_status"] == "cautious_computational_claim_allowed"]
    mock_only = [row for row in audit_rows if row["manuscript_use_status"] == "mock_only_not_real_claims"]
    restricted = [
        row
        for row in audit_rows
        if row["manuscript_use_status"] in {"hypothesis_or_planned_test_only", "do_not_use_as_result_claim", "do_not_use_until_workflow_validation_passes"}
    ]
    report_rows = [
        {
            "severity": "info" if claims else "error",
            "item": "claim_support_audit",
            "status": "pass" if claims else "fail",
            "message": f"claims={len(audit_rows)}; cautious_real_claims={len(real_claim_ready)}; mock_only={len(mock_only)}; restricted={len(restricted)}",
        }
    ]
    if restricted:
        report_rows.append(
            {
                "severity": "warning",
                "item": "claim_support_audit",
                "status": "warn",
                "message": "One or more claims must remain hypotheses, planned tests, or experimental-validation targets.",
            }
        )

    write_tsv(Path(args.audit_output), AUDIT_COLUMNS, audit_rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report_rows)
    print(f"Wrote claim support audit rows for {len(audit_rows)} claims.")


if __name__ == "__main__":
    main()
