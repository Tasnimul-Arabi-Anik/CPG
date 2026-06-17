#!/usr/bin/env python3
"""Build an H1-H6 traceability matrix across sources, evidence, models, figures, and claims."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


TRACE_COLUMNS = [
    "hypothesis",
    "primary_question",
    "source_unlock_status",
    "missing_sources",
    "external_evidence_status",
    "missing_evidence",
    "sample_support_status",
    "model_summary_status",
    "claim_status",
    "figure_ids",
    "figure_statuses",
    "readiness_status",
    "overall_trace_status",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]
HYPOTHESES = ["H1", "H2", "H3", "H4", "H5", "H6"]
HYPOTHESIS_FIGURES = {
    "H1": ["figure_3_rbp_module_network", "figure_4_k_o_association"],
    "H2": ["figure_3_rbp_module_network", "figure_4_k_o_association"],
    "H3": ["figure_3_rbp_module_network", "figure_6_novelty_prioritization"],
    "H4": ["figure_5_defense_counterdefense"],
    "H5": ["figure_5_defense_counterdefense"],
    "H6": ["figure_6_novelty_prioritization"],
}
MISSING = {"", "NA", "N/A", "na", "n/a", "None", "none", "-"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build H1-H6 traceability matrix.")
    parser.add_argument("--source-plan", required=True, help="minimum_hypothesis_source_plan.tsv.")
    parser.add_argument("--evidence-plan", required=True, help="external_evidence_unlock_plan.tsv.")
    parser.add_argument("--sample-support", required=True, help="sample_support_by_hypothesis.tsv.")
    parser.add_argument("--hypothesis-summary", required=True, help="models/hypothesis_summary.tsv.")
    parser.add_argument("--hypothesis-coverage", required=True, help="validation/hypothesis_coverage.tsv.")
    parser.add_argument("--figure-manifest", required=True, help="figures/figure_manifest.tsv.")
    parser.add_argument("--readiness", required=True, help="validation/study_readiness.tsv.")
    parser.add_argument("--trace-output", required=True, help="Output traceability TSV.")
    parser.add_argument("--report-output", required=True, help="Output report TSV.")
    return parser.parse_args()


def is_missing(value: str | None) -> bool:
    return value is None or value.strip() in MISSING


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


def split_values(value: str) -> list[str]:
    if is_missing(value):
        return []
    return [token.strip() for token in value.replace(",", ";").split(";") if token.strip()]


def join(values: Iterable[str]) -> str:
    cleaned: list[str] = []
    for value in values:
        if not is_missing(value) and value not in cleaned:
            cleaned.append(value)
    return ";".join(cleaned) if cleaned else "NA"


def figure_status_text(figure_ids: list[str], figure_map: dict[str, dict[str, str]]) -> str:
    values = []
    for figure_id in figure_ids:
        row = figure_map.get(figure_id, {})
        values.append(f"{figure_id}:{row.get('status', 'missing')}")
    return ";".join(values) if values else "NA"


def trace_status(parts: list[str]) -> str:
    if any(part in {"missing", "fail", "blocked", "blocked_missing_required_sources", "blocked_missing_required_evidence", "blocked_minimum_sample_support"} for part in parts):
        return "blocked"
    if any(part in {"warn", "data_dependent", "empty_schema_valid"} for part in parts):
        return "limited"
    ready_parts = {
        "pass",
        "ok",
        "ready",
        "ready_minimum_sample_support",
        "ready_sources",
        "ready_evidence",
        "minimum_evidence_ready",
        "supported",
        "workflow_supported",
    }
    if all(part in ready_parts for part in parts):
        return "ready"
    return "limited"


def main() -> None:
    args = parse_args()
    _, source_rows = read_tsv(Path(args.source_plan))
    _, evidence_rows = read_tsv(Path(args.evidence_plan))
    _, support_rows = read_tsv(Path(args.sample_support))
    _, summary_rows = read_tsv(Path(args.hypothesis_summary))
    _, coverage_rows = read_tsv(Path(args.hypothesis_coverage))
    _, figure_rows = read_tsv(Path(args.figure_manifest))
    _, readiness_rows = read_tsv(Path(args.readiness))

    source_map = by_key(source_rows, "hypothesis")
    evidence_map = by_key(evidence_rows, "hypothesis")
    support_map = by_key(support_rows, "hypothesis")
    summary_map = by_key(summary_rows, "hypothesis")
    coverage_map = by_key(coverage_rows, "hypothesis")
    figure_map = by_key(figure_rows, "figure_id")
    readiness_map = by_key(readiness_rows, "area")

    readiness_status = readiness_map.get("hypothesis_tests", {}).get("status", "missing")
    source_readiness_pass = all(
        readiness_map.get(area, {}).get("status") == "pass"
        for area in ["dataset_curation", "source_curation", "source_acquisition"]
    )
    rows: list[dict[str, str]] = []
    for hypothesis in HYPOTHESES:
        source = source_map.get(hypothesis, {})
        evidence = evidence_map.get(hypothesis, {})
        support = support_map.get(hypothesis, {})
        summary = summary_map.get(hypothesis, {})
        coverage = coverage_map.get(hypothesis, {})
        figure_ids = HYPOTHESIS_FIGURES[hypothesis]
        fig_statuses = figure_status_text(figure_ids, figure_map)
        figure_parts = [figure_map.get(fig, {}).get("status", "missing") for fig in figure_ids]
        source_status = "ready_sources" if source_readiness_pass else source.get("minimum_unlock_status", "missing")
        missing_sources = "NA" if source_readiness_pass else source.get("missing_required_sources", "NA")
        source_action = "No action required." if source_readiness_pass else source.get("next_action", "")
        missing_evidence = evidence.get("blocking_required_evidence", "NA")
        if is_missing(missing_evidence):
            missing_evidence = "NA"
        parts = [
            source_status,
            evidence.get("minimum_unlock_status", "missing"),
            support.get("support_status", "missing"),
            summary.get("summary_status", coverage.get("status", "missing")),
            summary.get("claim_status", "missing"),
            readiness_status,
            *figure_parts,
        ]
        overall = trace_status(parts)
        next_actions = [
            source_action,
            evidence.get("next_action", ""),
            support.get("next_action", ""),
            summary.get("next_action", coverage.get("notes", "")),
        ]
        rows.append({
            "hypothesis": hypothesis,
            "primary_question": summary.get("primary_question", coverage.get("required_test", "NA")),
            "source_unlock_status": source_status,
            "missing_sources": missing_sources,
            "external_evidence_status": evidence.get("minimum_unlock_status", "missing"),
            "missing_evidence": missing_evidence,
            "sample_support_status": support.get("support_status", "missing"),
            "model_summary_status": summary.get("summary_status", coverage.get("status", "missing")),
            "claim_status": summary.get("claim_status", "missing"),
            "figure_ids": ";".join(figure_ids),
            "figure_statuses": fig_statuses,
            "readiness_status": readiness_status,
            "overall_trace_status": overall,
            "next_action": join(next_actions),
        })

    blocked = [row for row in rows if row.get("overall_trace_status") == "blocked"]
    limited = [row for row in rows if row.get("overall_trace_status") == "limited"]
    ready = [row for row in rows if row.get("overall_trace_status") == "ready"]
    report_rows = [
        {"severity": "info", "item": "hypothesis_traceability", "message": f"hypotheses={len(rows)}; ready={len(ready)}; limited={len(limited)}; blocked={len(blocked)}"}
    ]
    if blocked:
        report_rows.append({"severity": "warning", "item": "hypothesis_traceability", "message": "One or more hypotheses are blocked upstream of interpretation."})

    write_tsv(Path(args.trace_output), TRACE_COLUMNS, rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report_rows)
    print(f"Wrote traceability rows for {len(rows)} hypotheses.")


if __name__ == "__main__":
    main()
