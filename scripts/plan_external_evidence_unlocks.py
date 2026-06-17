#!/usr/bin/env python3
"""Map external evidence readiness to H1-H6 downstream analysis unlocks."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


PLAN_COLUMNS = [
    "hypothesis",
    "required_evidence_ids",
    "ready_required_evidence",
    "blocking_required_evidence",
    "minimum_unlock_status",
    "next_action",
    "analysis_layers_unlocked",
]
MATRIX_COLUMNS = [
    "hypothesis",
    "evidence_id",
    "analysis_layer",
    "optional_input_key",
    "evidence_role",
    "evidence_status",
    "blocking_for_manuscript",
    "eligible_sequence_records",
    "tool_status",
    "template_path",
    "configured_input_path",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]

REQUIRED_EVIDENCE_BY_HYPOTHESIS = {
    "H1": ["pairwise_similarity", "phage_annotation", "rbp_domain_evidence", "rbp_structural_evidence", "kleborate_host_features", "kaptive_ko_typing"],
    "H2": ["phage_annotation", "rbp_domain_evidence", "rbp_structural_evidence", "kleborate_host_features", "kaptive_ko_typing"],
    "H3": ["phage_annotation", "rbp_domain_evidence", "rbp_structural_evidence", "phage_antidefense_candidates"],
    "H4": ["phage_annotation", "kaptive_ko_typing", "kleborate_host_features", "host_defense_systems", "phage_antidefense_candidates"],
    "H5": ["kleborate_host_features", "kaptive_ko_typing", "host_defense_systems"],
    "H6": ["pairwise_similarity", "phage_annotation", "rbp_domain_evidence", "rbp_structural_evidence"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan which external evidence tables unlock H1-H6 analyses.")
    parser.add_argument("--external-evidence-plan", required=True, help="External evidence plan TSV.")
    parser.add_argument("--external-evidence-template-manifest", required=True, help="External evidence template manifest TSV.")
    parser.add_argument("--plan-output", required=True, help="Output H1-H6 evidence unlock plan TSV.")
    parser.add_argument("--matrix-output", required=True, help="Output H1-H6 evidence unlock matrix TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    return parser.parse_args()


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


def split_values(value: str) -> list[str]:
    return [item.strip() for item in value.replace(",", ";").split(";") if item.strip()]


def join(values: list[str]) -> str:
    return ";".join(values)


def evidence_ready(row: dict[str, str]) -> bool:
    return row.get("evidence_status") == "provided_input_ready"


def build_unlocks(evidence_rows: list[dict[str, str]], template_rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    by_id = {row.get("evidence_id", ""): row for row in evidence_rows if row.get("evidence_id")}
    templates = {row.get("evidence_id", ""): row for row in template_rows if row.get("evidence_id")}
    plan_rows = []
    matrix_rows = []
    for hypothesis, required_ids in REQUIRED_EVIDENCE_BY_HYPOTHESIS.items():
        ready = [evidence_id for evidence_id in required_ids if evidence_ready(by_id.get(evidence_id, {}))]
        blocking = [evidence_id for evidence_id in required_ids if evidence_id not in ready]
        layers = sorted({by_id.get(evidence_id, {}).get("analysis_layer", "") for evidence_id in required_ids if by_id.get(evidence_id, {}).get("analysis_layer")})
        if blocking:
            status = "blocked_missing_required_evidence"
            next_action = "Generate or configure required evidence TSVs: " + join(blocking)
        else:
            status = "minimum_evidence_ready"
            next_action = "Run downstream workflow stages and inspect model/figure outputs."
        plan_rows.append(
            {
                "hypothesis": hypothesis,
                "required_evidence_ids": join(required_ids),
                "ready_required_evidence": join(ready),
                "blocking_required_evidence": join(blocking),
                "minimum_unlock_status": status,
                "next_action": next_action,
                "analysis_layers_unlocked": join(layers),
            }
        )
        for evidence_id in required_ids:
            evidence = by_id.get(evidence_id, {})
            template = templates.get(evidence_id, {})
            matrix_rows.append(
                {
                    "hypothesis": hypothesis,
                    "evidence_id": evidence_id,
                    "analysis_layer": evidence.get("analysis_layer", ""),
                    "optional_input_key": evidence.get("optional_input_key", ""),
                    "evidence_role": "required",
                    "evidence_status": evidence.get("evidence_status", "evidence_not_configured"),
                    "blocking_for_manuscript": evidence.get("blocking_for_manuscript", "true"),
                    "eligible_sequence_records": evidence.get("eligible_sequence_records", "0"),
                    "tool_status": evidence.get("tool_status", ""),
                    "template_path": template.get("template_path", ""),
                    "configured_input_path": evidence.get("configured_input_path", ""),
                    "next_action": evidence.get("next_action", "Configure or generate this evidence table."),
                }
            )
    return plan_rows, matrix_rows


def main() -> int:
    args = parse_args()
    _, evidence_rows = read_tsv(Path(args.external_evidence_plan))
    _, template_rows = read_tsv(Path(args.external_evidence_template_manifest))
    plan_rows, matrix_rows = build_unlocks(evidence_rows, template_rows)
    blocked = [row for row in plan_rows if row.get("minimum_unlock_status") != "minimum_evidence_ready"]
    report = [
        {
            "severity": "info",
            "item": "external_evidence_unlocks",
            "message": f"hypotheses={len(plan_rows)}; minimum_ready={len(plan_rows) - len(blocked)}; blocked={len(blocked)}; matrix_rows={len(matrix_rows)}",
        }
    ]
    if blocked:
        report.append(
            {
                "severity": "warning",
                "item": "external_evidence_unlocks",
                "message": "One or more hypotheses are blocked by missing required external evidence tables.",
            }
        )
    write_tsv(Path(args.plan_output), PLAN_COLUMNS, plan_rows)
    write_tsv(Path(args.matrix_output), MATRIX_COLUMNS, matrix_rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Wrote external evidence unlock plan for {len(plan_rows)} hypotheses.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
