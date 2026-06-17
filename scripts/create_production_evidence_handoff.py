#!/usr/bin/env python3
"""Create a reviewer-facing handoff for production external evidence gaps."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


REPORT_COLUMNS = ["severity", "item", "message"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize external-evidence readiness into a Markdown handoff that "
            "distinguishes current bridge evidence from production-grade evidence."
        )
    )
    parser.add_argument("--external-evidence-plan", required=True, help="results/qc/external_evidence_plan.tsv")
    parser.add_argument("--unlock-plan", required=True, help="results/qc/external_evidence_unlock_plan.tsv")
    parser.add_argument("--output", required=True, help="Markdown handoff output.")
    parser.add_argument("--report-output", required=True, help="TSV report output.")
    return parser.parse_args()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return reader.fieldnames or [], [{key: (value or "").strip() for key, value in row.items()} for row in reader]


def write_tsv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def production_expectation(evidence_id: str) -> str:
    expectations = {
        "pairwise_similarity": "VIRIDIC or documented all-vs-all Mash/ANI-style similarity across sequence-backed phage/prophage genomes.",
        "phage_annotation": "Standardized Pharokka/PHROGs annotation generated from reviewed FASTA files for all phage/prophage records.",
        "rbp_domain_evidence": "Domain/profile evidence for RBP/depolymerase candidates, linked by annotation_gene_id.",
        "rbp_structural_evidence": "Structure-informed or remote-homology evidence such as Phold/Foldseek-style hits, linked by annotation_gene_id.",
        "kleborate_host_features": "Kleborate-style host species/ST/AMR/virulence output for reviewed Klebsiella host assemblies.",
        "kaptive_ko_typing": "Kaptive-style K/O locus typing for reviewed Klebsiella host assemblies.",
        "host_defense_systems": "DefenseFinder/PADLOC host antiviral-defense calls for reviewed host assemblies.",
        "phage_antidefense_candidates": "Curated phage anti-defense calls from standardized annotation/domain/structural evidence, not keyword inference alone.",
    }
    return expectations.get(evidence_id, "Reviewed production evidence TSV matching the configured schema.")


def current_role(row: dict[str, str]) -> str:
    evidence_id = row.get("evidence_id", "")
    status = row.get("evidence_status", "")
    origin = row.get("evidence_origin", "")
    if evidence_id == "phage_annotation" and status == "provided_input_ready":
        return "Bridge evidence: GenBank CDS product annotations, not standardized de novo annotation."
    if evidence_id == "pairwise_similarity" and status == "provided_input_ready":
        return "Bridge evidence: local BLASTN baseline, not production all-vs-all phage similarity."
    if evidence_id in {"kleborate_host_features", "kaptive_ko_typing"} and status == "provided_input_ready":
        configured_path = row.get("configured_input_path", "")
        if "host_feature_bridge" in configured_path or "kleborate_host_features.tsv" in configured_path or "kaptive_ko_typing.tsv" in configured_path:
            return "Bridge evidence: reviewed host manifest metadata normalized from prior Kleborate/Kaptive notes; rerun production tools for expanded host sets."
    if status == "provided_input_ready":
        return f"Configured reviewed TSV ({origin}); review provenance before manuscript use."
    if status in {"missing_tool_or_input", "not_configured", "manual_evidence_required"}:
        return "Missing production evidence."
    return status or "NA"


def handoff_text(plan_rows: list[dict[str, str]], unlock_rows: list[dict[str, str]]) -> str:
    blocking = [
        row
        for row in plan_rows
        if row.get("blocking_for_manuscript", "").lower() == "true"
        and row.get("real_claim_use_status") != "usable_after_source_and_claim_audits"
    ]
    lines = [
        "# Production Evidence Handoff",
        "",
        "This file is generated from `results/qc/external_evidence_plan.tsv` and `results/qc/external_evidence_unlock_plan.tsv`.",
        "",
        "It separates current bridge evidence from production-grade evidence expected before strong biological claims.",
        "",
        "## Evidence Layers",
        "",
        "| evidence_id | current role | production expectation | configured rows | status | next action |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for row in plan_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{escape_md(row.get('evidence_id', ''))}`",
                    escape_md(current_role(row)),
                    escape_md(production_expectation(row.get("evidence_id", ""))),
                    escape_md(row.get("configured_input_rows", "0")),
                    escape_md(row.get("evidence_status", "")),
                    escape_md(row.get("next_action", "")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Hypothesis Blocks",
            "",
            "| hypothesis | ready evidence | blocking evidence | next action |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in unlock_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{escape_md(row.get('hypothesis', ''))}`",
                    escape_md(row.get("ready_required_evidence", "")),
                    escape_md(row.get("blocking_required_evidence", "")),
                    escape_md(row.get("next_action", "")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Current Manuscript Guardrail",
            "",
            "Bridge evidence may support workflow/resource claims and prioritization scaffolds. It should not be used to claim receptor specificity, structural novelty, host-range prediction, or defense/counter-defense compatibility until production evidence is configured and the claim-support audit allows stronger wording.",
            "",
            f"Blocking manuscript evidence layers: {len(blocking)}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    report: list[dict[str, str]] = []
    plan_fields, plan_rows = read_tsv(Path(args.external_evidence_plan))
    unlock_fields, unlock_rows = read_tsv(Path(args.unlock_plan))
    required_plan = {"evidence_id", "evidence_status", "configured_input_rows", "next_action", "blocking_for_manuscript"}
    required_unlock = {"hypothesis", "ready_required_evidence", "blocking_required_evidence", "next_action"}
    missing_plan = sorted(required_plan - set(plan_fields))
    missing_unlock = sorted(required_unlock - set(unlock_fields))
    if missing_plan:
        report.append({"severity": "error", "item": "external_evidence_plan", "message": "Missing columns: " + ";".join(missing_plan)})
    if missing_unlock:
        report.append({"severity": "error", "item": "external_evidence_unlock_plan", "message": "Missing columns: " + ";".join(missing_unlock)})
    if not missing_plan and not missing_unlock:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(handoff_text(plan_rows, unlock_rows), encoding="utf-8")
        blocking = sum(
            1
            for row in plan_rows
            if row.get("blocking_for_manuscript", "").lower() == "true"
            and row.get("real_claim_use_status") != "usable_after_source_and_claim_audits"
        )
        report.append({"severity": "info", "item": "production_evidence_handoff", "message": f"evidence_layers={len(plan_rows)}; hypotheses={len(unlock_rows)}; blocking_layers={blocking}"})
    else:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text("# Production Evidence Handoff\n\nGeneration failed; see report TSV.\n", encoding="utf-8")
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    errors = sum(1 for row in report if row["severity"] == "error")
    print(f"Production evidence handoff complete: {len(plan_rows)} evidence rows, {errors} errors.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
