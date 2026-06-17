#!/usr/bin/env python3
"""Map configured source curation state to H1-H6 hypothesis unlock requirements."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable


PLAN_COLUMNS = [
    "hypothesis",
    "hypothesis_question",
    "required_source_ids",
    "optional_source_ids",
    "ready_required_sources",
    "blocking_required_sources",
    "ready_optional_sources",
    "blocking_optional_sources",
    "minimum_unlock_status",
    "next_action",
    "analysis_outputs_unlocked",
]
MATRIX_COLUMNS = [
    "hypothesis",
    "source_id",
    "source_role",
    "record_layer",
    "priority",
    "curation_status",
    "blocking_for_real_study",
    "expected_export_path",
    "template_path",
    "next_action",
]
REPORT_COLUMNS = ["severity", "item", "message"]

HYPOTHESIS_REQUIREMENTS = [
    {
        "hypothesis": "H1",
        "question": "Do RBP/depolymerase modules predict K/O association better than phage taxonomy?",
        "required": ["inphared_klebsiella_phages", "ncbi_virus_klebsiella_phages", "literature_klebsiella_phages", "klebsiella_host_genomes"],
        "optional": ["klebsiella_prophages", "metagenomic_discovery_contigs"],
        "outputs": "results/models/model_comparison.tsv; results/figures/figure_4_k_o_association_source.tsv",
    },
    {
        "hypothesis": "H2",
        "question": "Are prophages an under-sampled reservoir of capsule-recognition proteins?",
        "required": ["klebsiella_prophages", "klebsiella_host_genomes"],
        "optional": ["inphared_klebsiella_phages", "ncbi_virus_klebsiella_phages", "literature_klebsiella_phages"],
        "outputs": "results/rbp_depolymerase/novel_candidates.tsv; results/models/model_comparison.tsv",
    },
    {
        "hypothesis": "H3",
        "question": "Are broad-host-range phages enriched for modular RBPs and counter-defense genes?",
        "required": ["literature_klebsiella_phages", "inphared_klebsiella_phages", "ncbi_virus_klebsiella_phages"],
        "optional": ["klebsiella_host_genomes", "klebsiella_prophages"],
        "outputs": "results/models/feature_importance.tsv; results/models/model_comparison.tsv",
    },
    {
        "hypothesis": "H4",
        "question": "Do receptor plus defense/counter-defense features improve compatibility prediction?",
        "required": ["klebsiella_host_genomes", "inphared_klebsiella_phages", "ncbi_virus_klebsiella_phages"],
        "optional": ["literature_klebsiella_phages", "klebsiella_prophages"],
        "outputs": "results/defense_systems/compatibility_features.tsv; results/models/model_comparison.tsv",
    },
    {
        "hypothesis": "H5",
        "question": "Do clinically important Klebsiella lineages have distinct prophage and defense repertoires?",
        "required": ["klebsiella_host_genomes", "klebsiella_prophages"],
        "optional": ["literature_klebsiella_phages"],
        "outputs": "results/host_features/host_metadata.tsv; results/defense_systems/host_defense_systems.tsv; results/models/model_comparison.tsv",
    },
    {
        "hypothesis": "H6",
        "question": "Are novel RBP candidates enriched in under-sampled sources or singleton clusters?",
        "required": ["inphared_klebsiella_phages", "ncbi_virus_klebsiella_phages", "literature_klebsiella_phages"],
        "optional": ["metagenomic_discovery_contigs", "klebsiella_prophages"],
        "outputs": "results/rbp_depolymerase/novel_candidates.tsv; results/models/model_comparison.tsv; results/figures/figure_6_novelty_prioritization_source.tsv",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan which source exports unlock each study hypothesis.")
    parser.add_argument("--source-curation-tasks", required=True, help="Source curation tasks TSV.")
    parser.add_argument("--plan-output", required=True, help="Output hypothesis source unlock plan TSV.")
    parser.add_argument("--matrix-output", required=True, help="Output source-by-hypothesis matrix TSV.")
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


def source_is_ready(row: dict[str, str]) -> bool:
    return row.get("curation_status") == "ready_for_sample_build" and row.get("blocking_for_real_study") != "true"


def source_index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("source_id", ""): row for row in rows if row.get("source_id")}


def join(values: list[str]) -> str:
    return ";".join(values)


def build_plan(tasks: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    sources = source_index(tasks)
    plan_rows = []
    matrix_rows = []
    for spec in HYPOTHESIS_REQUIREMENTS:
        required = spec["required"]
        optional = spec["optional"]
        ready_required = [source for source in required if source_is_ready(sources.get(source, {}))]
        blocking_required = [source for source in required if source not in ready_required]
        ready_optional = [source for source in optional if source_is_ready(sources.get(source, {}))]
        blocking_optional = [source for source in optional if source not in ready_optional]
        if not blocking_required:
            status = "minimum_sources_ready"
            next_action = "Run the full workflow with populated source manifests and inspect downstream hypothesis outputs."
        else:
            status = "blocked_missing_required_sources"
            next_action = "Populate reviewed exports and enable required sources: " + join(blocking_required)
        plan_rows.append(
            {
                "hypothesis": spec["hypothesis"],
                "hypothesis_question": spec["question"],
                "required_source_ids": join(required),
                "optional_source_ids": join(optional),
                "ready_required_sources": join(ready_required),
                "blocking_required_sources": join(blocking_required),
                "ready_optional_sources": join(ready_optional),
                "blocking_optional_sources": join(blocking_optional),
                "minimum_unlock_status": status,
                "next_action": next_action,
                "analysis_outputs_unlocked": spec["outputs"],
            }
        )
        for role, source_ids in [("required", required), ("optional", optional)]:
            for source_id in source_ids:
                task = sources.get(source_id, {})
                matrix_rows.append(
                    {
                        "hypothesis": spec["hypothesis"],
                        "source_id": source_id,
                        "source_role": role,
                        "record_layer": task.get("record_layer", ""),
                        "priority": task.get("priority", ""),
                        "curation_status": task.get("curation_status", "source_not_configured"),
                        "blocking_for_real_study": task.get("blocking_for_real_study", "true"),
                        "expected_export_path": task.get("expected_export_path", ""),
                        "template_path": task.get("template_path", ""),
                        "next_action": task.get("next_action", "Configure or populate this source."),
                    }
                )
    return plan_rows, matrix_rows


def main() -> int:
    args = parse_args()
    _, task_rows = read_tsv(Path(args.source_curation_tasks))
    plan_rows, matrix_rows = build_plan(task_rows)
    blocked = [row for row in plan_rows if row.get("minimum_unlock_status") != "minimum_sources_ready"]
    report = [
        {
            "severity": "info",
            "item": "hypothesis_source_unlocks",
            "message": f"hypotheses={len(plan_rows)}; minimum_ready={len(plan_rows) - len(blocked)}; blocked={len(blocked)}; matrix_rows={len(matrix_rows)}",
        }
    ]
    if blocked:
        report.append(
            {
                "severity": "warning",
                "item": "hypothesis_source_unlocks",
                "message": "One or more hypotheses are blocked by missing required reviewed source exports.",
            }
        )
    write_tsv(Path(args.plan_output), PLAN_COLUMNS, plan_rows)
    write_tsv(Path(args.matrix_output), MATRIX_COLUMNS, matrix_rows)
    write_tsv(Path(args.report_output), REPORT_COLUMNS, report)
    print(f"Wrote hypothesis source unlock plan for {len(plan_rows)} hypotheses.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
